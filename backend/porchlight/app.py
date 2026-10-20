"""Porchlight API: wires the Ring stream watcher, vision, brain, agent, replayer and dashboard together.

Run:  uvicorn porchlight.app:app --reload --port 8000   (from backend/)
Contract: shared/CONTRACT.md
"""
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import routine, webhooks
from .agent import CareAgent
from .alerts import Notifier
from .brain import Brain, hhmm, iso
from .config import settings
from .hub import Hub
from .replayer import SCENARIOS, Replayer
from .ring import RingClient, token_expires_in_s
from .store import Store
from .vision import Observation, Vision
from .watcher import StreamWatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("porchlight")

settings.frames_dir.mkdir(parents=True, exist_ok=True)
store = Store(settings.db_path)
hub = Hub()
notifier = Notifier()
brain = Brain(store, hub, notifier, settings)
if settings.use_agent:
    brain.agent = CareAgent(brain, settings)
ring = RingClient()
vision: Vision | None = None
seen_webhooks: set[str] = set()

live: dict = {"time": iso(datetime.now(timezone.utc)), "frame_url": None,
              "description": "Waiting for the Ring stream…", "person": False, "package": False,
              "vehicle": False, "source": "ring_live"}
stream_status = {"value": "stopped"}


async def handle_webhook(raw: bytes, signature: str) -> dict:
    """One path for real Ring webhooks and the replayer's synthetic ones."""
    if not webhooks.verify(raw, signature, settings.hmac_key):
        raise HTTPException(401, "bad signature")
    w = webhooks.parse(raw)
    if w["request_id"] in seen_webhooks:  # Ring retries; request_id makes delivery idempotent
        return {"ok": True, "duplicate": True}
    seen_webhooks.add(w["request_id"])
    source = "replay" if w["device_id"] and "replay" in w["device_id"] else "ring_live"
    label = {"button_press": "Doorbell pressed", "motion_detected": "Motion at the door"}.get(w["type"], w["type"])
    if w["sub_type"] and w["sub_type"] != "motion":
        label += f" ({w['sub_type'].replace('_', ' ')})"
    brain.thought(label, f"Ring event: {w['type']}" + (f" / {w['sub_type']}" if w["sub_type"] else ""),
                  w["time"], source)
    return {"ok": True}


replayer = Replayer(brain, store, brain.tz, settings.hmac_key, handle_webhook)


def status() -> dict:
    return {"stream": stream_status["value"], "ring_token_expires_in_s": token_expires_in_s(),
            "demo_running": replayer.running, "parent_name": settings.parent_name, "timezone": settings.timezone}


async def on_status(value: str) -> None:
    stream_status["value"] = value
    hub.publish("status", status())


async def on_frame(jpeg: bytes, when: datetime) -> None:
    global vision
    name = f"{int(when.timestamp() * 1000)}.jpg"
    (settings.frames_dir / name).write_bytes(jpeg)
    vision = vision or Vision()
    obs: Observation = await vision.describe(jpeg, when, frame_name=name)
    live.update(time=iso(when), frame_url=f"/api/frames/{name}", description=obs.description,
                person=obs.person, package=obs.package, vehicle=obs.vehicle, source="ring_live")
    hub.publish("live", dict(live))
    if not replayer.running:  # a replayed day owns the brain while it runs
        await brain.on_observation(obs)
    prune_frames()


def prune_frames(keep: int = 600) -> None:
    frames = sorted(settings.frames_dir.glob("*.jpg"))
    for f in frames[:-keep]:
        f.unlink(missing_ok=True)


async def tick_loop() -> None:
    while True:
        await asyncio.sleep(20)
        if not replayer.running:
            try:
                await brain.tick(datetime.now(timezone.utc))
            except Exception:
                log.exception("tick failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    hub.bind(asyncio.get_running_loop())
    tasks = [asyncio.create_task(tick_loop())]
    if settings.watcher_enabled:
        watcher = StreamWatcher(ring, on_frame, on_status, every_s=settings.sample_every_s)
        tasks.append(asyncio.create_task(watcher.run()))
    log.info("Porchlight up: watcher=%s agent=%s alerts=%s", settings.watcher_enabled,
             bool(brain.agent), notifier.channel)
    yield
    for t in tasks:
        t.cancel()
    for t in tasks:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    await ring.aclose()


app = FastAPI(title="Porchlight", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/events")
def get_events(since: str | None = None, limit: int = 500):
    return store.events(since=since, limit=limit)


@app.get("/api/live")
def get_live():
    return live


@app.get("/api/status")
def get_status():
    return status()


@app.get("/api/frames/{name}")
def get_frame(name: str):
    path = brain.frame_path(name) if "/" not in name and ".." not in name else None
    if not path:
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/summary/today")
def get_summary():
    now = datetime.now(brain.tz)
    saved = store.get(f"summary:{now.date()}")
    if saved:
        return saved
    start = datetime.combine(now.date(), time(0, 0), brain.tz)
    events = [e for e in store.events(since=iso(start)) if e["type"] not in ("agent_thought", "daily_summary")]
    summary = brain.summary_counts(events)
    summary.update(date=str(now.date()), headline="So far today: " + summary["headline"][0].lower()
                   + summary["headline"][1:])
    return summary


@app.get("/api/baseline")
def get_baseline():
    now = datetime.now(brain.tz)
    today = now.date()
    stats = {r.key: r for r in routine.learn(store, today, brain.tz)}
    actual = {"first_out": routine.first_out_today(store, today, brain.tz),
              "walk": routine.afternoon_out(store, today, brain.tz)}
    items = []
    for key, r in stats.items():
        got = actual[key]
        if got:
            usual = datetime.combine(today, r.usual, brain.tz) if r.usual else got
            state = "ok" if abs((got - usual).total_seconds()) / 60 <= r.window_minutes else "late"
        elif r.latest and now > datetime.combine(today, r.latest, brain.tz) + timedelta(minutes=r.window_minutes):
            state = "missed"
        else:
            state = "pending"
        items.append({"label": r.label, "usual": r.usual.strftime("%H:%M") if r.usual else "—",
                      "window_minutes": r.window_minutes, "today": got.strftime("%H:%M") if got else None,
                      "status": state})
    night_start = datetime.combine(today, time(settings.night_start_hour), brain.tz)
    night = store.observations(night_start, night_start + timedelta(
        hours=settings.night_end_hour - settings.night_start_hour))
    night = [o for o in night if o.person]
    items.append({"label": f"Quiet at night ({settings.night_start_hour}–{settings.night_end_hour}am)",
                  "usual": "no activity", "window_minutes": 0,
                  "today": hhmm(night[0].time.astimezone(brain.tz)) if night else "no activity",
                  "status": "late" if night else "ok"})
    return {"parent_name": settings.parent_name, "days_learned": max((r.days for r in stats.values()), default=0),
            "items": items}


@app.post("/api/demo/{scenario}")
async def start_demo(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(404, f"unknown scenario; choose one of {sorted(SCENARIOS)}")
    if replayer.running:
        raise HTTPException(409, f"'{replayer.running}' is already running")

    async def run():
        try:
            await replayer.run(scenario)
        except Exception:
            log.exception("demo scenario failed")
        finally:
            hub.publish("status", status())

    asyncio.create_task(run())
    await asyncio.sleep(0)
    hub.publish("status", status())
    return {"started": True, "scenario": scenario}


@app.post("/webhooks/ring")
async def ring_webhook(request: Request):
    return await handle_webhook(await request.body(), request.headers.get("X-Signature", ""))


@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    q = hub.subscribe()
    try:
        await socket.send_json({"kind": "status", "data": status()})
        await socket.send_json({"kind": "live", "data": live})
        while True:
            await socket.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)
