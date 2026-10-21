# Welcome to Porchlight: your brief (evaluation)

Thanks for joining! This page tells you what Porchlight is, what we'd love you to own, and how to get going. Expect to spend about 15 minutes reading it.

**Deadline for your work: Thursday Oct 22, 4pm WAT (8am PDT).** Our feature freeze is Thursday 6pm WAT, and we submit on Friday.

## Porchlight in one minute

Porchlight watches an older parent's front door through their Ring doorbell and tells the family when something needs attention. There are no cameras inside the house.

1. A **watcher** pulls frames from the Ring live stream.
2. **Vision** (Claude Haiku on Amazon Bedrock) turns each frame into structured facts: is there a person or a package, what activity is happening, and so on.
3. The **brain** keeps memory and applies rules: a package left outside for hours, a missed morning routine, a repeat visitor, activity at night.
4. When the brain spots a situation, the **care agent** (Strands + Claude Sonnet on Bedrock) looks things up with tools and decides whether to message the family, and what to say.

The demo runs on Ring's **sandbox** doorbell, which has no real history. So a **replayer** plays scripted days (14 days of routine, then a test day) through the same code path. The [main README](../README.md) has the diagram and the full picture.

## Your mission: prove it works

A judge will ask: *"How do you know the AI gets it right?"* Today we can only show demos. You'll give us **numbers**. You own the evaluation, in a new `eval/` folder.

### 1. Vision accuracy (most important)
- Build a small labelled set: **30–60 frames** is plenty.
  - Sandbox frames: the Package, Vehicle and Motion scenes. You get these from `make run`, which saves them to `backend/data/frames/`, or ask Ola.
  - Royalty-free porch and doorstep photos: an empty porch, delivery people, visitors, an older woman at the door, night shots. Note the source and license of each one.
- Label each frame in `eval/labels.csv`: `file, person, package, vehicle, activity`. The activity values are listed in `ACTIVITIES` in `backend/porchlight/vision.py`.
- Run vision on every frame and measure it:
  - For person, package and vehicle: accuracy, plus false positives and misses.
  - For activity: a confusion matrix.

### 2. Alert decisions
- Run the replayed scenarios **with the real agent**, several times each.
  - Scenarios: `package`, `repeat_visitor`, `routine_missed`, `night_activity`, `full_day`.
- Add **"normal day" variations**: she's out a bit late but still in her usual window, a delivery she picks up quickly, a one-off visitor. These should *not* trigger alerts.
- Measure:
  - **Recall:** for days where an alert should fire, did it?
  - **False alarms:** across normal days, how many alerts fired that shouldn't have?
  - **Consistency:** across repeated runs, does the agent make the same call?

### 3. Stretch: a better routine model
Only if 1 and 2 are done. `backend/porchlight/routine.py` learns her usual morning time as "median + a fixed grace period". Ideas:
- a confidence score
- weekday vs weekend patterns
- needing fewer days of history before it's trustworthy

Any change here must keep `make test` passing.

### What "done" looks like
- An `eval/` folder: your scripts, `labels.csv`, and the frames (or a list of where they came from).
- `eval/RESULTS.md`: a short table of results, how you measured them, and the honest weak spots.
- **One headline sentence** we can put in the README and the demo video. For example: *"Vision was right on 54 of 60 frames; the agent caught 19 of 20 real situations with 1 false alarm in 30 normal days."*

Honest numbers beat impressive ones. If something is weak, say so. We'll mention it as a limitation.

## Getting set up (about 30 minutes)

1. **Get the code.** Accept the GitHub invite, then:
   ```bash
   git clone https://github.com/Pavilion-devs/porchlight.git && cd porchlight
   make setup
   ```
2. **Run it offline first.** No accounts are needed for this step:
   ```bash
   make run-offline          # terminal 1
   make demo                 # terminal 2: plays a full scripted day in about a minute
   ```
   Then open http://localhost:8000/api/events and watch the events arrive.
3. **AWS (needed for the real evaluation).** Ola will send you login details for an IAM user that can use Bedrock. Then run `aws configure` (region `us-east-1`) and `make check`. You should see both models ticked. *Never use or ask for the root account.*
4. **Ring (optional).** You only need this if you want to pull sandbox frames yourself. Make your own Ring developer account and Playground token. The README explains how.

**While you set up, note anything confusing or broken.** That's useful too: it fixes our README and goes into our [friction log](FRICTION_LOG.md).

## Code you'll use

Run these from `backend/` with `../.venv/bin/python`, so `porchlight` can be imported.

**Describe one frame:**
```python
import asyncio
from datetime import datetime, timezone
from porchlight.vision import Vision

obs = asyncio.run(Vision().describe(open("frame.jpg", "rb").read(), datetime.now(timezone.utc), "frame.jpg"))
print(obs.person, obs.package, obs.vehicle, obs.activity, obs.description)
```

**Run a scenario with the real agent, in memory:**
```python
import asyncio
from datetime import date
from porchlight.agent import CareAgent
from porchlight.brain import Brain
from porchlight.config import settings
from porchlight.hub import Hub
from porchlight.replayer import Replayer
from porchlight.store import Store

class Quiet:  # stands in for Telegram
    channel = "eval"
    async def send(self, text, photo=None): return True

async def run(scenario):
    store = Store(":memory:")
    brain = Brain(store, Hub(), Quiet(), settings)
    brain.agent = CareAgent(brain, settings)
    async def sink(raw, sig): pass
    await Replayer(brain, store, brain.tz, settings.hmac_key, sink, max_gap_s=0, min_gap_s=0).run(scenario, day=date(2026, 10, 20))
    return [e for e in store.events() if e["type"] != "agent_thought"]

for e in asyncio.run(run("package")):
    print(e["type"], e["severity"], e["title"])
```

To add normal-day variations, build your own `Step` lists in your eval code (see `SCENARIOS` in `backend/porchlight/replayer.py` for the format). Please don't edit the existing scenarios: the demo depends on them.

## How we work together

| Who | Owns | Folder |
|---|---|---|
| Ola (+ Claude) | Backend, submission, demo video | `backend/`, `docs/` |
| Dashboard teammate | The family dashboard | `dashboard/` |
| **You** | Evaluation (+ routine model if time allows) | `eval/`, `backend/porchlight/routine.py` |

- Work on a branch (`git checkout -b eval`) and open a pull request into `main`. Small, frequent pushes are great.
- **Never commit `.env`**, keys, tokens or AWS credentials. `.gitignore` already covers `.env`.
- Bedrock calls cost money. A full evaluation should cost a few dollars. Start small (5 frames, 1 scenario) before running everything.
- Got an idea for a new feature? Write it down and share it. We'll decide together. Nothing new goes in after Thursday 6pm WAT.
- Stuck for more than 30 minutes? Ask Ola.

Welcome aboard! 🏮
