from hmac import compare_digest

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from app.core.config import get_settings
from app.database import get_session
from app.services import telegram_service
from app.services import whatsapp_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp", response_class=PlainTextResponse, summary="Verificación del webhook de Meta")
def verify_whatsapp(hub_mode: str | None = Query(None, alias="hub.mode"),
                    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
                    hub_challenge: str | None = Query(None, alias="hub.challenge")) -> str:
    challenge = whatsapp_service.verify(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token de verificación inválido")
    return challenge


@router.post("/whatsapp", summary="Recepción de mensajes (texto, ubicación, imagen)")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks,
                           session: Session = Depends(get_session)) -> dict:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    # Meta reintenta si no recibe 200 rápidamente. Confirmamos primero y procesamos
    # después con una sesión propia para que Gemini, Storage o fotos no bloqueen la entrega.
    background_tasks.add_task(whatsapp_service.process_webhook, session, payload if isinstance(payload, dict) else {})
    return {"received": True, "folios": []}


@router.post("/telegram", summary="Recepcion de mensajes de Telegram")
async def receive_telegram(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    if not settings.telegram_webhook_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Telegram no esta configurado: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_WEBHOOK_SECRET")
    if not compare_digest(x_telegram_bot_api_secret_token or "", settings.telegram_webhook_secret or ""):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Secreto de webhook de Telegram invalido")
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    background_tasks.add_task(telegram_service.process_update, session,
                              payload if isinstance(payload, dict) else {})
    return {"received": True}
