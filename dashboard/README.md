# Porchlight dashboard

The family's view of the front door: the live view, a timeline of events (including the agent "thinking"), today's summary and how today compares with the usual routine.

> Not built yet. This folder is the dashboard's home.

## Build against mocks first

You don't need the backend, AWS or a Ring account to start:

- **The contract:** [`../shared/CONTRACT.md`](../shared/CONTRACT.md) lists every endpoint and WebSocket message.
- **Types:** [`../shared/types.ts`](../shared/types.ts) (copy it in or import it).
- **Mock data:** [`../shared/mock/`](../shared/mock/) has a normal day and a worrying day, plus real Ring sandbox frames.

Any stack is fine. Keep the dev server on a port other than 8000, which the backend uses.

## Switch to the real backend

```bash
# from the repo root
make setup
make run-offline                     # backend on :8000, no Ring or AWS needed
make demo SCENARIO=full_day          # plays a scripted day over the WebSocket in about a minute
```

- REST: `http://localhost:8000/api/...`
- Live updates: `ws://localhost:8000/ws`
- Images: `frame_url` values are relative (`/api/frames/x.jpg`), so prefix them with the backend URL.

CORS is open, so the dashboard can call the backend from any local port.
