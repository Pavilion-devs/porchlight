"""Watches the Ring doorbell's live stream (WHEP/WebRTC) and hands sampled frames to a callback.

The Ring sandbox closes each live-view session after ~7-8 s, so the watcher reconnects in a loop.
Frames that barely changed since the last analysed one are skipped to save Bedrock calls.
"""
import asyncio
import io
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from PIL import Image, ImageChops, ImageStat

from .ring import RingAuthError, RingClient

log = logging.getLogger("porchlight.watcher")

FrameCallback = Callable[[bytes, datetime], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]

CHANGE_THRESHOLD = 6.0  # mean abs pixel diff (0-255) on a 64x36 greyscale thumbnail
MAX_SKIP_S = 30  # analyse at least this often even if nothing changed


class StreamWatcher:
    def __init__(self, ring: RingClient, on_frame: FrameCallback, on_status: StatusCallback,
                 every_s: float = 3.0):
        self.ring = ring
        self.on_frame = on_frame
        self.on_status = on_status
        self.every_s = every_s
        self.status = "stopped"
        self.device_id: str | None = None
        self._last_thumb: Image.Image | None = None
        self._last_sent = 0.0
        self._queue: asyncio.Queue[tuple[bytes, datetime]] = asyncio.Queue(maxsize=1)

    async def _set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            log.info("stream status: %s", status)
            await self.on_status(status)

    async def run(self) -> None:
        consumer = asyncio.create_task(self._consume())
        backoff = 1.0
        try:
            while True:
                try:
                    if not self.device_id:
                        self.device_id = await self.ring.first_device_id()
                    await self._session()
                    backoff = 1.0
                    await asyncio.sleep(0.5)  # sandbox session ended normally; reconnect
                except RingAuthError as e:
                    log.warning("%s", e)
                    await self._set_status("token_expired")
                    await asyncio.sleep(15)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.warning("stream error: %r (retry in %.0fs)", e, backoff)
                    await self._set_status("reconnecting")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
        finally:
            consumer.cancel()
            await self._set_status("stopped")

    async def _session(self) -> None:
        pc = RTCPeerConnection(RTCConfiguration([RTCIceServer("stun:stun.l.google.com:19302")]))
        pc.addTransceiver("video", direction="recvonly")
        ended = asyncio.get_running_loop().create_future()
        session_url = None

        @pc.on("track")
        def on_track(track):
            if track.kind == "video":
                asyncio.ensure_future(self._read_track(track, ended))

        @pc.on("connectionstatechange")
        async def on_state():
            if pc.connectionState in ("failed", "closed") and not ended.done():
                ended.set_result(None)

        try:
            await pc.setLocalDescription(await pc.createOffer())  # aiortc gathers ICE first
            answer, session_url = await self.ring.whep_open(self.device_id, pc.localDescription.sdp)
            await pc.setRemoteDescription(RTCSessionDescription(answer, "answer"))
            await self._set_status("connected")
            await asyncio.wait_for(ended, timeout=120)
        finally:
            await pc.close()
            if session_url:
                await self.ring.whep_close(session_url)

    async def _read_track(self, track, ended: asyncio.Future) -> None:
        last_sample = 0.0
        try:
            while True:
                frame = await track.recv()
                now = time.monotonic()
                if now - last_sample < self.every_s and last_sample:
                    continue
                last_sample = now
                img = frame.to_image()
                if not self._changed(img):
                    continue
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                self._offer((buf.getvalue(), datetime.now(timezone.utc)))
        except Exception:
            pass  # Ring closed the stream
        finally:
            if not ended.done():
                ended.set_result(None)

    def _changed(self, img: Image.Image) -> bool:
        thumb = img.convert("L").resize((64, 36))
        due = time.monotonic() - self._last_sent > MAX_SKIP_S
        if self._last_thumb is not None and not due:
            diff = ImageStat.Stat(ImageChops.difference(thumb, self._last_thumb)).mean[0]
            if diff < CHANGE_THRESHOLD:
                return False
        self._last_thumb = thumb
        self._last_sent = time.monotonic()
        return True

    def _offer(self, item: tuple[bytes, datetime]) -> None:
        """Keep only the newest frame waiting, so slow vision calls never build a backlog."""
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(item)

    async def _consume(self) -> None:
        while True:
            jpeg, when = await self._queue.get()
            try:
                await self.on_frame(jpeg, when)
            except Exception:
                log.exception("frame handler failed")
