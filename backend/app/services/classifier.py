"""Clasificación del reporte: Gemini con salida estructurada y fallback por reglas.

Se llama de forma SÍNCRONA dentro del POST (ADR-03): en Vercel no hay
tareas en segundo plano fiables. Si Gemini falla, tarda o no está configurado,
las reglas por palabras clave clasifican el reporte y el flujo no se detiene (RNF-02).
A la IA solo se envían el texto y la foto del reporte, nunca datos del vecino (RNF-04).
"""

import logging
import unicodedata

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.catalog_service import load_catalog

log = logging.getLogger("micangrejo.classifier")


class EntityAssignment(BaseModel):
    code: str = Field(description="Código de la entidad, exactamente uno del catálogo")
    responsibility: str = Field(description="Qué le corresponde hacer a esa entidad en este caso")


class ClassificationResult(BaseModel):
    category: str = Field(description="Una categoría del catálogo")
    urgency: str = Field(description="Baja, Media o Alta")
    summary: str = Field(description="Resumen del problema en una o dos frases, en español")
    entities: list[EntityAssignment] = Field(description="Todas las entidades competentes, al menos una")


class ClassificationOutcome(BaseModel):
    result: ClassificationResult
    source: str            # gemini | reglas
    model: str | None = None   # modelo de Gemini que respondió (principal o de reserva)
    error: str | None = None


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def classify_by_rules(description: str, category_hint: str | None = None) -> ClassificationResult:
    catalog = load_catalog()
    text = _fold(description)
    scores: dict[str, int] = {}
    for category, words in catalog["keywords"].items():
        hits = sum(1 for w in words if _fold(w) in text)
        if hits:
            scores[category] = hits
    if category_hint and category_hint in catalog["categories"]:
        scores[category_hint] = scores.get(category_hint, 0) + 2
    category = max(scores, key=scores.get) if scores else "Otro"

    urgency = "Media"
    if any(_fold(w) in text for w in catalog["urgency_keywords"]["Alta"]):
        urgency = "Alta"
    elif any(_fold(w) in text for w in catalog["urgency_keywords"]["Baja"]):
        urgency = "Baja"

    entities = [
        EntityAssignment(code=r["entity"], responsibility=r["responsibility"])
        for r in catalog["routing"]
        if r["category"] == category
    ] or [EntityAssignment(code="ALCALDIA", responsibility="Canalizar a la entidad competente")]

    summary = description.strip()
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "…"
    return ClassificationResult(category=category, urgency=urgency, summary=summary, entities=entities)


def _build_prompt(description: str, category_hint: str | None) -> str:
    catalog = load_catalog()
    entities = "\n".join(f"- {e['code']}: {e['name']}" for e in catalog["entities"])
    routing = "\n".join(
        f"- {r['category']} → {r['entity']} ({r['responsibility']})" for r in catalog["routing"]
    )
    hint = f"\nEl vecino sugirió la categoría: {category_hint}." if category_hint else ""
    return f"""Eres el clasificador de reportes vecinales de miCangrejo, plataforma de la Junta de
Desarrollo Local de El Cangrejo (Ciudad de Panamá). Clasifica el reporte y decide qué entidades
públicas son competentes. Un caso puede involucrar a VARIAS entidades; incluye todas las que
deban actuar, cada una con su responsabilidad concreta.

Categorías permitidas: {", ".join(catalog["categories"])}.
Urgencia: Baja, Media o Alta (Alta solo si hay riesgo para personas o daño en curso).

Entidades disponibles (usa el código exacto):
{entities}

Enrutamiento habitual (guía, no obligación):
{routing}
{hint}
Reporte del vecino:
\"\"\"{description.strip()}\"\"\"
"""


def classify_with_gemini(description: str, category_hint: str | None, photo: bytes | None,
                         photo_mime: str | None, model: str | None = None,
                         thinking_budget: int | None = None) -> ClassificationResult:
    from google import genai
    from google.genai import types

    settings = get_settings()
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_s * 1000)),
    )
    parts: list = [types.Part.from_text(text=_build_prompt(description, category_hint))]
    if photo and photo_mime:
        parts.append(types.Part.from_bytes(data=photo, mime_type=photo_mime))
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClassificationResult,
            temperature=0,
            # Sin presupuesto de razonamiento el modelo responde en segundos; con razonamiento libre
            # gemini-3.8-flash supera el timeout en una clasificación de este tamaño.
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget) if thinking_budget is not None else None,
        ),
    )
    return ClassificationResult.model_validate_json(response.text)


def _model_attempts(settings) -> list[tuple[str, int | None]]:
    """Principal (con el presupuesto de razonamiento configurado) y las reservas, en orden, sin repetir.

    Las reservas van sin `thinking_config`: los modelos «lite» rechazan con 400 un presupuesto explícito.
    """
    attempts = [(settings.gemini_model, settings.gemini_thinking_budget)]
    vistos = {settings.gemini_model}
    for model in settings.gemini_fallback_models:
        if model and model not in vistos:
            attempts.append((model, None))
            vistos.add(model)
    return attempts


def _sanitize(result: ClassificationResult) -> ClassificationResult:
    """La IA solo puede devolver códigos y categorías del catálogo."""
    catalog = load_catalog()
    valid_codes = {e["code"] for e in catalog["entities"]}
    entities = [e for e in result.entities if e.code.upper() in valid_codes]
    for e in entities:
        e.code = e.code.upper()
    if not entities:
        raise ValueError("la IA no devolvió ninguna entidad válida")
    category = result.category if result.category in catalog["categories"] else "Otro"
    urgency = result.urgency.capitalize() if result.urgency else "Media"
    if urgency not in {"Baja", "Media", "Alta"}:
        urgency = "Media"
    return ClassificationResult(
        category=category, urgency=urgency, summary=result.summary[:600], entities=entities
    )


def classify(description: str, category_hint: str | None = None, photo: bytes | None = None,
             photo_mime: str | None = None) -> ClassificationOutcome:
    settings = get_settings()
    if not settings.gemini_enabled:
        return ClassificationOutcome(result=classify_by_rules(description, category_hint), source="reglas",
                                     error="GEMINI_API_KEY no configurada (modo de contingencia)")
    errors: list[str] = []
    for model, thinking_budget in _model_attempts(settings):
        try:
            result = _sanitize(classify_with_gemini(description, category_hint, photo, photo_mime,
                                                    model=model, thinking_budget=thinking_budget))
            return ClassificationOutcome(result=result, source="gemini", model=model)
        except Exception as exc:  # timeout, 503 por demanda, 429, red, JSON inválido, modelo inexistente…
            log.warning("Gemini (%s) falló: %s", model, exc)
            errors.append(f"{model}: {type(exc).__name__}: {str(exc)[:160]}")
    log.warning("Ningún modelo de Gemini respondió; se clasifica por reglas")
    return ClassificationOutcome(result=classify_by_rules(description, category_hint), source="reglas",
                                 error=" | ".join(errors))
