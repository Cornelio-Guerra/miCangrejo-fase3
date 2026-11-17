"""Panel de la JDL. ADR-06 / RF-11 / CU-07 — no implementado en la Fase 3: CU-07 no es uno de los tres
casos seleccionados. Punto único donde enchufar la autenticación: `require_admin`."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import Entidad
from app.schemas.report import (
    DeriveIn, PaginatedReports, ParticipationCreate, ParticipationOut, ParticipationPatch, ReportOut, ReportPatch,
    RoutingRuleIn, RoutingRuleOut, SendOut, StatsOut,
)
from app.services import servicio_expedientes
from app.services.catalog_service import categories, entities_map, entity_by_code
from pydantic import BaseModel, Field


def require_admin() -> None:
    """ADR-06 / RF-11 / CU-07 — no implementado en la Fase 3: CU-07 no es uno de los tres casos
    seleccionados. Punto único donde enchufar la autenticación."""
    return None


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/reports", response_model=PaginatedReports, summary="Listado paginado con filtros para mapa e indicadores")
def list_reports(
    status_: str | None = Query(None, alias="status"), category: str | None = None, urgency: str | None = None,
    date_from: datetime | None = Query(None, alias="from"), date_to: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session),
) -> PaginatedReports:
    return servicio_expedientes.listar_expedientes(session, status=status_, category=category, urgency=urgency,
                                   date_from=date_from, date_to=date_to, page=page, page_size=page_size)


@router.get("/reports/{case_id}", response_model=ReportOut)
def get_report(case_id: int, session: Session = Depends(get_session)) -> ReportOut:
    return servicio_expedientes.armar_salida(session, servicio_expedientes.obtener_expediente_o_404(session, case_id))


@router.patch("/reports/{case_id}", response_model=ReportOut, summary="Corrige clasificación / valida")
def patch_report(case_id: int, patch: ReportPatch, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.validar_o_corregir(session, servicio_expedientes.obtener_expediente_o_404(session, case_id), patch)
    return servicio_expedientes.armar_salida(session, case)


@router.post("/reports/{case_id}/classify", response_model=ReportOut, summary="Reintenta la clasificación con IA")
def classify_again(case_id: int, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.clasificar(session, servicio_expedientes.obtener_expediente_o_404(session, case_id))
    return servicio_expedientes.armar_salida(session, case)


@router.post("/reports/{case_id}/entities", response_model=ReportOut, status_code=status.HTTP_201_CREATED,
             summary="Agrega una entidad competente al expediente")
def add_entity(case_id: int, data: ParticipationCreate, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.obtener_expediente_o_404(session, case_id)
    servicio_expedientes.agregar_participacion(session, case, data)
    return servicio_expedientes.armar_salida(session, session.get(type(case), case_id))


@router.patch("/reports/{case_id}/entities/{ceid}", response_model=ReportOut,
              summary="Cambia el estado de una participación (409 si la transición no es válida)")
def patch_entity(case_id: int, ceid: int, patch: ParticipationPatch, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.obtener_expediente_o_404(session, case_id)
    servicio_expedientes.registrar_estado(session, case, ceid, patch)
    return servicio_expedientes.armar_salida(session, session.get(type(case), case_id))


@router.post("/reports/{case_id}/entities/{ceid}/derive", response_model=ReportOut,
             summary="Deriva a otra entidad: la origen queda Derivada con fecha, la destino nace con recepción")
def derive_entity(case_id: int, ceid: int, data: DeriveIn, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.obtener_expediente_o_404(session, case_id)
    servicio_expedientes.derivar(session, case, ceid, data)
    return servicio_expedientes.armar_salida(session, session.get(type(case), case_id))


@router.post("/reports/{case_id}/send", response_model=SendOut,
             summary="Envía el correo a las participaciones pendientes (503 si ninguna pudo enviarse)")
def send_report(case_id: int, session: Session = Depends(get_session)) -> SendOut:
    return servicio_expedientes.enviar_a_entidades(session, servicio_expedientes.obtener_expediente_o_404(session, case_id))


@router.get("/stats", response_model=StatsOut, summary="Tablero de cumplimiento por entidad")
def get_stats(session: Session = Depends(get_session)) -> StatsOut:
    return servicio_expedientes.tablero(session)


@router.get("/routing", response_model=list[RoutingRuleOut])
def get_routing(session: Session = Depends(get_session)) -> list[RoutingRuleOut]:
    return servicio_expedientes.reglas_enrutamiento(session)


@router.put("/routing", response_model=list[RoutingRuleOut], summary="Reemplaza la tabla categoría → entidad → responsabilidad")
def put_routing(rules: list[RoutingRuleIn], session: Session = Depends(get_session)) -> list[RoutingRuleOut]:
    return servicio_expedientes.reemplazar_enrutamiento(session, rules)


class EntityOut(BaseModel):
    code: str
    name: str
    email: str
    is_active: bool


class EntityPatch(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    is_active: bool | None = None


@router.get("/entities", response_model=list[EntityOut])
def list_entities(session: Session = Depends(get_session)) -> list[EntityOut]:
    return [EntityOut(code=e.code, name=e.name, email=e.email, is_active=e.is_active)
            for e in sorted(entities_map(session).values(), key=lambda e: e.code)]


@router.patch("/entities/{code}", response_model=EntityOut, summary="Edita nombre/correo de una entidad (buzones de demo)")
def patch_entity_catalog(code: str, patch: EntityPatch, session: Session = Depends(get_session)) -> EntityOut:
    entity = entity_by_code(session, code)
    if not entity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe la entidad {code}")
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return EntityOut(code=entity.code, name=entity.name, email=entity.email, is_active=entity.is_active)


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    return categories()
