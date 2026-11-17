"""Flujo del panel de la JDL: validar, enviar, transiciones, derivación, cierre y tablero."""

from tests.helpers import (
    CODIGOS_ENTIDADES, crear_reporte, derivar_aaud_a_minsa, expediente, flujo_hasta_resuelto,
    participacion, url_participacion, validar_y_enviar,
)


# ---------------------------------------------------------------- 5. validar

def test_validar_pasa_a_en_gestion(client):
    report = crear_reporte(client)

    response = client.patch(f"/api/v1/admin/reports/{report['id']}", json={"validated": True, "urgency": "Alta"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "En gestión"
    assert body["classification"]["urgency"] == "Alta"
    assert body["validated_at"] is not None
    assert [h["event"] for h in body["history"]] == ["creado", "clasificado", "corregido", "validado", "estado_expediente"]
    corregido, validado, estado = body["history"][2:]
    assert corregido["actor"] == "jdl" and corregido["note"] == "urgency=Alta"
    assert validado["actor"] == "jdl"
    assert (estado["previous"], estado["new"]) == ("Recibido", "En gestión")

    # Validar dos veces no duplica el evento
    again = client.patch(f"/api/v1/admin/reports/{report['id']}", json={"validated": True})
    assert again.status_code == 200
    assert [h["event"] for h in again.json()["history"]].count("validado") == 1


def test_patch_categoria_invalida_422_y_caso_inexistente_404(client):
    report = crear_reporte(client)

    invalid = client.patch(f"/api/v1/admin/reports/{report['id']}", json={"category": "Inventada"})
    assert invalid.status_code == 422
    assert "Categoría no válida" in invalid.json()["detail"]

    missing = client.patch("/api/v1/admin/reports/9999", json={"validated": True})
    assert missing.status_code == 404


# ---------------------------------------------------------------- 6. enviar

def test_enviar_a_entidades_simula_correos(client):
    report = crear_reporte(client)

    sent = validar_y_enviar(client, report["id"])
    assert sent["folio"] == report["folio"]
    assert sent["status"] == "Enviado a entidades"
    assert {r["entity"] for r in sent["results"]} == {"AAUD", "ALCALDIA"}
    for result in sent["results"]:
        assert result["email_status"] == "simulado"
        assert result["error"] is None

    detail = expediente(client, report["id"])
    assert detail["status"] == "Enviado a entidades"
    assert len(detail["participations"]) == 2
    for part in detail["participations"]:
        assert part["status"] == "Recibida"
        assert part["received_at"] is not None
        assert part["email_status"] == "simulado"
        assert part["email_sent_at"] is not None
        assert part["days_in_entity"] is not None
        assert part["overdue"] is False
    assert {(e["entity"]["code"], e["status"]) for e in detail["current_entities"]} == {
        ("AAUD", "Recibida"), ("ALCALDIA", "Recibida"),
    }
    correos = [h for h in detail["history"] if h["event"] == "correo"]
    assert {h["entity"] for h in correos} == {"AAUD", "ALCALDIA"}
    assert all(h["new"] == "simulado" and "modo de contingencia" in h["note"] for h in correos)
    assert any(f"Caso {report['folio']}" in h["note"] for h in correos)

    # Un segundo envío no tiene pendientes: no manda nada nuevo
    again = client.post(f"/api/v1/admin/reports/{report['id']}/send")
    assert again.status_code == 200
    assert again.json()["results"] == []
    assert again.json()["status"] == "Enviado a entidades"


def test_enviar_sin_validar_valida_implicitamente(client):
    report = crear_reporte(client)

    sent = client.post(f"/api/v1/admin/reports/{report['id']}/send")
    assert sent.status_code == 200
    detail = expediente(client, report["id"])
    assert detail["validated_at"] is not None
    validado = next(h for h in detail["history"] if h["event"] == "validado")
    assert validado["note"] == "Validación implícita al enviar"


# ---------------------------------------------------------------- 7. transiciones

def test_transiciones_de_participacion(client):
    report = crear_reporte(client)
    validar_y_enviar(client, report["id"])
    aaud = participacion(expediente(client, report["id"]), "AAUD")
    url = url_participacion(report["id"], aaud["id"])

    derivada = client.patch(url, json={"status": "Derivada"})
    assert derivada.status_code == 409
    assert "/derive" in derivada.json()["detail"]

    atencion = client.patch(url, json={"status": "En atención", "note": "Cuadrilla programada"})
    assert atencion.status_code == 200
    part = participacion(atencion.json(), "AAUD")
    assert part["status"] == "En atención"
    assert part["attention_at"] is not None
    assert part["note"] == "Cuadrilla programada"
    assert atencion.json()["status"] == "Enviado a entidades"
    cambio = [h for h in atencion.json()["history"] if h["event"] == "estado_participacion"]
    assert (cambio[-1]["previous"], cambio[-1]["new"], cambio[-1]["entity"]) == ("Recibida", "En atención", "AAUD")

    invalido = client.patch(url, json={"status": "Inventado"})
    assert invalido.status_code == 422

    ajena = client.patch(url_participacion(report["id"], 9999), json={"status": "En atención"})
    assert ajena.status_code == 404


def test_asignada_no_pasa_directo_a_en_atencion(client):
    report = crear_reporte(client)
    aaud = participacion(report, "AAUD")

    response = client.patch(url_participacion(report["id"], aaud["id"]), json={"status": "En atención"})
    assert response.status_code == 409


def test_agregar_participacion_manual(client):
    report = crear_reporte(client)
    url = f"/api/v1/admin/reports/{report['id']}/entities"

    added = client.post(url, json={"entity_code": "minsa", "responsibility": "Inspección sanitaria"})
    assert added.status_code == 201
    minsa = participacion(added.json(), "MINSA")
    assert minsa["status"] == "Asignada"
    assert minsa["responsibility"] == "Inspección sanitaria"

    repeated = client.post(url, json={"entity_code": "MINSA", "responsibility": "Inspección sanitaria"})
    assert repeated.status_code == 409

    unknown = client.post(url, json={"entity_code": "NOEXISTE", "responsibility": "Lo que sea"})
    assert unknown.status_code == 404


# ---------------------------------------------------------------- 8. derivación

def test_derivar_aaud_a_minsa(client):
    report = crear_reporte(client)
    validar_y_enviar(client, report["id"])

    body = derivar_aaud_a_minsa(client, report["id"])
    assert body["status"] == "Enviado a entidades"

    origen = participacion(body, "AAUD")
    assert origen["status"] == "Derivada"
    assert origen["derived_at"] is not None
    assert origen["derived_to"] == {"code": "MINSA", "name": "Ministerio de Salud (MINSA)"}
    assert origen["days_in_entity"] is not None

    minsa = participacion(body, "MINSA")
    assert minsa["status"] == "Recibida"
    assert minsa["received_at"] is not None
    assert minsa["email_status"] == "simulado"
    assert minsa["email_sent_at"] is not None
    assert minsa["responsibility"] == "Inspección sanitaria del punto"
    assert minsa["derived_to"] is None

    assert {(e["entity"]["code"], e["status"]) for e in body["current_entities"]} == {
        ("ALCALDIA", "Recibida"), ("MINSA", "Recibida"),
    }

    derivado = [h for h in body["history"] if h["event"] == "derivado"]
    assert len(derivado) == 1
    assert derivado[0]["entity"] == "AAUD"
    assert derivado[0]["actor"] == "jdl"
    assert (derivado[0]["previous"], derivado[0]["new"]) == ("En atención", "Derivada")
    assert "AAUD deriva a MINSA" in derivado[0]["note"]
    assert any(h["event"] == "correo" and h["entity"] == "MINSA" and h["new"] == "simulado" for h in body["history"])


def test_derivaciones_invalidas(client):
    report = crear_reporte(client)
    validar_y_enviar(client, report["id"])
    body = derivar_aaud_a_minsa(client, report["id"])
    aaud = participacion(body, "AAUD")
    alcaldia = participacion(body, "ALCALDIA")
    payload = {"to_entity_code": "MINSA", "responsibility": "Inspección sanitaria del punto"}

    # Repetir sobre una participación ya Derivada → 409
    repeated = client.post(f"{url_participacion(report['id'], aaud['id'])}/derive", json=payload)
    assert repeated.status_code == 409
    assert "Derivada" in repeated.json()["detail"]

    # A la misma entidad → 409
    same = client.post(f"{url_participacion(report['id'], alcaldia['id'])}/derive",
                       json={**payload, "to_entity_code": "ALCALDIA"})
    assert same.status_code == 409
    assert "misma entidad" in same.json()["detail"]

    # Entidad inexistente → 404
    unknown = client.post(f"{url_participacion(report['id'], alcaldia['id'])}/derive",
                          json={**payload, "to_entity_code": "NOEXISTE"})
    assert unknown.status_code == 404

    # Nada de lo anterior tocó a ALCALDIA
    assert participacion(expediente(client, report["id"]), "ALCALDIA")["status"] == "Recibida"


def test_no_se_deriva_una_participacion_asignada(client):
    report = crear_reporte(client)
    aaud = participacion(report, "AAUD")

    response = client.post(f"{url_participacion(report['id'], aaud['id'])}/derive",
                           json={"to_entity_code": "MINSA", "responsibility": "Inspección sanitaria"})
    assert response.status_code == 409
    assert "Asignada" in response.json()["detail"]


# ---------------------------------------------------------------- 9. cierre

def test_resolver_todas_las_participaciones_cierra_el_expediente(client):
    final = flujo_hasta_resuelto(client)

    assert final["status"] == "Resuelto"
    assert final["current_entities"] == []
    estados = {p["entity"]["code"]: p["status"] for p in final["participations"]}
    assert estados == {"AAUD": "Derivada", "ALCALDIA": "Resuelta", "MINSA": "Resuelta"}
    for part in final["participations"]:
        if part["status"] == "Resuelta":
            assert part["resolved_at"] is not None
            assert part["days_in_entity"] is not None

    eventos = {h["event"] for h in final["history"]}
    assert {"creado", "clasificado", "validado", "correo", "derivado", "estado_expediente"} <= eventos
    transiciones = [(h["previous"], h["new"]) for h in final["history"] if h["event"] == "estado_expediente"]
    assert transiciones == [
        ("Recibido", "En gestión"),
        ("En gestión", "Enviado a entidades"),
        ("Enviado a entidades", "Resuelto"),
    ]

    # Resuelta es terminal
    minsa = participacion(final, "MINSA")
    reopen = client.patch(url_participacion(final["id"], minsa["id"]), json={"status": "En atención"})
    assert reopen.status_code == 409

    # La consulta pública refleja el cierre
    public = client.get(f"/api/v1/reports/{final['folio']}")
    assert public.status_code == 200
    assert public.json()["status"] == "Resuelto"


def test_una_sola_resuelta_no_cierra_el_expediente(client):
    report = crear_reporte(client)
    validar_y_enviar(client, report["id"])
    alcaldia = participacion(expediente(client, report["id"]), "ALCALDIA")

    response = client.patch(url_participacion(report["id"], alcaldia["id"]), json={"status": "Resuelta"})
    assert response.status_code == 200
    assert response.json()["status"] == "Enviado a entidades"
    assert [e["entity"]["code"] for e in response.json()["current_entities"]] == ["AAUD"]


# ---------------------------------------------------------------- 10. tablero

def test_stats_del_tablero(client):
    flujo_hasta_resuelto(client)

    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 200
    tablero = response.json()
    assert tablero["sla_dias"] == 5
    assert tablero["total_cases"] == 1
    assert tablero["by_status"] == {"Resuelto": 1}
    assert tablero["by_category"] == {"Basura": 1}

    by_code = {e["entity"]["code"]: e for e in tablero["entities"]}
    assert set(by_code) == CODIGOS_ENTIDADES

    minsa = by_code["MINSA"]
    assert minsa["resolved"] == 1
    assert minsa["avg_response_days"] is not None
    assert minsa["avg_response_days"] >= 0
    assert minsa["open_cases"] == 0
    assert minsa["overdue"] == 0

    assert by_code["ALCALDIA"]["resolved"] == 1
    assert by_code["AAUD"] == {
        "entity": {"code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)"},
        "open_cases": 0, "avg_response_days": None, "derived_more_than_once": 0, "overdue": 0, "resolved": 0,
    }
    assert all(e["derived_more_than_once"] == 0 for e in tablero["entities"])


def test_stats_con_base_vacia(client):
    tablero = client.get("/api/v1/admin/stats").json()
    assert tablero["total_cases"] == 0
    assert tablero["by_status"] == {}
    assert tablero["by_category"] == {}
    assert len(tablero["entities"]) == len(CODIGOS_ENTIDADES)
    assert all(e["open_cases"] == 0 and e["avg_response_days"] is None for e in tablero["entities"])
