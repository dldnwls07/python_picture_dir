import unittest

from diary_categories import matches_filter


class DiaryCategoriesTest(unittest.TestCase):
    def test_weather_filters(self):
        self.assertTrue(matches_filter({"weather": "☀️", "score": "1"}, "☀️ 맑음"))
        self.assertTrue(matches_filter({"weather": "⛅", "score": "0"}, "⛅ 흐림"))
        self.assertFalse(matches_filter({"weather": "🌧️", "score": "-1"}, "☀️ 맑음"))

    def test_emotion_filters(self):
        self.assertTrue(matches_filter({"weather": "☀️", "score": "3"}, "긍정 일기"))
        self.assertTrue(matches_filter({"weather": "⛅", "score": "0"}, "중립 일기"))
        self.assertTrue(matches_filter({"weather": "🌧️", "score": "-3"}, "부정 일기"))
        self.assertFalse(matches_filter({"weather": "☀️", "score": "3"}, "부정 일기"))

    def test_weather_filter_prefers_actual_weather(self):
        row = {"weather": "☀️", "actual_weather": "🌧️", "score": "1"}
        self.assertTrue(matches_filter(row, "🌧️ 비"))
        self.assertFalse(matches_filter(row, "☀️ 맑음"))


if __name__ == "__main__":
    unittest.main()
