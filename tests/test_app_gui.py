import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt5.QtGui import QColor

from app_gui import AppGUI, EmotionCalendarWidget
from domain.model.diary import Diary
from domain.model.value_objects import EmotionScore, Weather
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

    def _wait_for_save_worker(self, timeout: float = 3.0):
        """비밀 일기는 찢기 연출이 끝난 뒤에야 _save_worker가 생기므로, 그때까지 이벤트 루프를 돌려준다."""
        deadline = time.time() + timeout
        while not hasattr(self.window, "_save_worker") and time.time() < deadline:
            QApplication.processEvents()
        self.assertTrue(hasattr(self.window, "_save_worker"), "찢기 연출 완료 후 _save_worker가 생성되지 않았습니다.")

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
        self.window.locationLineEdit.setCurrentText("Seoul")
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
            self._wait_for_save_worker()
            self.window._save_worker.wait()
        QApplication.processEvents()

        self.assertTrue(self.password_store.has_password())
        self.assertEqual(self.window.diaryListWidget.count(), 0)

    def _save_diary(self, date: str, is_hidden: bool = False) -> Diary:
        diary = Diary(
            diary_id=None,
            date=date,
            title="테스트 일기",
            content="내용",
            emotion_score=EmotionScore(3),
            emotion_label="재미있었어요",
            weather=Weather(emoji="☀️", actual_weather="☀️", location="Seoul"),
            is_hidden=is_hidden,
        )
        self.repo.save(diary)
        return diary

    def test_starts_on_calendar_page(self):
        self.assertEqual(self.window.rightStack.currentIndex(), 0)
        self.assertIs(self.window.rightStack.currentWidget(), self.window.calendarPage)

    def test_no_phantom_list_selection_on_startup(self):
        """QListWidget이 화면에 처음 표시될 때 0번 항목을 자동으로 선택해버리는 Qt 습성 때문에,
        아무것도 클릭하지 않았는데도 목록 맨 위 항목이 선택된 것처럼 보이는 문제가 있었다.
        창을 보여주고 이벤트 루프를 돌려도 currentRow가 -1(선택 없음)을 유지해야 한다."""
        self._save_diary("2026-01-01")
        self._save_diary("2026-01-02")
        self.window._load_diary_list()
        self.window.show()
        for _ in range(5):
            QApplication.processEvents()
        self.assertEqual(self.window.diaryListWidget.currentRow(), -1)
        self.assertEqual(self.window.diaryListWidget.selectedItems(), [])
        self.assertEqual(self.window.rightStack.currentIndex(), 0)

    def test_new_diary_button_switches_to_editor_page(self):
        self.window.newButton.click()
        self.assertEqual(self.window.rightStack.currentIndex(), 1)

    def test_back_to_calendar_button_returns_to_calendar_page(self):
        self.window.newButton.click()
        self.assertEqual(self.window.rightStack.currentIndex(), 1)
        self.window.backToCalendarButton.click()
        self.assertEqual(self.window.rightStack.currentIndex(), 0)

    def test_calendar_click_on_empty_date_opens_new_diary_form(self):
        from PyQt5.QtCore import QDate
        target = QDate.currentDate().addDays(5)
        self.window._on_calendar_date_clicked(target)
        self.assertEqual(self.window.rightStack.currentIndex(), 1)
        self.assertEqual(self.window.dateEdit.date(), target)
        self.assertIsNone(self.window._current_diary_id)

    def test_calendar_click_on_existing_date_loads_diary(self):
        diary = self._save_diary("2026-03-01")
        from PyQt5.QtCore import QDate
        self.window._on_calendar_date_clicked(QDate.fromString("2026-03-01", "yyyy-MM-dd"))
        self.assertEqual(self.window.rightStack.currentIndex(), 1)
        self.assertEqual(self.window._current_diary_id, diary.id)
        self.assertEqual(self.window.titleEdit.text(), "테스트 일기")

    @patch("PyQt5.QtWidgets.QMessageBox.information")
    def test_calendar_click_on_hidden_diary_date_is_blocked(self, mock_info):
        self._save_diary("2026-03-02", is_hidden=True)
        from PyQt5.QtCore import QDate
        self.window.rightStack.setCurrentIndex(0)
        self.window._on_calendar_date_clicked(QDate.fromString("2026-03-02", "yyyy-MM-dd"))
        mock_info.assert_called_once()
        self.assertEqual(self.window.rightStack.currentIndex(), 0)

    def test_delete_returns_to_calendar_page(self):
        diary = self._save_diary("2026-03-03")
        self.window._load_diary_into_form(diary)
        self.assertEqual(self.window.rightStack.currentIndex(), 1)
        with patch("PyQt5.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
            self.window._on_delete_clicked()
        self.assertEqual(self.window.rightStack.currentIndex(), 0)

    def test_calendar_color_palette_boundaries(self):
        self.assertEqual(EmotionCalendarWidget._color_for_score(0).name(), "#45475a")
        self.assertEqual(EmotionCalendarWidget._color_for_score(5).name(), "#f38ba8")
        self.assertEqual(EmotionCalendarWidget._color_for_score(-5).name(), "#89b4fa")
        # score가 0을 살짝 넘으면 완화(mild) 긍정/부정 끝점 색상에 가까워야 한다
        near_zero_positive = EmotionCalendarWidget._color_for_score(0.01)
        near_zero_negative = EmotionCalendarWidget._color_for_score(-0.01)
        mild_positive = QColor("#fab387")
        mild_negative = QColor("#b4befe")
        self.assertLess(abs(near_zero_positive.red() - mild_positive.red()), 3)
        self.assertLess(abs(near_zero_negative.red() - mild_negative.red()), 3)

    def test_calendar_overlay_and_cell_rects_populated(self):
        self.window.show()
        for _ in range(3):
            QApplication.processEvents()
        self.assertIsNotNone(self.window.emotionCalendar._line_overlay)
        self.assertGreater(len(self.window.emotionCalendar._last_cell_rects), 0)

    @patch("PyQt5.QtWidgets.QDialog.exec_")
    def test_emotion_graph_button_opens_dialog_without_crash(self, mock_dialog_exec):
        mock_dialog_exec.return_value = 1
        self._save_diary("2026-06-01")
        self.window.emotionGraphButton.click()

    def test_list_item_preview_does_not_expand_on_hover(self):
        """마우스오버로 항목 텍스트가 길어지면 목록 스크롤바가 나타났다 사라졌다 하는 문제가
        있었다(전문은 텍스트 대신 툴팁으로만 보여줘야 한다)."""
        long_summary = "요약 내용 " * 20
        diary = self._save_diary("2026-06-01")
        diary.summary = long_summary
        self.repo.save(diary)

        self.window._load_diary_list()
        item = self.window.diaryListWidget.item(0)
        self.assertNotIn(long_summary.strip(), item.text())
        self.assertIn(long_summary.strip(), item.toolTip())
        self.assertFalse(hasattr(self.window, "_hovered_diary_item"))
        self.assertFalse(hasattr(self.window, "_on_diary_item_hovered"))

    # ── 하루 1개 원칙: 자동 병합 & 날짜 내비게이션 ────────────────

    def test_save_merges_into_existing_diary_on_same_date(self):
        """diary_id 없이 저장해도 같은 날짜의 기존 일기를 수정하는 것으로 병합해야 한다."""
        service = self.window._diary_service
        service.generate_summary = MagicMock(return_value="")
        kwargs = dict(
            content="내용", location_name="", actual_weather="",
            emotion1="행복했어요", emotion2="", is_hidden=False,
        )
        ok1, d1 = service.save_diary(diary_id=None, date="2026-07-01", title="첫 번째", **kwargs)
        ok2, d2 = service.save_diary(diary_id=None, date="2026-07-01", title="두 번째", **kwargs)
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(d1.id, d2.id)
        same_date = [d for d in self.repo.find_all() if d.date == "2026-07-01"]
        self.assertEqual(len(same_date), 1)
        self.assertEqual(same_date[0].title, "두 번째")
        self.assertEqual(same_date[0].created_at, d1.created_at)

    def test_save_is_blocked_when_hidden_diary_exists_on_date(self):
        """비밀 일기가 있는 날짜에는 일반 저장이 병합 대신 거부되어야 한다."""
        self._save_diary("2026-07-02", is_hidden=True)
        service = self.window._diary_service
        service.generate_summary = MagicMock(return_value="")
        ok, diary = service.save_diary(
            diary_id=None, date="2026-07-02", title="일반 일기", content="내용",
            location_name="", actual_weather="", emotion1="행복했어요", emotion2="",
            is_hidden=False,
        )
        self.assertFalse(ok)
        self.assertIsNone(diary)
        self.assertEqual(len([d for d in self.repo.find_all() if d.date == "2026-07-02"]), 1)

    def test_editor_date_change_loads_existing_diary(self):
        from PyQt5.QtCore import QDate
        diary = self._save_diary("2026-03-01")
        self.window._on_editor_date_changed(QDate.fromString("2026-03-01", "yyyy-MM-dd"))
        self.assertEqual(self.window._current_diary_id, diary.id)
        self.assertEqual(self.window.titleEdit.text(), "테스트 일기")

    def test_editor_date_change_to_empty_date_keeps_draft(self):
        from PyQt5.QtCore import QDate
        self.window._on_new_clicked()
        self.window.contentEdit.setPlainText("초안 내용")
        self.window._on_editor_date_changed(QDate.fromString("2026-04-10", "yyyy-MM-dd"))
        self.assertIsNone(self.window._current_diary_id)
        self.assertEqual(self.window.contentEdit.toPlainText(), "초안 내용")

    @patch("PyQt5.QtWidgets.QMessageBox.information")
    def test_editor_date_change_to_hidden_date_reverts(self, mock_info):
        from PyQt5.QtCore import QDate
        self._save_diary("2026-03-02", is_hidden=True)
        self.window._on_editor_date_changed(QDate.fromString("2026-03-05", "yyyy-MM-dd"))
        self.window._on_editor_date_changed(QDate.fromString("2026-03-02", "yyyy-MM-dd"))
        mock_info.assert_called_once()
        self.assertEqual(self.window.dateEdit.date().toString("yyyy-MM-dd"), "2026-03-05")

    def test_new_diary_button_opens_todays_diary_if_exists(self):
        from PyQt5.QtCore import QDate
        today = QDate.currentDate().toString("yyyy-MM-dd")
        diary = self._save_diary(today)
        self.window._on_new_clicked()
        self.assertEqual(self.window._current_diary_id, diary.id)
        self.assertEqual(self.window.titleEdit.text(), "테스트 일기")


if __name__ == "__main__":
    unittest.main()
