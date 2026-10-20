# Porchlight backend

Ring live stream → frames → Claude vision on Bedrock → brain (rules) → **CareAgent** (Strands on Bedrock) → family alerts (Telegram) + dashboard API/WebSocket.

## Run it

```bash
# from the repo root
cp .env.example .env                       # fill in Ring credentials + Playground token (30-min lifetime)
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
aws configure   # or `aws login`: needs Bedrock access to Claude Haiku 4.5 + Sonnet 4.6 in us-east-1

cd backend
uvicorn porchlight.app:app --port 8000
```

- Click **Package / Vehicle / Motion** in the Ring Developer Playground to choose what the sandbox doorbell shows. The watcher picks it up automatically.
- Got a new Playground token? Paste it into `.env`. It's re-read on every request, so no restart is needed.
- Run a scripted day (labelled `replay`): `curl -X POST localhost:8000/api/demo/full_day`.
  Scenarios: `full_day`, `package`, `repeat_visitor`, `routine_missed`, `night_activity`.

## Tests

```bash
cd backend && pytest -q          # rules, webhook signatures, every replay scenario (agent off, no AWS calls)
```

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
