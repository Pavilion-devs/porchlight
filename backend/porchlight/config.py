"""Settings, read from the repo-root .env (see .env.example)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # Ring
    hmac_key: str = os.getenv("HMAC_SIGNATURE_KEY", "")
    ring_api: str = os.getenv("RING_API", "https://api.amazonvision.com")
    watcher_enabled: bool = _bool("WATCHER_ENABLED", True)
    sample_every_s: float = float(os.getenv("SAMPLE_EVERY_S", "3"))

    # AWS Bedrock (models enabled on our account, see docs/plan.md §2)
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    vision_model: str = os.getenv("VISION_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    agent_model: str = os.getenv("AGENT_MODEL", "us.anthropic.claude-sonnet-4-6")
    use_agent: bool = _bool("USE_AGENT", True)

    # Alerts
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # The household
    parent_name: str = os.getenv("PARENT_NAME", "Mom")
    family_name: str = os.getenv("FAMILY_NAME", "Ade")
    resident_description: str = os.getenv(
        "RESIDENT_DESCRIPTION", "an older woman in her late 70s with short grey hair"
    )
    timezone: str = os.getenv("TIMEZONE", "America/Los_Angeles")

    # Thresholds (shorten PACKAGE_ALERT_MINUTES for live demos)
    package_alert_minutes: float = float(os.getenv("PACKAGE_ALERT_MINUTES", "180"))
    routine_grace_minutes: float = float(os.getenv("ROUTINE_GRACE_MINUTES", "45"))
    night_start_hour: int = int(os.getenv("NIGHT_START_HOUR", "1"))
    night_end_hour: int = int(os.getenv("NIGHT_END_HOUR", "5"))
    summary_hour: int = int(os.getenv("SUMMARY_HOUR", "20"))

    # Ask Porchlight MCP server (/mcp): optional shared secret, sent as "Authorization: Bearer <token>"
    mcp_token: str = os.getenv("MCP_TOKEN", "")

    # Storage
    data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT / "backend" / "data")))

    @property
    def frames_dir(self) -> Path:
        return self.data_dir / "frames"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "porchlight.sqlite"


def ring_token() -> str:
    """Re-read the token from .env on every call, so a fresh Playground token works without a restart."""
    return (dotenv_values(ENV_PATH).get("OAUTH_TOKEN") or os.getenv("OAUTH_TOKEN") or "").strip()


settings = Settings()
