"""Spike: describe a Ring frame with Claude on Amazon Bedrock.

Proven on Oct 20, 2026 with us.anthropic.claude-sonnet-4-6 (~2.5 s, ~1.4k tokens).

Usage:
    python spikes/bedrock_vision.py frames/frame_xxx.jpg [MODEL_ID]

Uses your default AWS credentials (aws configure), region us-east-1.
Models enabled on our account: claude-sonnet-4-6, claude-haiku-4-5-20251001-v1:0,
claude-opus-4-5-20251101-v1:0 (all with the "us." inference-profile prefix).
"""
import sys

import boto3

image_path = sys.argv[1]
model_id = sys.argv[2] if len(sys.argv) > 2 else "us.anthropic.claude-haiku-4-5-20251001-v1:0"

client = boto3.client("bedrock-runtime", region_name="us-east-1")
resp = client.converse(
    modelId=model_id,
    messages=[{
        "role": "user",
        "content": [
            {"image": {"format": "jpeg", "source": {"bytes": open(image_path, "rb").read()}}},
            {"text": "This is a frame from a Ring doorbell camera. In 2 sentences: what is in view, "
                     "and is there anything a family caregiver should be alerted about?"},
        ],
    }],
    inferenceConfig={"maxTokens": 300},
)
print(resp["output"]["message"]["content"][0]["text"])
print("usage:", resp["usage"], "latency ms:", resp["metrics"]["latencyMs"])
