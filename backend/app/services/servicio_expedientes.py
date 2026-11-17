"""Lógica del expediente: crear, clasificar, agrupar duplicados, participaciones,
derivación con fechas, correo por entidad, estado calculado y tablero (RF-01 a RF-07, RF-09, RF-10)."""

import logging
import math
from datetime import timedelta

from fastapi import HTTPException, status as http
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.models import (
    Expediente, Participacion, EstadoExpediente, EstadoClasificacion, EstadoCorreo, Entidad, EstadoParticipacion,
    ReglaEnrutamiento, EventoHistorial, PARTICIPACION_CERRADA, as_utc, utcnow,
)
from app.schemas.report import (
    ClassificationOut, CurrentEntityOut, DeriveIn, EntityRef, EntityStats, HistoryOut, PaginatedReports,
    ParticipationCreate, ParticipationOut, ParticipationPatch, ReportCreate, ReportLocation, ReportOut,
    ReportPatch, ReportSummaryOut, RoutingRuleIn, RoutingRuleOut, SendOut, SendResult, StatsOut,
)
from app.services import storage_service
from app.services.catalog_service import categories, entities_map, entity_by_code
from app.services.classifier import classify
from app.services.mailer import render_email, send_email

log = logging.getLogger("micangrejo.cases")

RADIO_DUPLICADO_M = 150
VENTANA_DUPLICADO = timedelta(days=7)
PARTICIPACION_ABIERTA = {EstadoParticipacion.ASIGNADA, EstadoParticipacion.RECIBIDA, EstadoParticipacion.EN_ATENCION}
CORREO_ENVIADO = {EstadoCorreo.ENVIADO, EstadoCorreo.SIMULADO}

# Transiciones manuales permitidas por participación (la derivación tiene su endpoint)
TRANSICIONES_PERMITIDAS = {
    EstadoParticipacion.ASIGNADA: {EstadoParticipacion.RECIBIDA},
    EstadoParticipacion.RECIBIDA: {EstadoParticipacion.EN_ATENCION, EstadoParticipacion.RESUELTA},
    EstadoParticipacion.EN_ATENCION: {EstadoParticipacion.RESUELTA},
}


# ===== Utilidades compartidas =====

def _registrar_historial(session: Session, case: Expediente, event: str, *, new: str | None = None, previous: str | None = None,
             note: str | None = None, actor: str = "sistema", participation: Participacion | None = None) -> None:
    session.add(EventoHistorial(
        case_id=case.id, case_entity_id=participation.id if participation else None,
        event=event, previous=previous, new=new, note=(note or None) and note[:2000], actor=actor,
    ))


def participaciones_de(session: Session, case_id: int) -> list[Participacion]:
    return list(session.exec(select(Participacion).where(Participacion.case_id == case_id).order_by(Participacion.id)).all())


def obtener_expediente_o_404(session: Session, case_id: int) -> Expediente:
    case = session.get(Expediente, case_id)
    if not case:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No existe el expediente {case_id}")
    return case


def _participacion_o_404(session: Session, case: Expediente, ceid: int) -> Participacion:
    part = session.get(Participacion, ceid)
    if not part or part.case_id != case.id:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"La participación {ceid} no pertenece al expediente {case.folio}")
    return part


def _rechazar_si_agrupado(session: Session, case: Expediente) -> None:
    if case.merged_into_id:
        principal = session.get(Expediente, case.merged_into_id)
        raise HTTPException(http.HTTP_409_CONFLICT,
                            f"El reporte {case.folio} está agrupado en el expediente {principal.folio if principal else case.merged_into_id}; gestiona ese expediente")



# ===== CU-01 Registrar reporte · RF-01, RF-02, RF-03 =====

def registrar_reporte(session: Session, payload: ReportCreate, *, source: str = "web",
                reporter_contact: str | None = None) -> Expediente:
    case = Expediente(
        description=payload.description, category=payload.category, location_label=payload.location.label,
        latitude=payload.location.latitude, longitude=payload.location.longitude, photo_path=payload.photo_path,
        ticket_311=payload.ticket_311, source=source, reporter_contact=reporter_contact,
    )
    session.add(case)
    session.flush()
    case.folio = f"MC-{as_utc(case.created_at).year}-{case.id:04d}"
    _registrar_historial(session, case, "creado", new=EstadoExpediente.RECIBIDO, note=f"Reporte recibido por {source}")
    session.commit()
    session.refresh(case)

    try:
        clasificar(session, case, actor_note="clasificación inicial")
    except Exception as exc:  # el reporte ya está guardado: nunca se pierde (RNF-02)
        log.exception("clasificación falló para %s", case.folio)
        case.classification_status = EstadoClasificacion.FALLIDA
        case.classification_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        session.add(case)
        session.commit()

    duplicate = _buscar_duplicado(session, case)
    if duplicate:
        # El reporte nuevo se agrupa: sus participaciones propuestas se descartan
        # (sin historial asociado) para que el tablero no las cuente como abiertas.
        for part in participaciones_de(session, case.id):
            session.delete(part)
        duplicate.reports_count += 1
        duplicate.updated_at = utcnow()
        if case.photo_path and not duplicate.photo_path:
            duplicate.photo_path = case.photo_path  # la evidencia nueva sirve al expediente principal
        _registrar_historial(session, duplicate, "duplicado", note=f"Reporte adicional agrupado desde {case.folio}: {case.description[:200]}")
        case.merged_into_id = duplicate.id
        case.status = EstadoExpediente.RESUELTO  # el nuevo se cierra como agrupado; queda inmutable
        _registrar_historial(session, case, "agrupado", new=EstadoExpediente.RESUELTO, note=f"Agrupado en el expediente {duplicate.folio}")
        session.add(duplicate)
        session.add(case)
        session.commit()
        session.refresh(duplicate)
        return duplicate
    return case


def _buscar_duplicado(session: Session, case: Expediente) -> Expediente | None:
    """Mismo problema y lugar en los últimos días → un solo expediente (RF-03)."""
    if case.latitude is None or case.longitude is None or not case.category:
        return None
    since = utcnow() - VENTANA_DUPLICADO
    candidates = session.exec(
        select(Expediente).where(Expediente.id != case.id, Expediente.category == case.category, Expediente.status != EstadoExpediente.RESUELTO)
    ).all()
    for other in candidates:
        if other.latitude is None or other.longitude is None or as_utc(other.created_at) < since:
            continue
        if _distancia_m(case.latitude, case.longitude, other.latitude, other.longitude) <= RADIO_DUPLICADO_M:
            return other
    return None


def _distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def clasificar(session: Session, case: Expediente, *, actor_note: str = "reclasificación") -> Expediente:
    if actor_note != "clasificación inicial":
        _rechazar_si_agrupado(session, case)
    photo = storage_service.download(case.photo_path) if case.photo_path else None
    outcome = classify(case.description, case.category, *(photo or (None, None)))
    result = outcome.result
    previous = f"{case.category or '-'} / {case.urgency or '-'}"
    case.category, case.urgency, case.summary = result.category, result.urgency, result.summary
    case.classification_source = outcome.source
    case.classification_status = EstadoClasificacion.LISTA if outcome.source == "gemini" else EstadoClasificacion.PROVISIONAL
    case.classification_error = outcome.error

    present = {p.entity_id for p in participaciones_de(session, case.id)}
    added: list[str] = []
    for assignment in result.entities:
        entity = entity_by_code(session, assignment.code)
        if entity and entity.id not in present:
            session.add(Participacion(case_id=case.id, entity_id=entity.id, responsibility=assignment.responsibility[:240]))
            present.add(entity.id)
            added.append(entity.code)
    _registrar_historial(
        session, case, "clasificado", previous=previous, new=f"{case.category} / {case.urgency}",
        actor="ia" if outcome.source == "gemini" else "sistema",
        note=f"{actor_note} por {outcome.source}" + (f" ({outcome.model})" if outcome.model else "")
        + (f"; entidades: {', '.join(added)}" if added else "")
        + (f"; aviso: {outcome.error}" if outcome.error else ""),
    )
    recalcular_estado(session, case)
    session.commit()
    session.refresh(case)
    return case



# ===== CU-03 Validar y enviar expediente · RF-04, RF-05 =====

def validar_o_corregir(session: Session, case: Expediente, patch: ReportPatch) -> Expediente:
    _rechazar_si_agrupado(session, case)
    changes = patch.model_dump(exclude_unset=True)
    validated = changes.pop("validated", None)
    if "category" in changes and changes["category"] and changes["category"] not in categories():
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_CONTENT, f"Categoría no válida. Usa: {', '.join(categories())}")
    for field, value in changes.items():
        setattr(case, field, value)
    if changes:
        _registrar_historial(session, case, "corregido", actor="jdl", note=", ".join(f"{k}={v}" for k, v in changes.items()))
    if validated and not case.validated_at:
        case.validated_at = utcnow()
        _registrar_historial(session, case, "validado", actor="jdl", note="La JDL validó la clasificación")
    recalcular_estado(session, case)
    session.commit()
    session.refresh(case)
    return case


def agregar_participacion(session: Session, case: Expediente, data: ParticipationCreate) -> Participacion:
    _rechazar_si_agrupado(session, case)
    entity = entity_by_code(session, data.entity_code)
    if not entity:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No existe la entidad {data.entity_code}")
    for p in participaciones_de(session, case.id):
        if p.entity_id == entity.id and p.status not in PARTICIPACION_CERRADA:
            raise HTTPException(http.HTTP_409_CONFLICT, f"{entity.code} ya participa en este expediente")
    part = Participacion(case_id=case.id, entity_id=entity.id, responsibility=data.responsibility)
    session.add(part)
    session.flush()
    _registrar_historial(session, case, "participacion_agregada", new=part.status, actor="jdl", participation=part,
             note=f"{entity.code}: {data.responsibility}")
    recalcular_estado(session, case)
    session.commit()
    session.refresh(part)
    return part


def enviar_a_entidades(session: Session, case: Expediente) -> SendOut:
    _rechazar_si_agrupado(session, case)
    if not case.validated_at:
        case.validated_at = utcnow()
        _registrar_historial(session, case, "validado", actor="jdl", note="Validación implícita al enviar")
    targets = [p for p in participaciones_de(session, case.id) if p.email_status in {EstadoCorreo.PENDIENTE, EstadoCorreo.FALLIDO}]
    results = [_enviar_a_entidad(session, case, p) for p in targets]
    recalcular_estado(session, case)
    session.commit()
    session.refresh(case)
    out = SendOut(folio=case.folio, status=case.status, results=results)
    if targets and all(r.email_status == EstadoCorreo.FALLIDO for r in results):
        raise HTTPException(http.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"message": "No se pudo enviar ningún correo; el expediente se conserva con envío pendiente",
                                    "results": [r.model_dump() for r in results]})
    return out


def _enviar_a_entidad(session: Session, case: Expediente, part: Participacion) -> SendResult:
    ents = entities_map(session)
    entity = ents[part.entity_id]
    others = [ents[p.entity_id].name for p in participaciones_de(session, case.id) if p.id != part.id and p.status in PARTICIPACION_ABIERTA]
    subject, body = render_email(case, part, entity, storage_service.read_url(case.photo_path), others)
    cc = case.reporter_contact if case.reporter_contact and "@" in case.reporter_contact else None
    status, error = send_email(entity.email, subject, body, cc=cc)
    part.email_status = status
    part.email_error = error if status == EstadoCorreo.FALLIDO else None
    if status in CORREO_ENVIADO:
        part.email_sent_at = utcnow()
        if part.status == EstadoParticipacion.ASIGNADA:
            part.status = EstadoParticipacion.RECIBIDA
            part.received_at = part.email_sent_at
    session.add(part)
    note = f"Correo simulado a {entity.email} (modo de contingencia)\n\n{subject}\n\n{body}" if status == EstadoCorreo.SIMULADO \
        else (f"Correo enviado a {entity.email}" if status == EstadoCorreo.ENVIADO else f"Fallo al enviar a {entity.email}: {error}")
    _registrar_historial(session, case, "correo", new=status, participation=part, note=note)
    return SendResult(participation_id=part.id, entity=entity.code, email_status=status, error=part.email_error)



# ===== CU-04 Registrar seguimiento · RF-06   |   CU-05 Derivar · RF-07 =====

def registrar_estado(session: Session, case: Expediente, ceid: int, patch: ParticipationPatch) -> Participacion:
    part = _participacion_o_404(session, case, ceid)
    if patch.status and patch.status != part.status:
        if part.status in PARTICIPACION_CERRADA:
            raise HTTPException(http.HTTP_409_CONFLICT, f"La participación está {part.status}; no admite cambios")
        if patch.status not in TRANSICIONES_PERMITIDAS.get(EstadoParticipacion(part.status), set()):
            raise HTTPException(http.HTTP_409_CONFLICT,
                                f"Transición inválida: {part.status} → {patch.status}. Para derivar usa /derive")
        now = utcnow()
        previous = part.status
        part.status = patch.status
        if patch.status == EstadoParticipacion.RECIBIDA:
            part.received_at = part.received_at or now
        elif patch.status == EstadoParticipacion.EN_ATENCION:
            part.attention_at = now
        elif patch.status == EstadoParticipacion.RESUELTA:
            part.resolved_at = now
        _registrar_historial(session, case, "estado_participacion", previous=previous, new=part.status, actor="jdl",
                 participation=part, note=patch.note)
    if patch.note is not None:
        part.note = patch.note
    session.add(part)
    recalcular_estado(session, case)
    session.commit()
    session.refresh(part)
    return part


def recalcular_estado(session: Session, case: Expediente) -> None:
    """Estado del expediente CALCULADO (RF-06; estados válidos, ADR-02). Nunca se edita a mano."""
    if case.merged_into_id:
        return  # un reporte agrupado no cambia de estado por sí mismo
    parts = participaciones_de(session, case.id)
    if not parts:
        new = EstadoExpediente.RECIBIDO
    elif all(p.status in PARTICIPACION_CERRADA for p in parts) and any(p.status == EstadoParticipacion.RESUELTA for p in parts):
        new = EstadoExpediente.RESUELTO
    elif any(p.email_status in CORREO_ENVIADO for p in parts):
        new = EstadoExpediente.ENVIADO
    elif case.validated_at:
        new = EstadoExpediente.EN_GESTION
    else:
        new = EstadoExpediente.RECIBIDO
    if new != case.status:
        _registrar_historial(session, case, "estado_expediente", previous=case.status, new=new)
        case.status = new
    case.updated_at = utcnow()
    session.add(case)


def derivar(session: Session, case: Expediente, ceid: int, data: DeriveIn) -> tuple[Participacion, Participacion, SendResult]:
    """RF-07: la entidad origen queda Derivada con fecha; la destino nace con fecha de recepción."""
    origin = _participacion_o_404(session, case, ceid)
    if origin.status not in {EstadoParticipacion.RECIBIDA, EstadoParticipacion.EN_ATENCION}:
        raise HTTPException(http.HTTP_409_CONFLICT,
                            f"Solo se deriva una participación Recibida o En atención (actual: {origin.status})")
    target = entity_by_code(session, data.to_entity_code)
    if not target:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No existe la entidad {data.to_entity_code}")
    if target.id == origin.entity_id:
        raise HTTPException(http.HTTP_409_CONFLICT, "No se puede derivar a la misma entidad")

    now = utcnow()
    previous_status = origin.status
    origin.status = EstadoParticipacion.DERIVADA
    origin.derived_at = now
    origin.derived_to_entity_id = target.id
    if data.note:
        origin.note = data.note
    session.add(origin)

    new = Participacion(case_id=case.id, entity_id=target.id, responsibility=data.responsibility, derived_from_id=origin.id)
    session.add(new)
    session.flush()
    ents = entities_map(session)
    _registrar_historial(session, case, "derivado", previous=previous_status, new=EstadoParticipacion.DERIVADA, actor="jdl",
             participation=origin, note=f"{ents[origin.entity_id].code} deriva a {target.code}: {data.note or data.responsibility}")
    result = _enviar_a_entidad(session, case, new)
    recalcular_estado(session, case)
    session.commit()
    session.refresh(origin)
    session.refresh(new)
    return origin, new, result



# ===== Consultas y tablero · RF-09, RF-10 =====

def obtener_por_folio(session: Session, folio: str) -> Expediente:
    case = session.exec(select(Expediente).where(Expediente.folio == folio.strip().upper())).first()
    if not case:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No existe el folio {folio}")
    return case


def listar_expedientes(session: Session, *, status: str | None, category: str | None, urgency: str | None,
               date_from, date_to, page: int, page_size: int) -> PaginatedReports:
    query = select(Expediente)
    if status:
        query = query.where(Expediente.status == status)
    if category:
        query = query.where(Expediente.category == category)
    if urgency:
        query = query.where(Expediente.urgency == urgency)
    if date_from:
        query = query.where(Expediente.created_at >= date_from)
    if date_to:
        query = query.where(Expediente.created_at <= date_to)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(query.order_by(Expediente.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    ents = entities_map(session)
    items = [_summary(session, c, ents) for c in rows]
    return PaginatedReports(items=items, total=int(total), page=page, page_size=page_size)


def _ref(entity: Entidad) -> EntityRef:
    return EntityRef(code=entity.code, name=entity.name)


def _current_entities(parts: list[Participacion], ents: dict[int, Entidad]) -> list[CurrentEntityOut]:
    return [
        CurrentEntityOut(entity=_ref(ents[p.entity_id]), status=p.status, since=as_utc(p.received_at or p.created_at))
        for p in parts if p.status in PARTICIPACION_ABIERTA and p.entity_id in ents
    ]


def _summary(session: Session, case: Expediente, ents: dict[int, Entidad]) -> ReportSummaryOut:
    parts = participaciones_de(session, case.id)
    return ReportSummaryOut(
        id=case.id, folio=case.folio, status=case.status, category=case.category, urgency=case.urgency,
        summary=case.summary, description=case.description,
        location=ReportLocation(label=case.location_label, latitude=case.latitude, longitude=case.longitude),
        photo_url=storage_service.read_url(case.photo_path), source=case.source,
        classification_status=case.classification_status,
        entities=_current_entities(parts, ents), reports_count=case.reports_count, created_at=as_utc(case.created_at),
    )


def _participation_out(p: Participacion, ents: dict[int, Entidad], sla_days: int) -> ParticipationOut:
    now = utcnow()
    received = as_utc(p.received_at)
    end = as_utc(p.resolved_at) or as_utc(p.derived_at) or now
    days = round((end - received).total_seconds() / 86400, 2) if received else None
    overdue = bool(received and p.status in {EstadoParticipacion.RECIBIDA, EstadoParticipacion.EN_ATENCION}
                   and received + timedelta(days=sla_days) < now)
    return ParticipationOut(
        id=p.id, entity=_ref(ents[p.entity_id]), responsibility=p.responsibility, status=p.status, note=p.note,
        received_at=received, attention_at=as_utc(p.attention_at), derived_at=as_utc(p.derived_at),
        resolved_at=as_utc(p.resolved_at),
        derived_to=_ref(ents[p.derived_to_entity_id]) if p.derived_to_entity_id in ents else None,
        email_status=p.email_status, email_sent_at=as_utc(p.email_sent_at), email_error=p.email_error,
        days_in_entity=days, overdue=overdue,
    )


def armar_salida(session: Session, case: Expediente) -> ReportOut:
    ents = entities_map(session)
    parts = participaciones_de(session, case.id)
    sla = get_settings().sla_dias
    part_by_id = {p.id: p for p in parts}
    history = session.exec(
        select(EventoHistorial).where(EventoHistorial.case_id == case.id).order_by(EventoHistorial.id)
    ).all()
    merged = session.get(Expediente, case.merged_into_id) if case.merged_into_id else None
    return ReportOut(
        id=case.id, folio=case.folio, status=case.status, description=case.description,
        merged_into=merged.folio if merged else None,
        location=ReportLocation(label=case.location_label, latitude=case.latitude, longitude=case.longitude),
        photo_url=storage_service.read_url(case.photo_path), ticket_311=case.ticket_311, source=case.source,
        reports_count=case.reports_count,
        classification=ClassificationOut(
            category=case.category, urgency=case.urgency, summary=case.summary, status=case.classification_status,
            source=case.classification_source, error=case.classification_error,
            entities=[{"code": ents[p.entity_id].code, "name": ents[p.entity_id].name, "responsibility": p.responsibility}
                      for p in parts if p.entity_id in ents],
        ),
        current_entities=_current_entities(parts, ents),
        participations=[_participation_out(p, ents, sla) for p in parts],
        history=[HistoryOut(
            event=h.event, previous=h.previous, new=h.new, note=h.note, actor=h.actor, created_at=as_utc(h.created_at),
            entity=ents[part_by_id[h.case_entity_id].entity_id].code if h.case_entity_id in part_by_id else None,
        ) for h in history],
        validated_at=as_utc(case.validated_at), created_at=as_utc(case.created_at), updated_at=as_utc(case.updated_at),
    )


def tablero(session: Session) -> StatsOut:
    sla = get_settings().sla_dias
    ents = entities_map(session)
    cases = session.exec(select(Expediente)).all()
    parts = session.exec(select(Participacion)).all()
    now = utcnow()

    derivations_per_case: dict[int, int] = {}
    for p in parts:
        if p.status == EstadoParticipacion.DERIVADA:
            derivations_per_case[p.case_id] = derivations_per_case.get(p.case_id, 0) + 1

    per_entity: list[EntityStats] = []
    for eid, entity in ents.items():
        mine = [p for p in parts if p.entity_id == eid]
        open_ = [p for p in mine if p.status in PARTICIPACION_ABIERTA]
        resolved = [p for p in mine if p.status == EstadoParticipacion.RESUELTA and p.received_at and p.resolved_at]
        durations = [(as_utc(p.resolved_at) - as_utc(p.received_at)).total_seconds() / 86400 for p in resolved]
        overdue = [p for p in mine if p.received_at and p.status in {EstadoParticipacion.RECIBIDA, EstadoParticipacion.EN_ATENCION}
                   and as_utc(p.received_at) + timedelta(days=sla) < now]
        multi = len({p.case_id for p in mine if derivations_per_case.get(p.case_id, 0) >= 2})
        per_entity.append(EntityStats(
            entity=_ref(entity), open_cases=len(open_),
            avg_response_days=round(sum(durations) / len(durations), 2) if durations else None,
            derived_more_than_once=multi, overdue=len(overdue), resolved=len(resolved),
        ))

    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for c in cases:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        by_category[c.category or "Sin categoría"] = by_category.get(c.category or "Sin categoría", 0) + 1
    return StatsOut(sla_dias=sla, total_cases=len(cases), by_status=by_status, by_category=by_category, entities=per_entity)



# ===== Catálogo de enrutamiento · RNF-09 =====

def reglas_enrutamiento(session: Session) -> list[RoutingRuleOut]:
    ents = entities_map(session)
    rules = session.exec(select(ReglaEnrutamiento).order_by(ReglaEnrutamiento.category, ReglaEnrutamiento.position)).all()
    return [RoutingRuleOut(id=r.id, category=r.category, entity_code=ents[r.entity_id].code, responsibility=r.responsibility,
                           entity_name=ents[r.entity_id].name, entity_email=ents[r.entity_id].email)
            for r in rules if r.entity_id in ents]


def reemplazar_enrutamiento(session: Session, rules: list[RoutingRuleIn]) -> list[RoutingRuleOut]:
    """PUT completo: reemplaza la tabla (catálogo editable desde el panel, RNF-09)."""
    resolved: list[tuple[RoutingRuleIn, Entidad]] = []
    for rule in rules:
        entity = entity_by_code(session, rule.entity_code)
        if not entity:
            raise HTTPException(http.HTTP_422_UNPROCESSABLE_CONTENT, f"No existe la entidad {rule.entity_code}")
        if rule.category not in categories():
            raise HTTPException(http.HTTP_422_UNPROCESSABLE_CONTENT, f"Categoría no válida: {rule.category}")
        resolved.append((rule, entity))
    for old in session.exec(select(ReglaEnrutamiento)).all():
        session.delete(old)
    for position, (rule, entity) in enumerate(resolved):
        session.add(ReglaEnrutamiento(category=rule.category, entity_id=entity.id, responsibility=rule.responsibility, position=position))
    session.commit()
    return reglas_enrutamiento(session)
