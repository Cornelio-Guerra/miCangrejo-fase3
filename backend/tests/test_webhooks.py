"""Webhook de WhatsApp (Meta Cloud API) sin credenciales: verificación y recepción."""

import json

import pytest

from app.services import whatsapp_service
from tests.helpers import PREFIJO_FOLIO

WEBHOOK = "/api/v1/webhooks/whatsapp"
TELEFONO = "50760000000"


@pytest.fixture(autouse=True)
def clear_recent_webhook_ids():
    with whatsapp_service._recent_message_lock:
        whatsapp_service._recent_message_ids.clear()
    yield
    with whatsapp_service._recent_message_lock:
        whatsapp_service._recent_message_ids.clear()


def payload_meta(*messages: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "50760000001", "phone_number_id": "111"},
                    "contacts": [{"profile": {"name": "Vecino"}, "wa_id": TELEFONO}],
                    "messages": list(messages),
                },
            }],
        }],
    }


def mensaje_texto(body: str) -> dict:
    return {"from": TELEFONO, "id": "wamid.TEXT1", "timestamp": "1700000000", "type": "text", "text": {"body": body}}


# ---------------------------------------------------------------- verificación (GET)

def test_verificacion_con_token_incorrecto_403(client):
    response = client.get(WEBHOOK, params={"hub.mode": "subscribe", "hub.verify_token": "incorrecto",
                                           "hub.challenge": "123456"})
    assert response.status_code == 403


def test_verificacion_sin_modo_subscribe_403(client):
    response = client.get(WEBHOOK, params={"hub.mode": "unsubscribe", "hub.verify_token": "prueba",
                                           "hub.challenge": "123456"})
    assert response.status_code == 403


def test_verificacion_correcta_devuelve_el_challenge(client):
    response = client.get(WEBHOOK, params={"hub.mode": "subscribe", "hub.verify_token": "prueba",
                                           "hub.challenge": "123456"})
    assert response.status_code == 200
    assert response.text == "123456"
    assert response.headers["content-type"].startswith("text/plain")


# ---------------------------------------------------------------- recepción (POST)

def test_mensaje_de_texto_crea_un_folio(client):
    response = client.post(WEBHOOK, json=payload_meta(mensaje_texto("Hay basura acumulada en la esquina de la calle 50")))
    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["folios"] == []

    detail = client.get(f"/api/v1/reports/{PREFIJO_FOLIO}0001")
    assert detail.status_code == 200
    report = detail.json()
    assert report["source"] == "whatsapp"
    assert report["status"] == "Recibido"
    assert report["description"] == "Hay basura acumulada en la esquina de la calle 50"
    assert report["classification"]["category"] == "Basura"
    assert report["classification"]["source"] == "reglas"
    assert report["location"] == {"label": "Ubicación pendiente (WhatsApp)", "latitude": None, "longitude": None}
    assert report["history"][0]["note"] == "Reporte recibido por whatsapp"
    # El teléfono del vecino nunca sale por la API
    assert TELEFONO not in json.dumps(report)


def test_mensaje_de_ubicacion_crea_folio_con_coordenadas(client):
    location = {
        "from": TELEFONO, "id": "wamid.LOC1", "timestamp": "1700000000", "type": "location",
        "location": {"latitude": 8.9924, "longitude": -79.5221, "name": "Parque Andrés Bello",
                     "address": "Vía Argentina"},
    }
    response = client.post(WEBHOOK, json=payload_meta(location))
    assert response.status_code == 200
    assert response.json()["folios"] == []

    report = client.get(f"/api/v1/reports/{PREFIJO_FOLIO}0001").json()
    assert report["source"] == "whatsapp"
    assert report["location"] == {"label": "Parque Andrés Bello", "latitude": 8.9924, "longitude": -79.5221}
    assert report["description"] == "Reporte por WhatsApp: Parque Andrés Bello"


def test_texto_corto_se_completa_para_cumplir_el_minimo(client):
    response = client.post(WEBHOOK, json=payload_meta(mensaje_texto("bache")))
    assert response.status_code == 200
    assert response.json()["folios"] == []
    assert client.get(f"/api/v1/reports/{PREFIJO_FOLIO}0001").json()["description"] == "Reporte por WhatsApp: bache"


def test_saludo_responde_ayuda_sin_crear_reporte(client, monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(whatsapp_service, "reply", lambda to, text: sent.append((to, text)))

    response = client.post(WEBHOOK, json=payload_meta(mensaje_texto("hola")))

    assert response.status_code == 200
    assert response.json()["folios"] == []
    assert client.get("/api/v1/reports").json()["total"] == 0
    assert sent == [(TELEFONO, whatsapp_service.HELP_TEXT)]


def test_opciones_del_menu_orientan_sin_crear_reporte(client, monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(whatsapp_service, "reply", lambda to, text: sent.append((to, text)))

    for index, option in enumerate(("1", "2", "3"), start=1):
        response = client.post(WEBHOOK, json=payload_meta({**mensaje_texto(option), "id": f"wamid.MENU{index}"}))
        assert response.status_code == 200
        assert response.json()["folios"] == []

    assert client.get("/api/v1/reports").json()["total"] == 0
    assert sent == [
        (TELEFONO, whatsapp_service.REPORT_PROMPT),
        (TELEFONO, whatsapp_service.STATUS_PROMPT),
        (TELEFONO, whatsapp_service.LOCATION_PROMPT),
    ]


def test_consulta_de_folio_responde_estado_sin_crear_otro_reporte(client, monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(whatsapp_service, "reply", lambda to, text: sent.append((to, text)))
    created = client.post(WEBHOOK, json=payload_meta(mensaje_texto("Hay basura acumulada en la esquina de la calle 50")))
    folio = f"{PREFIJO_FOLIO}0001"

    response = client.post(WEBHOOK, json=payload_meta({**mensaje_texto(f"estado {folio}"), "id": "wamid.STATUS1"}))

    assert response.status_code == 200
    assert response.json()["folios"] == []
    assert client.get("/api/v1/reports").json()["total"] == 1
    assert sent[-1] == (TELEFONO, f"miCangrejo: el folio {folio} está en estado: Recibido.")


def test_varios_mensajes_en_un_solo_webhook(client):
    response = client.post(WEBHOOK, json=payload_meta(
        mensaje_texto("Música a todo volumen en el edificio de la esquina"),
        {**mensaje_texto("Carro mal parqueado sobre la acera"), "id": "wamid.TEXT2"},
    ))
    assert response.status_code == 200
    assert response.json()["folios"] == []
    assert client.get("/api/v1/reports").json()["total"] == 2


def test_reintento_de_meta_no_duplica_el_reporte(client):
    message = mensaje_texto("Hay basura acumulada en la esquina de la calle 50")
    client.post(WEBHOOK, json=payload_meta(message))
    response = client.post(WEBHOOK, json=payload_meta(message))

    assert response.status_code == 200
    assert client.get("/api/v1/reports").json()["total"] == 1


def test_cuerpo_vacio_200_sin_folios(client):
    response = client.post(WEBHOOK, content=b"")
    assert response.status_code == 200
    assert response.json() == {"received": True, "folios": []}
    assert client.get("/api/v1/reports").json()["total"] == 0


def test_json_que_no_es_objeto_200_sin_folios(client):
    response = client.post(WEBHOOK, json=[1, 2, 3])
    assert response.status_code == 200
    assert response.json() == {"received": True, "folios": []}


def test_tipo_de_mensaje_no_soportado_se_ignora(client):
    sticker = {"from": TELEFONO, "id": "wamid.STK1", "timestamp": "1700000000", "type": "sticker",
               "sticker": {"id": "999"}}
    response = client.post(WEBHOOK, json=payload_meta(sticker))
    assert response.status_code == 200
    assert response.json()["folios"] == []
    assert client.get("/api/v1/reports").json()["total"] == 0
