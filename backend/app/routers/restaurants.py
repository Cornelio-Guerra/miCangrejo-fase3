from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.schemas.restaurant import Restaurant, RestaurantCollection
from app.services import restaurant_service


router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=RestaurantCollection)
def list_restaurants() -> RestaurantCollection:
    return restaurant_service.get_restaurant_collection()


@router.get("/geojson")
def get_restaurants_geojson() -> dict[str, object]:
    return restaurant_service.get_restaurants_geojson()


@router.get("/{restaurant_id}/logo")
def get_restaurant_logo(restaurant_id: str) -> Response:
    logo = restaurant_service.get_restaurant_logo(restaurant_id)
    if logo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo no disponible")

    content, media_type = logo
    return Response(content=content, media_type=media_type)


@router.get("/{restaurant_id}", response_model=Restaurant)
def get_restaurant(restaurant_id: str) -> Restaurant:
    restaurant = restaurant_service.get_restaurant(restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurante no encontrado")
    return restaurant
