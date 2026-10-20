"""Scenario replayer: 14 days of seeded history plus scripted demo days on a compressed clock.

Everything it produces is labelled source="replay". Doorbell presses and motion are sent as signed
Ring-format webhooks through the same handler real Ring webhooks use; what the camera "saw" is fed
in as observations, exactly as the vision step would produce them.
"""
import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .brain import Brain
from .store import Store
from .vision import Observation
from .webhooks import build_payload, sign

REPLAY_DEVICE = "ava1.ring.device.porchlight-replay"
VISITOR = dict(person_desc="Man in a grey hoodie holding a clipboard, no uniform or company logo",
               visitor_signature="man, grey hoodie, clipboard, no uniform")
RESIDENT = "older woman with short grey hair"

WebhookSink = Callable[[bytes, str], Awaitable[None]]


def _obs(when: datetime, activity: str, description: str, **kw) -> Observation:
    person = activity not in ("none", "delivery_left", "vehicle", "animal") or kw.pop("person", False)
    resident = activity.startswith("resident_")
    return Observation(time=when, description=description, activity=activity, person=person,
                       is_resident_likely=resident, source="replay", **kw)


def seed_history(store: Store, today: date, tz: ZoneInfo, days: int = 14, rng_seed: int = 7) -> int:
    """Two weeks of a believable routine, plus two earlier visits by the clipboard man."""
    rng = random.Random(rng_seed)
    n = 0
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        at = lambda hh, mm, jitter=0: datetime.combine(d, time(hh, mm), tz) + timedelta(  # noqa: E731
            minutes=rng.randint(-jitter, jitter))
        first = at(7, 52, 18)
        store.add_observation(_obs(first, "resident_at_door", f"The resident, an {RESIDENT}, picked up the newspaper."))
        if rng.random() < 0.85:
            walk = at(13, 5, 20)
            store.add_observation(_obs(walk, "resident_leaving", f"The resident, an {RESIDENT}, left for a walk."))
            store.add_observation(_obs(walk + timedelta(minutes=rng.randint(35, 55)), "resident_returning",
                                       f"The resident, an {RESIDENT}, came home."))
        if rng.random() < 0.4:
            store.add_observation(_obs(at(11, 0, 90), "delivery", "A courier in uniform left a parcel.",
                                       package=True))
        n += 1
    for i, hhmm in ((2, (15, 40)), (1, (11, 5))):  # Sunday + Monday visits for the repeat-visitor story
        d = today - timedelta(days=i)
        store.add_observation(_obs(datetime.combine(d, time(*hhmm), tz), "visitor_at_door",
                                   "A man with a clipboard rang the doorbell and left after a few minutes.", **VISITOR))
    return n


@dataclass
class Step:
    at: str  # local "HH:MM"
    action: str  # "obs" | "ring" | "tick" | "summary"
    activity: str = ""
    description: str = ""
    ring: tuple[str, str | None] | None = None  # (event_type, sub_type) sent before the observation
    extra: dict | None = None


PKG_FRAME = "porch_package.jpg"

SCENARIOS: dict[str, list[Step]] = {
    "night_activity": [
        Step("03:12", "obs", "resident_at_door", f"An {RESIDENT} in a robe stepped onto the porch and looked around.",
             ring=("motion_detected", "human")),
        Step("03:16", "obs", "none", "The porch is empty; the door is closed."),
    ],
    "routine_missed": [
        Step("03:12", "obs", "resident_at_door", f"An {RESIDENT} in a robe stepped onto the porch and looked around.",
             ring=("motion_detected", "human")),
        Step("03:16", "obs", "none", "The porch is empty; the door is closed."),
        Step("08:00", "tick"), Step("08:30", "tick"), Step("09:00", "tick"), Step("09:20", "tick"),
        Step("10:20", "obs", "resident_at_door", f"An {RESIDENT} picked up the newspaper and waved at a neighbour.",
             ring=("motion_detected", "human")),
    ],
    "repeat_visitor": [
        Step("14:12", "obs", "visitor_at_door", "A man in a grey hoodie with a clipboard rang the doorbell.",
             ring=("button_press", None), extra=VISITOR),
        Step("14:15", "obs", "none", "The porch is empty."),
    ],
    "package": [
        Step("10:06", "obs", "delivery", "A courier left a brown box on the top step.",
             ring=("motion_detected", "package_delivery"), extra={"package": True, "frame_name": PKG_FRAME}),
        Step("10:07", "obs", "none", "A brown box is sitting on the top step.",
             extra={"package": True, "frame_name": PKG_FRAME}),
        Step("12:00", "tick"), Step("13:10", "tick"),
        Step("15:05", "obs", "resident_at_door", f"An {RESIDENT} picked up the box and took it inside.",
             ring=("motion_detected", "human")),
    ],
}
SCENARIOS["full_day"] = (
    [Step("07:48", "obs", "resident_at_door", f"An {RESIDENT} picked up the newspaper.",
          ring=("motion_detected", "human"))]
    + SCENARIOS["package"][:4]          # delivery, 12:00 + 13:10 checks
    + SCENARIOS["repeat_visitor"]       # 14:12
    + SCENARIOS["package"][4:]          # 15:05 Mom brings the box in
    + [Step("20:00", "summary")]
)


class Replayer:
    def __init__(self, brain: Brain, store: Store, tz: ZoneInfo, hmac_key: str, webhook_sink: WebhookSink,
                 sim_minutes_per_s: float = 20, max_gap_s: float = 5, min_gap_s: float = 1.2):
        self.brain, self.store, self.tz = brain, store, tz
        self.hmac_key, self.webhook_sink = hmac_key, webhook_sink
        self.speed, self.max_gap_s, self.min_gap_s = sim_minutes_per_s, max_gap_s, min_gap_s
        self.running: str | None = None

    async def run(self, scenario: str, day: date | None = None) -> None:
        steps = SCENARIOS[scenario]
        day = day or datetime.now(self.tz).date()
        self.running = scenario
        try:
            self.store.clear_source("replay")
            self.brain.reset()
            seed_history(self.store, day, self.tz)
            prev = None
            for step in steps:
                when = datetime.combine(day, time.fromisoformat(step.at), self.tz)
                if prev is not None:
                    gap = (when - prev).total_seconds() / 60 / self.speed
                    await asyncio.sleep(min(self.max_gap_s, max(self.min_gap_s, gap)))
                prev = when
                await self._do(step, when)
        finally:
            self.running = None

    async def _do(self, step: Step, when: datetime) -> None:
        if step.ring:
            raw = json.dumps(build_payload(step.ring[0], REPLAY_DEVICE, when, step.ring[1])).encode()
            await self.webhook_sink(raw, sign(raw, self.hmac_key))
        if step.action == "obs":
            extra = dict(step.extra or {})
            await self.brain.on_observation(_obs(when, step.activity, step.description, **extra))
            await self.brain.tick(when, "replay")
        elif step.action == "tick":
            await self.brain.tick(when, "replay")
        elif step.action == "summary":
            await self.brain.daily_summary(when, "replay")
