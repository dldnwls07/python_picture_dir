import os
import tempfile
import unittest

from diary_categories import (
    matches_filter,
    score_to_tier,
)
from manager.file_manager import FileManager
from domain.model.value_objects import EmotionScore
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from application.service.diary_service import DiaryService


class RefactoringBehaviorTest(unittest.TestCase):
    """Refactored DDD components are 100% equivalent to legacy components."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="refactor_test_", dir="/private/tmp")
        self.csv_path = os.path.join(self.temp_dir, "diary.csv")
        self.file_manager = FileManager(self.csv_path)
        self.repository = CSVDiaryRepository(self.csv_path)
        self.service = DiaryService(repository=self.repository)

    def test_score_to_tier_equivalence(self):
        """Verify that score_to_tier is perfectly equivalent to EmotionScore.tier."""
        for score in range(-100, 101):
            legacy_tier = score_to_tier(score)
            new_tier = EmotionScore(score).tier
            self.assertEqual(
                legacy_tier,
                new_tier,
                f"Mismatch for score {score}: {legacy_tier} vs {new_tier}",
            )

    def test_matches_filter_equivalence(self):
        """Verify that matches_filter is perfectly equivalent to Diary.matches_filter."""
        test_rows = [
            {"id": "1", "date": "2026-07-08", "score": "5", "weather": "☀️", "actual_weather": "☀️"},
            {"id": "2", "date": "2026-07-08", "score": "-2", "weather": "☁️", "actual_weather": "☁️"},
            {"id": "3", "date": "2026-07-08", "score": "0", "weather": "⛅", "actual_weather": "⛅"},
            {"id": "4", "date": "2026-07-08", "weather": "☀️", "emotion_label": "행복했어요,슬펐어요"},
            {"id": "5", "date": "2026-07-08", "weather": "☀️,⛅", "actual_weather": "☀️,⛅", "score": "1"},
            {"id": "6", "date": "2026-07-08", "is_hidden": "True", "password": "123", "score": "3"},
        ]

        filters = [
            "전체보기",
            "☀️ 맑음",
            "⛅ 흐림",
            "☁️ 구름많음",
            "🌧️ 비",
            "긍정 일기",
            "중립 일기",
            "부정 일기",
        ]

        for row in test_rows:
            # Map row to Diary entity
            diary = self.repository._row_to_entity(row)
            for f in filters:
                legacy_res = matches_filter(row, f)
                new_res = diary.matches_filter(f)
                self.assertEqual(
                    legacy_res,
                    new_res,
                    f"Mismatch for row {row} and filter '{f}': {legacy_res} vs {new_res}",
                )

    def test_save_and_update_equivalence(self):
        """Verify saving and updating via service and repository produces identical CSV formats."""
        # 1. Save new diary via Service
        success, diary = self.service.save_diary(
            diary_id=None,
            date="2026-07-08",
            title="Refactor Save",
            content="Testing DDD refactoring",
            location_name="Seoul",
            actual_weather1="☀️ 맑음",
            actual_weather2="선택안함",
            emotion1="행복했어요",
            emotion2="선택안함",
            is_hidden=True,
            password="pwd123",
        )
        self.assertTrue(success)
        self.assertIsNotNone(diary)

        # Read back using FileManager (legacy) and verify columns
        legacy_rows = self.file_manager.read_all_csv()
        self.assertEqual(len(legacy_rows), 1)
        row = legacy_rows[0]

        self.assertEqual(row["id"], "1")
        self.assertEqual(row["date"], "2026-07-08")
        self.assertEqual(row["title"], "Refactor Save")
        self.assertEqual(row["content"], "Testing DDD refactoring")
        self.assertEqual(row["score"], "5.0")
        self.assertEqual(row["emotion_label"], "행복했어요")
        self.assertEqual(row["weather"], "☀️")
        self.assertEqual(row["actual_weather"], "☀️")
        self.assertEqual(row["actual_weather_text"], "맑음")
        self.assertEqual(row["location_name"], "Seoul")
        self.assertEqual(row["is_hidden"], "True")
        # 비밀번호는 SHA-256 해시로 저장된다
        import hashlib
        expected_hash = hashlib.sha256("pwd123".encode("utf-8")).hexdigest()
        self.assertEqual(row["password"], expected_hash)

        # 2. Update diary via Service
        success, updated_diary = self.service.save_diary(
            diary_id=1,
            date="2026-07-09",
            title="Refactor Update",
            content="Updated content",
            location_name="Busan",
            actual_weather1="☁️ 구름많음",
            actual_weather2="선택안함",
            emotion1="슬펐어요",
            emotion2="선택안함",
            is_hidden=False,
            password="",
        )
        self.assertTrue(success)

        legacy_rows = self.file_manager.read_all_csv()
        self.assertEqual(len(legacy_rows), 1)
        row = legacy_rows[0]

        self.assertEqual(row["id"], "1")
        self.assertEqual(row["date"], "2026-07-09")
        self.assertEqual(row["title"], "Refactor Update")
        self.assertEqual(row["content"], "Updated content")
        self.assertEqual(row["score"], "-4.0")
        self.assertEqual(row["emotion_label"], "슬펐어요")
        self.assertEqual(row["weather"], "🌧️")
        self.assertEqual(row["actual_weather"], "☁️")
        self.assertEqual(row["actual_weather_text"], "구름많음")
        self.assertEqual(row["location_name"], "Busan")
        self.assertEqual(row["is_hidden"], "False")
        self.assertEqual(row["password"], "")

    def test_delete_equivalence(self):
        """Verify deleting via service deletes the record and matches legacy delete behavior."""
        # Setup: append two diaries
        self.service.save_diary(
            diary_id=None,
            date="2026-07-08",
            title="D1",
            content="C1",
            location_name="L1",
            actual_weather1="☀️ 맑음",
            actual_weather2="선택안함",
            emotion1="행복했어요",
            emotion2="선택안함",
            is_hidden=False,
            password="",
        )
        self.service.save_diary(
            diary_id=None,
            date="2026-07-08",
            title="D2",
            content="C2",
            location_name="L2",
            actual_weather1="🌧️ 비",
            actual_weather2="선택안함",
            emotion1="슬펐어요",
            emotion2="선택안함",
            is_hidden=False,
            password="",
        )

        self.assertEqual(len(self.file_manager.read_all_csv()), 2)

        # Delete the first one
        self.assertTrue(self.service.delete_diary(1))
        rows = self.file_manager.read_all_csv()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "2")
        self.assertEqual(rows[0]["title"], "D2")


if __name__ == "__main__":
    unittest.main()
