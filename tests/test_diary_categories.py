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

    def test_multiple_weather_and_emotion_filters(self):
        # 콤마로 구분된 여러 날씨/감정이 있을 때 매칭 테스트
        row = {
            "weather": "☀️,⛅",
            "actual_weather": "☀️,⛅",
            "emotion_label": "행복했어요,슬펐어요",
            "score": "1" # (5 + -4)/2 = 0.5 -> 1
        }
        self.assertTrue(matches_filter(row, "☀️ 맑음"))
        self.assertTrue(matches_filter(row, "⛅ 흐림"))
        self.assertFalse(matches_filter(row, "🌧️ 비"))
        
        # score가 없는 경우 emotion_label로부터 유추
        row_no_score = {
            "weather": "☀️",
            "emotion_label": "행복했어요,슬펐어요"
        }
        # (5 + -4)/2 = 0.5 -> 긍정 일기
        self.assertTrue(matches_filter(row_no_score, "긍정 일기"))
        self.assertFalse(matches_filter(row_no_score, "부정 일기"))

        # 부정적인 감정이 지배적인 경우
        row_negative = {
            "weather": "🌧️",
            "emotion_label": "슬펐어요,피곤했어요"
        }
        # (-4 + -1)/2 = -2.5 -> 부정 일기
        self.assertTrue(matches_filter(row_negative, "부정 일기"))
        self.assertFalse(matches_filter(row_negative, "긍정 일기"))


if __name__ == "__main__":
    unittest.main()
