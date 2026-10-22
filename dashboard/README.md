# Porchlight dashboard

The family's view of the front door. It's a React + Vite app, and the backend serves the built version at `/`. Locally that's **http://localhost:8000**; on AWS it's the server's address.

| Panel | What it shows | Data |
|---|---|---|
| Door view | The latest Ring frame, what the AI sees in it, and Person / Package / Vehicle chips | `GET /api/live` + `live` messages |
| At the door today | Newest first. Situations are cards, with the family text message and "resolved" attached. Observations are small rows | `GET /api/events` + `event` messages |
| Care agent | The agent's investigation steps as they happen | `agent_thought` events |
| Today at Mom's | Today's summary: headline, mood, counts | `GET /api/summary/today` |
| Mom's usual day | The learned routine vs today | `GET /api/baseline` |
| Replay a day | Starts a scripted day | `POST /api/demo/<scenario>` |

The **Live door / Replayed day** switch picks which data you see. The two never mix. The dashboard switches to the replayed day automatically when a replay starts.

## Run it

```bash
# from the repo root
make setup             # also builds the dashboard
make run-offline       # backend + dashboard on http://localhost:8000 (no Ring or AWS needed)
```

**For dashboard work with hot reload,** keep the backend running and in another terminal run:

```bash
make dashboard-dev     # http://localhost:5173, proxies /api and /ws to :8000
```

Run `make dashboard` to rebuild what the backend serves.

## Code

- `src/usePorch.ts`: all state. It loads over REST, then the WebSocket keeps it current, reconnecting if needed.
- `src/DoorView.tsx`, `src/Timeline.tsx`, `src/Panels.tsx`: the panels.
- Types come straight from [`../shared/types.ts`](../shared/types.ts). The API is described in [`../shared/CONTRACT.md`](../shared/CONTRACT.md).
