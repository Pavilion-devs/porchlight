"""Ask Porchlight: an MCP server (Streamable HTTP) so the family can ask about their parent from any assistant.

"How's Mom doing today?", "Has that clipboard guy been back?", "What's at her door right now?"
Built for Alexa+-style integrations (MCP spec 2025-11-25+, Streamable HTTP) and works with any MCP client.
Mounted by app.py at /mcp. Answers are short, plain sentences so they read well and sound right when spoken.
"""
import hmac
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Callable

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .brain import Brain, hhmm, iso
from .config import Settings
from .vision import Observation

SITUATIONS = {"package_unattended", "package_taken", "repeat_visitor", "routine_missed", "night_activity"}
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _clock(hh_mm: str | None) -> str:
    """"07:52" -> "7:52am" (reads and sounds natural)."""
    try:
        return hhmm(datetime.strptime(hh_mm, "%H:%M"))
    except (TypeError, ValueError):
        return hh_mm or ""


def _t(iso_or_dt, tz) -> datetime:
    if isinstance(iso_or_dt, datetime):
        return iso_or_dt.astimezone(tz)
    return datetime.fromisoformat(iso_or_dt.replace("Z", "+00:00")).astimezone(tz)


def build(brain: Brain, settings: Settings, live: dict, stream_status: Callable[[], dict],
          active_source: Callable[[], str], source_now: Callable[[str], datetime],
          summary: Callable[[str], dict], baseline: Callable[[str], dict]) -> MCPServer:
    store, tz, name = brain.store, brain.tz, settings.parent_name

    server = MCPServer(
        name="porchlight",
        title="Porchlight",
        version="1.0.0",
        instructions=(
            f"Porchlight watches {name}'s front door through a Ring video doorbell and helps the family look "
            f"after {name}, an older adult who lives alone. It only sees the front door, never inside the home. "
            "Use these tools to answer questions like 'How is Mom doing today?' or 'Has anyone strange been "
            "around?'. Be warm and brief, give specific times, and don't claim more than the doorbell can see. "
            f"Times are local to {name} ({settings.timezone})."
        ),
    )

    def today_events(src: str) -> list[dict]:
        now = source_now(src)
        start = datetime.combine(now.date(), time(0, 0), tz)
        return store.events(since=iso(start), source=src, limit=1000)

    def open_and_closed(events: list[dict]) -> tuple[list[dict], list[dict], dict[str, dict]]:
        alerts = {e["related_id"]: e for e in events if e["type"] == "alert_sent" and e.get("related_id")}
        resolved = {e["related_id"]: e for e in events if e["type"] == "resolved" and e.get("related_id")}
        sits = [e for e in events if e["type"] in SITUATIONS]
        return [e for e in sits if e["id"] not in resolved], [e for e in sits if e["id"] in resolved], alerts

    def label(src: str) -> str:
        return "" if src == "ring_live" else " (from the replayed demo day, not the live doorbell)"

    @server.tool(title=f"How is {name} doing?", annotations=READ_ONLY)
    def how_is_parent_doing() -> str:
        """The overall picture for today: how the day is going, anything that still needs attention, when
        the parent was last seen at the door, and whether the day looks like their usual routine.
        Start here for questions like "How's Mom doing?" or "Is everything OK at Mom's?"."""
        src = active_source()
        events = today_events(src)
        s = summary(src)
        still_open, closed, _ = open_and_closed(events)
        lines = [f"Today at {name}'s{label(src)}: {s['headline']}"]
        if s.get("body") and s["body"] != s["headline"]:
            lines.append(s["body"])
        if still_open:
            lines.append("Still needs attention: " + "; ".join(
                f"{e['title']} ({hhmm(_t(e['time'], tz))})" for e in still_open) + ".")
        elif closed:
            lines.append("Everything flagged today has since been resolved.")
        seen = [o for o in store.observations(datetime.combine(source_now(src).date(), time(0, 0), tz),
                                               source=src) if o.is_resident_likely or o.activity.startswith("resident_")]
        lines.append(f"{name} was last seen at the door at {hhmm(seen[-1].time.astimezone(tz))}." if seen
                     else f"{name} hasn't been seen at the front door yet today.")
        off = [i for i in baseline(src)["items"] if i["status"] in ("late", "missed")]
        if off:
            lines.append("Different from her usual routine: " + ", ".join(i["label"].lower() for i in off) + ".")
        return "\n".join(lines)

    @server.tool(title="Recent activity at the door", annotations=READ_ONLY)
    def recent_activity(hours: int = 6) -> str:
        """What the doorbell saw in the last few hours (deliveries, visitors, the parent coming and going),
        oldest first. Use for "What's been happening at Mom's?" or "Did anyone come by this morning?"."""
        src = active_source()
        now = source_now(src)
        hours = max(1, min(hours, 48))
        events = [e for e in store.events(since=iso(now - timedelta(hours=hours)), source=src, limit=1000)
                  if e["type"] == "observation" or e["type"] in SITUATIONS]
        if not events:
            return f"Nothing happened at {name}'s door in the last {hours} hours{label(src)}."
        return f"Last {hours} hours at {name}'s door{label(src)}:\n" + "\n".join(
            f"- {hhmm(_t(e['time'], tz))}: {e['title']}. {e['summary']}" for e in events)

    @server.tool(title="Open concerns", annotations=READ_ONLY)
    def open_concerns() -> str:
        """Anything Porchlight flagged today, what the family was told, and whether it has been resolved.
        Use for "Is there anything I should worry about?" or "Did you send me anything today?"."""
        src = active_source()
        still_open, closed, alerts = open_and_closed(today_events(src))
        if not still_open and not closed:
            return f"Nothing has been flagged at {name}'s today{label(src)}. All quiet."
        out = [f"Flagged today at {name}'s{label(src)}:"]
        for e in still_open + closed:
            state = "STILL OPEN" if e in still_open else "resolved"
            told = alerts.get(e["id"])
            out.append(f"- {hhmm(_t(e['time'], tz))} [{e['severity']}, {state}] {e['title']}: {e['summary']}"
                       + (f" The family was messaged: {told['summary'].split(': ', 1)[-1]}" if told else ""))
        return "\n".join(out)

    @server.tool(title=f"{name}'s usual routine", annotations=READ_ONLY)
    def usual_routine() -> str:
        """The routine Porchlight has learned from the last two weeks (when the parent usually first goes
        out, their afternoon walk, quiet nights) and how today compares."""
        src = active_source()
        b = baseline(src)
        if not b["days_learned"]:
            return f"Porchlight is still learning {name}'s routine: there isn't enough door history yet."
        words = {"ok": "as usual", "late": "at an unusual time", "missed": "hasn't happened", "pending": "not due yet"}
        lines = [f"Learned from {b['days_learned']} days{label(src)}:"]
        for i in b["items"]:
            usual = i["usual"] if i["usual"] == "no activity" else f"around {_clock(i['usual'])}"
            today = f", today {_clock(i['today'])}" if i["today"] else ""
            lines.append(f"- {i['label']}: usually {usual}{today} ({words[i['status']]}).")
        return "\n".join(lines)

    @server.tool(title="Visitors this week", annotations=READ_ONLY)
    def visitors_this_week(days: int = 7) -> str:
        """People who came to the door who were not the parent, grouped by how they looked, with every visit.
        Use for "Has that man with the clipboard been back?" or "Who's been coming by?"."""
        src = active_source()
        now = source_now(src)
        obs: list[Observation] = store.observations(now - timedelta(days=max(1, min(days, 14))), now,
                                                    ["visitor_at_door"], src)
        if not obs:
            return f"No visitors at {name}'s door in the last {days} days{label(src)}."
        groups: dict[str, list[Observation]] = defaultdict(list)
        for o in obs:
            groups[o.visitor_signature or o.person_desc or "unknown visitor"].append(o)
        lines = [f"Visitors in the last {days} days{label(src)}:"]
        for who, visits in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            when = ", ".join(v.time.astimezone(tz).strftime("%a ") + hhmm(v.time.astimezone(tz)) for v in visits)
            lines.append(f"- {who}: {len(visits)} visit{'s' if len(visits) > 1 else ''} ({when})")
        return "\n".join(lines)

    @server.tool(title="Front door right now", annotations=READ_ONLY)
    def front_door_now() -> str:
        """What the Ring doorbell sees at this moment, from the live stream."""
        status = stream_status()
        if not live.get("frame_url"):
            return f"The live doorbell view isn't available right now (stream: {status['stream']})."
        age = (datetime.now(tz) - _t(live["time"], tz)).total_seconds()
        when = "just now" if age < 60 else f"{int(age // 60)} minutes ago"
        return f"Live from the Ring doorbell ({when}): {live['description']}"

    return server


class BearerGate:
    """Optional shared-secret check (MCP_TOKEN in .env) in front of the MCP endpoint."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.token:
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            if not hmac.compare_digest(auth, f"Bearer {self.token}"):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)
