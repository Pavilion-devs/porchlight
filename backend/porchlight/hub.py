"""Fan-out of live messages to every connected dashboard WebSocket.

publish() is safe to call from worker threads (Strands may run agent tools off the event loop).
"""
import asyncio


class Hub:
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, kind: str, data: dict) -> None:
        msg = {"kind": kind, "data": data}
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if self._loop and running is not self._loop:
            self._loop.call_soon_threadsafe(self._deliver, msg)
        else:
            self._deliver(msg)

    def _deliver(self, msg: dict) -> None:
        for q in list(self._subscribers):
            if q.full():  # a stalled client drops its oldest message rather than blocking everyone
                q.get_nowait()
            q.put_nowait(msg)
