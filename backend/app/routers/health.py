from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Estado del servicio y modo de cada integración")
def health_check() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "service": "micangrejo-api",
        "database": "postgres" if s.uses_postgres else "sqlite (contingencia)",
        "ia": f"gemini:{s.gemini_model}" if s.gemini_enabled else "reglas (contingencia)",
        "email": "smtp" if s.smtp_enabled else "simulado (contingencia)",
        "storage": "supabase" if s.storage_enabled else "desactivado (fotos opcionales)",
        "whatsapp": "meta" if s.whatsapp_enabled else "solo webhook local",
        "telegram": (
            "bot + webhook configurado" if s.telegram_webhook_enabled and s.telegram_webhook_url
            else "bot (webhook pendiente)" if s.telegram_enabled
            else "desactivado"
        ),
        "sla_dias": s.sla_dias,
    }
