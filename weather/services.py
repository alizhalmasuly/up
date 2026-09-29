import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache


def find_place(query, language="en"):
    query = " ".join(query.split())[:120]
    if len(query) < 2:
        return []
    cache_key = "weather-place:" + sha256(f"{language}:{query.casefold()}".encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    if not cache.add("mountain-search:provider-request", True, timeout=1):
        return None
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": language,
    }
    if settings.MOUNTAIN_SEARCH_CONTACT:
        params["email"] = settings.MOUNTAIN_SEARCH_CONTACT
    url = f"{settings.MOUNTAIN_SEARCH_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": settings.MOUNTAIN_SEARCH_USER_AGENT})
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read())
    results = []
    for item in payload if isinstance(payload, list) else []:
        try:
            latitude, longitude = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            results.append({"latitude": latitude, "longitude": longitude, "name": item.get("display_name", query)})
            break
    cache.set(cache_key, results, timeout=60 * 60)
    return results


def _local_time(timestamp, offset):
    return datetime.fromtimestamp(timestamp + offset, timezone.utc)


def _icon_for(code):
    if 200 <= code < 300:
        return "cloud-lightning"
    if 300 <= code < 600:
        return "cloud-rain"
    if 600 <= code < 700:
        return "cloud-snow"
    if code == 800:
        return "sun"
    if 801 <= code < 900:
        return "cloud-sun"
    return "cloud"


def _sample(period, offset):
    weather = period["weather"][0]
    timestamp = int(period["dt"])
    return {
        "time": _local_time(timestamp, offset).isoformat(),
        "temperature": round(period["main"]["temp"]),
        "condition": weather["description"].capitalize(),
        "icon": _icon_for(int(weather["id"])),
        "precipitation_probability": round(float(period.get("pop", 0)) * 100),
        "precipitation": round(float((period.get("rain") or {}).get("3h", 0)) + float((period.get("snow") or {}).get("3h", 0)), 1),
        "wind": round(float(period.get("wind", {}).get("speed", 0)), 1),
    }


def _daily_forecast(periods, offset):
    days = {}
    for period in periods:
        moment = _local_time(int(period["dt"]), offset)
        key = moment.strftime("%Y-%m-%d")
        sample = _sample(period, offset)
        existing = days.get(key)
        noon_distance = abs(moment.hour - 12)
        if existing is None or noon_distance < existing["noon_distance"]:
            sample["noon_distance"] = noon_distance
            sample["date"] = key
            sample["weekday"] = moment.strftime("%A")
            sample["temperature_min"] = round(period["main"]["temp_min"])
            sample["temperature_max"] = round(period["main"]["temp_max"])
            days[key] = sample
        else:
            existing["temperature_min"] = min(existing["temperature_min"], round(period["main"]["temp_min"]))
            existing["temperature_max"] = max(existing["temperature_max"], round(period["main"]["temp_max"]))
    return [{key: value for key, value in day.items() if key != "noon_distance"} for day in list(days.values())[:5]]


def _unavailable(reason):
    return {
        "available": False,
        "error": reason,
        "source": "unavailable",
        "temperature": None,
        "feels_like": None,
        "condition": "",
        "wind": None,
        "humidity": None,
        "precipitation": None,
        "visibility": None,
        "sunrise": None,
        "sunset": None,
        "hourly": [],
        "forecast": [],
    }


def _meteo_condition(code, language):
    conditions = {
        0: ("Ясно", "Ашық", "Clear"),
        1: ("Преимущественно ясно", "Көбіне ашық", "Mainly clear"),
        2: ("Переменная облачность", "Ауыспалы бұлтты", "Partly cloudy"),
        3: ("Облачно", "Бұлтты", "Overcast"),
        45: ("Туман", "Тұман", "Fog"), 48: ("Изморозь и туман", "Қыраулы тұман", "Rime fog"),
        51: ("Лёгкая морось", "Сәл сіркіреме", "Light drizzle"),
        53: ("Морось", "Сіркіреме", "Drizzle"), 55: ("Сильная морось", "Қатты сіркіреме", "Heavy drizzle"),
        61: ("Небольшой дождь", "Аздаған жаңбыр", "Light rain"),
        63: ("Дождь", "Жаңбыр", "Rain"), 65: ("Сильный дождь", "Қатты жаңбыр", "Heavy rain"),
        71: ("Небольшой снег", "Аздаған қар", "Light snow"),
        73: ("Снег", "Қар", "Snow"), 75: ("Сильный снег", "Қатты қар", "Heavy snow"),
        77: ("Снежная крупа", "Қар түйіршіктері", "Snow grains"),
        80: ("Небольшой ливень", "Аздаған нөсер", "Light rain showers"),
        81: ("Ливень", "Нөсер", "Rain showers"), 82: ("Сильный ливень", "Қатты нөсер", "Heavy rain showers"),
        85: ("Небольшой снегопад", "Аздаған қарлы боран", "Light snow showers"),
        86: ("Сильный снегопад", "Қатты қарлы боран", "Heavy snow showers"),
        95: ("Гроза", "Найзағай", "Thunderstorm"), 96: ("Гроза с градом", "Бұршақты найзағай", "Thunderstorm with hail"),
        99: ("Сильная гроза с градом", "Қатты бұршақты найзағай", "Heavy thunderstorm with hail"),
    }
    return conditions.get(int(code), ("Переменная облачность", "Ауыспалы бұлтты", "Partly cloudy"))[{"ru": 0, "kk": 1}.get(language, 2)]


def _meteo_icon(code):
    code = int(code)
    if code >= 95:
        return "cloud-lightning"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "cloud-rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "cloud-snow"
    if code == 0:
        return "sun"
    if code in {1, 2}:
        return "cloud-sun"
    return "cloud"


def _get_open_meteo_weather(latitude, longitude, language):
    params = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,visibility",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code",
        "daily": "weather_code,temperature_2m_min,temperature_2m_max,sunrise,sunset",
        "forecast_days": 5,
        "timezone": "auto",
        "wind_speed_unit": "ms",
    })
    try:
        with urlopen(f"{settings.OPEN_METEO_API_URL}?{params}", timeout=10) as response:
            data = json.loads(response.read())
        current = data["current"]
        daily = data["daily"]
        hourly = data["hourly"]
        current_code = int(current["weather_code"])
        daily_items = []
        for index, date in enumerate(daily.get("time", [])[:5]):
            code = int(daily["weather_code"][index])
            daily_items.append({
                "date": date,
                "condition": _meteo_condition(code, language),
                "icon": _meteo_icon(code),
                "temperature_min": round(daily["temperature_2m_min"][index]),
                "temperature_max": round(daily["temperature_2m_max"][index]),
            })
        hourly_items = []
        for index, time in enumerate(hourly.get("time", [])[:8]):
            code = int(hourly["weather_code"][index])
            hourly_items.append({
                "time": time,
                "temperature": round(hourly["temperature_2m"][index]),
                "condition": _meteo_condition(code, language),
                "icon": _meteo_icon(code),
                "precipitation_probability": round(float(hourly["precipitation_probability"][index])),
                "precipitation": round(float(hourly["precipitation"][index]), 1),
            })
        first_sunrise = (daily.get("sunrise") or [None])[0]
        first_sunset = (daily.get("sunset") or [None])[0]
        result = {
            "available": True,
            "error": "",
            "forecast_error": False,
            "source": "open-meteo",
            "location_name": "",
            "temperature": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]),
            "condition": _meteo_condition(current_code, language),
            "icon": _meteo_icon(current_code),
            "wind": round(float(current["wind_speed_10m"]), 1),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": round(float(current.get("precipitation") or 0), 1),
            "visibility": round(float(current["visibility"]) / 1000, 1) if current.get("visibility") is not None else None,
            "sunrise": first_sunrise[11:16] if first_sunrise else None,
            "sunset": first_sunset[11:16] if first_sunset else None,
            "hourly": hourly_items,
            "forecast": daily_items,
        }
        return result
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return _unavailable("upstream_error")


def get_weather(latitude=None, longitude=None, language="ru"):
    api_key = os.getenv("WEATHER_API_KEY", "").strip()
    if not api_key and (latitude is None or longitude is None):
        return _unavailable("missing_api_key")
    if latitude is None or longitude is None:
        return _unavailable("missing_coordinates")
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return _unavailable("missing_coordinates")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return _unavailable("invalid_coordinates")

    cache_key = f"live-weather:{sha256(f'{latitude:.3f}:{longitude:.3f}:{language}'.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    def fallback():
        result = _get_open_meteo_weather(latitude, longitude, language)
        if result["available"]:
            cache.set(cache_key, result, timeout=60 * 5)
        return result

    if not api_key:
        return fallback()

    query = urlencode({"lat": latitude, "lon": longitude, "appid": api_key, "units": "metric", "lang": language})
    try:
        with urlopen(f"{settings.WEATHER_API_URL}?{query}", timeout=8) as response:
            current = json.loads(response.read())
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return fallback()

    try:
        offset = int(current.get("timezone", 0))
        weather = current["weather"][0]
        main = current["main"]
        wind_data = current.get("wind") or {}
        system_data = current.get("sys") or {}
        temperature = round(main["temp"])
        feels_like = round(main["feels_like"])
        wind_speed = round(float(wind_data["speed"]), 1)
    except (KeyError, IndexError, TypeError, ValueError):
        return fallback()

    try:
        with urlopen(f"{settings.WEATHER_FORECAST_API_URL}?{query}", timeout=10) as response:
            forecast_data = json.loads(response.read())
        periods = forecast_data.get("list", [])
        forecast_offset = int((forecast_data.get("city") or {}).get("timezone", offset))
        hourly = [_sample(period, forecast_offset) for period in periods[:8]]
        daily = _daily_forecast(periods, forecast_offset)
        forecast_error = False
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return fallback()

    sunrise = system_data.get("sunrise")
    sunset = system_data.get("sunset")
    precipitation = float((current.get("rain") or {}).get("1h", 0) or 0) + float((current.get("snow") or {}).get("1h", 0) or 0)
    result = {
        "available": True,
        "error": "",
        "forecast_error": forecast_error,
        "source": "openweathermap",
        "location_name": current.get("name", ""),
        "temperature": temperature,
        "feels_like": feels_like,
        "condition": weather["description"].capitalize(),
        "icon": _icon_for(int(weather["id"])),
        "wind": wind_speed,
        "humidity": main.get("humidity"),
        "precipitation": round(float(precipitation), 1),
        "visibility": round(current["visibility"] / 1000, 1) if current.get("visibility") is not None else None,
        "sunrise": _local_time(int(sunrise), offset).strftime("%H:%M") if sunrise else None,
        "sunset": _local_time(int(sunset), offset).strftime("%H:%M") if sunset else None,
        "hourly": hourly,
        "forecast": daily,
    }
    cache.set(cache_key, result, timeout=60 * 5)
    return result
