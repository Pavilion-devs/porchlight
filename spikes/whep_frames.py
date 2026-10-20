"""Spike: open a Ring WHEP live stream from the sandbox doorbell and save frames.

Proven on Oct 20, 2026 against the Ring Developer Playground device.
The sandbox closes each stream after ~7-8 s, so expect 2-3 frames per session.

Usage:
    pip install -r spikes/requirements.txt
    python spikes/whep_frames.py [N_FRAMES] [EVERY_SECONDS]

Reads OAUTH_TOKEN from .env (Playground token, valid for 30 minutes).
Pick the footage first by clicking Package / Vehicle / Motion in the Playground.
"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.amazonvision.com"
N_FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 3
EVERY_S = int(sys.argv[2]) if len(sys.argv) > 2 else 3
OUT_DIR = ROOT / "frames"


def load_token():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("OAUTH_TOKEN="):
            return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("OAUTH_TOKEN missing from .env")


TOKEN = load_token()


def http(method, url, body=None, ctype=None):
    req = urllib.request.Request(url, data=body, method=method, headers={"Authorization": f"Bearer {TOKEN}"})
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def first_device_id():
    status, _, body = http("GET", f"{API}/v1/devices")
    if status == 401:
        sys.exit("401: Playground token expired. Generate a new one and update .env")
    return json.loads(body)["data"][0]["id"]


async def main():
    OUT_DIR.mkdir(exist_ok=True)
    device_id = first_device_id()
    pc = RTCPeerConnection(RTCConfiguration([RTCIceServer("stun:stun.l.google.com:19302")]))
    pc.addTransceiver("video", direction="recvonly")
    done = asyncio.get_event_loop().create_future()

    @pc.on("track")
    def on_track(track):
        if track.kind != "video":
            return

        async def grab():
            saved, start = 0, time.time()
            try:
                while saved < N_FRAMES:
                    frame = await track.recv()
                    if time.time() - start >= saved * EVERY_S:
                        path = OUT_DIR / f"frame_{int(time.time())}_{saved}.jpg"
                        frame.to_image().save(path, quality=85)
                        print("saved", path)
                        saved += 1
            except Exception:  # Ring closed the stream (~8 s in the sandbox)
                pass
            if not done.done():
                done.set_result(saved)

        asyncio.ensure_future(grab())

    @pc.on("connectionstatechange")
    async def on_state():
        print("connection:", pc.connectionState)
        if pc.connectionState in ("closed", "failed") and not done.done():
            done.set_result(0)

    await pc.setLocalDescription(await pc.createOffer())  # aiortc gathers ICE before returning
    status, headers, body = http(
        "POST", f"{API}/v1/devices/{device_id}/media/streaming/whep/sessions",
        pc.localDescription.sdp.encode(), "application/sdp",
    )
    print("WHEP POST ->", status)
    if status not in (200, 201):
        print(body.decode()[:500])
        await pc.close()
        return
    location = headers.get("Location") or headers.get("location")
    await pc.setRemoteDescription(RTCSessionDescription(body.decode(), "answer"))
    try:
        await asyncio.wait_for(done, N_FRAMES * EVERY_S + 30)
    except asyncio.TimeoutError:
        print("timed out; state:", pc.connectionState)
    finally:
        await pc.close()
        if location:
            url = location if location.startswith("http") else API + location
            print("WHEP DELETE ->", http("DELETE", url)[0])


if __name__ == "__main__":
    asyncio.run(main())
