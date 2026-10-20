"""Ring webhook signing/verification (HMAC-SHA256, hex, 'sha256=' prefix) and payload building.

Real Ring webhooks and our replayer's synthetic ones go through the same verify + parse path.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone


def sign(raw_body: bytes, key: str) -> str:
    return "sha256=" + hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()


def verify(raw_body: bytes, signature: str, key: str) -> bool:
    """Verify against the raw bytes as received: never re-serialised JSON."""
    if not key or not signature:
        return False
    return hmac.compare_digest(sign(raw_body, key), signature)


def build_payload(event_type: str, device_id: str, when: datetime, sub_type: str | None = None,
                  account_id: str = "ava1.ring.account.porchlight-replay") -> dict:
    """A Ring v1.1 webhook payload (motion_detected / button_press), as documented by Ring."""
    ts = int(when.timestamp() * 1000)
    attributes = {"source": device_id, "source_type": "devices", "timestamp": ts}
    if event_type == "motion_detected":
        attributes["sub_type"] = sub_type or "motion"
        attributes["timestamp_readable"] = when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "meta": {"version": "1.1", "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                 "request_id": str(uuid.uuid4()), "account_id": account_id},
        "data": {"id": f"{device_id}_{sub_type or event_type}_{ts}", "type": event_type, "attributes": attributes,
                 "relationships": {"devices": {"links": {"self": f"/v1/devices/{device_id}"}}}},
    }


def parse(raw_body: bytes) -> dict:
    """Flatten the fields we use: type, sub_type, device_id, time, request_id."""
    payload = json.loads(raw_body)
    data, attrs = payload["data"], payload["data"].get("attributes", {})
    ts = attrs.get("timestamp")
    return {
        "type": data["type"],
        "sub_type": attrs.get("sub_type"),
        "device_id": attrs.get("source"),
        "time": datetime.fromtimestamp(ts / 1000, timezone.utc) if ts else datetime.now(timezone.utc),
        "request_id": payload.get("meta", {}).get("request_id"),
    }
