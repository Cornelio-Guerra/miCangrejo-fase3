"""Canal conversacional de Telegram para crear y consultar reportes."""

import logging
import re
from collections import OrderedDict
from pathlib import PurePosixPath
from threading import Lock

import httpx
from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import get_settings
from app.models import Expediente, BorradorTelegram
from app.schemas.report import ReportCreate, ReportLocation
from app.services import storage_service
from app.services.servicio_expedientes import registrar_reporte, obtener_por_folio

log = logging.getLogger("micangrejo.telegram")
FOLIO_PATTERN = re.compile(r"\bMC-\d{4}-\d{4,}\b", re.IGNORECASE)
MAX_RECENT_UPDATE_IDS = 1_000
_recent_update_ids: OrderedDict[str, None] = OrderedDict()
_recent_update_lock = Lock()

HELP_WORDS = {"/start", "/help", "ayuda", "menu", "menú", "help", "comandos", "hola"}
REPORT_WORDS = {"1", "/reporte", "/reportar", "reportar", "reporte", "nuevo reporte"}
STATUS_WORDS = {"2", "/estado", "estado", "consultar estado", "mis reportes"}
LOCATION_WORDS = {"3", "/ubicacion", "/ubicación", "ubicacion", "ubicación", "enviar ubicacion", "enviar ubicación"}
OMIT_WORDS = {"omitir", "/omitir", "sin foto", "no tengo foto", "no tengo"}

HELP_TEXT = (
    "Hola. Soy miCangrejo.\n\n"
    "Que deseas hacer?\n"
    "1. Reportar un problema\n"
    "2. Consultar el estado de un folio\n"
    "3. Enviar tu ubicacion\n\n"
    "Para reportar, te pedire descripcion, ubicacion y una foto opcional."
)
REPORT_PROMPT = "Escribe una descripcion del problema con detalle (que ocurre y alguna referencia del lugar)."
LOCATION_PROMPT = "Ahora comparte tu ubicacion usando el clip de Telegram. Es necesaria para completar el reporte."
PHOTO_PROMPT = "Ubicacion recibida. Envia una foto opcional o escribe 'omitir' para continuar sin foto."
STATUS_PROMPT = "Escribe: estado MC-AAAA-NNNN. Encontraras el folio en la confirmacion de tu reporte."
DESCRIPTION_ERROR = "Respuesta no valida. Envia una descripcion escrita de al menos 10 caracteres y maximo 500."
LOCATION_ERROR = "Respuesta no valida. Comparte una ubicacion de Telegram con latitud y longitud; no puedes omitirla."
PHOTO_ERROR = "Respuesta no valida. Envia una foto o escribe exactamente 'omitir' para continuar sin foto."
UNKNOWN_COMMAND = "No reconoci ese comando. Escribe /start para ver las opciones o /reporte para comenzar."


def _api_url(method: str) -> str | None:
    token = get_settings().telegram_bot_token
    return f"https://api.telegram.org/bot{token}/{method}" if token else None


def send_message(chat_id: str | int, text: str) -> bool:
    """Envía un mensaje al chat; devuelve False si Telegram no está disponible."""
    url = _api_url("sendMessage")
    if not url:
        return False
    try:
        response = httpx.post(url, json={"chat_id": chat_id, "text": text[:4096]}, timeout=10)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:
        log.warning("Telegram rechazo el mensaje para %s: HTTP %s", chat_id, exc.response.status_code)
    except Exception as exc:
        log.warning("No se pudo responder por Telegram a %s: %s", chat_id, exc)
    return False


def _claim_update_id(update_id: object) -> bool:
    """Evita crear dos reportes si Telegram reintenta el mismo update."""
    if update_id is None:
        return True
    key = str(update_id)
    with _recent_update_lock:
        if key in _recent_update_ids:
            return False
        _recent_update_ids[key] = None
        if len(_recent_update_ids) > MAX_RECENT_UPDATE_IDS:
            _recent_update_ids.popitem(last=False)
        return True


def _get_draft(session: Session, chat_id: str | int) -> BorradorTelegram | None:
    return session.get(BorradorTelegram, str(chat_id))


def _start_draft(session: Session, chat_id: str | int) -> BorradorTelegram:
    draft = _get_draft(session, chat_id)
    if draft is None:
        draft = BorradorTelegram(chat_id=str(chat_id))
    else:
        draft.description = None
        draft.location_label = None
        draft.latitude = None
        draft.longitude = None
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def _clear_draft(session: Session, draft: BorradorTelegram | None) -> None:
    if draft is not None:
        session.delete(draft)
        session.commit()


def _store_photo(photo_sizes: list[dict]) -> str | None:
    """Descarga la foto más grande de Telegram y la guarda en Supabase si está activo."""
    settings = get_settings()
    if not settings.storage_enabled or not photo_sizes:
        return None
    photo = max(photo_sizes, key=lambda item: item.get("file_size", 0))
    file_id = photo.get("file_id")
    if not file_id:
        return None
    try:
        get_file_url = _api_url("getFile")
        if not get_file_url:
            return None
        metadata = httpx.get(get_file_url, params={"file_id": file_id}, timeout=10).raise_for_status()
        file_path = metadata.json().get("result", {}).get("file_path")
        if not file_path:
            return None
        token = settings.telegram_bot_token
        download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        response = httpx.get(download_url, timeout=15).raise_for_status()
        data = response.content
        if len(data) > settings.max_photo_bytes:
            log.warning("La foto de Telegram supera MAX_PHOTO_BYTES")
            return None
        extension = PurePosixPath(file_path).suffix.lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(extension)
        if not mime:
            mime = "image/jpeg"
        path = storage_service.safe_object_path(f"telegram-{file_id}", mime)
        storage_service._bucket().upload(path, data, {"content-type": mime})
        return path
    except Exception as exc:
        log.warning("No se pudo guardar la foto de Telegram: %s", exc)
        return None


def _create_case_from_draft(session: Session, draft: BorradorTelegram, chat_id: str | int,
                            photo_path: str | None = None) -> str | None:
    # Esta validacion final evita que un cambio futuro en el flujo cree expedientes
    # incompletos aunque el usuario haya llegado a esta funcion por otra ruta.
    if (
        not draft.description
        or len(draft.description.strip()) < 10
        or not draft.location_label
        or not _valid_coordinate(draft.latitude, -90, 90)
        or not _valid_coordinate(draft.longitude, -180, 180)
    ):
        send_message(chat_id, "No puedo crear el reporte todavia. Completa primero la descripcion y la ubicacion.")
        return None
    location = ReportLocation(label=draft.location_label or "Ubicacion enviada por Telegram",
                               latitude=draft.latitude, longitude=draft.longitude)
    payload = ReportCreate(description=draft.description.strip(),
                           location=location, photo_path=photo_path)
    case: Expediente = registrar_reporte(session, payload, source="telegram", reporter_contact=f"telegram:{chat_id}")
    _clear_draft(session, draft)
    if case.classification_source == "gemini":
        classification = "Clasificacion realizada con Gemini"
    elif case.classification_source == "reglas":
        classification = "Clasificacion de respaldo por reglas"
    else:
        classification = "Clasificacion pendiente"
    details = []
    if case.category:
        details.append(f"Categoria: {case.category}")
    if case.urgency:
        details.append(f"Urgencia: {case.urgency}")
    if case.summary:
        details.append(f"Resumen: {case.summary}")
    details_text = "\n".join(details)
    send_message(chat_id, f"Reporte recibido por miCangrejo.\n\nFolio: {case.folio}\n"
                          f"{classification}.\n{details_text}\n\n"
                          f"Puedes consultar avances con: estado {case.folio}")
    return case.folio


def _valid_coordinate(value: object, minimum: float, maximum: float) -> bool:
    """Valida coordenadas numericas sin aceptar booleanos ni valores fuera de rango."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= float(value) <= maximum
    )


def handle_update(session: Session, update: dict) -> str | None:
    """Procesa un update de Telegram y devuelve el folio creado, si aplica."""
    if not _claim_update_id(update.get("update_id")):
        return None

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return None

    text = str(message.get("text") or message.get("caption") or "").strip()
    normalized = " ".join(text.lower().split())
    draft = _get_draft(session, chat_id)

    if normalized in {"/cancelar", "cancelar"}:
        _clear_draft(session, draft)
        send_message(chat_id, "Reporte cancelado. Cuando quieras comenzar, escribe /reporte.")
        return None
    if normalized in HELP_WORDS:
        send_message(chat_id, HELP_TEXT)
        return None

    # Los comandos desconocidos no se interpretan como una descripcion.
    # Asi un typo como /reportarrr no puede iniciar un expediente por accidente.
    # OMIT_WORDS entra aquí porque incluye "/omitir": sin ella, saltarse la foto se leía como
    # comando desconocido y el expediente nunca llegaba a crearse.
    known_commands = (HELP_WORDS | REPORT_WORDS | STATUS_WORDS | LOCATION_WORDS | OMIT_WORDS
                      | {"/cancelar", "cancelar"})
    if text.startswith("/") and normalized not in known_commands and not FOLIO_PATTERN.search(text):
        send_message(chat_id, UNKNOWN_COMMAND)
        return None

    match = FOLIO_PATTERN.search(text)
    if match and not (message.get("location") or message.get("photo")):
        folio = match.group(0).upper()
        try:
            case = obtener_por_folio(session, folio)
        except HTTPException:
            send_message(chat_id, f"No encontramos el folio {folio}. Revisa el codigo e intentalo otra vez.")
            return None
        send_message(chat_id, f"El folio {case.folio} esta en estado: {case.status}.")
        return None

    if normalized in REPORT_WORDS:
        _start_draft(session, chat_id)
        send_message(chat_id, REPORT_PROMPT)
        return None
    if normalized in STATUS_WORDS:
        send_message(chat_id, STATUS_PROMPT)
        return None
    if normalized in LOCATION_WORDS:
        send_message(chat_id, LOCATION_PROMPT)
        return None

    has_location = "location" in message
    has_photo = "photo" in message
    if has_location and has_photo:
        send_message(chat_id, "Envia solo la ubicacion en este paso. La foto se solicita despues.")
        return None

    location_data = message.get("location")
    if has_location:
        if draft is None or not draft.description:
            send_message(chat_id, REPORT_PROMPT)
            return None
        if not isinstance(location_data, dict) or not _valid_coordinate(location_data.get("latitude"), -90, 90) \
                or not _valid_coordinate(location_data.get("longitude"), -180, 180):
            send_message(chat_id, LOCATION_ERROR)
            return None
        label = location_data.get("title") or location_data.get("address") or "Ubicacion enviada por Telegram"
        if not isinstance(label, str) or not label.strip():
            label = "Ubicacion enviada por Telegram"
        draft.location_label = label.strip()[:160]
        draft.latitude = location_data.get("latitude")
        draft.longitude = location_data.get("longitude")
        session.add(draft)
        session.commit()
        send_message(chat_id, PHOTO_PROMPT)
        return None

    if has_photo:
        if draft is None or not draft.description:
            send_message(chat_id, REPORT_PROMPT)
            return None
        if draft.location_label is None:
            send_message(chat_id, LOCATION_PROMPT)
            return None
        photo = message.get("photo")
        if not isinstance(photo, list) or not photo or not any(
            isinstance(item, dict) and isinstance(item.get("file_id"), str) and item.get("file_id")
            for item in photo
        ):
            send_message(chat_id, PHOTO_ERROR)
            return None
        return _create_case_from_draft(session, draft, chat_id, _store_photo(photo))

    if not text:
        return None
    if draft is None:
        draft = _start_draft(session, chat_id)
    if not draft.description:
        if len(text) < 10:
            send_message(chat_id, DESCRIPTION_ERROR)
            return None
        if len(text) > 500:
            send_message(chat_id, DESCRIPTION_ERROR)
            return None
        draft.description = text
        session.add(draft)
        session.commit()
        send_message(chat_id, LOCATION_PROMPT)
        return None
    if draft.location_label is None:
        send_message(chat_id, LOCATION_ERROR)
        return None
    if normalized in OMIT_WORDS:
        return _create_case_from_draft(session, draft, chat_id)

    send_message(chat_id, PHOTO_ERROR)
    return None


def process_update(session: Session, update: dict) -> None:
    """Procesa el update fuera de la respuesta HTTP para responder 200 rápido."""
    try:
        handle_update(session, update)
    except Exception:
        log.exception("Error procesando update de Telegram")
