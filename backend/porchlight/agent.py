"""CareAgent: a Strands agent on Amazon Bedrock that decides whether and how to tell the family.

The brain detects a situation; the agent investigates it with tools (recent activity, learned routine,
visitor history, alerts already sent today), then returns a structured decision. Each tool call is
published as an "agent_thought" so the dashboard can show the agent thinking.
"""
import asyncio
import json
from datetime import datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

from . import routine
from .brain import Decision, Situation, hhmm, iso
from .config import Settings

SYSTEM = """You are Porchlight's care agent. You help a family look after {parent}, an older adult who lives
alone. Your only sensor is the Ring video doorbell at {parent}'s front door: there are no cameras inside.

When a situation is detected, investigate it with your tools before deciding. Then decide:
- whether the family should be messaged now (send_alert). Don't cry wolf: one clear message beats many.
- severity: info (no message), notice (worth knowing today), urgent (act now, e.g. call {parent}).
- a short message to {family}, written like a calm, caring sibling would text: specific times, no jargon,
  one suggested next step. Never claim certainty you don't have: you only see the front door.
- reasoning: 1-3 sentences on why, citing what your tools showed.
Timezone for all times: {tz}."""


class AlertDecision(BaseModel):
    send_alert: bool
    severity: Literal["info", "notice", "urgent"]
    title: str = Field(description="Short card title, under 8 words")
    summary: str = Field(description="One or two sentences for the family dashboard")
    family_message: str = Field(description="The text message to the family, under 300 characters")
    reasoning: str = Field(description="Why, citing the evidence you checked")


class DaySummary(BaseModel):
    headline: str = Field(description="Under 10 words, e.g. 'Normal day, all fine.'")
    body: str = Field(description="2-3 warm, specific sentences for the family")
    visitors: int
    deliveries: int
    alerts: int
    mood: Literal["calm", "watch", "concern"]


class CareAgent:
    def __init__(self, brain, settings: Settings, timeout_s: float = 60):
        self.brain = brain
        self.settings = settings
        self.timeout_s = timeout_s
        self.model = BedrockModel(model_id=settings.agent_model, region_name=settings.aws_region,
                                  temperature=0.2, max_tokens=1200)
        self._ctx: Situation | None = None

    def _system(self) -> str:
        s = self.settings
        return SYSTEM.format(parent=s.parent_name, family=s.family_name, tz=s.timezone)

    def _think(self, title: str, summary: str) -> None:
        if self._ctx:
            self.brain.thought(title, summary, self._ctx.time, self._ctx.source)

    def _tools(self):
        brain, tz, name = self.brain, self.brain.tz, self.settings.parent_name

        @tool
        def get_recent_activity(hours: int = 12) -> str:
            """List what the doorbell saw in the last N hours (times are local)."""
            now = self._ctx.time
            self._think("Looking back", f"Checking the last {hours}h of door activity.")
            obs = brain.store.observations(now - timedelta(hours=hours), now + timedelta(seconds=1),
                                           source=self._ctx.source)
            rows = [f"{hhmm(o.time.astimezone(tz))}: {o.activity} - {o.description}" for o in obs
                    if o.activity != "none"]
            return "\n".join(rows[-40:]) or "No activity at the door in that window."

        @tool
        def get_routine_baseline() -> str:
            """The routine learned from the last 14 days, and what has happened so far today."""
            now = self._ctx.time
            today = now.astimezone(tz).date()
            self._think("Checking the routine", f"Comparing today with {name}'s usual days.")
            src = self._ctx.source
            stats = routine.learn(brain.store, today, tz, source=src)
            first = routine.first_out_today(brain.store, today, tz, src)
            if not any(r.days for r in stats):
                return (f"No routine learned yet: there is no history of {name}'s door activity. "
                        "Don't assume anything about her usual times.")
            lines = [f"{r.label}: usually ~{hhmm(r.usual)}, latest {hhmm(r.latest)}, seen on {r.days} of the "
                     f"learned days" for r in stats]
            lines.append(f"Today's first time outside: {hhmm(first) if first else 'not yet'}")
            last = brain.state.resident_last_seen
            lines.append(f"Last seen at the door: {hhmm(last.astimezone(tz)) if last else 'not today'}")
            return "\n".join(lines)

        @tool
        def get_visitor_history(signature: str) -> str:
            """Earlier visits this week by someone matching a comma-separated trait signature."""
            self._think("Checking visitor history", f"Has someone like \"{signature}\" been here before?")
            visits = routine.visitor_history(brain.store, signature, self._ctx.time, tz, source=self._ctx.source)
            return ("Earlier visits: " + ", ".join(v.astimezone(tz).strftime("%a %-I:%M%p") for v in visits)
                    if visits else "No earlier visits by anyone matching that description this week.")

        @tool
        def get_alerts_sent_today() -> str:
            """Messages already sent to the family today, to avoid repeating ourselves."""
            now = self._ctx.time
            start = datetime.combine(now.astimezone(tz).date(), time(0, 0), tz)
            sent = [e for e in brain.store.events(since=iso(start), until=iso(now + timedelta(seconds=1)),
                                                  source=self._ctx.source) if e["type"] == "alert_sent"]
            return "\n".join(e["summary"] for e in sent) or "No alerts sent today."

        return [get_recent_activity, get_routine_baseline, get_visitor_history, get_alerts_sent_today]

    async def decide(self, sit: Situation) -> Decision:
        self._ctx = sit
        agent = Agent(model=self.model, system_prompt=self._system(), tools=self._tools(), callback_handler=None)
        prompt = (f"Situation detected: {sit.kind} (default severity {sit.severity}).\n"
                  f"Time: {hhmm(sit.time.astimezone(self.brain.tz))} on "
                  f"{sit.time.astimezone(self.brain.tz):%A %b %-d}.\nFacts: {sit.facts}\n"
                  "Investigate with your tools, then decide.")
        try:
            result = await asyncio.wait_for(agent.invoke_async(prompt, structured_output_model=AlertDecision),
                                            self.timeout_s)
        finally:
            self._ctx = None
        d: AlertDecision = result.structured_output
        return Decision(d.send_alert, d.severity, d.title, d.summary, d.family_message, d.reasoning)

    async def summarize(self, events: list[dict], local_now: datetime) -> dict:
        agent = Agent(model=self.model, system_prompt=self._system(), callback_handler=None)
        lines = [f"{hhmm(datetime.fromisoformat(e['time'].replace('Z', '+00:00')).astimezone(self.brain.tz))} "
                 f"[{e['type']}/{e['severity']}] {e['title']}: {e['summary']}" for e in events]
        prompt = (f"Write the evening summary for {local_now:%A %b %-d} from today's events. Count visitors "
                  f"(non-residents who came to the door), deliveries and alerts sent.\n\n"
                  + ("\n".join(lines) or "No events today."))
        result = await asyncio.wait_for(agent.invoke_async(prompt, structured_output_model=DaySummary),
                                        self.timeout_s)
        return json.loads(result.structured_output.model_dump_json())
