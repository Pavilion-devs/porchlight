"""Check that everything Porchlight needs is set up, and say how to fix whatever isn't.

Run:  make check      (or: .venv/bin/python scripts/doctor.py)
Never prints secret values, only whether they're present.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import boto3  # noqa: E402
import httpx  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from porchlight.config import ring_token, settings  # noqa: E402
from porchlight.ring import token_expires_in_s  # noqa: E402

problems = 0


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def warn(msg: str, fix: str) -> None:
    print(f"  ⚠️  {msg}\n      → {fix}")


def bad(msg: str, fix: str) -> None:
    global problems
    problems += 1
    print(f"  ❌ {msg}\n      → {fix}")


def check_env() -> None:
    print("\n.env")
    env = ROOT / ".env"
    if not env.exists():
        bad(".env is missing", "run `make setup` (copies .env.example), then fill it in")
        return
    values = dotenv_values(env)
    for key, where in [("HMAC_SIGNATURE_KEY", "Ring Developer Console → your app"),
                       ("OAUTH_TOKEN", "Ring Developer Console → Playground → Generate token")]:
        if values.get(key):
            ok(f"{key} is set")
        else:
            bad(f"{key} is empty", f"set it in .env ({where})")


def check_ring() -> None:
    print("\nRing sandbox")
    left = token_expires_in_s()
    if left is None:
        bad("No readable Ring token", "paste a Playground token into OAUTH_TOKEN in .env")
        return
    if left <= 0:
        bad("Ring token has expired", "generate a new one in the Playground and paste it into .env (no restart needed)")
        return
    try:
        r = httpx.get(f"{settings.ring_api}/v1/devices", timeout=20,
                      headers={"Authorization": f"Bearer {ring_token()}"})
        r.raise_for_status()
        n = len(r.json().get("data", []))
        ok(f"Ring API reachable, {n} device(s); token valid for {left // 60} more min")
    except Exception as e:
        bad(f"Ring API call failed ({e.__class__.__name__})", "check the token and your internet connection")


def check_aws() -> None:
    print("\nAmazon Bedrock")
    try:
        ident = boto3.client("sts", region_name=settings.aws_region).get_caller_identity()
        if ident["Arn"].endswith(":root"):
            warn("Signed in to AWS as the root user", "works, but an IAM user with Bedrock access is safer")
        else:
            ok("AWS credentials found")
    except Exception as e:
        bad(f"No usable AWS credentials ({e.__class__.__name__})", "run `aws login` or `aws configure`")
        return
    rt = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    for label, model in [("vision", settings.vision_model), ("agent", settings.agent_model)]:
        try:
            rt.converse(modelId=model, messages=[{"role": "user", "content": [{"text": "Say ok"}]}],
                        inferenceConfig={"maxTokens": 5})
            ok(f"{label} model works: {model}")
        except Exception as e:
            bad(f"{label} model {model} failed: {str(e)[:120]}",
                f"enable it in the Bedrock console ({settings.aws_region}) or set "
                f"{label.upper()}_MODEL in .env to a model you can use")


def check_telegram() -> None:
    print("\nFamily alerts")
    if not settings.telegram_bot_token:
        warn("Telegram not set up: alerts will only be printed in the server log",
             "optional. See `make telegram`")
    elif not settings.telegram_chat_id:
        warn("TELEGRAM_BOT_TOKEN is set but TELEGRAM_CHAT_ID isn't", "message your bot, then run `make telegram`")
    else:
        r = httpx.get(f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe", timeout=20)
        if r.is_success:
            ok(f"Telegram bot @{r.json()['result']['username']} ready")
        else:
            bad("Telegram rejected the bot token", "copy it again from @BotFather")


if __name__ == "__main__":
    print("Porchlight setup check")
    check_env()
    check_ring()
    check_aws()
    check_telegram()
    print("\n" + ("All good. Start it with `make run`." if not problems
                  else f"{problems} thing(s) to fix. Replay demos still work offline: `make run-offline`."))
    sys.exit(1 if problems else 0)
