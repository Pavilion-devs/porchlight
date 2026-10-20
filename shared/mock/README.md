# Mock data for the dashboard

Realistic payloads matching [`../CONTRACT.md`](../CONTRACT.md), so the dashboard can be built before the backend is ready.

| File | Matches |
|---|---|
| `events-day-normal.json` | `GET /api/events`: an eventful but OK day (package left out, repeat visitor) |
| `events-day-worrying.json` | `GET /api/events`: a worrying day (3am door activity, missed morning routine, urgent alerts) |
| `live.json` | `GET /api/live` and WebSocket `live` messages |
| `summary-today.json` | `GET /api/summary/today` |
| `baseline.json` | `GET /api/baseline` |
| `status.json` | `GET /api/status` and WebSocket `status` messages |
| `frames/` | Real frames from the Ring Developer Playground doorbell (`frame_url: /api/frames/<name>`) |

**Tip:** to fake the live WebSocket, replay an events file one item every 1–2 seconds.

**Frame credits:** `porch_package.jpg` is from Ring Playground footage "Thief stealing our package" by YouTube user frollard (CC BY 4.0). `feeder_motion.jpg` is from "Birds on Feeders" by Vimeo user Michael Black (CC BY 4.0). Both were captured from the Ring sandbox live stream.
