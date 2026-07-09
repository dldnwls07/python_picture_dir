import os
import tempfile
import unittest

from application.service.diary_service import DiaryService
from domain.model.diary import Diary
from domain.model.value_objects import EmotionScore, Weather
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository


class DiaryServiceEmotionScoresTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="diary_service_test_")
        self.repo = CSVDiaryRepository(os.path.join(self.temp_dir, "diary.csv"))
        self.service = DiaryService(repository=self.repo)

    def _save(self, date: str, score: float, is_hidden: bool = False):
        diary = Diary(
            diary_id=None,
            date=date,
            title="t",
            content="c",
            emotion_score=EmotionScore(score),
            emotion_label="x",
            weather=Weather(),
            is_hidden=is_hidden,
        )
        self.repo.save(diary)

    def test_averages_multiple_entries_on_same_date(self):
        self._save("2026-06-01", 3)
        self._save("2026-06-01", -1)
        scores = self.service.get_emotion_scores_by_date()
        self.assertEqual(scores["2026-06-01"], 1.0)

    def test_excludes_hidden_diaries(self):
        self._save("2026-06-01", 3)
        self._save("2026-06-02", 5, is_hidden=True)
        scores = self.service.get_emotion_scores_by_date()
        self.assertIn("2026-06-01", scores)
        self.assertNotIn("2026-06-02", scores)

    def test_respects_date_range(self):
        self._save("2026-06-01", 3)
        self._save("2026-06-10", -2)
        scores = self.service.get_emotion_scores_by_date(date_from="2026-06-05", date_to="2026-06-15")
        self.assertNotIn("2026-06-01", scores)
        self.assertIn("2026-06-10", scores)

    def test_generate_trend_chart_returns_png_when_data_exists(self):
        self._save("2026-06-01", 3)
        png_bytes = self.service.generate_trend_chart("2026-06-01", "2026-06-05")
        self.assertTrue(png_bytes)

    def test_generate_trend_chart_empty_when_no_data(self):
        png_bytes = self.service.generate_trend_chart("2026-01-01", "2026-01-05")
        self.assertEqual(png_bytes, b"")


if __name__ == "__main__":
    unittest.main()
