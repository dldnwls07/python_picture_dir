import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app_gui import AppGUI
from manager.file_manager import FileManager


class AppGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="app_gui_test_", dir="/private/tmp")
        self.window = AppGUI(start_weather_thread=False)
        self.window._file_manager = FileManager(os.path.join(self.temp_dir, "diary.csv"))

    def test_tabs_and_filter_exist(self):
        self.assertIsNotNone(self.window.drawingCanvas)
        self.assertIsNotNone(self.window.contentEdit)
        self.assertEqual(self.window.filterComboBox.count(), 8)

    def test_save_text_and_drawing_diary(self):
        self.window.titleEdit.setText("qt diary")
        self.window.locationLineEdit.setText("Seoul")
        self.window.actualWeatherComboBox.setCurrentText("🌧️ 비")
        self.window.emotionComboBox.setCurrentText("행복했어요")
        self.window.contentEdit.setPlainText("오늘은 정말 좋았다")
        self.window.drawingCanvas._has_content = True
        self.window.drawingCanvas._dirty = True

        self.window.on_save_clicked()

        rows = self.window._file_manager.read_all_csv()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "qt diary")
        self.assertEqual(rows[0]["location_name"], "Seoul")
        self.assertEqual(rows[0]["actual_weather"], "🌧️")
        self.assertEqual(rows[0]["emotion_label"], "행복했어요")
        self.assertTrue(rows[0]["image_path"])
        self.assertNotEqual(rows[0]["score"], "")


if __name__ == "__main__":
    unittest.main()
