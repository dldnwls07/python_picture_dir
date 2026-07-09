import os
import tempfile
import unittest
import csv
from PIL import Image
from PyQt5.QtGui import QImage, QColor

from domain.model.diary import Diary
from domain.model.value_objects import EmotionScore, Weather
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository

class CSVDiaryRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="csv_repo_test_")
        self.csv_path = os.path.join(self.temp_dir, "diary.csv")
        self.repository = CSVDiaryRepository(self.csv_path)

    def test_save_pil_image_and_save_diary(self):
        image = Image.new("RGB", (16, 16), "red")
        image_path = self.repository.save_image(image, "pil.png")

        self.assertTrue(os.path.exists(image_path))

        diary = Diary(
            diary_id=None,
            date="2026-07-08",
            title="pil diary",
            content="content",
            emotion_score=EmotionScore(1.0),
            emotion_label="보통",
            weather=Weather(emoji="☀️", text="맑음", source="manual", location="Seoul", actual_weather="☀️", actual_weather_text="맑음"),
            image_path=image_path
        )
        self.assertTrue(self.repository.save(diary))

        rows = self.repository._read_all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["image_path"], image_path)

    def test_save_qimage_and_replace_then_delete(self):
        first = QImage(16, 16, QImage.Format_RGB32)
        first.fill(QColor("red"))
        first_path = self.repository.save_image(first, "first.png")

        diary = Diary(
            diary_id=None,
            date="2026-07-08",
            title="qt diary",
            content="content",
            emotion_score=EmotionScore(2.0),
            emotion_label="행복했어요",
            weather=Weather(emoji="☀️", text="맑음"),
            image_path=first_path
        )
        self.assertTrue(self.repository.save(diary))
        self.assertEqual(diary.id, 1)

        # Update image
        second = QImage(16, 16, QImage.Format_RGB32)
        second.fill(QColor("blue"))
        second_path = self.repository.save_image(second, "second.png")

        diary.image_path = second_path
        self.assertTrue(self.repository.save(diary))
        
        # We manually clean up the old image in the service, but let's test delete_image
        self.repository.delete_image(first_path)
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(second_path))

        self.assertTrue(self.repository.delete_by_id(1))
        self.assertFalse(os.path.exists(second_path))

    def test_read_legacy_csv_normalizes_missing_columns(self):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["id", "date", "title", "content", "score", "weather", "created_at"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "id": 1,
                    "date": "2026-07-08",
                    "title": "legacy",
                    "content": "old row",
                    "score": 0,
                    "weather": "⛅",
                    "created_at": "2026-07-08 10:00:00",
                }
            )

        rows = self.repository._read_all_rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("actual_weather", rows[0])
        self.assertIn("location_name", rows[0])
        self.assertEqual(rows[0]["actual_weather"], "")

if __name__ == "__main__":
    unittest.main()
