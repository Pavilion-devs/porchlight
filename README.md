# Porchlight

**An AI helper that watches an older parent's front door through their Ring doorbell, and tells the family when something needs attention. No cameras inside the house.**

Built for the *Build, Ship, Shape: Amazon Developer Hackathon* (Ring track + AWS Builder).

## What it does

Porchlight learns the parent's normal days from the front door, then speaks up when something is off:

| Situation | Example message to the family |
|---|---|
| 📦 Package left outside | "A package arrived at Mom's door at 2:04pm and it's still outside." |
| 🚨 Package taken | "Someone who isn't Mom just picked up the package from the step." |
| 🧍 Repeat visitor | "A man with a clipboard has come to the door 3 days in a row." |
| ⏰ Routine missed | "Mom usually steps out by 8:15am. It's 9:40 and she hasn't yet. Maybe give her a call?" |
| 🌙 Night activity | "Mom was at the front door at 3:12am." |
| 📝 Daily summary | "Normal day. Two visitors, one delivery, all fine." |

Before it sends anything, an AI agent checks the history (recent activity, her usual routine, past visitors, alerts already sent) so the family gets one clear, calm message instead of a stream of motion alerts.

## How it works

```
Ring doorbell ──live video (WHEP)──▶ Stream watcher ──frames──▶ Vision: Claude Haiku on Bedrock
                                                                        │ "package on the step"
Ring webhooks ──signed events──────────────────────────────┐            ▼
                                                           └──▶ Brain (rules + memory, SQLite)
                                                                        │ "package outside 3h"
                                                                        ▼
                                                     Care agent: Strands + Claude Sonnet on Bedrock
                                                     (looks things up with tools, then decides)
                                                                        │
                                              ┌─────────────────────────┴───────────┐
                                              ▼                                     ▼
                                     Telegram message                   Dashboard (REST + WebSocket)
```

It runs on the **Ring Developer sandbox** doorbell. A sandbox has no real history, so the **replayer** plays clearly labelled scripted days (14 days of routine, then a test day) through the same code path as real Ring webhooks. Live and replayed data are kept separate everywhere.

## Run it

You need **Python 3.11+**, **make** and **curl**. For the live doorbell you also need a Ring developer account and AWS access to Bedrock. To try it offline, skip to step 3.

**1. Install**

```bash
git clone https://github.com/Pavilion-devs/porchlight.git && cd porchlight
make setup                 # creates .venv, installs everything, creates .env
```

**2. Fill in `.env`** (only needed for the live doorbell)

| Key | Where to get it |
|---|---|
| `HMAC_SIGNATURE_KEY` (and `CLIENT_ID`, `CLIENT_SECRET`) | Ring Developer Console → your app |
| `OAUTH_TOKEN` | Ring Developer Console → **Playground** → Generate token. It lasts 30 minutes; paste a new one any time, no restart needed |
| AWS credentials | Not in `.env`: run `aws login` or `aws configure`. Enable **Claude Haiku 4.5** and **Claude Sonnet 4.6** in the Bedrock console (us-east-1) |
| `TELEGRAM_BOT_TOKEN` (optional) | Telegram → **@BotFather** → `/newbot`. Then message your bot and run `make telegram` to fill in the chat ID |

Then check everything:

```bash
make check                 # tests Ring, Bedrock and Telegram, and says how to fix anything missing
```

**3. Start it**

```bash
make run                   # live: Ring stream + Bedrock, on http://localhost:8000
make run-offline           # or: no Ring, no AWS (replayed days with template messages)
```

**4. Make something happen**

- **Live:** in the Ring Playground, click **Package**, **Vehicle** or **Motion** to choose what the sandbox doorbell sees. Porchlight picks it up within seconds. Set `PACKAGE_ALERT_MINUTES=2` in `.env` to see a package alert quickly.
- **Replay:** in a second terminal, play a scripted day:

```bash
make demo                            # a full day, in about a minute
make demo SCENARIO=routine_missed    # or: package, repeat_visitor, night_activity
```

Watch the events in the server log, at http://localhost:8000/api/events, or on the dashboard.

**Tests**

```bash
make test                  # no AWS or Ring calls needed
```

Run `make` on its own to see every command.

## What's in the repo

| Folder | What it is |
|---|---|
| [`backend/`](backend/) | The Python service: stream watcher, vision, brain, care agent, alerts, replayer and API. See its [README](backend/README.md) for how each part works |
| [`dashboard/`](dashboard/) | The family dashboard (in progress) |
| [`shared/`](shared/) | The contract between backend and dashboard: [API + messages](shared/CONTRACT.md), [TypeScript types](shared/types.ts) and [mock data](shared/mock/) |
| [`scripts/`](scripts/) | `doctor.py` (`make check`) and `telegram_setup.py` (`make telegram`) |
| [`spikes/`](spikes/) | The first standalone experiments that proved the Ring stream and Bedrock vision work |
| [`docs/`](docs/) | [Build plan](docs/plan.md) and [friction log](docs/FRICTION_LOG.md) (what was hard about the Ring and AWS developer tools) |

## Troubleshooting

| You see | Fix |
|---|---|
| `token_expired` in the log or `/api/status` | The Playground token lasts 30 min. Generate a new one and save it in `.env` |
| The stream reconnects every ~8 seconds | Expected: the sandbox ends each live session after about 8 s, and the watcher reconnects |
| `AccessDeniedException` from Bedrock | Enable the model in the Bedrock console, or set `VISION_MODEL` / `AGENT_MODEL` in `.env` to one you can use |
| `MissingDependencyException` with `aws login` | Run `make setup` again (it installs `botocore[crt]`) |
| Alerts appear only in the log | Telegram isn't configured. See `make telegram` |
| `Address already in use` | Something is already on port 8000. Stop it, or use `make run PORT=8001` |

## Credits and license

The sandbox footage is the Ring Developer Playground's (see [`shared/mock/README.md`](shared/mock/README.md) for clip credits). The code is MIT licensed. See [LICENSE](LICENSE).
