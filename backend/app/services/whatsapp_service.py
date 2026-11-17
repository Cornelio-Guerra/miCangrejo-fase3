"""Canal de WhatsApp con la Cloud API de Meta (canal definido en la Fase 1; FA-1 de CU-01 y RF-08): verificación del webhook,
recepción de mensajes (texto, ubicación, imagen) y respuesta con el folio.
Sin credenciales de Meta, el endpoint sigue funcionando para pruebas con curl
(modo de contingencia); solo no descarga imágenes ni responde al vecino."""

import logging
import re
from collections import OrderedDict
from os import getenv
from threading import Lock

import httpx
from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import get_settings
from app.models import Expediente
from app.schemas.report import ReportCreate, ReportLocation
from app.services import storage_service
from app.services.servicio_expedientes import registrar_reporte, obtener_por_folio

log = logging.getLogger("micangrejo.whatsapp")
GRAPH = f"https://graph.facebook.com/{getenv('META_GRAPH_VERSION', 'v22.0')}"
FOLIO_PATTERN = re.compile(r"\bMC-\d{4}-\d{4,}\b", re.IGNORECASE)
HELP_WORDS = {"ayuda", "menu", "menú", "help", "comandos"}
GREETING_WORDS = {"hola", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches"}
REPORT_WORDS = {"1", "reportar", "reporte", "nuevo reporte"}
STATUS_WORDS = {"2", "estado", "consultar estado", "mis reportes"}
LOCATION_WORDS = {"3", "ubicacion", "ubicación", "enviar ubicacion", "enviar ubicación"}
HELP_TEXT = (
    "¡Hola! Soy miCangrejo 🦀, el asistente comunitario de Vía Argentina.\n\n"
    "¿Qué deseas hacer?\n"
    "1️⃣ Reportar un problema\n"
    "2️⃣ Consultar el estado de un folio\n"
    "3️⃣ Enviar tu ubicación\n\n"
    "También puedes escribir directamente lo que sucede, enviar una foto con descripción o consultar: "
    "estado MC-AAAA-NNNN."
)
REPORT_PROMPT = (
    "Cuéntame qué sucede y dónde ocurre. Por ejemplo: “Hay basura acumulada frente al edificio X”. "
    "También puedes adjuntar una foto o compartir tu ubicación."
)
STATUS_PROMPT = "Escribe: estado MC-AAAA-NNNN. Encontrarás el folio en la confirmación de tu reporte."
LOCATION_PROMPT = "Comparte tu ubicación desde el botón 📎 → Ubicación. La usaremos como referencia para tu reporte."
MAX_RECENT_MESSAGE_IDS = 1_000
_recent_message_ids: OrderedDict[str, None] = OrderedDict()
_recent_message_lock = Lock()


def verify(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    settings = get_settings()
    if mode == "subscribe" and settings.meta_verify_token and token == settings.meta_verify_token:
        return challenge
    return None


def _fetch_media(media_id: str) -> tuple[bytes, str] | None:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return None
    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
    try:
        with httpx.Client(timeout=15) as client:
            meta = client.get(f"{GRAPH}/{media_id}", headers=headers).raise_for_status().json()
            data = client.get(meta["url"], headers=headers).raise_for_status()
            return data.content, meta.get("mime_type", "image/jpeg")
    except Exception as exc:
        log.warning("no se pudo descargar la imagen %s: %s", media_id, exc)
        return None


def _store_photo(media_id: str) -> str | None:
    media = _fetch_media(media_id)
    if not media or not get_settings().storage_enabled:
        return None
    data, mime = media
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        return None
    path = storage_service.safe_object_path(f"whatsapp-{media_id}", mime)
    try:
        storage_service._bucket().upload(path, data, {"content-type": mime})
        return path
    except Exception as exc:
        log.warning("no se pudo guardar la imagen en Storage: %s", exc)
        return None


def reply(to: str, text: str) -> None:
    settings = get_settings()
    if not settings.whatsapp_enabled:
        return
    try:
        response = httpx.post(
            f"{GRAPH}/{settings.meta_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.meta_access_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            error = exc.response.json().get("error", {})
            detail = f"Meta {error.get('code')}: {error.get('message', 'sin detalle')}"
        except ValueError:
            detail = f"HTTP {exc.response.status_code}"
        log.warning("no se pudo responder por WhatsApp a %s: %s", to, detail)
    except Exception as exc:
        log.warning("no se pudo responder por WhatsApp a %s: %s", to, exc)


def handle_webhook(session: Session, payload: dict) -> list[str]:
    """Convierte cada mensaje entrante en un expediente. Devuelve los folios creados."""
    folios: list[str] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if not _claim_message_id(msg.get("id")):
                    continue
                folio = _handle_message(session, msg)
                if folio:
                    folios.append(folio)
    return folios


def process_webhook(session: Session, payload: dict) -> None:
    """Procesa fuera de la respuesta HTTP para que Meta reciba 200 de inmediato."""
    try:
        handle_webhook(session, payload)
    except Exception as exc:
        log.exception("error procesando webhook: %s", exc)


def _claim_message_id(message_id: str | None) -> bool:
    """Evita que los reintentos de Meta creen o respondan el mismo reporte dos veces."""
    if not message_id:
        return True
    with _recent_message_lock:
        if message_id in _recent_message_ids:
            return False
        _recent_message_ids[message_id] = None
        if len(_recent_message_ids) > MAX_RECENT_MESSAGE_IDS:
            _recent_message_ids.popitem(last=False)
        return True


def _handle_message(session: Session, msg: dict) -> str | None:
    sender = msg.get("from")
    kind = msg.get("type")
    text = ""
    location = ReportLocation(label="Ubicación pendiente (WhatsApp)")
    photo_path = None

    if kind == "text":
        text = msg.get("text", {}).get("body", "")
        command_result = _handle_text_command(session, sender, text)
        if command_result is not None:
            return command_result
    elif kind == "image":
        text = msg.get("image", {}).get("caption", "")
        photo_path = _store_photo(msg["image"]["id"]) if msg.get("image", {}).get("id") else None
    elif kind == "location":
        loc = msg.get("location", {})
        location = ReportLocation(
            label=(loc.get("name") or loc.get("address") or "Ubicación enviada por WhatsApp")[:160],
            latitude=loc.get("latitude"), longitude=loc.get("longitude"),
        )
        text = f"Reporte por WhatsApp: {loc.get('name') or loc.get('address') or 'ubicación compartida'}"
    else:
        return None

    description = text.strip() or "Reporte recibido por WhatsApp sin descripción"
    if len(description) < 10:
        description = f"Reporte por WhatsApp: {description}"
    payload = ReportCreate(description=description[:500], location=location, photo_path=photo_path)
    case: Expediente = registrar_reporte(session, payload, source="whatsapp", reporter_contact=sender)
    if sender:
        reply(sender, f"✅ Reporte recibido por miCangrejo.\n\nFolio: {case.folio}\n"
                      "El equipo comunitario lo revisará. Puedes consultar avances con: "
                      f"estado {case.folio}")
    return case.folio


def _handle_text_command(session: Session, sender: str | None, text: str) -> str | None:
    """Atiende ayuda y consulta de folio; devuelve '' cuando ya respondió al vecino."""
    normalized = " ".join(text.lower().split())
    if not normalized or normalized in HELP_WORDS or normalized in GREETING_WORDS:
        if sender:
            reply(sender, HELP_TEXT)
        return ""

    if normalized in REPORT_WORDS:
        if sender:
            reply(sender, REPORT_PROMPT)
        return ""

    if normalized in STATUS_WORDS:
        if sender:
            reply(sender, STATUS_PROMPT)
        return ""

    if normalized in LOCATION_WORDS:
        if sender:
            reply(sender, LOCATION_PROMPT)
        return ""

    match = FOLIO_PATTERN.search(text)
    if not match:
        return None

    folio = match.group(0).upper()
    try:
        case = obtener_por_folio(session, folio)
    except HTTPException:
        if sender:
            reply(sender, f"miCangrejo: no encontramos el folio {folio}. Revisa el código e inténtalo otra vez.")
        return ""

    if sender:
        reply(sender, f"miCangrejo: el folio {case.folio} está en estado: {case.status}.")
    return ""
