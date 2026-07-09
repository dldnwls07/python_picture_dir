import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app_gui import AppGUI
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from application.service.diary_service import DiaryService


class AppGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="app_gui_test_")
        self.window = AppGUI(start_weather_thread=False)
        self.repo = CSVDiaryRepository(os.path.join(self.temp_dir, "diary.csv"))
        self.window._diary_service = DiaryService(repository=self.repo)

    def test_tabs_and_filter_exist(self):
        self.assertIsNotNone(self.window.drawingCanvas)
        self.assertIsNotNone(self.window.contentEdit)
        self.assertEqual(self.window.filterComboBox.count(), 10)

    def test_save_text_and_drawing_diary(self):
        self.window.titleEdit.setText("qt diary")
        self.window.locationLineEdit.setText("Seoul")
        self.window.actualWeatherComboBox.setCurrentText("🌧️ 비")
        self.window.emotionComboBox.setCurrentText("행복했어요")
        self.window.contentEdit.setPlainText("오늘은 정말 좋았다")
        self.window.drawingCanvas._has_content = True
        self.window.drawingCanvas._dirty = True

        self.window.on_save_clicked()

        rows = self.repo._read_all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "qt diary")
        self.assertEqual(rows[0]["location_name"], "Seoul")
        self.assertEqual(rows[0]["actual_weather"], "🌧️")
        self.assertEqual(rows[0]["emotion_label"], "행복했어요")
        self.assertTrue(rows[0]["image_path"])
        self.assertNotEqual(rows[0]["score"], "")

    @patch("PyQt5.QtWidgets.QDialog.exec_")
    def test_show_ai_empathy_window(self, mock_dialog_exec):
        # QDialog.exec_가 호출될 때 즉시 닫히도록 설정
        mock_dialog_exec.return_value = 1
        
        # AIHelper.analyze_diary 모킹
        self.window._ai_helper.analyze_diary = MagicMock(return_value={
            "summary": "Mock 요약",
            "empathy": "Mock 공감",
            "drawing_analysis": "Mock 그림 분석"
        })
        
        # 내용이 비었을 때는 경고만 울리고 API를 호출하지 않음
        self.window.contentEdit.setPlainText("")
        # display_alert 모킹해서 실제 다이얼로그 팝업 차단
        self.window.display_alert = MagicMock()
        self.window.show_ai_empathy_window()
        self.window.display_alert.assert_called_once()
        self.window._ai_helper.analyze_diary.assert_not_called()
        
        # 본문 기입 후 정상 작동 테스트
        self.window.contentEdit.setPlainText("오늘 정말 신나는 일상을 보냈다.")
        self.window.show_ai_empathy_window()
        if hasattr(self.window, "_ai_worker"):
            self.window._ai_worker.wait()
        self.window._ai_helper.analyze_diary.assert_called_once()


if __name__ == "__main__":
    unittest.main()
