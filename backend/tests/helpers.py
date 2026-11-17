"""Datos de referencia y ayudas para llevar un expediente hasta cada etapa del flujo."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

UBICACION = {"label": "Vía Argentina frente al parque Andrés Bello", "latitude": 8.9924, "longitude": -79.5221}
UBICACION_A_30_M = {**UBICACION, "latitude": UBICACION["latitude"] + 0.00027}   # ≈ 30 m al norte
UBICACION_A_1_KM = {**UBICACION, "latitude": UBICACION["latitude"] + 0.01}      # ≈ 1,1 km al norte
DESCRIPCION_BASURA = "Hay basura acumulada frente al edificio desde hace tres días"
DESCRIPCION_BASURA_2 = "Bolsas de basura tiradas junto al contenedor de la esquina"
DESCRIPCION_ESTACIONAMIENTO = "Carro mal parqueado sobre la acera del edificio"
PREFIJO_FOLIO = f"MC-{datetime.now(UTC).year}-"
CODIGOS_ENTIDADES = {"AAUD", "ATTT", "JUEZ_PAZ", "POLICIA", "ALCALDIA", "ENSA", "IDAAN", "MINSA"}


def crear_reporte(client: TestClient, description: str = DESCRIPCION_BASURA, location: dict | None = None,
                  **extra) -> dict:
    payload = {"description": description, "location": location or UBICACION, **extra}
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def participacion(report: dict, code: str) -> dict:
    """Última participación de la entidad `code` dentro de un ReportOut."""
    matches = [p for p in report["participations"] if p["entity"]["code"] == code]
    assert matches, f"{code} no participa en {report['folio']}: {[p['entity']['code'] for p in report['participations']]}"
    return matches[-1]


def expediente(client: TestClient, case_id: int) -> dict:
    response = client.get(f"/api/v1/admin/reports/{case_id}")
    assert response.status_code == 200, response.text
    return response.json()


def url_participacion(case_id: int, ceid: int) -> str:
    return f"/api/v1/admin/reports/{case_id}/entities/{ceid}"


def validar_y_enviar(client: TestClient, case_id: int) -> dict:
    """PATCH validated + POST send: deja el expediente 'Enviado a entidades'."""
    patched = client.patch(f"/api/v1/admin/reports/{case_id}", json={"validated": True, "urgency": "Alta"})
    assert patched.status_code == 200, patched.text
    sent = client.post(f"/api/v1/admin/reports/{case_id}/send")
    assert sent.status_code == 200, sent.text
    return sent.json()


def derivar_aaud_a_minsa(client: TestClient, case_id: int) -> dict:
    """AAUD pasa a 'En atención' y se deriva a MINSA. Devuelve el ReportOut resultante."""
    aaud = participacion(expediente(client, case_id), "AAUD")
    base = url_participacion(case_id, aaud["id"])
    atencion = client.patch(base, json={"status": "En atención"})
    assert atencion.status_code == 200, atencion.text
    derived = client.post(f"{base}/derive",
                          json={"to_entity_code": "MINSA", "responsibility": "Inspección sanitaria del punto"})
    assert derived.status_code == 200, derived.text
    return derived.json()


def flujo_hasta_resuelto(client: TestClient) -> dict:
    """Crea → valida → envía → deriva AAUD a MINSA → resuelve ALCALDIA y MINSA."""
    report = crear_reporte(client)
    validar_y_enviar(client, report["id"])
    body = derivar_aaud_a_minsa(client, report["id"])
    activas = [p for p in body["participations"] if p["status"] in {"Recibida", "En atención"}]
    assert {p["entity"]["code"] for p in activas} == {"ALCALDIA", "MINSA"}
    for part in activas:
        resolved = client.patch(url_participacion(report["id"], part["id"]), json={"status": "Resuelta"})
        assert resolved.status_code == 200, resolved.text
        body = resolved.json()
    return body
