import json
from io import BytesIO
from urllib.error import URLError
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from weather.services import get_weather


class WeatherEndpointTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("weather.views.get_weather", return_value={"available": True, "temperature": 8})
    def test_weather_api_uses_selected_coordinates(self, get_weather):
        response = self.client.get("/weather/api/?lat=27.9881&lon=86.925")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["temperature"], 8)
        get_weather.assert_called_once_with(latitude=27.9881, longitude=86.925, language="ru")

    def test_weather_api_rejects_invalid_coordinates(self):
        response = self.client.get("/weather/api/?lat=100&lon=0")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_coordinates")

    @override_settings(OPEN_METEO_API_URL="https://weather.test/v1/forecast")
    @patch("weather.services.os.getenv", return_value="")
    @patch("weather.services.urlopen")
    def test_weather_works_without_openweather_key_using_open_meteo(self, urlopen, _getenv):
        payload = {
            "current": {
                "temperature_2m": 12.4, "apparent_temperature": 10.8,
                "relative_humidity_2m": 67, "precipitation": 0.2,
                "weather_code": 2, "wind_speed_10m": 3.2, "visibility": 12000,
            },
            "hourly": {
                "time": ["2026-09-29T12:00"], "temperature_2m": [12.4],
                "precipitation_probability": [30], "precipitation": [0.2], "weather_code": [2],
            },
            "daily": {
                "time": ["2026-09-29"], "weather_code": [2],
                "temperature_2m_min": [8.1], "temperature_2m_max": [14.7],
                "sunrise": ["2026-09-29T06:30"], "sunset": ["2026-09-29T18:30"],
            },
        }
        urlopen.return_value = BytesIO(json.dumps(payload).encode())

        result = get_weather(latitude=43.15, longitude=77.05, language="ru")

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "open-meteo")
        self.assertEqual(result["temperature"], 12)
        self.assertEqual(result["forecast"][0]["temperature_max"], 15)
        self.assertIn("latitude=43.15", urlopen.call_args.args[0])

    @override_settings(OPEN_METEO_API_URL="https://weather.test/v1/forecast")
    @patch("weather.services.os.getenv", return_value="configured-key")
    @patch("weather.services.urlopen")
    def test_weather_falls_back_when_openweather_is_unavailable(self, urlopen, _getenv):
        payload = {
            "current": {"temperature_2m": 4, "apparent_temperature": 2, "weather_code": 0, "wind_speed_10m": 1, "visibility": 10000},
            "hourly": {"time": [], "temperature_2m": [], "precipitation_probability": [], "precipitation": [], "weather_code": []},
            "daily": {"time": [], "weather_code": [], "temperature_2m_min": [], "temperature_2m_max": [], "sunrise": [], "sunset": []},
        }
        urlopen.side_effect = [URLError("OpenWeather unavailable"), BytesIO(json.dumps(payload).encode())]

        result = get_weather(latitude=43.15, longitude=77.05)

        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "open-meteo")
        self.assertEqual(urlopen.call_count, 2)
