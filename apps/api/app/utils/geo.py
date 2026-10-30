import math
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

# Nigeria's bounding box. Rejects swapped lat/lng and out-of-country points.
NG_LAT = (4.2, 13.9)
NG_LNG = (2.6, 14.7)


@dataclass(frozen=True)
class BBox:
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float


def parse_bbox(raw: str) -> BBox:
    """Parse "min_lng,min_lat,max_lng,max_lat"."""
    try:
        values = [float(part) for part in raw.split(",")]
    except ValueError as exc:
        raise ValueError("bbox must be four comma-separated numbers") from exc
    if len(values) != 4 or not all(math.isfinite(v) for v in values):
        raise ValueError("bbox must be min_lng,min_lat,max_lng,max_lat")
    min_lng, min_lat, max_lng, max_lat = values
    if not (-180 <= min_lng < max_lng <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("bbox coordinates are out of range or min is not below max")
    return BBox(min_lng, min_lat, max_lng, max_lat)


def geog_point(lng: float, lat: float) -> ColumnElement[object]:
    """Geography point. WKT order is longitude then latitude."""
    return func.ST_GeogFromText(f"SRID=4326;POINT({lng!r} {lat!r})")


def _edge(a: float, b: float, step: float = 1.0) -> list[float]:
    n = max(1, math.ceil(abs(b - a) / step))
    return [a + (b - a) * i / n for i in range(n)]


def geog_bbox(box: BBox) -> ColumnElement[object]:
    """Rectangle as a geography polygon. Edges are densified because geography edges are
    geodesics; one vertex per degree keeps them within a few hundred meters of a flat box."""
    ring: list[tuple[float, float]] = []
    ring += [(x, box.min_lat) for x in _edge(box.min_lng, box.max_lng)]
    ring += [(box.max_lng, y) for y in _edge(box.min_lat, box.max_lat)]
    ring += [(x, box.max_lat) for x in _edge(box.max_lng, box.min_lng)]
    ring += [(box.min_lng, y) for y in _edge(box.max_lat, box.min_lat)]
    ring.append(ring[0])
    coords = ",".join(f"{x!r} {y!r}" for x, y in ring)
    return func.ST_GeogFromText(f"SRID=4326;POLYGON(({coords}))")
