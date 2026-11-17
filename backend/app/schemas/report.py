"""Entradas y salidas de la API según docs/api-contract.md + issues #3 y #4."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import EstadoParticipacion, Urgencia


class ReportLocation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(min_length=2, max_length=160, description="Calle, edificio o referencia")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ReportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(min_length=10, max_length=500)
    location: ReportLocation
    photo_path: str | None = Field(default=None, max_length=300, description="Ruta devuelta por POST /uploads/sign")
    category: str | None = Field(default=None, max_length=80, description="Pista opcional; la IA decide")
    ticket_311: str | None = Field(default=None, max_length=40)

    @field_validator("photo_path", "category", "ticket_311", mode="before")
    @classmethod
    def _vacio_es_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value


class EntityRef(BaseModel):
    code: str
    name: str


class ParticipationOut(BaseModel):
    id: int
    entity: EntityRef
    responsibility: str
    status: str
    note: str | None
    received_at: datetime | None
    attention_at: datetime | None
    derived_at: datetime | None
    resolved_at: datetime | None
    derived_to: EntityRef | None
    email_status: str
    email_sent_at: datetime | None
    email_error: str | None
    days_in_entity: float | None
    overdue: bool


class ClassificationOut(BaseModel):
    category: str | None
    urgency: str | None
    summary: str | None
    status: str
    source: str | None
    error: str | None
    entities: list[dict]


class HistoryOut(BaseModel):
    event: str
    previous: str | None
    new: str | None
    note: str | None
    actor: str
    entity: str | None
    created_at: datetime


class CurrentEntityOut(BaseModel):
    entity: EntityRef
    status: str
    since: datetime | None


class ReportOut(BaseModel):
    id: int
    folio: str
    status: str
    description: str
    location: ReportLocation
    photo_url: str | None
    ticket_311: str | None
    source: str
    reports_count: int
    merged_into: str | None = Field(default=None, description="Folio del expediente principal si este reporte se agrupó")
    classification: ClassificationOut
    current_entities: list[CurrentEntityOut]
    participations: list[ParticipationOut]
    history: list[HistoryOut]
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportSummaryOut(BaseModel):
    """Fila del listado de la JDL (mapa, filtros, indicadores)."""

    id: int
    folio: str
    status: str
    category: str | None
    urgency: str | None
    summary: str | None
    description: str
    location: ReportLocation
    photo_url: str | None
    source: str
    classification_status: str
    entities: list[CurrentEntityOut]
    reports_count: int
    created_at: datetime


class PaginatedReports(BaseModel):
    items: list[ReportSummaryOut]
    total: int
    page: int
    page_size: int


# ---- Administración ---------------------------------------------------------

class ReportPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str | None = Field(default=None, max_length=80)
    urgency: Urgencia | None = None
    summary: str | None = Field(default=None, max_length=600)
    ticket_311: str | None = Field(default=None, max_length=40)
    validated: bool | None = Field(default=None, description="true = la JDL valida la clasificación")


class ParticipationCreate(BaseModel):
    entity_code: str = Field(min_length=2, max_length=40)
    responsibility: str = Field(min_length=3, max_length=240)


class ParticipationPatch(BaseModel):
    status: EstadoParticipacion | None = None
    note: str | None = Field(default=None, max_length=600)


class DeriveIn(BaseModel):
    to_entity_code: str = Field(min_length=2, max_length=40)
    responsibility: str = Field(min_length=3, max_length=240)
    note: str | None = Field(default=None, max_length=600)


class SendResult(BaseModel):
    participation_id: int
    entity: str
    email_status: str
    error: str | None


class SendOut(BaseModel):
    folio: str
    status: str
    results: list[SendResult]


class RoutingRuleIn(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    entity_code: str = Field(min_length=2, max_length=40)
    responsibility: str = Field(min_length=3, max_length=240)


class RoutingRuleOut(RoutingRuleIn):
    id: int
    entity_name: str
    entity_email: str


class EntityStats(BaseModel):
    entity: EntityRef
    open_cases: int
    avg_response_days: float | None
    derived_more_than_once: int
    overdue: int
    resolved: int


class StatsOut(BaseModel):
    sla_dias: int
    total_cases: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    entities: list[EntityStats]
