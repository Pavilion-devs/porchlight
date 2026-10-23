"""The brain: turns observations into state, spots situations, and escalates them.

Detection is deterministic (fast, testable). Deciding *whether and how* to tell the family is done by
the CareAgent (Strands on Bedrock) when it's enabled, with a template fallback so alerts never get lost.
Everything is driven by the observation's own timestamp, so replayed days on a compressed clock behave
exactly like live ones.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import routine
from .alerts import Notifier
from .config import ROOT, Settings
from .hub import Hub
from .store import Store
from .vision import Observation

log = logging.getLogger("porchlight.brain")
MOCK_FRAMES = ROOT / "shared" / "mock" / "frames"


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmm(t: datetime | time | None) -> str:
    """7:05am. Built by hand because strftime's "%-I" doesn't exist on Windows."""
    return f"{t.hour % 12 or 12}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}" if t else "never"


def day_hhmm(t: datetime) -> str:
    """Tue 3:40pm"""
    return f"{t:%a} {hhmm(t)}"


def long_date(t: datetime) -> str:
    """Friday Oct 23"""
    return f"{t:%A %b} {t.day}"


@dataclass
class Situation:
    """Something the agent should decide about."""
    kind: str  # event type, e.g. "package_unattended"
    severity: str
    title: str
    facts: str  # plain-language facts for the agent / template
    time: datetime
    source: str
    frame_name: str | None = None
    key: str = ""  # de-duplication key


@dataclass
class Decision:
    send_alert: bool
    severity: str
    title: str
    summary: str
    family_message: str
    reasoning: str


@dataclass
class State:
    package_since: datetime | None = None
    package_frame: str | None = None
    package_alert_id: str | None = None
    package_misses: int = 0
    resident_last_seen: datetime | None = None
    last_scene: tuple | None = None
    handled: set[str] = field(default_factory=set)  # de-dup keys already escalated
    open: dict[str, str] = field(default_factory=dict)  # situation key -> event id (for "resolved")


class Brain:
    def __init__(self, store: Store, hub: Hub, notifier: Notifier, settings: Settings, agent=None):
        self.store = store
        self.hub = hub
        self.notifier = notifier
        self.settings = settings
        self.agent = agent
        self.tz = ZoneInfo(settings.timezone)
        self.state = State()

    def reset(self) -> None:
        self.state = State()

    # --- output -----------------------------------------------------------------------------------
    def emit(self, type: str, severity: str, title: str, summary: str, when: datetime, source: str,
             reasoning: str | None = None, frame_name: str | None = None, related_id: str | None = None) -> dict:
        event = {"id": f"evt_{uuid.uuid4().hex[:12]}", "time": iso(when), "type": type, "severity": severity,
                 "title": title, "summary": summary, "source": source}
        if reasoning:
            event["reasoning"] = reasoning
        if frame_name:
            event["frame_url"] = f"/api/frames/{frame_name}"
        if related_id:
            event["related_id"] = related_id
        self.store.add_event(event)
        self.hub.publish("event", event)
        return event

    def thought(self, title: str, summary: str, when: datetime, source: str, reasoning: str | None = None):
        return self.emit("agent_thought", "info", title, summary, when, source, reasoning)

    # --- input: what the camera saw ---------------------------------------------------------------
    async def on_observation(self, obs: Observation) -> None:
        self.store.add_observation(obs)
        s, local, name = self.state, obs.time.astimezone(self.tz), self.settings.parent_name
        resident = obs.is_resident_likely or obs.activity.startswith("resident_")

        scene = (obs.person, obs.package, obs.vehicle, obs.activity)
        if scene != s.last_scene and (obs.person or obs.package or obs.vehicle or s.last_scene):
            self.emit("observation", "info", self._obs_title(obs, resident), obs.description,
                      obs.time, obs.source, frame_name=obs.frame_name)
        s.last_scene = scene

        if resident:
            s.resident_last_seen = obs.time
            self._resolve("routine", f"{name} came to the door at {hhmm(local)}.", obs)

        await self._check_package(obs, resident)

        if obs.person and self._is_night(local):
            await self._escalate(Situation(
                "night_activity", "urgent", f"{name} was at the door at {hhmm(local)}" if resident
                else f"Someone was at the door at {hhmm(local)}",
                f"At {hhmm(local)} the doorbell saw: {obs.description} "
                f"{'This looks like ' + name + '.' if resident else 'This does not look like ' + name + '.'} "
                f"In the learned routine there is normally no door activity between "
                f"{self.settings.night_start_hour}am and {self.settings.night_end_hour}am.",
                obs.time, obs.source, obs.frame_name, key=f"night:{local.date()}"))

        if obs.person and not resident and obs.activity == "visitor_at_door" and obs.visitor_signature:
            earlier = routine.visitor_history(self.store, obs.visitor_signature, obs.time, self.tz,
                                              source=obs.source)
            if len(earlier) >= 2:
                days = ", ".join(day_hhmm(e.astimezone(self.tz)) for e in earlier)
                await self._escalate(Situation(
                    "repeat_visitor", "notice", f"Same visitor, {self._ordinal(len(earlier) + 1)} time this week",
                    f"A visitor ({obs.person_desc or obs.visitor_signature}) came to the door at {hhmm(local)}. "
                    f"Someone matching '{obs.visitor_signature}' also came on: {days}. "
                    f"No delivery was made. {name} is an older adult who lives alone.",
                    obs.time, obs.source, obs.frame_name, key=f"visitor:{obs.visitor_signature}:{local.date()}"))

    async def _check_package(self, obs: Observation, resident: bool) -> None:
        s, name = self.state, self.settings.parent_name
        local = obs.time.astimezone(self.tz)
        if obs.package:
            s.package_misses = 0
            if s.package_since is None:
                s.package_since, s.package_frame = obs.time, obs.frame_name
                self.thought("Tracking a package", f"A package arrived at {hhmm(local)}. I'll check that "
                             f"{name} brings it in.", obs.time, obs.source)
            return
        if s.package_since is None:
            return
        s.package_misses += 1
        taken = obs.activity == "package_pickup" and not resident
        if not (taken or resident or s.package_misses >= 3):
            return  # one frame without the box isn't enough to say it's gone
        since = s.package_since.astimezone(self.tz)
        if taken:
            await self._escalate(Situation(
                "package_taken", "urgent", "Package taken by someone else",
                f"A package delivered at {hhmm(since)} was picked up at {hhmm(local)} by someone who does not "
                f"look like {name}: {obs.person_desc or obs.description}", obs.time, obs.source, obs.frame_name,
                key=f"taken:{iso(s.package_since)}"))
        else:
            msg = f"The package was brought in at {hhmm(local)}" + (f" by {name}." if resident else ".")
            if not self._resolve("package", msg, obs):
                self.thought("Package brought in", msg, obs.time, obs.source)
        s.package_since = s.package_frame = s.package_alert_id = None

    # --- input: time passing ----------------------------------------------------------------------
    async def tick(self, now: datetime, source: str = "ring_live") -> None:
        s, name, local = self.state, self.settings.parent_name, now.astimezone(self.tz)

        if s.package_since and now - s.package_since >= timedelta(minutes=self.settings.package_alert_minutes):
            since = s.package_since.astimezone(self.tz)
            seen = s.resident_last_seen.astimezone(self.tz) if s.resident_last_seen else None
            await self._escalate(Situation(
                "package_unattended", "notice", "Package still outside",
                f"A package has been outside {name}'s door since {hhmm(since)} "
                f"({self._duration(now - s.package_since)}). "
                + (f"{name} was last seen at the door at {hhmm(seen)}." if seen
                   else f"{name} hasn't been seen at the door today."),
                now, source, s.package_frame, key=f"package:{iso(s.package_since)}"))

        today = local.date()
        stats = {r.key: r for r in routine.learn(self.store, today, self.tz, source=source)}
        first = stats["first_out"]
        if first.latest and first.days >= 3 and not routine.first_out_today(self.store, today, self.tz, source):
            deadline = datetime.combine(today, first.latest, self.tz) + timedelta(
                minutes=self.settings.routine_grace_minutes)
            if local >= deadline:
                night = f"night:{today}" in s.handled
                await self._escalate(Situation(
                    "routine_missed", "urgent" if night else "notice", f"{name} hasn't been out this morning",
                    f"It is {hhmm(local)} and {name} has not come to the door today. Over the last {first.days} "
                    f"days she was usually out around {hhmm(first.usual)} and never later than "
                    f"{hhmm(first.latest)}." + (" She was also at the door during the night." if night else ""),
                    now, source, key=f"routine:{today}"))

        if local.hour >= self.settings.summary_hour and f"summary:{today}" not in s.handled:
            s.handled.add(f"summary:{today}")
            await self.daily_summary(now, source)

    # --- decisions --------------------------------------------------------------------------------
    async def _escalate(self, sit: Situation) -> None:
        s = self.state
        if sit.key in s.handled:
            return
        s.handled.add(sit.key)
        decision = None
        if self.agent:
            try:
                decision = await self.agent.decide(sit)
            except Exception:
                log.exception("agent failed; using template")
        decision = decision or self._template(sit)
        event = self.emit(sit.kind, decision.severity, decision.title, decision.summary, sit.time, sit.source,
                          reasoning=decision.reasoning, frame_name=sit.frame_name)
        s.open[sit.kind.split("_")[0]] = event["id"]  # "package", "routine", "night", "repeat"
        if sit.kind == "package_unattended":
            s.package_alert_id = event["id"]
        if decision.send_alert:
            photo = self.frame_path(sit.frame_name)
            delivered = await self.notifier.send(decision.family_message, photo)
            channel = self.notifier.channel if delivered else f"{self.notifier.channel}, not delivered"
            self.emit("alert_sent", decision.severity, "Sent to family",
                      f"📱 {channel} → {self.settings.family_name}: \"{decision.family_message}\"",
                      sit.time, sit.source, related_id=event["id"])

    def _resolve(self, kind: str, summary: str, obs: Observation) -> bool:
        event_id = self.state.open.pop(kind, None)
        if event_id:
            self.emit("resolved", "info", "Resolved", summary, obs.time, obs.source,
                      frame_name=obs.frame_name, related_id=event_id)
        return bool(event_id)

    def _template(self, sit: Situation) -> Decision:
        return Decision(send_alert=sit.severity != "info", severity=sit.severity, title=sit.title,
                        summary=sit.facts, family_message=f"Porchlight: {sit.title}. {sit.facts}",
                        reasoning="Rule-based alert (agent unavailable).")

    async def daily_summary(self, now: datetime, source: str) -> dict:
        local = now.astimezone(self.tz)
        start = datetime.combine(local.date(), time(0, 0), self.tz)
        events = [e for e in self.store.events(since=iso(start), until=iso(now + timedelta(seconds=1)),
                                               source=source)
                  if e["type"] not in ("agent_thought", "daily_summary")]
        summary = None
        if self.agent:
            try:
                summary = await self.agent.summarize(events, local)
            except Exception:
                log.exception("agent summary failed; using template")
        if summary is None:
            summary = self.summary_counts(events)
        summary["date"] = str(local.date())
        self.store.put(f"summary:{source}:{local.date()}", summary)
        self.emit("daily_summary", "urgent" if summary["mood"] == "concern" else "info",
                  f"Today at {self.settings.parent_name}'s", summary["headline"], now, source,
                  reasoning=summary.get("body"))
        return summary

    def summary_counts(self, events: list[dict]) -> dict:
        obs = [e for e in events if e["type"] == "observation"]
        alerts = sum(e["type"] == "alert_sent" for e in events)
        urgent = any(e["severity"] == "urgent" for e in events if e["type"] != "alert_sent")
        deliveries = sum(e["title"] == "Package delivered" for e in obs)
        visitors = sum(e["title"].startswith("Visitor") for e in obs)
        mood = "concern" if urgent else "watch" if alerts else "calm"
        headline = {"calm": "Normal day, all fine.", "watch": "Mostly normal, a couple of things worth knowing.",
                    "concern": "Worth a phone call today."}[mood]
        return {"date": None, "headline": headline, "body": f"{self._n(visitors, 'visitor')}, {self._n(deliveries, 'delivery', 'deliveries')}, "
                f"{self._n(alerts, 'alert')}.", "visitors": visitors, "deliveries": deliveries, "alerts": alerts, "mood": mood}

    # --- helpers ----------------------------------------------------------------------------------
    def frame_path(self, name: str | None) -> Path | None:
        """Captured frames live in data/frames; replay scenarios reuse the real Ring frames in shared/mock."""
        if not name:
            return None
        for folder in (self.settings.frames_dir, MOCK_FRAMES):
            if (folder / name).is_file():
                return folder / name
        return None

    def _is_night(self, local: datetime) -> bool:
        return self.settings.night_start_hour <= local.hour < self.settings.night_end_hour

    def _obs_title(self, obs: Observation, resident: bool) -> str:
        name = self.settings.parent_name
        return {
            "delivery": "Package delivered", "package_pickup": "Package picked up",
            "resident_leaving": f"{name} went out", "resident_returning": f"{name} came home",
            "resident_at_door": f"{name} at the door", "visitor_at_door": "Visitor at the door",
            "vehicle": "Vehicle outside", "passerby": "Someone passing by", "animal": "Animal at the door",
        }.get(obs.activity, f"{name} at the door" if resident else
              "Package at the door" if obs.package else
              "Activity at the door" if obs.person or obs.vehicle else "Porch is clear")

    @staticmethod
    def _n(n: int, one: str, many: str | None = None) -> str:
        return f"{n} {one if n == 1 else many or one + 's'}"

    @staticmethod
    def _duration(d: timedelta) -> str:
        m = int(d.total_seconds() // 60)
        return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m} min"

    @staticmethod
    def _ordinal(n: int) -> str:
        return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")
