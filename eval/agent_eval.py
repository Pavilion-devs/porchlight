"""Does the care agent message the family when it should, and stay quiet when it shouldn't?

Runs every demo scenario plus five "normal day" variations through the real pipeline (brain + Strands
CareAgent on Amazon Bedrock), several times each, and scores the messages the family would receive.

Run from backend/ with Bedrock access (AWS credentials or an instance role):
    ../.venv/bin/python ../eval/agent_eval.py --runs 3
Writes eval/agent_eval.json, then summarise it with --report.
"""
import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from porchlight.agent import CareAgent  # noqa: E402
from porchlight.brain import Brain  # noqa: E402
from porchlight.config import settings  # noqa: E402
from porchlight.hub import Hub  # noqa: E402
from porchlight.replayer import MORNING, PKG_FRAME, RESIDENT, SCENARIOS, Replayer, Step  # noqa: E402
from porchlight.store import Store  # noqa: E402

OUT = Path(__file__).with_name("agent_eval.json")
DAY = date(2026, 10, 20)
PKG = {"package": True, "frame_name": PKG_FRAME}

# Days where nothing needs a message. The routine Mom follows is seeded the same way as the demo.
NORMAL_DAYS: dict[str, list[Step]] = {
    "normal_quick_pickup": [
        MORNING,
        Step("10:06", "obs", "delivery", "A courier left a brown box on the top step.", extra=PKG),
        Step("10:07", "obs", "none", "A brown box is sitting on the top step.", extra=PKG),
        Step("10:40", "obs", "resident_at_door", f"An {RESIDENT} picked up the box and took it inside."),
        Step("12:00", "tick"), Step("14:00", "tick"),
    ],
    "normal_a_bit_late": [
        Step("08:20", "obs", "resident_at_door", f"An {RESIDENT} picked up the newspaper."),
        Step("09:00", "tick"), Step("10:00", "tick"), Step("11:00", "tick"),
    ],
    "normal_new_visitor_once": [
        MORNING,
        Step("14:00", "obs", "visitor_at_door", "A woman in a red coat holding flowers rang the doorbell.",
             extra={"person_desc": "Woman in a red coat holding flowers",
                    "visitor_signature": "woman, red coat, flowers"}),
        Step("14:05", "obs", "resident_at_door", f"An {RESIDENT} opened the door and took the flowers."),
        Step("15:00", "tick"),
    ],
    "normal_walk_day": [
        MORNING,
        Step("13:02", "obs", "resident_leaving", f"An {RESIDENT} left the house with a walking stick."),
        Step("13:48", "obs", "resident_returning", f"An {RESIDENT} came back and went inside."),
        Step("15:00", "tick"),
    ],
    "normal_busy_street": [
        MORNING,
        Step("11:00", "obs", "passerby", "A jogger ran past on the sidewalk."),
        Step("12:30", "obs", "animal", "A cat walked across the porch."),
        Step("16:00", "obs", "vehicle", "A car drove past on the street."),
        Step("17:00", "tick"),
    ],
}

# Situations that must reach the family for each demo scenario.
EXPECTED = {
    "package": {"package_unattended"},
    "repeat_visitor": {"repeat_visitor"},
    "routine_missed": {"routine_missed", "night_activity"},
    "night_activity": {"night_activity"},
    "full_day": {"package_unattended", "repeat_visitor"},
    **{name: set() for name in NORMAL_DAYS},
}


class Quiet:
    channel = "eval"

    async def send(self, text, photo=None):
        return True


async def run_case(name: str) -> dict:
    store = Store(":memory:")
    brain = Brain(store, Hub(), Quiet(), settings)
    brain.agent = CareAgent(brain, settings)

    async def sink(raw, sig):
        pass

    t0 = time.monotonic()
    await Replayer(brain, store, brain.tz, settings.hmac_key, sink, max_gap_s=0, min_gap_s=0).run(name, day=DAY)
    events = store.events(limit=1000)
    by_id = {e["id"]: e for e in events}
    sent = [by_id[e["related_id"]] for e in events if e["type"] == "alert_sent" and e.get("related_id") in by_id]
    flagged = [e for e in events if e["type"] in {"package_unattended", "package_taken", "repeat_visitor",
                                                  "routine_missed", "night_activity"}]
    return {
        "case": name,
        "seconds": round(time.monotonic() - t0, 1),
        "flagged": [e["type"] for e in flagged],
        "messaged": [e["type"] for e in sent],
        "severity": {e["type"]: e["severity"] for e in sent},
        "fallback": any("agent unavailable" in (e.get("reasoning") or "") for e in flagged),
        "messages": [e["summary"] for e in events if e["type"] == "alert_sent"],
    }


async def main(runs: int) -> None:
    SCENARIOS.update(NORMAL_DAYS)
    results = []
    for case in EXPECTED:
        for i in range(runs):
            r = await run_case(case)
            r["run"] = i + 1
            results.append(r)
            print(f"{case:26} run {i + 1}: messaged {r['messaged'] or '-'} ({r['seconds']}s)", flush=True)
            OUT.write_text(json.dumps(results, indent=2))


def report() -> None:
    results = json.loads(OUT.read_text())
    should, caught, normal_runs, false_alarm_runs, false_alarms = 0, 0, 0, 0, 0
    consistent = Counter()
    for case, expected in EXPECTED.items():
        rows = [r for r in results if r["case"] == case]
        if not rows:
            continue
        consistent[len({tuple(sorted(set(r["messaged"]))) for r in rows}) == 1] += 1
        for r in rows:
            got = set(r["messaged"])
            if expected:
                should += len(expected)
                caught += len(expected & got)
            else:
                normal_runs += 1
                false_alarm_runs += bool(got)
                false_alarms += len(got)
    fallbacks = sum(r["fallback"] for r in results)
    print(f"Runs: {len(results)}  (fallback to templates: {fallbacks})")
    print(f"Caught: {caught}/{should} situations that should reach the family")
    print(f"False alarms: {false_alarms} messages across {normal_runs} normal-day runs "
          f"({false_alarm_runs} runs with any message)")
    print(f"Same decision every run: {consistent[True]}/{consistent[True] + consistent[False]} cases")
    agent_runs = sorted(r["seconds"] for r in results if r["flagged"])
    print(f"Median time for a replayed day where the agent was consulted: {agent_runs[len(agent_runs) // 2]}s")
    print(f"Normal-day runs where the rules raised anything for the agent: "
          f"{sum(bool(r['flagged']) for r in results if not EXPECTED[r['case']])}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--report", action="store_true")
    a = p.parse_args()
    report() if a.report else asyncio.run(main(a.runs))
