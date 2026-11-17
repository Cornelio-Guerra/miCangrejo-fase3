"""Motor de base de datos con SQLModel.

- Postgres (Supabase): la URL del pooler en modo transacción (puerto 6543) exige
  NullPool (cada invocación serverless abre y cierra su conexión) y desactivar los
  prepared statements de psycopg3, que ese modo no soporta.
- SQLite: modo de contingencia y desarrollo local, sin nada que instalar.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_settings = get_settings()


def _normalize_url(url: str) -> str:
    # Supabase entrega postgresql://…; SQLAlchemy necesita el driver explícito.
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def _build_engine():
    url = _normalize_url(_settings.database_url)
    if url.startswith("postgresql"):
        return create_engine(
            url,
            poolclass=NullPool,
            connect_args={"prepare_threshold": None},
            pool_pre_ping=False,
        )
    if url.startswith("sqlite"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


engine = _build_engine()


def initialize_database() -> None:
    """Crea las tablas si no existen y siembra el catálogo. Se llama al arrancar."""
    import app.models  # noqa: F401  (registra las tablas en SQLModel.metadata)
    from app.services.catalog_service import seed_catalog

    SQLModel.metadata.create_all(engine)
    _ensure_columns()
    with Session(engine) as session:
        seed_catalog(session)


def _ensure_columns() -> None:
    """Migración mínima: agrega columnas nuevas a tablas ya existentes (create_all no lo hace)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}'))


def get_session() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    with Session(engine) as session:
        yield session
