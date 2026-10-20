# Porchlight: Build Plan

> An AI helper that watches an older parent's front door through their Ring doorbell and tells the family when something needs attention, without any cameras inside the house.

**Hackathon:** Build, Ship, Shape: Amazon Developer Hackathon (Devpost)
**Track:** Ring (primary) + AWS Builder (mini challenge) + Open Source (stretch)
**Deadline:** **Fri Oct 23, 2026, 12:00pm PDT** (8:00pm WAT). We aim to submit Thursday night.

---

## 1. The idea in 30 seconds

Adult children who live far from an aging parent worry. The parent doesn't want cameras inside. Most Ring homes already have one device: **a doorbell**. Porchlight watches that doorbell's video, understands it with Claude on AWS Bedrock, and only speaks up when it matters:

| Feature | Example alert |
|---|---|
| **Packages** | "A package was delivered at 2pm and it's still outside at 6pm." |
| **Visitors** | "Someone you don't recognise has come to the door 3 times this week." |
| **Routine** | "Mom usually steps out by 10am. Today she hasn't." |
| **Daily summary** | "Normal day. Two visitors, one delivery, all fine." |

**Why it can win:** the Ring judges list non-security uses (caretaking, accessibility, package management) and event-based triggers as "creative," and motion alerts and live view as "obvious." We need no new hardware, and we have a strong privacy story: front door only.

---

## 2. What we've already proven (Oct 19–20)

Everything below was tested against the real Ring API and Bedrock, not just read in the docs.

| Piece | Result | Notes |
|---|---|---|
| Ring auth + `GET /v1/devices` | ✅ | Sandbox has **one device**: "Playground Device", a Video Doorbell Pro. **No sensors, no Chime.** |
| Event history `GET /v1/history/devices/{id}/events` | ✅ | Live views show up as `on_demand` events. There's a `cv_detections` field (empty so far). |
| Snapshot / clip download | ❌ in sandbox | Request format works (`{"type":"at_timestamp","timestamp":<ms>}` → 303 redirect), but always `416 MEDIA_NOT_FOUND`. The sandbox doorbell never records. |
| **Live stream (WHEP/WebRTC) → frames in our code** | ✅ | 1280×720 frames via `aiortc`. See `spikes/whep_frames.py`. |
| **Choosing the scene** | ✅ | The Playground's **Package / Vehicle / Motion** buttons set the footage our own stream receives, and it persists after the popup closes. |
| Stream length | ⚠️ ~7–8 s | The sandbox closes each session after ~7–8 s. **The watcher must reconnect in a loop.** |
| **Bedrock vision on Ring frames** | ✅ | Sonnet 4.6 described a real Ring frame correctly in 2.5 s (~1.4k tokens). |
| Bedrock models enabled | ✅ / ❌ | ✅ `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-opus-4-5-20251101-v1:0`. ❌ Sonnet 5 / 5.5, Haiku 5.5 ("not available for this account"). |
| Playground token lifetime | ⚠️ 30 min | Regenerate before each work/recording session. Look into a refreshable token for the app. |
| Webhooks | ❓ | Not tested yet; needs a public HTTPS URL (cloudflared/ngrok). |

**Sandbox footage available:**
- **Motion:** birds at a snowy feeder
- **Package:** a porch with a box ("Thief stealing our package", CC BY 4.0)
- **Vehicle:** not yet viewed

**To check:** does a person ever appear in the Package clip?

---

## 3. How it works

```
 Ring doorbell (sandbox)
        │  WHEP live stream (reconnect every ~8s)
        ▼
 ┌─────────────┐   frames    ┌──────────────┐  observations  ┌─────────────────┐
 │ Stream      │ ──────────► │ Vision       │ ─────────────► │ Brain (agent)   │
 │ watcher     │  (1 / 2-3s) │ Bedrock      │  (JSON facts)  │ Strands+Bedrock │
 └─────────────┘             │ Haiku 4.5    │                │ memory + rules  │
                             └──────────────┘                └───────┬─────────┘
 Scenario replayer ── synthetic doorbell/motion events ──────────────┤
 (+ 14-day seeded history, clearly labelled)                         │ events
                                                                     ▼
                                    ┌────────────────┐     ┌─────────────────┐
                                    │ Telegram alert │ ◄── │ API (FastAPI)   │ ──► Dashboard
                                    │ (family phone) │     │ SQLite + WS     │     (React)
                                    └────────────────┘     └─────────────────┘
```

**Stack**
- **Backend:** Python 3.12, FastAPI, `aiortc` (WebRTC), `boto3` / **Strands Agents SDK** (Bedrock), SQLite, WebSocket for live updates
- **Frontend:** React + Vite + TypeScript
- **Alerts:** Telegram Bot API (free, instant, shows nicely on camera)
- **AWS (for the AWS Builder challenge):** Bedrock (vision + agent reasoning), Strands (agent framework), and AgentCore Memory if time allows (otherwise SQLite memory)

---

## 4. Who does what

| | **Teammate: backend** | **Ola + Claude: everything else** |
|---|---|---|
| Builds | Stream watcher, vision, brain/agent, alerts, replayer, API (§5 items 2–6) | Repo setup, **dashboard** (item 7), data contract + mock data |
| Owns | Backend README section, AWS notes for the feedback form | **Friction log**, product feedback, write-up, demo video, Devpost submission |
| Together | Data contract (§6) on day one, integration Thursday, final demo run | |

Claude has already written working spikes for the hardest parts (WHEP frames, Bedrock vision). The backend should start from `spikes/`.

---

## 5. Build list

### 1. Repo setup (Ola + Claude, Tue) ✅ in progress
- [x] `.gitignore` (blocks `.env`, keys, venvs, frames), `.env.example`, MIT `LICENSE`
- [x] `plan.md`, `FRICTION_LOG.md`, `spikes/`
- [ ] Folder skeleton: `backend/`, `frontend/`, `shared/` (contract + mock events)

### 2. Stream watcher (backend)
- [ ] Open a WHEP session, receive video, sample 1 frame every 2–3 s
- [ ] **Reconnect automatically** when Ring closes the session (~8 s), with backoff on errors
- [ ] Always `DELETE` the session on exit
- [ ] Keep the latest frame in memory for the dashboard's "live" view
- [ ] Read the token from `.env`, with a clear error when it has expired (401)

### 3. Vision (backend)
- [ ] Send each sampled frame to **Haiku 4.5** on Bedrock and get **structured JSON** back:
  `{ person: bool, person_desc, package: bool, package_desc, vehicle: bool, activity, confidence }`
- [ ] Skip frames that haven't changed (cheap pixel-diff) to save cost
- [ ] Use **Sonnet 4.6** only for the escalation/summary step

### 4. Brain / agent (backend)
- [ ] Turn observations into **state**: "package on porch since 14:02," "person seen 3× this week"
- [ ] Rules + agent reasoning for:
  - `package_unattended`: a package has been present more than N hours (demo: minutes, on a compressed clock)
  - `repeat_visitor`: the same described person on several days
  - `routine_missed`: no "resident leaves/returns" activity by the usual time (uses the seeded history)
  - `night_activity`: door activity between 1–5am
  - `daily_summary`: evening digest
- [ ] Strands agent with tools: `get_recent_observations`, `get_baseline`, `send_alert`, `write_summary`
- [ ] Every decision stores a short **reasoning string**, which the dashboard shows live

### 5. Alerts (backend)
- [ ] Telegram bot: text + the frame image + severity
- [ ] De-duplicate so the same situation isn't alerted twice

### 6. Scenario replayer + seeded history (backend)
- [ ] Seed **14 days** of believable routine events so "day 15" has a baseline
- [ ] Replay a scripted demo day on a **compressed clock** (one day in about 60 s)
- [ ] Synthetic events use the **real Ring webhook payload format**, signed with our HMAC key, and go through the same handler as real webhooks
- [ ] Everything synthetic is labelled `source: "replay"` and shown that way in the dashboard
- [ ] Stretch: package it as a standalone open-source tool (Open Source mini challenge)

### 7. Dashboard (Ola + Claude)
- [ ] **Live porch panel:** latest frame plus the AI's description
- [ ] **Agent thinking panel:** the live stream of reasoning strings
- [ ] **Timeline:** today's events with icons and severity
- [ ] **Daily summary card**
- [ ] "Mom's routine" view: baseline vs today
- [ ] Badge showing **LIVE (Ring)** vs **REPLAY**, for honesty
- [ ] Builds against `shared/mock-events.json` first, then switches to the real WebSocket

---

## 6. Data contract (agree on day one)

The backend sends the dashboard **events** over WebSocket `ws://localhost:8000/ws` and serves history at `GET /api/events?since=<iso>`.

```jsonc
{
  "id": "evt_01J...",                 // unique
  "time": "2026-10-20T14:02:11Z",     // ISO 8601, UTC
  "type": "observation" | "package_unattended" | "repeat_visitor" | "routine_missed"
        | "night_activity" | "daily_summary" | "agent_thought" | "alert_sent",
  "severity": "info" | "notice" | "urgent",
  "title": "Package still outside",
  "summary": "A brown box has been on the steps since 2:02pm (4h).",
  "reasoning": "Package first seen 14:02. Resident hasn't been seen since 13:40. Past 3h threshold.",
  "frame_url": "/api/frames/abc.jpg",  // optional
  "source": "ring_live" | "replay",
  "device_id": "ava1.ring.device...."  // optional
}
```

Other endpoints:
- `GET /api/live`: latest frame plus its description
- `GET /api/summary/today`
- `GET /api/baseline`

Any change to the contract goes in this section **before** it goes in code.

---

## 7. Schedule

| Day | Teammate (backend) | Ola + Claude |
|---|---|---|
| **Tue Oct 20** | Set up accounts (Ring dev, Playground token); run `spikes/`; stream watcher with reconnect | Repo skeleton, data contract, mock events, dashboard layout |
| **Wed Oct 21** | Vision JSON, brain rules + Strands agent, Telegram alerts | Dashboard panels: live, thinking, timeline, summary |
| **Thu Oct 22** | Replayer + seeded history, API + WebSocket, **integration** | Wire the dashboard to the real API, video script, write-up draft, friction log |
| **Fri Oct 23 (a.m.)** | Bug fixes only | Record + edit video, **submit before 12pm PDT** |

**Rule:** after Thursday 6pm WAT, no new features, only fixes.

---

## 8. Demo video plan (under 3:00, lead with the best part)

1. **0:00–0:20 Hook.** A phone buzzes: "Package still outside Mom's door, 4 hours." *"She refused cameras inside. So we didn't use any."*
2. **0:20–1:20 Live Ring scene.** The real Ring stream (Package scene) on the dashboard; the AI describes it; the agent's thinking; the Telegram alert arrives on a real phone.
3. **1:20–2:00 Routine.** Compressed-clock replay (labelled): "Mom hasn't stepped out by 10am" → check-in → escalation.
4. **2:00–2:30 Repeat visitor + daily summary card.**
5. **2:30–3:00 Architecture diagram** + the privacy pitch + "works with the Ring doorbell families already have."

**Honesty line, in the video and README:** "Runs on the Ring Developer sandbox; routine events come from our labelled scenario replayer."

---

## 9. Submission checklist

- [ ] Public repo with LICENSE, plus run instructions in the README
- [ ] Repo **actually calls the Ring API in code** (Stage 1 pass/fail check)
- [ ] Demo video < 3 min, public on YouTube/Vimeo, English, no copyrighted music
- [ ] Text description: what it does and how it works
- [ ] **Product feedback** for each tool (Ring API, Playground, Ring MCP, Bedrock, Strands): what worked, what didn't, onboarding, would we use it again
- [ ] **Friction log** (up to +10%) → `FRICTION_LOG.md`
- [ ] Feature requests (optional)
- [ ] Track: **Ring**. Mini challenges: **AWS Builder** (+ **Open Source** if the replayer ships)
- [ ] Teammate added as a team member on Devpost

---

## 10. Secrets and accounts

- **Never commit `.env`.** It's in `.gitignore`. Copy `.env.example` to `.env` and fill it in.
- **Each person uses their own credentials:** their own Ring developer account and Playground token, their own Telegram bot, and an AWS **IAM user** (not root).
- Playground tokens last **30 minutes**. Regenerate when you see `401`.

## 11. Open questions

- [ ] Does a person appear in the sandbox Package clip? What does Vehicle show?
- [ ] Do Playground actions fire **webhooks** to our URL?
- [ ] Can app credentials (client ID/secret) give us a longer-lived or refreshable token?
- [ ] AgentCore Memory vs SQLite: decide Wednesday based on time.
