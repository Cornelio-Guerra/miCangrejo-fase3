from pydantic import BaseModel, Field


class Restaurant(BaseModel):
    id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    price_range: str | None = None
    description: str | None = None
    image_url: str | None = None
    maps_url: str


class RestaurantCollection(BaseModel):
    source: str
    total: int
    restaurants: list[Restaurant]
