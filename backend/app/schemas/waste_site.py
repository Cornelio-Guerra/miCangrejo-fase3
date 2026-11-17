from pydantic import BaseModel, Field


class WasteSite(BaseModel):
    id: str
    name: str
    kind: str = "tinaco"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    description: str | None = None
    image_url: str | None = None


class WasteSiteCollection(BaseModel):
    source: str
    total: int
    sites: list[WasteSite]
