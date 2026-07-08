import os
import tempfile
import unittest
import csv

from PIL import Image
from PyQt5.QtGui import QImage, QColor

from manager.file_manager import FileManager


class FileManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="file_manager_test_", dir="/private/tmp")
        self.csv_path = os.path.join(self.temp_dir, "diary.csv")
        self.file_manager = FileManager(self.csv_path)

    def test_save_pil_image_and_append_row(self):
        image = Image.new("RGB", (16, 16), "red")
        image_path = self.file_manager.save_diary_image(image, "pil.png")

        self.assertTrue(os.path.exists(image_path))
        self.assertTrue(
            self.file_manager.append_to_csv(
                {
                    "date": "2026-07-08",
                    "title": "pil diary",
                    "content": "content",
                    "score": 1,
                    "weather": "☀️",
                    "image_path": image_path,
                }
            )
        )

        rows = self.file_manager.read_all_csv()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["image_path"], image_path)

    def test_save_qimage_and_replace_then_delete(self):
        first = QImage(16, 16, QImage.Format_RGB32)
        first.fill(QColor("red"))
        first_path = self.file_manager.save_diary_image(first, "first.png")

        self.assertTrue(
            self.file_manager.append_to_csv(
                {
                    "date": "2026-07-08",
                    "title": "qt diary",
                    "content": "content",
                    "score": 2,
                    "weather": "☀️",
                    "image_path": first_path,
                }
            )
        )

        second = QImage(16, 16, QImage.Format_RGB32)
        second.fill(QColor("blue"))
        second_path = self.file_manager.save_diary_image(second, "second.png")

        self.assertTrue(
            self.file_manager.update_by_id(
                1,
                {
                    "image_path": second_path,
                    "remove_image": True,
                },
            )
        )
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(second_path))

        self.assertTrue(self.file_manager.delete_by_id(1))
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

        rows = self.file_manager.read_all_csv()
        self.assertEqual(len(rows), 1)
        self.assertIn("actual_weather", rows[0])
        self.assertIn("location_name", rows[0])
        self.assertEqual(rows[0]["actual_weather"], "")
        self.assertEqual(rows[0]["location_name"], "")

    def test_update_preserves_existing_actual_weather_when_not_provided(self):
        self.assertTrue(
            self.file_manager.append_to_csv(
                {
                    "date": "2026-07-08",
                    "title": "weather diary",
                    "content": "content",
                    "score": 1,
                    "weather": "☀️",
                    "actual_weather": "🌧️",
                    "actual_weather_text": "비",
                    "weather_source": "kma",
                    "location_name": "Seoul",
                }
            )
        )

        self.assertTrue(
            self.file_manager.update_by_id(
                1,
                {
                    "title": "updated title",
                    "content": "new content",
                },
            )
        )

        rows = self.file_manager.read_all_csv()
        self.assertEqual(rows[0]["title"], "updated title")
        self.assertEqual(rows[0]["actual_weather"], "🌧️")
        self.assertEqual(rows[0]["weather_source"], "kma")


if __name__ == "__main__":
    unittest.main()
