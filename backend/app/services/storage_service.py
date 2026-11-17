"""Fotos en Supabase Storage con URL firmada (Fase 2, vista física: carpeta de evidencias).

El backend NUNCA recibe los bytes de la imagen (Vercel limita el cuerpo a 4,5 MB):
emite una URL firmada, el navegador hace PUT directo al bucket y luego manda
`photo_path` en el POST /reports.
"""

import re
import uuid
from functools import lru_cache

from app.core.config import get_settings

_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
SIGNED_UPLOAD_TTL_S = 2 * 60 * 60   # Supabase: las URL de subida valen 2 horas
SIGNED_READ_TTL_S = 60 * 60


class StorageNotConfigured(RuntimeError):
    pass


@lru_cache
def _client():
    from supabase import create_client

    settings = get_settings()
    if not settings.storage_enabled:
        raise StorageNotConfigured("Supabase Storage no está configurado")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _bucket():
    return _client().storage.from_(get_settings().supabase_bucket)


def safe_object_path(filename: str, content_type: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", filename.rsplit(".", 1)[0])[:40].strip("-") or "foto"
    return f"casos/{uuid.uuid4().hex}-{stem}.{_EXT[content_type]}"


def create_signed_upload(filename: str, content_type: str, size: int) -> dict:
    settings = get_settings()
    if content_type not in _EXT:
        raise ValueError("Formato no permitido: usa JPG, PNG o WEBP")
    if size > settings.max_photo_bytes:
        raise ValueError(f"La imagen supera el máximo de {settings.max_photo_bytes // (1024 * 1024)} MB")
    path = safe_object_path(filename, content_type)
    signed = _bucket().create_signed_upload_url(path)
    return {
        "path": path,
        "upload_url": signed["signed_url"],
        "method": "PUT",
        "headers": {"Content-Type": content_type, "x-upsert": "false"},
        "expires_in_s": SIGNED_UPLOAD_TTL_S,
        "public_url": read_url(path),
    }


def read_url(path: str | None) -> str | None:
    """URL para ver la foto. Bucket público → URL pública; si no, firmada por 1 h."""
    if not path:
        return None
    settings = get_settings()
    if not settings.storage_enabled:
        return None
    try:
        return _bucket().get_public_url(path)
    except Exception:
        try:
            return _bucket().create_signed_url(path, SIGNED_READ_TTL_S)["signedURL"]
        except Exception:
            return None


def download(path: str) -> tuple[bytes, str] | None:
    """Bytes y mime de la foto para mandarla a la IA. None si no se puede."""
    if not path or not get_settings().storage_enabled:
        return None
    try:
        data = _bucket().download(path)
    except Exception:
        return None
    ext = path.rsplit(".", 1)[-1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext)
    return (data, mime) if mime else None
