# Does Porchlight message the family at the right times?

**30 runs with the real care agent (Strands + Claude Sonnet 4.6 on Amazon Bedrock), on our AWS server:**

| | Result |
|---|---|
| Situations that should reach the family | **21 / 21 messaged** |
| Normal days (5 kinds × 3 runs) | **0 messages** |
| Same decision on every run | 9 / 10 cases |
| Fell back to template messages (agent failed) | 0 |
| Median time for a day where the agent was consulted | 19.8 s (about 10 s per decision) |

Run it yourself: `cd backend && ../.venv/bin/python ../eval/agent_eval.py --runs 3`, then `--report`. Raw results are in [`agent_eval.json`](agent_eval.json), including every message the family would have received.

## What we tested

**Days that need a message** (the demo scenarios):

| Day | Must reach the family |
|---|---|
| `package` | Package left outside |
| `repeat_visitor` | Same stranger, third day this week |
| `routine_missed` | Up at 3am, then not out by her usual time |
| `night_activity` | At the front door at 3:12am |
| `full_day` | Package left out, plus the repeat visitor |

**Normal days that should stay quiet:**
- **Quick pickup:** a delivery she brings in after 30 minutes.
- **A bit late:** out at 8:20 instead of around 7:52.
- **New visitor once:** a woman with flowers.
- **Walk day:** out and back for her afternoon walk.
- **Busy street:** a jogger, a cat, a passing car.

Every run starts from the same 14 days of seeded history.

## Honest notes

- **The 0 false alarms come from the rules layer, not the agent.** On every normal day, the brain's rules found nothing worth escalating, so the agent was never asked. That's by design: the cheap rules filter first, and the LLM only weighs in on real situations. But this test doesn't measure the agent's own restraint.
- **The one inconsistent case is `repeat_visitor`.** That scripted day has no morning sighting of Mom. In 1 of 3 runs the agent also messaged that she hadn't been out, which is arguably right. In the other 2 runs it chose to mention only the visitor.
- **These are scripted days, not real-world footage.** The vision model was only checked on the Ring sandbox clips: a package on the step, and birds at a feeder. Both were described correctly, but that's too few frames to call it an accuracy number.
- **First evaluation pass:** [`RESULTS.md`](RESULTS.md) has all tests passing, and it found a Windows bug (`%-I` time formatting) that crashed replays. Now fixed.
