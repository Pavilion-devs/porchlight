# Porchlight backend

Ring live stream → frames → Claude vision on Bedrock → brain (rules) → **CareAgent** (Strands on Bedrock) → family alerts (Telegram) + dashboard API/WebSocket.

## Run it

Setup and commands live in the [main README](../README.md#run-it). In short, from the repo root:

```bash
make setup && make check
make run            # live Ring stream + Bedrock
make run-offline    # replay only, no Ring or AWS
make demo           # play a scripted day (SCENARIO=full_day|package|repeat_visitor|routine_missed|night_activity)
make test           # rules, webhook signatures, every replay scenario (agent off, no AWS calls)
```

Without make: `cd backend && ../.venv/bin/uvicorn porchlight.app:app --port 8000`.

## How it fits together

| Module | Job |
|---|---|
| `watcher.py` | Opens Ring WHEP live-view sessions, **reconnects every ~8 s** (sandbox limit), samples a frame every 3 s, skips unchanged frames |
| `vision.py` | Bedrock Converse (**Haiku 4.5**) with a forced tool call → structured `Observation` JSON |
| `brain.py` | Turns observations into state; detects `package_unattended`, `package_taken`, `repeat_visitor`, `routine_missed`, `night_activity`; daily summary |
| `agent.py` | **CareAgent**: Strands + Bedrock (**Sonnet 4.6**). Investigates with tools (recent activity, learned routine, visitor history, alerts already sent), then returns a structured decision and the family message. Every tool call shows up as an `agent_thought` |
| `routine.py` | Learns the routine from 14 days of door activity; matches repeat visitors by trait signature |
| `webhooks.py` | Ring v1.1 webhook payloads + HMAC-SHA256 verification (raw body, `sha256=` hex) |
| `replayer.py` | Seeds 14 days of history and plays scripted days on a compressed clock, sending **signed Ring-format webhooks through the same handler** as real ones |
| `app.py` | FastAPI: REST + WebSocket per [`shared/CONTRACT.md`](../shared/CONTRACT.md) |

## Settings (`.env`)

| Key | Default | Notes |
|---|---|---|
| `OAUTH_TOKEN`, `HMAC_SIGNATURE_KEY` | | From the Ring Developer Console |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | empty → alerts are logged only | Make a bot with @BotFather |
| `PARENT_NAME`, `FAMILY_NAME`, `RESIDENT_DESCRIPTION`, `TIMEZONE` | Mom, Ade, …, America/Los_Angeles | |
| `PACKAGE_ALERT_MINUTES` | 180 | Set to `2` for a live demo |
| `VISION_MODEL`, `AGENT_MODEL` | Haiku 4.5, Sonnet 4.6 (`us.` inference profiles) | |
| `USE_AGENT`, `WATCHER_ENABLED` | true | Turn off to run without Bedrock agent / Ring stream |
