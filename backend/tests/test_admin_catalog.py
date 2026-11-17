"""Listado con filtros, tabla de enrutamiento y catálogo de entidades del panel."""

from tests.helpers import (
    CODIGOS_ENTIDADES, DESCRIPCION_ESTACIONAMIENTO, UBICACION_A_1_KM, crear_reporte, flujo_hasta_resuelto,
)

RUTAS_CATALOGO = {
    ("Basura", "AAUD"), ("Basura", "ALCALDIA"), ("Estacionamiento", "ATTT"), ("Ruido", "JUEZ_PAZ"),
    ("Ruido", "POLICIA"), ("Seguridad", "POLICIA"), ("Alumbrado o aceras", "ALCALDIA"), ("Otro", "ALCALDIA"),
}


# ---------------------------------------------------------------- 11a. listado

def test_listado_admin_filtrado_por_estado(client):
    resuelto = flujo_hasta_resuelto(client)
    abierto = crear_reporte(client, DESCRIPCION_ESTACIONAMIENTO, UBICACION_A_1_KM)

    response = client.get("/api/v1/admin/reports", params={"status": "Resuelto"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [i["folio"] for i in body["items"]] == [resuelto["folio"]]
    item = body["items"][0]
    assert item["status"] == "Resuelto"
    assert item["category"] == "Basura"
    assert item["urgency"] == "Alta"
    assert item["classification_status"] == "provisional"
    assert item["entities"] == []
    assert item["reports_count"] == 1

    por_categoria = client.get("/api/v1/admin/reports", params={"category": "Estacionamiento"}).json()
    assert por_categoria["total"] == 1
    assert por_categoria["items"][0]["folio"] == abierto["folio"]
    assert [e["entity"]["code"] for e in por_categoria["items"][0]["entities"]] == ["ATTT"]

    por_urgencia = client.get("/api/v1/admin/reports", params={"urgency": "Alta"}).json()
    assert [i["folio"] for i in por_urgencia["items"]] == [resuelto["folio"]]

    paginado = client.get("/api/v1/admin/reports", params={"page": 2, "page_size": 1}).json()
    assert paginado["total"] == 2
    assert paginado["page"] == 2
    assert len(paginado["items"]) == 1

    fuera_de_rango = client.get("/api/v1/admin/reports", params={"page_size": 500})
    assert fuera_de_rango.status_code == 422


# ---------------------------------------------------------------- 11b. enrutamiento

def test_routing_sembrado_desde_el_catalogo(client):
    response = client.get("/api/v1/admin/routing")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) == 8
    assert {(r["category"], r["entity_code"]) for r in rules} == RUTAS_CATALOGO
    for rule in rules:
        assert {"id", "category", "entity_code", "responsibility", "entity_name", "entity_email"} <= set(rule)
        assert rule["entity_email"].endswith("@demo.micangrejo.local")


def test_put_routing_reemplaza_la_tabla(client):
    nuevas = [
        {"category": "Basura", "entity_code": "AAUD", "responsibility": "Recolección del punto"},
        {"category": "Ruido", "entity_code": "POLICIA", "responsibility": "Atención nocturna"},
        {"category": "Otro", "entity_code": "alcaldia", "responsibility": "Canalizar"},
    ]

    response = client.put("/api/v1/admin/routing", json=nuevas)
    assert response.status_code == 200
    assert {(r["category"], r["entity_code"], r["responsibility"]) for r in response.json()} == {
        ("Basura", "AAUD", "Recolección del punto"),
        ("Ruido", "POLICIA", "Atención nocturna"),
        ("Otro", "ALCALDIA", "Canalizar"),
    }
    assert len(client.get("/api/v1/admin/routing").json()) == 3


def test_put_routing_con_entidad_inexistente_422(client):
    response = client.put("/api/v1/admin/routing", json=[
        {"category": "Basura", "entity_code": "NOEXISTE", "responsibility": "Lo que sea"},
    ])
    assert response.status_code == 422
    assert "NOEXISTE" in response.json()["detail"]
    # La tabla original sigue intacta
    assert len(client.get("/api/v1/admin/routing").json()) == 8


def test_put_routing_con_categoria_invalida_422(client):
    response = client.put("/api/v1/admin/routing", json=[
        {"category": "Inventada", "entity_code": "AAUD", "responsibility": "Lo que sea"},
    ])
    assert response.status_code == 422
    assert "Inventada" in response.json()["detail"]


# ---------------------------------------------------------------- 11c. entidades

def test_editar_correo_de_entidad(client):
    response = client.patch("/api/v1/admin/entities/AAUD", json={"email": "aaud@demo.test"})
    assert response.status_code == 200
    assert response.json() == {
        "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)",
        "email": "aaud@demo.test", "is_active": True,
    }

    listado = client.get("/api/v1/admin/entities").json()
    assert [e["code"] for e in listado] == sorted(CODIGOS_ENTIDADES)
    assert {e["code"]: e["email"] for e in listado}["AAUD"] == "aaud@demo.test"

    # El correo nuevo es el que usa el envío
    report = crear_reporte(client)
    client.post(f"/api/v1/admin/reports/{report['id']}/send")
    detail = client.get(f"/api/v1/admin/reports/{report['id']}").json()
    correo_aaud = next(h for h in detail["history"] if h["event"] == "correo" and h["entity"] == "AAUD")
    assert "Correo simulado a aaud@demo.test" in correo_aaud["note"]


def test_editar_entidad_validaciones(client):
    minusculas = client.patch("/api/v1/admin/entities/aaud", json={"name": "AAUD demo"})
    assert minusculas.status_code == 200
    assert minusculas.json()["name"] == "AAUD demo"

    invalido = client.patch("/api/v1/admin/entities/AAUD", json={"email": "no-es-correo"})
    assert invalido.status_code == 422

    inexistente = client.patch("/api/v1/admin/entities/NOEXISTE", json={"email": "x@y.z"})
    assert inexistente.status_code == 404


def test_categorias(client):
    response = client.get("/api/v1/admin/categories")
    assert response.status_code == 200
    assert response.json() == ["Basura", "Estacionamiento", "Ruido", "Seguridad", "Alumbrado o aceras", "Otro"]
