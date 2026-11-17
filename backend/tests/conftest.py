"""Arranque de las pruebas.

La configuración (`app.core.config.get_settings`) usa `lru_cache` y el motor de base
de datos se construye al importar `app.database`, así que las variables de entorno
se fijan AQUÍ, antes de importar cualquier módulo de `app`. Todas las integraciones
quedan apagadas para que la suite corra en modo de contingencia sin credenciales.

Cada test recibe una base SQLite nueva (archivo distinto en `tmp_path`): se sustituye
`app.database.engine` y el lifespan de la app crea las tablas y siembra el catálogo.
"""

import os
import tempfile

# --- 1. Entorno de contingencia, antes de importar `app` --------------------------
_BOOT_DIR = tempfile.mkdtemp(prefix="micangrejo-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_BOOT_DIR}/boot.db"
os.environ["META_VERIFY_TOKEN"] = "prueba"
os.environ["SLA_DIAS"] = "5"
for _var in (
    "GEMINI_API_KEY", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_DEMO_OVERRIDE_TO",
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID",
    "PUBLIC_BASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "TELEGRAM_WEBHOOK_URL",
):
    os.environ[_var] = ""          # `getenv(...) or None` → None; load_dotenv no lo pisa

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import create_engine  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Cliente HTTP con lifespan activo sobre una base SQLite limpia por test."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
