# Backend ↔ Dashboard contract

The backend runs at `http://localhost:8000`. Everything the dashboard needs comes from the endpoints below. TypeScript types are in [`types.ts`](types.ts). Example payloads are in [`mock/`](mock/).

**Build against `mock/` first.** Switch to the real backend on Thursday by changing one base URL.

## REST

| Method | Path | Returns |
|---|---|---|
| GET | `/api/events?since=<iso>&limit=<n>` | `PorchEvent[]`, oldest first |
| GET | `/api/live` | `LiveView`: the latest Ring frame plus what the AI sees in it |
| GET | `/api/summary/today` | `DailySummary` |
| GET | `/api/baseline` | `Baseline`: the parent's usual routine vs today |
| GET | `/api/status` | `Status`: is the Ring stream connected, is the token valid, demo mode |
| GET | `/api/frames/<name>.jpg` | JPEG image (`frame_url` values point here) |
| POST | `/api/demo/<scenario>` | Starts a replay scenario: `routine_missed`, `repeat_visitor`, `night_activity`, `full_day`. Returns `{ "started": true }` |

## WebSocket: `ws://localhost:8000/ws`

The server pushes messages shaped `{ "kind": ..., "data": ... }`:

| kind | data | When |
|---|---|---|
| `event` | `PorchEvent` | Every new event (observations, agent thoughts, alerts, summaries) |
| `live` | `LiveView` | Every new analysed frame (~every 3 s while the stream runs) |
| `status` | `Status` | When the stream connects/disconnects or the token expires |

On connect, the server sends one `status` and one `live` message, then streams new ones. Load history from `GET /api/events`.

## Event types and how to show them

| `type` | Meaning | Suggested UI |
|---|---|---|
| `observation` | The AI saw something at the door | Timeline row, small, with thumbnail |
| `agent_thought` | The agent's reasoning step | **"Thinking" panel** (live, typewriter feel) |
| `package_unattended` | Package left outside too long | Timeline card, amber |
| `package_taken` | Someone other than the parent took a package | Timeline card, red if `urgent` |
| `repeat_visitor` | Unknown person, repeat visits | Timeline card, amber |
| `routine_missed` | Parent hasn't done their usual thing | Timeline card, red if `urgent` |
| `night_activity` | Door activity 1–5am | Timeline card, red |
| `alert_sent` | A message went to the family's phone | Small "📱 sent to family" chip under the card it belongs to (`related_id`) |
| `daily_summary` | Evening digest | Summary card |
| `resolved` | A situation cleared ("Mom brought the package in") | Green check on the related card (`related_id`) |

`source` is `"ring_live"` (real Ring stream) or `"replay"` (scenario replayer). **Always show it** (e.g. a LIVE / REPLAY badge). We're honest in the demo about what's simulated.

`severity`: `info` (grey), `notice` (amber), `urgent` (red).

## Rules
- Times are ISO 8601 UTC. Display them in `Status.timezone`.
- Any change to this contract is made here first, then in code.
