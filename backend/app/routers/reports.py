from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_session
from app.schemas.report import PaginatedReports, ReportCreate, ReportOut
from app.services import servicio_expedientes

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED,
             summary="Crea un reporte (JSON). La foto va antes por POST /uploads/sign")
def create_report(payload: ReportCreate, session: Session = Depends(get_session)) -> ReportOut:
    case = servicio_expedientes.registrar_reporte(session, payload, source="web")
    return servicio_expedientes.armar_salida(session, case)


@router.get("", response_model=PaginatedReports, summary="Últimos reportes (vista pública resumida)")
def list_reports(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 session: Session = Depends(get_session)) -> PaginatedReports:
    return servicio_expedientes.listar_expedientes(session, status=None, category=None, urgency=None, date_from=None, date_to=None,
                                   page=page, page_size=page_size)


@router.get("/{folio}", response_model=ReportOut, summary="Estado, entidad actual e historial por folio")
def get_report(folio: str, session: Session = Depends(get_session)) -> ReportOut:
    return servicio_expedientes.armar_salida(session, servicio_expedientes.obtener_por_folio(session, folio))
