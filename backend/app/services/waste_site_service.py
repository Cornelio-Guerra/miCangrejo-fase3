import json
import re
from functools import lru_cache
from pathlib import Path
from html import unescape
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.schemas.waste_site import WasteSite, WasteSiteCollection


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "waste_sites.json"
SOURCE_NAME = "Mapa comunitario de tinacos compartido por la JDL"
SOURCE_KML_URL = "https://www.google.com/maps/d/kml?mid=1RxGLgtLrOArcqDgiMKN4wj6N8CZeioc&forcekml=1"
KML_NAMESPACE = "{http://www.opengis.net/kml/2.2}"


@lru_cache
def list_waste_sites() -> tuple[WasteSite, ...]:
    raw_sites = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    source_details = _load_source_details()
    return tuple(
        WasteSite.model_validate({**site, **source_details.get(site["id"], {})})
        for site in raw_sites
    )


def get_waste_site(site_id: str) -> WasteSite | None:
    return next((site for site in list_waste_sites() if site.id == site_id), None)


def get_waste_site_collection() -> WasteSiteCollection:
    sites = list(list_waste_sites())
    return WasteSiteCollection(source=SOURCE_NAME, total=len(sites), sites=sites)


def get_waste_site_image(site_id: str) -> tuple[bytes, str] | None:
    site = get_waste_site(site_id)
    if site is None or site.image_url is None:
        return None

    try:
        request = Request(site.image_url, headers={"User-Agent": "miCangrejo-prototype/0.1"})
        with urlopen(request, timeout=20) as response:
            return response.read(), response.headers.get_content_type()
    except (OSError, URLError):
        return None


def get_waste_sites_geojson() -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": site.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [site.longitude, site.latitude],
                },
                "properties": {
                    "name": site.name,
                    "kind": site.kind,
                    "description": site.description,
                    "image_url": site.image_url,
                },
            }
            for site in list_waste_sites()
        ],
    }


@lru_cache
def _load_source_details() -> dict[str, dict[str, str]]:
    """Obtiene la información pública del mapa sin hacer que la API dependa de ella."""
    try:
        request = Request(SOURCE_KML_URL, headers={"User-Agent": "miCangrejo-prototype/0.1"})
        with urlopen(request, timeout=10) as response:
            root = ElementTree.fromstring(response.read())
    except (ElementTree.ParseError, OSError, URLError):
        return {}

    details: dict[str, dict[str, str]] = {}
    point_index = 1
    for placemark in root.iter(f"{KML_NAMESPACE}Placemark"):
        coordinates = placemark.find(f"./{KML_NAMESPACE}Point/{KML_NAMESPACE}coordinates")
        if coordinates is None:
            continue

        name = (placemark.findtext(f"{KML_NAMESPACE}name") or "").strip()
        description_html = placemark.findtext(f"{KML_NAMESPACE}description") or ""
        description = _plain_text(description_html)
        image_url = _image_url(description_html)
        point_id = f"tinaco-{point_index:02d}"
        details[point_id] = {
            "name": name or f"Punto de tinaco {point_index:02d}",
            **({"description": description} if description else {}),
            **({"image_url": image_url} if image_url else {}),
        }
        point_index += 1

    return details


def _plain_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def _image_url(value: str) -> str | None:
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', value, flags=re.IGNORECASE)
    if match is None:
        return None

    candidate = unescape(match.group(1))
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.netloc != "mymaps.usercontent.google.com":
        return None
    return re.sub(r"([?&]fife=s)\d+", r"\g<1>800", candidate)
