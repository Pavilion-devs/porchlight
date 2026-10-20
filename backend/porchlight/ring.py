"""Thin async client for the Ring Partner API (api.amazonvision.com)."""
import base64
import json
import time

import httpx

from .config import ring_token, settings


class RingAuthError(Exception):
    """The OAuth token is missing or expired (Playground tokens last 30 minutes)."""


def token_expires_in_s(token: str | None = None) -> int | None:
    token = token if token is not None else ring_token()
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload))["exp"] - time.time())
    except Exception:
        return None


class RingClient:
    def __init__(self, base_url: str = settings.ring_api):
        self.base_url = base_url
        self.http = httpx.AsyncClient(base_url=base_url, timeout=20)

    def _headers(self, content_type: str | None = None) -> dict:
        token = ring_token()
        if not token:
            raise RingAuthError("OAUTH_TOKEN is not set in .env")
        headers = {"Authorization": f"Bearer {token}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _check(self, r: httpx.Response) -> httpx.Response:
        if r.status_code == 401:
            raise RingAuthError("Ring returned 401: generate a new Playground token and update .env")
        r.raise_for_status()
        return r

    async def devices(self) -> list[dict]:
        r = self._check(await self.http.get("/v1/devices", headers=self._headers()))
        return r.json()["data"]

    async def first_device_id(self) -> str:
        devices = await self.devices()
        if not devices:
            raise RuntimeError("No Ring devices on this account")
        return devices[0]["id"]

    async def history(self, device_id: str, event_types: str | None = None) -> list[dict]:
        params = {"event_types": event_types} if event_types else None
        r = self._check(await self.http.get(f"/v1/history/devices/{device_id}/events",
                                            headers=self._headers(), params=params))
        return r.json()["data"]

    async def whep_open(self, device_id: str, offer_sdp: str) -> tuple[str, str | None]:
        """Start a live-view session. Returns (answer SDP, session URL for DELETE)."""
        r = self._check(await self.http.post(
            f"/v1/devices/{device_id}/media/streaming/whep/sessions",
            headers=self._headers("application/sdp"), content=offer_sdp.encode(),
        ))
        location = r.headers.get("location")
        if location and not location.startswith("http"):
            location = self.base_url + location
        return r.text, location

    async def whep_close(self, session_url: str) -> None:
        try:
            await self.http.delete(session_url, headers=self._headers())
        except Exception:
            pass  # best effort: Ring also expires sessions on its own

    async def aclose(self) -> None:
        await self.http.aclose()
