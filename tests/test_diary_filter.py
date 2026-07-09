import os
import tempfile
import unittest

from domain.model.diary import Diary
from domain.model.value_objects import DiaryFilter, EmotionScore, Weather
from infrastructure.persistence.location_preset_store import LocationPresetStore


def make_diary(title="", content="", summary="", location="", weather_emoji="☀️", score=0.0):
    return Diary(
        diary_id=1,
        date="2026-07-09",
        title=title,
        content=content,
        emotion_score=EmotionScore(score),
        emotion_label="",
        weather=Weather(emoji=weather_emoji, actual_weather=weather_emoji, location=location),
        summary=summary,
    )


class DiaryFilterTest(unittest.TestCase):
    def test_empty_filter_matches_everything(self):
        diary = make_diary(title="아무 제목")
        self.assertTrue(diary.matches_filter(DiaryFilter()))

    def test_category_filter_still_works(self):
        diary = make_diary(weather_emoji="🌧️", score=3)
        self.assertTrue(diary.matches_filter(DiaryFilter(category="🌧️ 비")))
        self.assertFalse(diary.matches_filter(DiaryFilter(category="☀️ 맑음")))
        self.assertTrue(diary.matches_filter(DiaryFilter(category="긍정 일기")))
        self.assertFalse(diary.matches_filter(DiaryFilter(category="부정 일기")))

    def test_location_keyword_is_case_insensitive_substring(self):
        diary = make_diary(location="Seoul Station")
        self.assertTrue(diary.matches_filter(DiaryFilter(location="seoul")))
        self.assertFalse(diary.matches_filter(DiaryFilter(location="busan")))

    def test_title_content_summary_keywords(self):
        diary = make_diary(title="오늘의 일기", content="맛있는 낙지볶음을 먹었다", summary="맛있는 하루")
        self.assertTrue(diary.matches_filter(DiaryFilter(title_keyword="오늘")))
        self.assertTrue(diary.matches_filter(DiaryFilter(content_keyword="낙지")))
        self.assertTrue(diary.matches_filter(DiaryFilter(summary_keyword="하루")))
        self.assertFalse(diary.matches_filter(DiaryFilter(title_keyword="없는단어")))

    def test_multiple_conditions_are_and_combined(self):
        diary = make_diary(title="학교 일기", content="공부했다", location="학교", score=3)
        # 제목/위치 둘 다 맞음 -> 통과
        self.assertTrue(diary.matches_filter(DiaryFilter(title_keyword="학교", location="학교")))
        # 위치는 맞지만 본문 키워드가 안 맞음 -> 실패
        self.assertFalse(diary.matches_filter(DiaryFilter(location="학교", content_keyword="그림")))

    def test_tier_filter_matches_emotion_score_tier(self):
        diary = make_diary(score=5)  # tier == "A+"
        self.assertTrue(diary.matches_filter(DiaryFilter(tier="A+")))
        self.assertFalse(diary.matches_filter(DiaryFilter(tier="F")))

    def test_tier_filter_empty_or_all_matches_everything(self):
        diary = make_diary(score=-5)  # tier == "F"
        self.assertTrue(diary.matches_filter(DiaryFilter(tier="")))
        self.assertTrue(diary.matches_filter(DiaryFilter(tier="전체")))

    def test_tier_combined_with_other_conditions(self):
        diary = make_diary(title="학교 일기", location="학교", score=1)  # tier == "B"
        self.assertTrue(diary.matches_filter(DiaryFilter(tier="B", location="학교")))
        self.assertFalse(diary.matches_filter(DiaryFilter(tier="A", location="학교")))


class LocationPresetStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="location_preset_test_")
        self.filepath = os.path.join(self.temp_dir, "location.txt")

    def test_default_presets_created_on_first_use(self):
        store = LocationPresetStore(self.filepath)
        self.assertEqual(store.get_all(), ["학교", "직장", "집"])
        self.assertTrue(os.path.exists(self.filepath))

    def test_add_appends_new_preset_without_duplicating(self):
        store = LocationPresetStore(self.filepath)
        store.add("롯데월드")
        self.assertEqual(store.get_all(), ["학교", "직장", "집", "롯데월드"])

        store.add("롯데월드")  # 중복 추가 시도
        self.assertEqual(store.get_all(), ["학교", "직장", "집", "롯데월드"])

    def test_add_ignores_blank_input(self):
        store = LocationPresetStore(self.filepath)
        store.add("   ")
        self.assertEqual(store.get_all(), ["학교", "직장", "집"])


if __name__ == "__main__":
    unittest.main()
