from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.schemas.waste_site import WasteSite, WasteSiteCollection
from app.services import waste_site_service


router = APIRouter(prefix="/waste-sites", tags=["waste sites"])


@router.get("", response_model=WasteSiteCollection)
def list_waste_sites() -> WasteSiteCollection:
    return waste_site_service.get_waste_site_collection()


@router.get("/geojson")
def get_waste_sites_geojson() -> dict[str, object]:
    return waste_site_service.get_waste_sites_geojson()


@router.get("/{site_id}/image")
def get_waste_site_image(site_id: str) -> Response:
    image = waste_site_service.get_waste_site_image(site_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no disponible")

    content, media_type = image
    return Response(content=content, media_type=media_type)


@router.get("/{site_id}", response_model=WasteSite)
def get_waste_site(site_id: str) -> WasteSite:
    site = waste_site_service.get_waste_site(site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado")
    return site
