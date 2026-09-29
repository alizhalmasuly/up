import json
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from mountains.forms import PreparationForm
from mountains.services import get_nearby_trails, search_mountains


class MountainProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(MOUNTAIN_SEARCH_URL="https://nominatim.test/search", MOUNTAIN_SEARCH_CONTACT="hiker@example.test")
    @patch("mountains.services.urlopen")
    def test_search_returns_international_peak_coordinates_and_elevation(self, urlopen):
        response = [{
            "osm_type": "node", "osm_id": 123, "category": "natural", "type": "peak",
            "name": "Mount Example", "display_name": "Mount Example, Nepal", "lat": "27.9881", "lon": "86.9250",
            "address": {"state": "Koshi", "country": "Nepal"}, "extratags": {"ele": "8848", "description": "A high mountain"},
        }]
        urlopen.return_value = BytesIO(json.dumps(response).encode())

        results = search_mountains("Mount Example", "en")

        self.assertEqual(results[0]["name"], "Mount Example")
        self.assertEqual(results[0]["location"], "Koshi, Nepal")
        self.assertEqual(results[0]["elevation"], 8848)
        self.assertEqual(results[0]["latitude"], 27.9881)
        self.assertEqual(results[0]["description"], "A high mountain")
        self.assertEqual(results[0]["display_name"], "Mount Example, Nepal")
        request = urlopen.call_args.args[0]
        self.assertIn("user-agent", {name.lower() for name in request.headers})
        self.assertIn("email=hiker%40example.test", request.full_url)

    def test_preparation_form_accepts_places_outside_the_curated_mountain_list(self):
        form = PreparationForm(data={
            "mountain": "Big Almaty Lake",
            "difficulty": "moderate",
            "duration_hours": "5",
            "season": "summer",
            "people_count": "2",
        })

        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(OVERPASS_API_URL="https://overpass.test/api/interpreter")
    @patch("mountains.services.urlopen")
    def test_trails_use_real_overpass_relation_geometry(self, urlopen):
        response = {
            "elements": [{
                "type": "relation", "id": 42, "tags": {"name": "Summit Trail", "route": "hiking"},
                "members": [{"type": "way", "geometry": [
                    {"lat": 1.0, "lon": 2.0}, {"lat": 1.2, "lon": 2.3},
                ]}],
            }],
        }
        urlopen.return_value = BytesIO(json.dumps(response).encode())

        result = get_nearby_trails(1, 2)

        self.assertEqual(result["trails"][0]["name"], "Summit Trail")
        self.assertEqual(result["trails"][0]["start"], [1.0, 2.0])
        self.assertEqual(result["trails"][0]["finish"], [1.2, 2.3])
        query = parse_qs(urlopen.call_args.args[0].data.decode())["data"][0]
        self.assertIn("around:4500,1.0,2.0", query)


class MountainEndpointTests(SimpleTestCase):
    @patch("mountains.views.search_mountains", return_value=[{"name": "Fuji", "latitude": 35.36, "longitude": 138.73}])
    def test_search_api_returns_provider_results(self, search):
        response = self.client.get("/mountains/api/search/?q=Fuji")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["name"], "Fuji")
        search.assert_called_once()

    @patch("mountains.views.get_nearby_trails", return_value={"trails": [], "source": "OpenStreetMap"})
    def test_trail_api_validates_and_forwards_peak_coordinates(self, trails):
        response = self.client.get("/mountains/api/trails/?lat=35.36&lon=138.73")
        self.assertEqual(response.status_code, 200)
        trails.assert_called_once_with(35.36, 138.73)
        self.assertEqual(self.client.get("/mountains/api/trails/?lat=91&lon=181").status_code, 400)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PreparationPageTests(TestCase):
    def test_prepare_page_shows_place_search_without_curated_mountain_options(self):
        user = get_user_model().objects.create_user(username="prepare-test", password="test-password")
        self.client.force_login(user)

        response = self.client.get("/mountains/prepare/")

        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn("Введите место для похода...", page)
        self.assertIn("Найти", page)
        self.assertIn('data-prepare-place-search', page)
        self.assertNotIn('data-route-option', page)
