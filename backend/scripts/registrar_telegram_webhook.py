"""Registra en Telegram la URL pública del webhook configurada en .env.

Uso desde backend/:
    python scripts/registrar_telegram_webhook.py
"""

import sys
from pathlib import Path

import httpx

# Permite ejecutar el archivo directamente desde backend/scripts/.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    missing = [
        name for name, value in (
            ("TELEGRAM_BOT_TOKEN", settings.telegram_bot_token),
            ("TELEGRAM_WEBHOOK_SECRET", settings.telegram_webhook_secret),
            ("TELEGRAM_WEBHOOK_URL", settings.telegram_webhook_url),
        ) if not value
    ]
    if missing:
        print("Faltan variables en backend/.env: " + ", ".join(missing))
        return 2

    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
    try:
        response = httpx.post(
            endpoint,
            json={"url": settings.telegram_webhook_url, "secret_token": settings.telegram_webhook_secret},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"No se pudo registrar el webhook: {exc}")
        return 1

    if not data.get("ok"):
        print("Telegram rechazo el registro:", data.get("description", "sin detalle"))
        return 1
    print("Webhook de Telegram registrado correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
