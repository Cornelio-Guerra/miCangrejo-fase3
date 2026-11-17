"""Deja la base con seis expedientes de demostración coherentes para el pitch.

Borra TODOS los expedientes (y las fotos del bucket de evidencias) y los sustituye por:

  1. Basura en Vía Argentina — dos entidades; la AAUD lleva 8 días sin atender (vencida).
  2. Duplicado del anterior — queda agrupado en el expediente 1 (reports_count = 2).
  3. Ruido en un PH — la Policía lo deriva a la Alcaldía (permiso municipal).
  4. Alumbrado apagado con ticket 311 — la Alcaldía deriva a ENSA y ENSA lo resuelve.
  5. Carro sobre la acera — recién recibido, pendiente de validar por la JDL.
  6. Intento de robo en un PH — urgente, la Policía en atención.

Pasa por los mismos servicios que la API (clasificación, agrupación, envío, derivación),
así que el historial de cada expediente es real; solo las fechas se retrasan al final
para que parezca una semana de uso. Por defecto los correos se generan en modo de
contingencia (quedan como "simulado"); con `--correo-real` salen por el SMTP del .env
(todos al buzón de MAIL_DEMO_OVERRIDE_TO) y quedan como "enviado".

Uso (desde backend/, con el .env apuntando a la base que quieres poblar):
    python scripts/sembrar_demo.py                          # muestra qué haría
    python scripts/sembrar_demo.py --confirmar              # correos simulados
    python scripts/sembrar_demo.py --confirmar --correo-real
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Las variables deben fijarse antes de importar `app` (Settings se lee una sola vez).
CORREO_REAL = "--correo-real" in sys.argv
if not CORREO_REAL:  # sin SMTP el mailer marca los correos como "simulado"
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASSWORD"] = ""
os.environ["GEMINI_API_KEY"] = ""  # clasificación por reglas: determinista y sin gastar cuota

from sqlmodel import Session, select, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.database import engine, initialize_database  # noqa: E402
from app.models import Expediente, Participacion, EstadoParticipacion  # noqa: E402
from app.schemas.report import DeriveIn, ParticipationPatch, ReportCreate, ReportPatch  # noqa: E402
from app.services import servicio_expedientes as cs  # noqa: E402
from app.services.catalog_service import entities_map  # noqa: E402

ARGENTINA = {"label": "Vía Argentina con Calle Eusebio A. Morales", "latitude": 8.9898, "longitude": -79.5276}

CASOS = [
    {
        "clave": "basura",
        "payload": {
            "description": "Contenedor desbordado y bolsas rotas en la esquina de Vía Argentina con Calle Eusebio A. "
                           "Morales; llevan cuatro días sin recoger y hay mal olor",
            "location": ARGENTINA,
        },
        "urgencia": "Alta", "creado_hace": 9,
        "pasos": [("recibida", "AAUD"), ("recibida", "ALCALDIA"),
                  ("en_atencion", "ALCALDIA", "La Alcaldía envió inspector; el contenedor pertenece a la AAUD")],
        "recibido_hace": {"AAUD": 8, "ALCALDIA": 3},
    },
    {
        "clave": "duplicado",
        "payload": {
            "description": "Otra vez la basura acumulada en la misma esquina de Vía Argentina, los perros la riegan por la acera",
            "location": {**ARGENTINA, "label": "Vía Argentina con Eusebio A. Morales", "latitude": 8.98985},
        },
        "creado_hace": 2, "pasos": [],
    },
    {
        "clave": "ruido",
        "payload": {
            "description": "Fiesta con música a todo volumen en el PH Torres de Bella Vista todos los viernes hasta "
                           "las 3 de la mañana; ya son tres semanas seguidas",
            "location": {"label": "Calle 52 Este, PH Torres de Bella Vista", "latitude": 8.9845, "longitude": -79.5160},
        },
        "creado_hace": 5,
        "pasos": [("recibida", "JUEZ_PAZ"), ("recibida", "POLICIA"),
                  ("derivar", "POLICIA", "ALCALDIA", "Verificar permiso municipal del local y aplicar sanción",
                   "La Policía informa que el local tiene permiso de eventos; corresponde a la Alcaldía"),
                  ("recibida", "ALCALDIA")],
        "recibido_hace": {"JUEZ_PAZ": 4, "POLICIA": 4, "ALCALDIA": 2}, "derivado_hace": 2,
    },
    {
        "clave": "alumbrado",
        "payload": {
            "description": "Poste de alumbrado apagado frente al Parque Andrés Bello; la acera queda a oscuras y los "
                           "vecinos evitan pasar de noche",
            "location": {"label": "Parque Andrés Bello, Vía Argentina", "latitude": 8.9924, "longitude": -79.5221},
            "ticket_311": "CAC-2026-0412337",
        },
        "creado_hace": 7,
        "pasos": [("recibida", "ALCALDIA"),
                  ("derivar", "ALCALDIA", "ENSA", "Reposición de luminaria y revisión del circuito",
                   "El poste pertenece a la red de ENSA"),
                  ("recibida", "ENSA"),
                  ("resuelta", "ENSA", "Luminaria repuesta; el vecino confirmó que enciende")],
        "recibido_hace": {"ALCALDIA": 6, "ENSA": 4}, "derivado_hace": 4, "resuelto_hace": 1,
    },
    {
        "clave": "estacionamiento",
        "payload": {
            "description": "Carro estacionado sobre la acera de Calle 50 bloqueando el paso de peatones y coches de "
                           "bebé desde ayer",
            "location": {"label": "Calle 50 con Vía Argentina, frente a la farmacia", "latitude": 8.9905, "longitude": -79.5240},
        },
        "creado_hace": 0, "pasos": [], "sin_validar": True,
    },
    {
        "clave": "seguridad",
        "payload": {
            "description": "Personas sospechosas forzando la reja del PH Vista Hermosa de madrugada, parece un intento "
                           "de robo; hay una cámara que lo grabó",
            "location": {"label": "Calle 55 Este, PH Vista Hermosa", "latitude": 8.9815, "longitude": -79.5190},
        },
        "urgencia": "Alta", "creado_hace": 2,
        "pasos": [("recibida", "POLICIA"), ("en_atencion", "POLICIA", "Patrulla asignada; se pidió el video al PH")],
        "recibido_hace": {"POLICIA": 2},
    },
]


def _participacion(session: Session, case: Expediente, code: str) -> Participacion:
    codigos = {eid: e.code for eid, e in entities_map(session).items()}
    for p in cs.participaciones_de(session, case.id):
        if p.status != EstadoParticipacion.DERIVADA and codigos[p.entity_id] == code:
            return p
    raise SystemExit(f"{case.folio}: no hay participación activa de {code} (clasificó como {case.category})")


def vaciar(session: Session) -> None:
    for tabla in ("status_history", "case_entities", "cases"):
        session.exec(text(f"DELETE FROM {tabla}"))
    if get_settings().uses_postgres:
        for seq in ("cases_id_seq", "case_entities_id_seq", "status_history_id_seq"):
            session.exec(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
    else:
        session.exec(text("DELETE FROM sqlite_sequence WHERE name IN ('cases', 'case_entities', 'status_history')"))
    session.commit()


def vaciar_fotos() -> None:
    if not get_settings().storage_enabled:
        return
    from app.services.storage_service import _bucket
    objetos = _bucket().list("casos")
    if objetos:
        _bucket().remove([f"casos/{o['name']}" for o in objetos])
    print(f"  fotos borradas del bucket: {len(objetos)}")


def sembrar(session: Session) -> list[tuple[dict, Expediente]]:
    creados = []
    for spec in CASOS:
        case = cs.registrar_reporte(session, ReportCreate(**spec["payload"]))
        creados.append((spec, case))
        if case.merged_into_id or spec.get("sin_validar"):
            continue
        patch = ReportPatch(validated=True, **({"urgency": spec["urgencia"]} if spec.get("urgencia") else {}))
        cs.validar_o_corregir(session, case, patch)
        cs.enviar_a_entidades(session, case)
        for paso in spec["pasos"]:
            accion, code = paso[0], paso[1]
            if accion == "recibida":
                cs.registrar_estado(session, case, _participacion(session, case, code).id,
                                       ParticipationPatch(status=EstadoParticipacion.RECIBIDA))
            elif accion == "en_atencion":
                cs.registrar_estado(session, case, _participacion(session, case, code).id,
                                       ParticipationPatch(status=EstadoParticipacion.EN_ATENCION, note=paso[2]))
            elif accion == "resuelta":
                cs.registrar_estado(session, case, _participacion(session, case, code).id,
                                       ParticipationPatch(status=EstadoParticipacion.RESUELTA, note=paso[2]))
            elif accion == "derivar":
                cs.derivar(session, case, _participacion(session, case, code).id,
                          DeriveIn(to_entity_code=paso[2], responsibility=paso[3], note=paso[4]))
        session.refresh(case)
    return creados


def retrasar_fechas(session: Session, creados: list[tuple[dict, Expediente]]) -> None:
    """Mueve las fechas al pasado para que el tablero muestre plazos reales (vencidos, promedios)."""
    def hace(dias: float) -> str:
        return f"CURRENT_TIMESTAMP - INTERVAL '{dias} days'" if get_settings().uses_postgres \
            else f"datetime('now', '-{dias} days')"

    for spec, case in creados:
        d = spec["creado_hace"]
        session.exec(text(f"UPDATE cases SET created_at = {hace(d)}, updated_at = {hace(max(d - 1, 0))} WHERE id = {case.id}"))
        session.exec(text(f"UPDATE status_history SET created_at = {hace(d)} WHERE case_id = {case.id}"))
        session.exec(text(f"UPDATE case_entities SET created_at = {hace(d)}, email_sent_at = {hace(d)} WHERE case_id = {case.id}"))
        for code, dias in spec.get("recibido_hace", {}).items():
            session.exec(text(
                f"UPDATE case_entities SET received_at = {hace(dias)}, "
                f"attention_at = CASE WHEN attention_at IS NULL THEN NULL ELSE {hace(max(dias - 1, 0))} END "
                f"WHERE case_id = {case.id} AND received_at IS NOT NULL "
                f"AND entity_id = (SELECT id FROM entities WHERE code = '{code}')"))
        if "derivado_hace" in spec:
            session.exec(text(f"UPDATE case_entities SET derived_at = {hace(spec['derivado_hace'])} "
                              f"WHERE case_id = {case.id} AND derived_at IS NOT NULL"))
        if "resuelto_hace" in spec:
            session.exec(text(f"UPDATE case_entities SET resolved_at = {hace(spec['resuelto_hace'])} "
                              f"WHERE case_id = {case.id} AND resolved_at IS NOT NULL"))
            session.exec(text(f"UPDATE cases SET updated_at = {hace(spec['resuelto_hace'])} WHERE id = {case.id}"))
    session.commit()


def resumen(session: Session) -> None:
    tablero = cs.tablero(session)
    print(f"\n  expedientes: {tablero.total_cases} · {dict(tablero.by_status)}")
    for e in tablero.entities:
        if e.open_cases or e.resolved or e.overdue:
            print(f"    {e.entity.code:9} abiertos {e.open_cases} · vencidos {e.overdue} · resueltos {e.resolved}"
                  f" · derivados>1 {e.derived_more_than_once}")
    for case in session.exec(select(Expediente).order_by(Expediente.id)).all():
        out = cs.armar_salida(session, case)
        print(f"  {out.folio} · {out.status} · {out.classification.category}"
              f" · {[(p.entity.code, p.status, p.email_status) for p in out.participations]}"
              + (f" · agrupado en {out.merged_into}" if out.merged_into else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirmar", action="store_true", help="borra los expedientes actuales y siembra la demo")
    parser.add_argument("--correo-real", action="store_true",
                        help="envía los correos por el SMTP del .env (a MAIL_DEMO_OVERRIDE_TO) en vez de simularlos")
    args = parser.parse_args()
    settings = get_settings()
    destino = "Postgres (Supabase)" if settings.uses_postgres else "SQLite local"
    fotos = f"bucket {settings.supabase_bucket}" if settings.storage_enabled else "sin Storage"
    if args.correo_real and not settings.smtp_enabled:
        raise SystemExit("--correo-real requiere SMTP_USER y SMTP_PASSWORD en el .env")
    correo = f"real por {settings.smtp_host} → {settings.mail_demo_override_to or 'destinatarios reales'}" \
        if args.correo_real else "simulado"
    print(f"Base de datos: {destino} · fotos: {fotos} · correo: {correo}")
    initialize_database()
    with Session(engine) as session:
        actuales = session.exec(text("SELECT count(*) FROM cases")).one()[0]
        print(f"Expedientes actuales: {actuales} → se sustituirán por {len(CASOS)} de demostración.")
        if not args.confirmar:
            print("Nada cambiado. Repite con --confirmar para ejecutar.")
            return
        vaciar(session)
        vaciar_fotos()
        creados = sembrar(session)
        retrasar_fechas(session, creados)
        resumen(session)


if __name__ == "__main__":
    main()
