"""Tablas del expediente (Fase 2 · RF-01, RF-05, RF-06, RF-07; ADR-02)."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; las tratamos como UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _dt_column(nullable: bool = True) -> Column:
    return Column(DateTime(timezone=True), nullable=nullable)


class EstadoExpediente(StrEnum):
    """Estado del expediente. Se CALCULA a partir de las participaciones."""

    RECIBIDO = "Recibido"
    EN_GESTION = "En gestión"
    ENVIADO = "Enviado a entidades"
    RESUELTO = "Resuelto"


class EstadoParticipacion(StrEnum):
    """Estado de cada entidad dentro del expediente."""

    ASIGNADA = "Asignada"        # propuesta por la clasificación, aún sin enviar
    RECIBIDA = "Recibida"        # el correo salió: la entidad tiene el caso
    EN_ATENCION = "En atención"
    DERIVADA = "Derivada"        # terminal para esta entidad; la nueva nace Asignada
    RESUELTA = "Resuelta"


PARTICIPACION_CERRADA = {EstadoParticipacion.DERIVADA, EstadoParticipacion.RESUELTA}


class EstadoClasificacion(StrEnum):
    PENDIENTE = "pendiente"
    LISTA = "lista"
    PROVISIONAL = "provisional"  # clasificada por reglas, no por IA
    FALLIDA = "fallida"


class EstadoCorreo(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    SIMULADO = "simulado"        # modo de contingencia: no hay SMTP configurado
    FALLIDO = "fallido"


class Urgencia(StrEnum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"


class Entidad(SQLModel, table=True):
    __tablename__ = "entities"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=40)
    name: str = Field(max_length=160)
    email: str = Field(max_length=160)
    is_active: bool = True


class ReglaEnrutamiento(SQLModel, table=True):
    """categoría → entidad → responsabilidad (RF-05; catálogo configurable, RNF-09)."""

    __tablename__ = "routing_rules"

    id: int | None = Field(default=None, primary_key=True)
    category: str = Field(index=True, max_length=80)
    entity_id: int = Field(foreign_key="entities.id")
    responsibility: str = Field(max_length=240)
    position: int = 0


class Expediente(SQLModel, table=True):
    __tablename__ = "cases"

    id: int | None = Field(default=None, primary_key=True)
    folio: str | None = Field(default=None, index=True, unique=True, max_length=20)
    description: str = Field(max_length=2000)
    category: str | None = Field(default=None, max_length=80)
    urgency: str | None = Field(default=None, max_length=20)
    summary: str | None = Field(default=None, max_length=600)
    location_label: str = Field(max_length=160)
    latitude: float | None = None
    longitude: float | None = None
    photo_path: str | None = Field(default=None, max_length=300)
    ticket_311: str | None = Field(default=None, max_length=40)
    source: str = Field(default="web", max_length=20)          # web | whatsapp | telegram
    reporter_contact: str | None = Field(default=None, max_length=160)  # nunca se envía a la IA
    reports_count: int = 1
    merged_into_id: int | None = Field(default=None, foreign_key="cases.id")  # agrupado en otro expediente (RF-03)
    status: str = Field(default=EstadoExpediente.RECIBIDO, index=True, max_length=40)
    classification_status: str = Field(default=EstadoClasificacion.PENDIENTE, max_length=20)
    classification_source: str | None = Field(default=None, max_length=20)  # gemini | reglas
    classification_error: str | None = Field(default=None, max_length=300)
    validated_at: datetime | None = Field(default=None, sa_column=_dt_column())
    created_at: datetime = Field(default_factory=utcnow, sa_column=_dt_column(nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=_dt_column(nullable=False))


class BorradorTelegram(SQLModel, table=True):
    """Borrador conversacional de un reporte iniciado por Telegram."""

    __tablename__ = "telegram_drafts"

    chat_id: str = Field(primary_key=True, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    location_label: str | None = Field(default=None, max_length=160)
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_column=_dt_column(nullable=False))


class Participacion(SQLModel, table=True):
    """Una fila por entidad competente dentro de un expediente (RF-05, RF-06, RF-07)."""

    __tablename__ = "case_entities"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="cases.id", index=True)
    entity_id: int = Field(foreign_key="entities.id", index=True)
    responsibility: str = Field(max_length=240)
    status: str = Field(default=EstadoParticipacion.ASIGNADA, max_length=20)
    note: str | None = Field(default=None, max_length=600)
    received_at: datetime | None = Field(default=None, sa_column=_dt_column())
    attention_at: datetime | None = Field(default=None, sa_column=_dt_column())
    derived_at: datetime | None = Field(default=None, sa_column=_dt_column())
    resolved_at: datetime | None = Field(default=None, sa_column=_dt_column())
    derived_to_entity_id: int | None = Field(default=None, foreign_key="entities.id")
    derived_from_id: int | None = Field(default=None, foreign_key="case_entities.id")
    email_status: str = Field(default=EstadoCorreo.PENDIENTE, max_length=20)
    email_sent_at: datetime | None = Field(default=None, sa_column=_dt_column())
    email_error: str | None = Field(default=None, max_length=300)
    created_at: datetime = Field(default_factory=utcnow, sa_column=_dt_column(nullable=False))


class EventoHistorial(SQLModel, table=True):
    """Quién, qué y cuándo (RF-06, ADR-05: historial de solo inserción), por expediente y por participación."""

    __tablename__ = "status_history"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="cases.id", index=True)
    case_entity_id: int | None = Field(default=None, foreign_key="case_entities.id")
    event: str = Field(max_length=40)
    previous: str | None = Field(default=None, max_length=40)
    new: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    actor: str = Field(default="sistema", max_length=20)   # sistema | ia | jdl | entidad
    created_at: datetime = Field(default_factory=utcnow, sa_column=_dt_column(nullable=False))
