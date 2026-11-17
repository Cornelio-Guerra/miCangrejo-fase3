"""Catálogo de entidades, categorías y enrutamiento, sembrado desde catalog.json."""

import json
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, select

from app.models import Entidad, ReglaEnrutamiento

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


@lru_cache
def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def categories() -> list[str]:
    return list(load_catalog()["categories"])


def seed_catalog(session: Session) -> None:
    """Idempotente: solo inserta lo que falta. Nunca pisa correos editados desde el panel."""
    catalog = load_catalog()
    by_code: dict[str, Entidad] = {e.code: e for e in session.exec(select(Entidad)).all()}
    for item in catalog["entities"]:
        if item["code"] not in by_code:
            entity = Entidad(code=item["code"], name=item["name"], email=item["email"])
            session.add(entity)
            session.flush()
            by_code[entity.code] = entity
    if not session.exec(select(ReglaEnrutamiento)).first():
        for position, rule in enumerate(catalog["routing"]):
            session.add(
                ReglaEnrutamiento(
                    category=rule["category"],
                    entity_id=by_code[rule["entity"]].id,
                    responsibility=rule["responsibility"],
                    position=position,
                )
            )
    session.commit()


def entity_by_code(session: Session, code: str) -> Entidad | None:
    return session.exec(select(Entidad).where(Entidad.code == code.strip().upper())).first()


def entities_map(session: Session) -> dict[int, Entidad]:
    return {e.id: e for e in session.exec(select(Entidad)).all()}


def rules_for_category(session: Session, category: str | None) -> list[tuple[Entidad, str]]:
    """[(entidad, responsabilidad)] para una categoría; 'Otro' si no hay regla."""
    if not category:
        category = "Otro"
    rules = session.exec(
        select(ReglaEnrutamiento).where(ReglaEnrutamiento.category == category).order_by(ReglaEnrutamiento.position)
    ).all()
    if not rules:
        rules = session.exec(
            select(ReglaEnrutamiento).where(ReglaEnrutamiento.category == "Otro").order_by(ReglaEnrutamiento.position)
        ).all()
    ents = entities_map(session)
    return [(ents[r.entity_id], r.responsibility) for r in rules if r.entity_id in ents]
