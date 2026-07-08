import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main


class MainTest(unittest.TestCase):
    def test_check_weather_outputs_expected_fields(self):
        fake_weather = {
            "source": "open-meteo",
            "location": "Seoul",
            "emoji": "☀️",
            "text": "맑음",
            "error": "",
        }
        buffer = io.StringIO()
        with patch("engine.weather_engine.WeatherEngine.get_current_weather", return_value=fake_weather):
            with redirect_stdout(buffer):
                main.check_weather()

        output = buffer.getvalue()
        self.assertIn("provider: open-meteo", output)
        self.assertIn("location: Seoul", output)
        self.assertIn("weather: ☀️ 맑음", output)

    def test_check_weather_json_output(self):
        fake_weather = {
            "source": "kma",
            "location": "Seoul",
            "emoji": "🌧️",
            "text": "비",
            "error": "",
        }
        buffer = io.StringIO()
        with patch("engine.weather_engine.WeatherEngine.get_current_weather", return_value=fake_weather):
            with redirect_stdout(buffer):
                main.check_weather(as_json=True)

        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["source"], "kma")
        self.assertEqual(payload["location"], "Seoul")
        self.assertEqual(payload["emoji"], "🌧️")


if __name__ == "__main__":
    unittest.main()
