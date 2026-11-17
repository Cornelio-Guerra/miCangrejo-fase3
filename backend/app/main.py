from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database import initialize_database
from app.routers import admin, health, reports, restaurants, uploads, waste_sites, webhooks


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


settings = get_settings()
app = FastAPI(
    title="miCangrejo API",
    version="0.2.0",
    description="Expediente vecinal con estado por entidad, derivación registrada y tablero de cumplimiento (Visión v1.1).",
    lifespan=lifespan,
)

# En Vercel con Services el frontend comparte dominio; CORS solo importa en desarrollo local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router, reports.router, uploads.router, admin.router, webhooks.router,
    waste_sites.router, restaurants.router,
):
    app.include_router(router, prefix="/api/v1")
