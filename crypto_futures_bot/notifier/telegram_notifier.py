"""
telegram_notifier.py — Telegram bildirimi (İSKELET).

telegram_enabled=False (varsayılan) iken tüm çağrılar no-op'tur; bot Telegram
olmadan da sorunsuz çalışır. Enabled + token/chat_id varsa sendMessage ile
mesaj gönderir.

PC'de yapılacak: zengin formatlama (HTML/markdown), sinyal kartları, hata
uyarıları, /status komutu vb.
"""

from __future__ import annotations

import requests

from config import CONFIG, SECRETS


class TelegramNotifier:
    def __init__(self, logger):
        self.log = logger
        self.enabled = (
            CONFIG.telegram_enabled
            and bool(SECRETS.telegram_bot_token)
            and bool(SECRETS.telegram_chat_id)
        )
        if CONFIG.telegram_enabled and not self.enabled:
            self.log.warning("Telegram etkin ama token/chat_id eksik → bildirimler kapalı")

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{SECRETS.telegram_bot_token}/sendMessage"
        try:
            requests.post(
                url,
                json={"chat_id": SECRETS.telegram_chat_id, "text": text},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 — bildirim hatası botu durdurmaz
            self.log.warning(f"Telegram gönderilemedi: {exc}")
