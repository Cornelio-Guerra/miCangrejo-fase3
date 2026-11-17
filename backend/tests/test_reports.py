"""POST/GET /api/v1/reports: creación, agrupación de duplicados y validaciones."""

import re

from tests.helpers import (
    DESCRIPCION_BASURA, DESCRIPCION_BASURA_2, DESCRIPCION_ESTACIONAMIENTO, PREFIJO_FOLIO,
    UBICACION, UBICACION_A_1_KM, UBICACION_A_30_M, crear_reporte,
)


def test_crear_reporte_de_basura(client):
    report = crear_reporte(client)

    assert re.fullmatch(r"MC-\d{4}-\d{4}", report["folio"])
    assert report["folio"] == f"{PREFIJO_FOLIO}0001"
    assert report["status"] == "Recibido"
    assert report["source"] == "web"
    assert report["reports_count"] == 1
    assert report["description"] == DESCRIPCION_BASURA
    assert report["location"] == UBICACION
    assert report["photo_url"] is None
    assert report["validated_at"] is None

    classification = report["classification"]
    assert classification["source"] == "reglas"
    assert classification["status"] == "provisional"
    assert classification["category"] == "Basura"
    assert classification["urgency"] == "Media"
    assert classification["error"] == "GEMINI_API_KEY no configurada (modo de contingencia)"
    assert [e["code"] for e in classification["entities"]] == ["AAUD", "ALCALDIA"]

    assert {(e["entity"]["code"], e["status"]) for e in report["current_entities"]} == {
        ("AAUD", "Asignada"), ("ALCALDIA", "Asignada"),
    }
    for part in report["participations"]:
        assert part["status"] == "Asignada"
        assert part["email_status"] == "pendiente"
        assert part["received_at"] is None
        assert part["overdue"] is False
    assert [h["event"] for h in report["history"]] == ["creado", "clasificado"]
    assert report["history"][0]["note"] == "Reporte recibido por web"


def test_consultar_por_folio(client):
    created = crear_reporte(client)

    response = client.get(f"/api/v1/reports/{created['folio']}")
    assert response.status_code == 200
    assert response.json()["folio"] == created["folio"]
    assert response.json()["id"] == created["id"]

    # El folio se normaliza (mayúsculas, espacios)
    lower = client.get(f"/api/v1/reports/{created['folio'].lower()}")
    assert lower.status_code == 200
    assert lower.json()["folio"] == created["folio"]


def test_reporte_cercano_de_la_misma_categoria_se_agrupa(client):
    first = crear_reporte(client)
    second = crear_reporte(client, DESCRIPCION_BASURA_2, UBICACION_A_30_M)

    assert second["folio"] == first["folio"]
    assert second["id"] == first["id"]
    assert second["reports_count"] == 2
    assert second["status"] == "Recibido"
    assert [h["event"] for h in second["history"]] == ["creado", "clasificado", "duplicado"]
    assert DESCRIPCION_BASURA_2 in second["history"][-1]["note"]

    # El reporte agrupado existe con su propio folio, cerrado y sin entidades
    grouped = client.get(f"/api/v1/reports/{PREFIJO_FOLIO}0002")
    assert grouped.status_code == 200
    assert grouped.json()["status"] == "Resuelto"
    assert grouped.json()["current_entities"] == []
    assert grouped.json()["participations"] == []
    assert grouped.json()["history"][-1]["event"] == "agrupado"
    assert first["folio"] in grouped.json()["history"][-1]["note"]

    # El tablero no cuenta participaciones extra
    tablero = client.get("/api/v1/admin/stats").json()
    assert tablero["total_cases"] == 2
    assert tablero["by_status"] == {"Recibido": 1, "Resuelto": 1}
    by_code = {e["entity"]["code"]: e for e in tablero["entities"]}
    assert by_code["AAUD"]["open_cases"] == 1
    assert by_code["ALCALDIA"]["open_cases"] == 1


def test_reporte_lejano_no_se_agrupa(client):
    first = crear_reporte(client)
    far = crear_reporte(client, DESCRIPCION_BASURA_2, UBICACION_A_1_KM)

    assert far["folio"] == f"{PREFIJO_FOLIO}0002"
    assert far["folio"] != first["folio"]
    assert far["reports_count"] == 1
    assert first["reports_count"] == 1


def test_otra_categoria_en_el_mismo_lugar_no_se_agrupa(client):
    first = crear_reporte(client)
    other = crear_reporte(client, DESCRIPCION_ESTACIONAMIENTO, UBICACION)

    assert other["folio"] == f"{PREFIJO_FOLIO}0002"
    assert other["classification"]["category"] == "Estacionamiento"
    assert [e["code"] for e in other["classification"]["entities"]] == ["ATTT"]
    assert first["reports_count"] == 1


def test_listado_publico_paginado(client):
    crear_reporte(client)
    crear_reporte(client, DESCRIPCION_ESTACIONAMIENTO)

    response = client.get("/api/v1/reports", params={"page": 1, "page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1


def test_descripcion_corta_422(client):
    response = client.post("/api/v1/reports", json={"description": "basura", "location": UBICACION})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "description"]


def test_ubicacion_sin_label_422(client):
    response = client.post("/api/v1/reports", json={
        "description": DESCRIPCION_BASURA, "location": {"latitude": 8.9924, "longitude": -79.5221},
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "location", "label"]


def test_latitud_fuera_de_rango_422(client):
    response = client.post("/api/v1/reports", json={
        "description": DESCRIPCION_BASURA, "location": {**UBICACION, "latitude": 95},
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "location", "latitude"]


def test_folio_inexistente_404(client):
    response = client.get(f"/api/v1/reports/{PREFIJO_FOLIO}9999")
    assert response.status_code == 404
    assert f"{PREFIJO_FOLIO}9999" in response.json()["detail"]
