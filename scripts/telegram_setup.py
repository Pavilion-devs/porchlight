"""Connect Porchlight's family alerts to Telegram.

1. In Telegram, message @BotFather, send /newbot, and copy the token it gives you.
2. Put it in .env as TELEGRAM_BOT_TOKEN=...
3. Send your new bot any message (e.g. "hi"), so it knows which chat to talk to.
4. Run:  make telegram      (or: .venv/bin/python scripts/telegram_setup.py)

This finds your chat ID, saves it to .env as TELEGRAM_CHAT_ID and sends a test message.
Restart the backend afterwards so it picks up the new settings.
"""
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ENV = Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    if not ENV.exists():
        print("No .env yet. Run `make setup` first.")
        return 1
    token = (dotenv_values(ENV).get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN is empty in .env. Create a bot with @BotFather (/newbot) and paste its token.")
        return 1
    api = f"https://api.telegram.org/bot{token}"
    with httpx.Client(timeout=20) as http:
        me = http.get(f"{api}/getMe").json()
        if not me.get("ok"):
            print("Telegram rejected the bot token. Copy it again from @BotFather.")
            return 1
        bot = me["result"]["username"]
        updates = http.get(f"{api}/getUpdates").json().get("result", [])
        chats = [u[k]["chat"] for u in updates for k in ("message", "my_chat_member") if k in u]
        if not chats:
            print(f"Found your bot @{bot}, but nobody has messaged it yet.\n"
                  f"Open https://t.me/{bot}, press Start (or send 'hi'), then run this again.")
            return 1
        chat = chats[-1]
        set_key(ENV, "TELEGRAM_CHAT_ID", str(chat["id"]), quote_mode="never")
        who = chat.get("first_name") or chat.get("title") or chat["id"]
        r = http.post(f"{api}/sendMessage", data={
            "chat_id": chat["id"],
            "text": "👋 Porchlight is connected. Family alerts from the front door will arrive here."})
        print(f"Saved TELEGRAM_CHAT_ID for {who} (bot @{bot}).")
        print("Test message sent ✅" if r.is_success else f"Test message failed: {r.text}")
        print("Restart the backend (make run) to start sending alerts here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
