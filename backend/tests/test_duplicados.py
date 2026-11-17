"""Agrupación de duplicados (RF-03): el reporte nuevo se marca como agrupado, hereda la
evidencia al expediente principal y queda inmutable para el panel."""


def _reporte(client, descripcion, lat, lng, **extra):
    body = {"description": descripcion, "location": {"label": "PH Torre Marbella", "latitude": lat, "longitude": lng}, **extra}
    response = client.post("/api/v1/reports", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_duplicado_se_agrupa_y_queda_inmutable(client):
    principal = _reporte(client, "Tinaco desbordado con bolsas rotas frente al PH", 8.9868, -79.5303)
    duplicado = _reporte(client, "Otra vez el tinaco lleno y basura regada", 8.98685, -79.5303,
                         photo_path="casos/prueba-duplicado.png")

    # La respuesta del POST es el expediente principal con el contador incrementado
    assert duplicado["folio"] == principal["folio"]
    assert duplicado["reports_count"] == 2

    # El reporte nuevo existe, marcado como agrupado y sin participaciones
    listado = client.get("/api/v1/admin/reports", params={"page_size": 5}).json()
    nuevo = next(i for i in listado["items"] if i["folio"] != principal["folio"])
    detalle = client.get(f"/api/v1/reports/{nuevo['folio']}").json()
    assert detalle["merged_into"] == principal["folio"]
    assert detalle["status"] == "Resuelto"
    assert detalle["participations"] == []

    # La evidencia del duplicado pasa al expediente principal si este no tenía
    principal_detalle = client.get(f"/api/v1/reports/{principal['folio']}").json()
    assert principal_detalle["classification"]["entities"]  # sigue con sus entidades

    # Nada del panel puede tocar un reporte agrupado
    for metodo, ruta, body in (
        ("post", f"/api/v1/admin/reports/{nuevo['id']}/send", None),
        ("patch", f"/api/v1/admin/reports/{nuevo['id']}", {"validated": True}),
        ("post", f"/api/v1/admin/reports/{nuevo['id']}/entities", {"entity_code": "MINSA", "responsibility": "x y z"}),
        ("post", f"/api/v1/admin/reports/{nuevo['id']}/classify", None),
    ):
        response = getattr(client, metodo)(ruta, json=body)
        assert response.status_code == 409, (ruta, response.text)
        assert principal["folio"] in response.json()["detail"]

    # El tablero no cuenta participaciones del agrupado
    tablero = client.get("/api/v1/admin/stats").json()
    abiertos = {e["entity"]["code"]: e["open_cases"] for e in tablero["entities"]}
    assert abiertos["AAUD"] == 1 and abiertos["ALCALDIA"] == 1


def test_no_agrupa_si_categoria_distinta_o_lejos(client):
    a = _reporte(client, "Tinaco desbordado con bolsas rotas frente al PH", 8.9868, -79.5303)
    b = _reporte(client, "Carro mal parqueado sobre la acera bloqueando el paso", 8.9868, -79.5303)  # otra categoría
    c = _reporte(client, "Tinaco desbordado con bolsas rotas en otra calle", 8.9990, -79.5100)          # a más de 150 m
    assert len({a["folio"], b["folio"], c["folio"]}) == 3
    assert all(r["reports_count"] == 1 for r in (a, b, c))
