import hashlib
import json
import math
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache


class MountainProviderError(Exception):
    pass


class MountainSearchRateLimited(MountainProviderError):
    pass


def _user_agent():
    agent = settings.MOUNTAIN_SEARCH_USER_AGENT
    contact = settings.MOUNTAIN_SEARCH_CONTACT
    return f"{agent} ({contact})" if contact else agent


def _read_json(request, timeout):
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise MountainProviderError from exc


def _elevation(value):
    if not value:
        return None
    try:
        return round(float(str(value).strip().removesuffix("m").strip()))
    except ValueError:
        return None


def search_mountains(query, language="en"):
    query = " ".join(query.split())[:120]
    if len(query) < 3:
        return []

    cache_key = "map-place-search:" + hashlib.sha256(f"{language}:{query.casefold()}".encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    if not cache.add("mountain-search:provider-request", True, timeout=1):
        raise MountainSearchRateLimited

    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
        "limit": 8,
        "accept-language": language,
    }
    if settings.MOUNTAIN_SEARCH_CONTACT:
        params["email"] = settings.MOUNTAIN_SEARCH_CONTACT
    url = f"{settings.MOUNTAIN_SEARCH_URL}?{urlencode(params)}"
    data = _read_json(Request(url, headers={"User-Agent": _user_agent()}), timeout=8)

    results = []
    for item in data if isinstance(data, list) else []:
        tags = item.get("extratags") or {}
        category = item.get("category") or item.get("class")
        item_type = item.get("type")
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            continue
        address = item.get("address") or {}
        locality = next((address.get(key) for key in ("city", "town", "village", "hamlet", "municipality") if address.get(key)), None)
        location_parts = (locality, address.get("county"), address.get("state"), address.get("country"))
        location = ", ".join(dict.fromkeys(part for part in location_parts if part))
        display_name = item.get("display_name", "")
        kind = item_type or category or "place"
        results.append({
            "id": f"{item.get('osm_type', 'node')}:{item.get('osm_id', '')}",
            "name": (item.get("namedetails") or {}).get("name") or item.get("name") or item.get("display_name", "").split(",")[0],
            "location": location or display_name,
            "display_name": display_name,
            "description": tags.get("description", ""),
            "latitude": latitude,
            "longitude": longitude,
            "elevation": _elevation(tags.get("ele")),
            "is_peak": category == "natural" and item_type in {"peak", "mountain", "volcano"},
            "kind": kind,
            "category": category or "",
            "source": "OpenStreetMap",
        })

    cache.set(cache_key, results, timeout=60 * 60)
    return results


def _coordinates(geometry):
    if not isinstance(geometry, list) or len(geometry) < 2:
        return []
    step = max(1, math.ceil(len(geometry) / 600))
    path = [[float(point["lat"]), float(point["lon"])] for point in geometry[::step] if "lat" in point and "lon" in point]
    last = geometry[-1]
    if path and "lat" in last and "lon" in last:
        endpoint = [float(last["lat"]), float(last["lon"])]
        if path[-1] != endpoint:
            path.append(endpoint)
    return path if len(path) >= 2 else []


def get_nearby_trails(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordinates are outside the valid range")

    cache_key = f"mountain-trails:{latitude:.3f}:{longitude:.3f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    if not cache.add("mountain-trails:provider-request", True, timeout=2):
        raise MountainSearchRateLimited

    query = f"""[out:json][timeout:18];
(
  way(around:4500,{latitude},{longitude})["highway"~"^(path|footway|steps|track)$"];
  relation(around:4500,{latitude},{longitude})["route"~"^(hiking|foot)$"];
);
out tags geom;"""
    request = Request(
        settings.OVERPASS_API_URL,
        data=urlencode({"data": query}).encode(),
        headers={"User-Agent": _user_agent(), "Content-Type": "application/x-www-form-urlencoded"},
    )
    data = _read_json(request, timeout=22)
    trails = []
    for relation in data.get("elements", []):
        tags = relation.get("tags") or {}
        if relation.get("type") == "way":
            path = _coordinates(relation.get("geometry"))
            if path:
                trails.append({
                    "id": relation.get("id"),
                    "name": tags.get("name") or tags.get("ref") or "",
                    "ref": tags.get("ref", ""),
                    "network": "",
                    "paths": [path],
                    "start": path[0],
                    "finish": path[-1],
                })
            if len(trails) == 5:
                break
            continue
        paths = []
        for member in relation.get("members", []):
            if member.get("type") != "way":
                continue
            path = _coordinates(member.get("geometry"))
            if path:
                paths.append(path)
        if not paths:
            continue
        trails.append({
            "id": relation.get("id"),
            "name": tags.get("name") or tags.get("ref") or "",
            "ref": tags.get("ref", ""),
            "network": tags.get("network", ""),
            "paths": paths,
            "start": paths[0][0],
            "finish": paths[-1][-1],
        })
        if len(trails) == 5:
            break

    result = {"trails": trails, "source": "OpenStreetMap", "attribution": "© OpenStreetMap contributors"}
    cache.set(cache_key, result, timeout=60 * 60 * 6)
    return result
