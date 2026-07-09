import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from engine.weather_engine import WeatherEngine
from runtime_env import configure_runtime


class RuntimeAndWeatherTest(unittest.TestCase):
    def test_configure_runtime_loads_dotenv(self):
        temp_dir = tempfile.mkdtemp(prefix="runtime_env_test_")
        env_path = os.path.join(temp_dir, ".env")
        with open(env_path, "w", encoding="utf-8") as env_file:
            env_file.write("WEATHER_PROVIDER=kma\n")
            env_file.write("KMA_SERVICE_KEY=test-key\n")

        with patch.dict(os.environ, {}, clear=True):
            configure_runtime(temp_dir)
            self.assertEqual(os.environ.get("WEATHER_PROVIDER"), "kma")
            self.assertEqual(os.environ.get("KMA_SERVICE_KEY"), "test-key")
            self.assertTrue(os.environ.get("MPLCONFIGDIR", "").endswith("matplotlib"))

    def test_parse_kma_items(self):
        weather_engine = WeatherEngine()
        future_date = "20991231"
        items = [
            {"fcstDate": future_date, "fcstTime": "1200", "category": "SKY", "fcstValue": "1"},
            {"fcstDate": future_date, "fcstTime": "1200", "category": "PTY", "fcstValue": "0"},
        ]
        self.assertEqual(weather_engine._parse_kma_items(items), {"emoji": "☀️", "text": "맑음"})

    def test_open_meteo_code_mapping(self):
        weather_engine = WeatherEngine()
        self.assertEqual(weather_engine._map_open_meteo_code(0), {"emoji": "☀️", "text": "맑음"})
        self.assertEqual(weather_engine._map_open_meteo_code(61), {"emoji": "🌧️", "text": "비"})
        self.assertEqual(weather_engine._map_open_meteo_code(71), {"emoji": "❄️", "text": "눈"})

    def test_manual_location_override(self):
        with patch.dict(
            os.environ,
            {
                "WEATHER_LATITUDE": "37.5665",
                "WEATHER_LONGITUDE": "126.9780",
                "WEATHER_LOCATION_NAME": "Seoul Override",
            },
            clear=True,
        ):
            weather_engine = WeatherEngine()
            lat, lon, location = weather_engine.get_current_location()

        self.assertEqual(lat, 37.5665)
        self.assertEqual(lon, 126.9780)
        self.assertEqual(location, "Seoul Override")

    def test_kma_request_path_with_mocked_response(self):
        with patch.dict(
            os.environ,
            {
                "KMA_SERVICE_KEY": "test-key",
                "WEATHER_PROVIDER": "kma",
            },
            clear=True,
        ):
            weather_engine = WeatherEngine()

        mocked_response = Mock()
        mocked_response.raise_for_status.return_value = None
        mocked_response.json.return_value = {
            "response": {
                "body": {
                    "items": {
                        "item": [
                            {
                                "fcstDate": "20991231",
                                "fcstTime": "1200",
                                "category": "SKY",
                                "fcstValue": "1",
                            },
                            {
                                "fcstDate": "20991231",
                                "fcstTime": "1200",
                                "category": "PTY",
                                "fcstValue": "0",
                            },
                        ]
                    }
                }
            }
        }

        with patch("engine.weather_engine.requests.get", return_value=mocked_response) as mocked_get:
            result = weather_engine._get_weather_from_kma(37.5665, 126.9780, "Seoul")

        self.assertEqual(result["source"], "kma")
        self.assertEqual(result["emoji"], "☀️")
        self.assertEqual(result["text"], "맑음")
        self.assertEqual(result["location"], "Seoul")
        self.assertEqual(result["error"], "")
        self.assertTrue(mocked_get.called)
        called_params = mocked_get.call_args.kwargs["params"]
        self.assertEqual(called_params["serviceKey"], "test-key")
        self.assertIn("nx", called_params)
        self.assertIn("ny", called_params)


if __name__ == "__main__":
    unittest.main()
