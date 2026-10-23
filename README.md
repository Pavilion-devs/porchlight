# Porchlight

**An AI helper that watches an older parent's front door through their Ring doorbell, and tells the family when something needs attention. No cameras inside the house.**

Built for the *Build, Ship, Shape: Amazon Developer Hackathon* (Ring track + AWS Builder).

**Try it:** https://100-57-176-133.sslip.io. Press a scenario under *Replay a day* to watch a whole day in about a minute. Then ask about it from any MCP client: [Ask Porchlight](#ask-porchlight-mcp).

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

## Does it work?

We ran 30 replayed days through the real agent on Amazon Bedrock. **21 of 21 situations reached the family. 15 normal days sent 0 messages. The agent made the same decision on every run in 9 of 10 cases.** The full method and caveats are in [`eval/AGENT_EVAL.md`](eval/AGENT_EVAL.md).

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

You need **Python 3.11+**, **Node 18+**, **make** and **curl**. For the live doorbell you also need a Ring developer account and AWS access to Bedrock. To try it offline, skip to step 3.

**1. Install**

```bash
git clone https://github.com/Pavilion-devs/porchlight.git && cd porchlight
make setup                 # creates .venv, installs everything, builds the dashboard, creates .env
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
make run                   # live: Ring stream + Bedrock. Open http://localhost:8000 for the dashboard
make run-offline           # or: no Ring, no AWS (replayed days with template messages)
```

**4. Make something happen**

- **Live:** in the Ring Playground, click **Package**, **Vehicle** or **Motion** to choose what the sandbox doorbell sees. Porchlight picks it up within seconds. Set `PACKAGE_ALERT_MINUTES=2` in `.env` to see a package alert quickly.
- **Replay:** on the dashboard, press a scenario under **Replay a day**. Or, from a second terminal:

```bash
make demo                            # a full day, in about a minute
make demo SCENARIO=routine_missed    # or: package, repeat_visitor, night_activity
```

Watch it unfold on the dashboard: the agent's steps, the family's text message, the routine, and the evening summary.

**Tests**

```bash
make test                  # no AWS or Ring calls needed
```

Run `make` on its own to see every command.

## What's in the repo

| Folder | What it is |
|---|---|
| [`backend/`](backend/) | The Python service: stream watcher, vision, brain, care agent, alerts, replayer and API. See its [README](backend/README.md) for how each part works |
| [`dashboard/`](dashboard/) | The family dashboard (React + Vite), served by the backend at `/`. See its [README](dashboard/README.md) |
| [`deploy/`](deploy/) | Deploying to AWS (EC2): `make deploy`, `make push-token` |
| [`shared/`](shared/) | The contract between backend and dashboard: [API + messages](shared/CONTRACT.md), [TypeScript types](shared/types.ts) and [mock data](shared/mock/) |
| [`scripts/`](scripts/) | `doctor.py` (`make check`) and `telegram_setup.py` (`make telegram`) |
| [`spikes/`](spikes/) | The first standalone experiments that proved the Ring stream and Bedrock vision work |
| [`eval/`](eval/) | Testing and the [agent evaluation](eval/AGENT_EVAL.md) |
| [`docs/`](docs/) | [Build plan](docs/plan.md), [evaluation brief](docs/onboarding-eval.md) and [friction log](docs/FRICTION_LOG.md) (what was hard about the Ring and AWS developer tools) |

## Ask Porchlight (MCP)

Families don't want another dashboard to check. So Porchlight is also an **MCP server**: Streamable HTTP at `/mcp`, built with the official MCP Python SDK, MCP spec 2025-11-25 and newer. That's the standard Alexa+ integrations are built on. Any MCP-capable assistant can answer *"How's Mom doing today?"* from what the doorbell saw.

| Tool | Answers |
|---|---|
| `how_is_parent_doing` | "How's Mom today?": the day's summary, anything still open, when she was last seen, routine changes |
| `open_concerns` | "Anything I should worry about?": what was flagged, what the family was told, what's resolved |
| `visitors_this_week` | "Has that clipboard guy been back?": visitors grouped by appearance, with every visit |
| `usual_routine` | Her learned routine vs today |
| `recent_activity` | The last N hours at the door |
| `front_door_now` | What the Ring doorbell sees right now |

All tools are read-only. Answers are short sentences that read and sound natural, and they always say when they come from the replayed day.

```bash
# Claude Code
claude mcp add --transport http porchlight https://100-57-176-133.sslip.io/mcp
# Claude app: Settings → Connectors → Add custom connector → https://100-57-176-133.sslip.io/mcp
```

Set `MCP_TOKEN` in `.env` to require `Authorization: Bearer <token>`.

## Running on AWS

The hosted version runs on **one EC2 instance** (t3.small, us-east-1):

- Bedrock access comes from the instance's **IAM role** (`porchlight-ec2`, allowed to invoke Anthropic models only), so the server holds no AWS keys.
- **Caddy** provides HTTPS on a free `sslip.io` name, so Ring can send webhooks to it.
- **systemd** keeps the backend running.

```bash
make deploy                # build the dashboard, copy code + .env, install, restart (~1 min)
make push-token            # send a fresh Ring Playground token to the server (they last 30 min)
```

The scripts default to our server. To use your own, set `DEPLOY_HOST`, `DEPLOY_KEY` (SSH key) and `DEPLOY_SG` (security group).

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
