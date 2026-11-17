import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.schemas.restaurant import Restaurant, RestaurantCollection


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "restaurants.json"
SOURCE_NAME = "Lista compartida de restaurantes de El Cangrejo"


def list_restaurants() -> tuple[Restaurant, ...]:
    raw_restaurants = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return tuple(Restaurant.model_validate(restaurant) for restaurant in raw_restaurants)


def get_restaurant(restaurant_id: str) -> Restaurant | None:
    return next(
        (restaurant for restaurant in list_restaurants() if restaurant.id == restaurant_id),
        None,
    )


def get_restaurant_collection() -> RestaurantCollection:
    restaurants = list(list_restaurants())
    return RestaurantCollection(
        source=SOURCE_NAME,
        total=len(restaurants),
        restaurants=restaurants,
    )


def get_restaurant_logo(restaurant_id: str) -> tuple[bytes, str] | None:
    restaurant = get_restaurant(restaurant_id)
    if restaurant is None or restaurant.image_url is None:
        return None

    parsed = urlparse(restaurant.image_url)
    if parsed.scheme != "https" or parsed.netloc != "www.google.com":
        return None

    try:
        request = Request(restaurant.image_url, headers={"User-Agent": "miCangrejo-prototype/0.1"})
        with urlopen(request, timeout=15) as response:
            media_type = response.headers.get_content_type()
            if not media_type.startswith("image/"):
                return None
            return response.read(), media_type
    except (OSError, URLError):
        return None


def get_restaurants_geojson() -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": restaurant.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [restaurant.longitude, restaurant.latitude],
                },
                "properties": restaurant.model_dump(exclude={"latitude", "longitude"}),
            }
            for restaurant in list_restaurants()
        ],
    }
