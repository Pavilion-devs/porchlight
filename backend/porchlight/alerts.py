"""Sends alerts to the family's phone via a Telegram bot (or logs them when no bot is configured)."""
import logging
from pathlib import Path

import httpx

from .config import settings

log = logging.getLogger("porchlight.alerts")


class Notifier:
    def __init__(self, bot_token: str = settings.telegram_bot_token, chat_id: str = settings.telegram_chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def channel(self) -> str:
        return "Telegram" if self.bot_token and self.chat_id else "log only"

    async def send(self, text: str, photo: Path | None = None) -> bool:
        if not (self.bot_token and self.chat_id):
            log.info("ALERT (no Telegram configured): %s", text)
            return False
        base = f"https://api.telegram.org/bot{self.bot_token}"
        try:
            async with httpx.AsyncClient(timeout=20) as http:
                if photo and photo.exists():
                    r = await http.post(f"{base}/sendPhoto", data={"chat_id": self.chat_id, "caption": text[:1024]},
                                        files={"photo": (photo.name, photo.read_bytes(), "image/jpeg")})
                else:
                    r = await http.post(f"{base}/sendMessage", data={"chat_id": self.chat_id, "text": text})
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("Telegram send failed: %r", e)
            return False
