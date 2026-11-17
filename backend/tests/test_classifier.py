"""Clasificador: reglas (sin IA) y orden de intentos con Gemini (principal → reserva → reglas)."""

import dataclasses

from app.services import classifier
from app.services.classifier import ClassificationResult, EntityAssignment, classify, classify_by_rules


def test_ruido_asigna_juez_de_paz_y_policia():
    result = classify_by_rules("música a todo volumen")
    assert result.category == "Ruido"
    assert result.urgency == "Media"
    assert [e.code for e in result.entities] == ["JUEZ_PAZ", "POLICIA"]
    assert result.entities[0].responsibility == "Proceso comunitario por ruido"
    assert result.entities[1].responsibility == "Atención inmediata en horario nocturno"


def test_estacionamiento_asigna_attt():
    result = classify_by_rules("carro mal parqueado en la acera")
    assert result.category == "Estacionamiento"
    assert [e.code for e in result.entities] == ["ATTT"]
    assert result.entities[0].responsibility == "Grúa, infracción y control vial"


def test_seguridad_con_arma_es_urgencia_alta():
    result = classify_by_rules("asalto con arma")
    assert result.category == "Seguridad"
    assert result.urgency == "Alta"
    assert [e.code for e in result.entities] == ["POLICIA"]


def test_sin_palabras_clave_cae_en_otro():
    result = classify_by_rules("necesito información general sobre la junta")
    assert result.category == "Otro"
    assert result.urgency == "Media"
    assert [e.code for e in result.entities] == ["ALCALDIA"]
    assert result.entities[0].responsibility == "Canalizar a la entidad competente"


def test_ignora_acentos_y_mayusculas():
    result = classify_by_rules("MÚSICA Y BULLA HASTA LA MADRUGADA")
    assert result.category == "Ruido"


def test_urgencia_baja_por_palabras_clave():
    result = classify_by_rules("basura leve en la acera, cuando puedan")
    assert result.category == "Basura"
    assert result.urgency == "Baja"


def test_pista_de_categoria_inclina_la_balanza():
    sin_pista = classify_by_rules("hay un problema en la esquina desde ayer")
    con_pista = classify_by_rules("hay un problema en la esquina desde ayer", "Ruido")
    assert sin_pista.category == "Otro"
    assert con_pista.category == "Ruido"


def test_pista_fuera_del_catalogo_se_ignora():
    result = classify_by_rules("hay un problema en la esquina desde ayer", "Inventada")
    assert result.category == "Otro"


def test_resumen_se_recorta_a_160_caracteres():
    largo = "basura " * 40
    result = classify_by_rules(largo)
    assert len(result.summary) <= 160
    assert result.summary.endswith("…")

    corto = classify_by_rules("  basura en la esquina  ")
    assert corto.summary == "basura en la esquina"


def test_classify_sin_gemini_usa_reglas_y_lo_deja_anotado():
    outcome = classify("asalto con arma en la entrada del edificio")
    assert outcome.source == "reglas"
    assert outcome.error == "GEMINI_API_KEY no configurada (modo de contingencia)"
    assert outcome.result.category == "Seguridad"
    assert outcome.result.urgency == "Alta"


# --- Orden de intentos con Gemini (sin llamar a la API: se sustituye classify_with_gemini) ---

def _con_gemini(monkeypatch):
    fake = dataclasses.replace(classifier.get_settings(), gemini_api_key="clave-de-prueba",
                               gemini_model="modelo-principal",
                               gemini_fallback_models=("modelo-reserva", "modelo-reserva-2"))
    monkeypatch.setattr(classifier, "get_settings", lambda: fake)


def _respuesta_ia():
    return ClassificationResult(category="Ruido", urgency="Media", summary="resumen de la IA",
                                entities=[EntityAssignment(code="juez_paz", responsibility="Mediar")])


def test_classify_usa_el_modelo_de_reserva_si_el_principal_falla(monkeypatch):
    _con_gemini(monkeypatch)
    llamadas = []

    def falso(description, category_hint, photo, photo_mime, model=None, thinking_budget=None):
        llamadas.append((model, thinking_budget))
        if model == "modelo-principal":
            raise TimeoutError("The read operation timed out")
        return _respuesta_ia()

    monkeypatch.setattr(classifier, "classify_with_gemini", falso)
    outcome = classify("fiesta con música hasta las 3 de la mañana")
    assert outcome.source == "gemini"
    assert outcome.model == "modelo-reserva"
    assert outcome.error is None
    assert outcome.result.entities[0].code == "JUEZ_PAZ"  # _sanitize normaliza el código
    assert llamadas == [("modelo-principal", 0), ("modelo-reserva", None)]


def test_classify_no_llama_a_la_reserva_si_el_principal_responde(monkeypatch):
    _con_gemini(monkeypatch)
    llamadas = []

    def falso(description, category_hint, photo, photo_mime, model=None, thinking_budget=None):
        llamadas.append(model)
        return _respuesta_ia()

    monkeypatch.setattr(classifier, "classify_with_gemini", falso)
    outcome = classify("fiesta con música hasta las 3 de la mañana")
    assert outcome.model == "modelo-principal"
    assert llamadas == ["modelo-principal"]


def test_classify_cae_a_reglas_si_todos_los_modelos_fallan(monkeypatch):
    """Con la cuota diaria agotada en todos los modelos, el reporte se clasifica igual (RNF-02)."""
    _con_gemini(monkeypatch)
    llamadas = []

    def falso(description, category_hint, photo, photo_mime, model=None, thinking_budget=None):
        llamadas.append(model)
        raise RuntimeError(f"429 RESOURCE_EXHAUSTED en {model}")

    monkeypatch.setattr(classifier, "classify_with_gemini", falso)
    outcome = classify("asalto con arma en la entrada del edificio")
    assert outcome.source == "reglas"
    assert outcome.model is None
    assert llamadas == ["modelo-principal", "modelo-reserva", "modelo-reserva-2"]
    assert all(f"{model}: RuntimeError" in outcome.error for model in llamadas)
    assert outcome.result.category == "Seguridad"
