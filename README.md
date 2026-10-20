# Porchlight

**An AI helper that watches an older parent's front door through their Ring doorbell and tells the family when something needs attention, without any cameras inside the house.**

Built for the *Build, Ship, Shape: Amazon Developer Hackathon* (Ring track + AWS Builder).

> 🚧 Work in progress. See [`plan.md`](plan.md) for the build plan, architecture, data contract and schedule.

## What it does
- **Packages:** "A package was delivered at 2pm and it's still outside at 6pm."
- **Visitors:** "Someone you don't recognise has come to the door 3 times this week."
- **Routine:** "Mom usually steps out by 10am. Today she hasn't."
- **Daily summary:** "Normal day. Two visitors, one delivery, all fine."

## How it works
Ring live stream (WHEP) → frames → Claude on Amazon Bedrock (vision) → Strands agent (memory + decisions) → family alerts + dashboard.

Runs on the **Ring Developer sandbox**. Routine events come from our clearly labelled scenario replayer.

## Quick start (spikes)
```bash
cp .env.example .env            # fill in your Ring app credentials + Playground token
python3 -m venv .venv && source .venv/bin/activate
pip install -r spikes/requirements.txt

python spikes/whep_frames.py 3 3                       # saves frames from the Ring live stream to frames/
python spikes/bedrock_vision.py frames/<file>.jpg      # describes a frame with Claude on Bedrock
```

## License
MIT. See [LICENSE](LICENSE).
