import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app_gui import AppGUI
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from infrastructure.persistence.secret_password_store import SecretPasswordStore
from application.service.diary_service import DiaryService


class AppGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="app_gui_test_")
        self.window = AppGUI()
        self.repo = CSVDiaryRepository(os.path.join(self.temp_dir, "diary.csv"))
        self.password_store = SecretPasswordStore(os.path.join(self.temp_dir, "password.txt"))
        self.window._diary_service = DiaryService(repository=self.repo, password_store=self.password_store)

    def test_tabs_and_filter_exist(self):
        self.assertIsNotNone(self.window.drawingCanvas)
        self.assertIsNotNone(self.window.contentEdit)
        self.assertEqual(self.window.filterComboBox.count(), 10)

    @patch("PyQt5.QtWidgets.QDialog.exec_")
    def test_save_text_and_drawing_diary(self, mock_dialog_exec):
        # QDialog.exec_가 호출될 때 즉시 닫히도록 설정
        mock_dialog_exec.return_value = 1

        # AIHelper 호출 모킹 (요약/공감을 각각 모킹)
        self.window._ai_helper.summarize_diary = MagicMock(return_value="Mock 요약")
        self.window._ai_helper.analyze_empathy = MagicMock(return_value={
            "empathy": "Mock 공감",
            "drawing_analysis": "Mock 그림 분석"
        })

        self.window.titleEdit.setText("qt diary")
        self.window.locationLineEdit.setText("Seoul")
        self.window.actualWeatherComboBox.setCurrentText("🌧️ 비")
        self.window.emotionComboBox.setCurrentText("행복했어요")
        self.window.contentEdit.setPlainText("오늘은 정말 좋았다")
        self.window.drawingCanvas._has_content = True
        self.window.drawingCanvas._dirty = True

        self.window.on_save_clicked()
        self.window._save_worker.wait()
        QApplication.processEvents()

        rows = self.repo._read_all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "qt diary")
        self.assertEqual(rows[0]["location_name"], "Seoul")
        self.assertEqual(rows[0]["actual_weather"], "🌧️")
        self.assertEqual(rows[0]["emotion_label"], "행복했어요")
        self.assertTrue(rows[0]["image_path"])
        self.assertNotEqual(rows[0]["score"], "")
        self.assertEqual(rows[0]["summary"], "Mock 요약")

    @patch("PyQt5.QtWidgets.QDialog.exec_")
    def test_save_runs_ai_summary_then_empathy(self, mock_dialog_exec):
        mock_dialog_exec.return_value = 1

        self.window._ai_helper.summarize_diary = MagicMock(return_value="Mock 요약")
        self.window._ai_helper.analyze_empathy = MagicMock(return_value={
            "empathy": "Mock 공감",
            "drawing_analysis": "Mock 그림 분석"
        })

        self.window.contentEdit.setPlainText("오늘 정말 신나는 일상을 보냈다.")
        self.window.on_save_clicked()
        self.window._save_worker.wait()
        QApplication.processEvents()

        self.window._ai_helper.summarize_diary.assert_called_once()
        self.window._ai_helper.analyze_empathy.assert_called_once()

    @patch("PyQt5.QtWidgets.QDialog.exec_")
    def test_hidden_diary_excluded_from_list(self, mock_dialog_exec):
        mock_dialog_exec.return_value = 1

        self.window._ai_helper.summarize_diary = MagicMock(return_value="")
        self.window._ai_helper.analyze_empathy = MagicMock(return_value={
            "empathy": "",
            "drawing_analysis": ""
        })

        with patch("PyQt5.QtWidgets.QInputDialog.getText", return_value=("pw123", True)):
            self.window.contentEdit.setPlainText("비밀 일기 내용")
            self.window.hideCheckBox.setChecked(True)
            self.window.on_save_clicked()
            self.window._save_worker.wait()
        QApplication.processEvents()

        self.assertTrue(self.password_store.has_password())
        self.assertEqual(self.window.diaryListWidget.count(), 0)


if __name__ == "__main__":
    unittest.main()
