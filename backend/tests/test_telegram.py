"""Webhook de Telegram: secreto y flujo conversacional de reportes."""

from types import SimpleNamespace

import pytest

from app.routers import webhooks
from app.services import telegram_service
from tests.helpers import PREFIJO_FOLIO

WEBHOOK = "/api/v1/webhooks/telegram"
CHAT_ID = 123456
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}


@pytest.fixture(autouse=True)
def clean_updates():
    with telegram_service._recent_update_lock:
        telegram_service._recent_update_ids.clear()
    yield
    with telegram_service._recent_update_lock:
        telegram_service._recent_update_ids.clear()


def settings():
    return SimpleNamespace(
        telegram_bot_token="test-token",
        telegram_webhook_secret="test-secret",
        telegram_webhook_url="https://example.com/api/v1/webhooks/telegram",
        telegram_enabled=True,
        telegram_webhook_enabled=True,
        storage_enabled=False,
        max_photo_bytes=5 * 1024 * 1024,
    )


def update(update_id: int, *, text: str | None = None, location: dict | None = None,
           photo: list[dict] | None = None) -> dict:
    message = {
        "message_id": update_id,
        "chat": {"id": CHAT_ID, "type": "private"},
        "from": {"id": CHAT_ID, "first_name": "Vecino"},
    }
    if text is not None:
        message["text"] = text
    if location is not None:
        message["location"] = location
    if photo is not None:
        message["photo"] = photo
    return {"update_id": update_id, "message": message}


def configure(monkeypatch, sent: list[tuple[str | int, str]]):
    configured = settings()
    monkeypatch.setattr(webhooks, "get_settings", lambda: configured)
    monkeypatch.setattr(telegram_service, "get_settings", lambda: configured)
    monkeypatch.setattr(telegram_service, "send_message", lambda chat_id, text: sent.append((chat_id, text)) or True)


def post(client, payload: dict):
    return client.post(WEBHOOK, headers=HEADERS, json=payload)


def test_secreto_incorrecto_403(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)
    response = client.post(WEBHOOK, headers={"X-Telegram-Bot-Api-Secret-Token": "incorrecto"}, json={})
    assert response.status_code == 403
    assert sent == []


def test_reporte_pide_descripcion_ubicacion_y_foto_opcional(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)

    assert post(client, update(1001, text="/reporte")).status_code == 200
    assert "descripcion" in sent[-1][1].lower()

    assert post(client, update(1002, text="Hay basura acumulada en la esquina de la calle 50")).status_code == 200
    assert "ubicacion" in sent[-1][1].lower()
    assert client.get("/api/v1/reports").json()["total"] == 0

    location = {"latitude": 8.9924, "longitude": -79.5221, "title": "Parque del barrio"}
    assert post(client, update(1003, location=location)).status_code == 200
    assert "foto opcional" in sent[-1][1].lower()

    assert post(client, update(1004, text="omitir")).status_code == 200
    report = client.get(f"/api/v1/reports/{PREFIJO_FOLIO}0001").json()
    assert report["source"] == "telegram"
    assert report["description"] == "Hay basura acumulada en la esquina de la calle 50"
    assert report["location"] == {"label": "Parque del barrio", "latitude": 8.9924, "longitude": -79.5221}
    assert report["photo_url"] is None
    assert "Clasificacion de respaldo por reglas" in sent[-1][1]
    assert f"Folio: {PREFIJO_FOLIO}0001" in sent[-1][1]


def test_foto_es_opcional_y_no_rompe_sin_storage(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)
    post(client, update(1101, text="Reporte de ruido fuerte durante la noche"))
    post(client, update(1102, location={"latitude": 8.99, "longitude": -79.52}))
    response = post(client, update(1103, photo=[{"file_id": "photo-1", "width": 100, "height": 100}]))
    assert response.status_code == 200
    assert client.get("/api/v1/reports").json()["total"] == 1
    assert "Folio:" in sent[-1][1]


def test_reintento_no_duplica_reporte(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)
    payload = update(1201, text="Bache grande frente al parque del barrio")
    post(client, payload)
    post(client, update(1202, location={"latitude": 8.99, "longitude": -79.52}))
    post(client, update(1203, text="/omitir"))
    post(client, payload)
    assert client.get("/api/v1/reports").json()["total"] == 1


def test_respuestas_invalidas_no_avanzan_ni_crean_reporte(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)

    post(client, update(1301, text="/reporte"))
    post(client, update(1302, text="corto"))
    assert "10 caracteres" in sent[-1][1]
    assert client.get("/api/v1/reports").json()["total"] == 0

    post(client, update(1303, text="Hay una luminaria dañada frente al parque"))
    post(client, update(1304, text="la ubicacion es por aqui"))
    assert "Comparte una ubicacion" in sent[-1][1]
    assert client.get("/api/v1/reports").json()["total"] == 0

    post(client, update(1305, location={"latitude": 95, "longitude": -79.52}))
    assert "latitud y longitud" in sent[-1][1]
    assert client.get("/api/v1/reports").json()["total"] == 0

    post(client, update(1306, location={"latitude": 8.99, "longitude": -79.52}))
    post(client, update(1307, text="listo"))
    assert "Envia una foto" in sent[-1][1]
    assert client.get("/api/v1/reports").json()["total"] == 0

    post(client, update(1308, photo=[]))
    assert "Envia una foto" in sent[-1][1]
    assert client.get("/api/v1/reports").json()["total"] == 0

    post(client, update(1309, text="omitir"))
    assert client.get("/api/v1/reports").json()["total"] == 1


def test_comando_desconocido_no_inicia_reporte(client, monkeypatch):
    sent: list[tuple[str | int, str]] = []
    configure(monkeypatch, sent)

    post(client, update(1401, text="/reportarrr"))
    assert "comando" in sent[-1][1].lower()
    assert client.get("/api/v1/reports").json()["total"] == 0
