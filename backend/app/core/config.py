"""Configuración de la API leída de variables de entorno.

Todo tiene un valor por defecto que permite levantar el backend SIN credenciales
(modo de contingencia): SQLite local, clasificación por reglas, correo simulado y
fotos opcionales. Con las variables reales, cada pieza pasa a modo real.
"""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    # CORS (solo aplica en desarrollo local; en Vercel con Services es el mismo dominio)
    frontend_origins: tuple[str, ...]

    # Base de datos: Postgres (Supabase, pooler modo transacción) o SQLite local
    database_url: str

    # IA
    gemini_api_key: str | None
    gemini_model: str
    gemini_timeout_s: float
    gemini_fallback_models: tuple[str, ...]  # se prueban en orden si el principal falla (timeout, 503, 429)
    gemini_thinking_budget: int | None  # 0 = sin razonamiento (rápido); None = lo decide el modelo

    # Correo
    smtp_host: str
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    mail_from: str | None
    mail_timeout_s: float
    mail_demo_override_to: str | None  # si está definido, TODO correo va a este buzón

    # Fotos (Supabase Storage)
    supabase_url: str | None
    supabase_service_role_key: str | None
    supabase_bucket: str
    max_photo_bytes: int

    # WhatsApp (Meta Cloud API)
    meta_verify_token: str | None
    meta_access_token: str | None
    meta_phone_number_id: str | None

    # Telegram Bot API
    telegram_bot_token: str | None
    telegram_webhook_secret: str | None
    telegram_webhook_url: str | None

    # Reglas de negocio
    sla_dias: int
    public_base_url: str | None

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    @property
    def storage_enabled(self) -> bool:
        """Solo con una clave de servidor. La publishable/anon es pública y no puede firmar subidas."""
        key = self.supabase_service_role_key or ""
        if not (self.supabase_url and key):
            return False
        return not key.startswith(("sb_publishable_", "sbp_"))

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.meta_access_token and self.meta_phone_number_id)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def telegram_webhook_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_webhook_secret)

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


def _thinking_budget(value: str | None) -> int | None:
    """GEMINI_THINKING_BUDGET: vacío → 0 (sin razonamiento, responde en segundos); 'auto' → lo decide el modelo."""
    if not value:
        return 0
    return None if value.strip().lower() == "auto" else int(value)


@lru_cache
def get_settings() -> Settings:
    default_sqlite = f"sqlite:///{BACKEND_DIR / 'data' / 'micangrejo.db'}"
    return Settings(
        frontend_origins=_split_csv(
            getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        ),
        database_url=getenv("DATABASE_URL") or default_sqlite,
        gemini_api_key=getenv("GEMINI_API_KEY") or None,
        gemini_model=getenv("GEMINI_MODEL") or "gemini-3.8-flash",
        gemini_timeout_s=float(getenv("GEMINI_TIMEOUT_S") or "20"),
        # El nivel gratuito limita a 20 peticiones por día y POR MODELO: varias reservas alargan la demo.
        gemini_fallback_models=_split_csv(
            getenv("GEMINI_FALLBACK_MODELS") or getenv("GEMINI_FALLBACK_MODEL")
            or "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.7-flash"
        ),
        gemini_thinking_budget=_thinking_budget(getenv("GEMINI_THINKING_BUDGET")),
        smtp_host=getenv("SMTP_HOST") or "smtp.gmail.com",
        smtp_port=int(getenv("SMTP_PORT") or "587"),
        smtp_user=getenv("SMTP_USER") or None,
        smtp_password=getenv("SMTP_PASSWORD") or None,
        mail_from=getenv("MAIL_FROM") or getenv("SMTP_USER") or None,
        mail_timeout_s=float(getenv("MAIL_TIMEOUT_S") or "15"),
        mail_demo_override_to=getenv("MAIL_DEMO_OVERRIDE_TO") or None,
        supabase_url=getenv("SUPABASE_URL") or None,
        supabase_service_role_key=getenv("SUPABASE_SERVICE_ROLE_KEY") or None,
        supabase_bucket=getenv("SUPABASE_BUCKET") or "evidencias",
        max_photo_bytes=int(getenv("MAX_PHOTO_BYTES") or 5 * 1024 * 1024),
        meta_verify_token=getenv("META_VERIFY_TOKEN") or None,
        meta_access_token=getenv("META_ACCESS_TOKEN") or None,
        meta_phone_number_id=getenv("META_PHONE_NUMBER_ID") or None,
        telegram_bot_token=getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_webhook_secret=getenv("TELEGRAM_WEBHOOK_SECRET") or None,
        telegram_webhook_url=getenv("TELEGRAM_WEBHOOK_URL") or None,
        sla_dias=int(getenv("SLA_DIAS") or "5"),
        public_base_url=getenv("PUBLIC_BASE_URL") or None,
    )
