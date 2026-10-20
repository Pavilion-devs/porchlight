"""Turns a doorbell frame into structured facts with Claude on Amazon Bedrock.

Uses the Converse API with a forced tool call, so the model always returns valid JSON.
"""
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime

import boto3

from .config import settings

ACTIVITIES = [
    "none",                # empty porch, nothing happening
    "delivery",            # courier dropping something off
    "package_pickup",      # someone taking a package away
    "visitor_at_door",     # non-resident at the door
    "resident_leaving",
    "resident_returning",
    "resident_at_door",    # resident on the porch / getting the mail
    "passerby",            # someone on the street, not approaching
    "vehicle",             # vehicle arriving / parked / leaving
    "animal",
    "other",
]

REPORT_TOOL = {
    "toolSpec": {
        "name": "report_observation",
        "description": "Report what is visible in this Ring doorbell frame.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "One plain sentence a family member would understand."},
                "person": {"type": "boolean"},
                "person_desc": {"type": "string", "description": "Clothing, build, items carried, uniform/logo. Empty if no person."},
                "is_resident_likely": {"type": "boolean", "description": "True only if the person matches the resident description."},
                "visitor_signature": {"type": "string", "description": "3-6 lowercase comma-separated traits to recognise this person again, e.g. 'man, grey hoodie, clipboard, no uniform'. Empty if no person or if resident."},
                "package": {"type": "boolean", "description": "A parcel/box/bag is left at the door."},
                "package_desc": {"type": "string"},
                "vehicle": {"type": "boolean"},
                "activity": {"type": "string", "enum": ACTIVITIES},
                "concern": {"type": "string", "description": "Anything a caregiver might want to know about, or empty."},
            },
            "required": ["description", "person", "is_resident_likely", "package", "vehicle", "activity"],
        }},
    }
}

SYSTEM = (
    "You are the eyes of Porchlight, a caregiving assistant that watches the front door of an older adult "
    "who lives alone. Describe only what is visible. Never guess identities beyond the resident description. "
    "Be calm and factual."
)


@dataclass
class Observation:
    time: datetime
    description: str
    person: bool = False
    person_desc: str = ""
    is_resident_likely: bool = False
    visitor_signature: str = ""
    package: bool = False
    package_desc: str = ""
    vehicle: bool = False
    activity: str = "none"
    concern: str = ""
    frame_name: str | None = None
    source: str = "ring_live"  # or "replay"
    extra: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        d = asdict(self)
        d["time"] = self.time.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Observation":
        d = dict(d)
        d["time"] = datetime.fromisoformat(d["time"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class Vision:
    def __init__(self, model_id: str = settings.vision_model, region: str = settings.aws_region):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def _describe_sync(self, jpeg: bytes, resident_description: str) -> dict:
        resp = self.client.converse(
            modelId=self.model_id,
            system=[{"text": SYSTEM}],
            messages=[{"role": "user", "content": [
                {"image": {"format": "jpeg", "source": {"bytes": jpeg}}},
                {"text": f"Resident description: {resident_description}.\nReport this frame."},
            ]}],
            toolConfig={"tools": [REPORT_TOOL], "toolChoice": {"tool": {"name": "report_observation"}}},
            inferenceConfig={"maxTokens": 400, "temperature": 0},
        )
        for block in resp["output"]["message"]["content"]:
            if "toolUse" in block:
                return block["toolUse"]["input"]
        raise RuntimeError("vision model returned no observation")

    async def describe(self, jpeg: bytes, when: datetime, frame_name: str | None = None,
                       resident_description: str = settings.resident_description) -> Observation:
        data = await asyncio.to_thread(self._describe_sync, jpeg, resident_description)
        if data.get("activity") not in ACTIVITIES:
            data["activity"] = "other"
        return Observation(time=when, frame_name=frame_name, source="ring_live",
                           **{k: v for k, v in data.items() if k in Observation.__dataclass_fields__})
