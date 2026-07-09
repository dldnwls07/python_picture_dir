import os
import tempfile
import unittest

from app_tkinter import AppGUI, EmotionCalendarFrame
from domain.model.diary import Diary
from domain.model.value_objects import EmotionScore, Weather
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from infrastructure.persistence.secret_password_store import SecretPasswordStore
from application.service.diary_service import DiaryService


class AppTkinterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="app_tkinter_test_")
        try:
            self.window = AppGUI()
        except Exception as e:
            self.skipTest(f"Tk 디스플레이를 사용할 수 없어 건너뜀: {e}")
            return
        self.repo = CSVDiaryRepository(os.path.join(self.temp_dir, "diary.csv"))
        self.password_store = SecretPasswordStore(os.path.join(self.temp_dir, "password.txt"))
        self.window._diary_service = DiaryService(repository=self.repo, password_store=self.password_store)

    def tearDown(self):
        if hasattr(self, "window"):
            self.window.destroy()

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
        self.window.update()
        self.assertTrue(self.window.calendar_page.winfo_ismapped())
        self.assertFalse(self.window.editor_page.winfo_ismapped())

    def test_new_diary_button_switches_to_editor_page(self):
        self.window.btn_new.invoke()
        self.window.update()
        self.assertTrue(self.window.editor_page.winfo_ismapped())

    def test_back_to_calendar_button_returns_to_calendar_page(self):
        self.window.btn_new.invoke()
        self.window.update()
        self.assertTrue(self.window.editor_page.winfo_ismapped())
        self.window.btn_back_to_calendar.invoke()
        self.window.update()
        self.assertTrue(self.window.calendar_page.winfo_ismapped())

    def test_calendar_click_on_empty_date_opens_new_diary_form(self):
        self.window._on_calendar_date_clicked("2026-05-05")
        self.window.update()
        self.assertTrue(self.window.editor_page.winfo_ismapped())
        self.assertEqual(self.window.date_var.get(), "2026-05-05")
        self.assertIsNone(self.window._current_diary_id)

    def test_calendar_click_on_existing_date_loads_diary(self):
        diary = self._save_diary("2026-03-01")
        self.window._on_calendar_date_clicked("2026-03-01")
        self.window.update()
        self.assertTrue(self.window.editor_page.winfo_ismapped())
        self.assertEqual(self.window._current_diary_id, diary.id)
        self.assertEqual(self.window.title_var.get(), "테스트 일기")

    def test_calendar_click_on_hidden_diary_date_is_blocked(self):
        self._save_diary("2026-03-02", is_hidden=True)
        alerts = []
        self.window.display_alert = lambda msg: alerts.append(msg)
        self.window._on_calendar_date_clicked("2026-03-02")
        self.window.update()
        self.assertEqual(len(alerts), 1)
        self.assertTrue(self.window.calendar_page.winfo_ismapped())

    def test_delete_returns_to_calendar_page(self):
        diary = self._save_diary("2026-03-03")
        self.window._load_diary_into_form(diary)
        self.window.update()
        self.assertTrue(self.window.editor_page.winfo_ismapped())

        import tkinter.messagebox as messagebox
        original_askyesno = messagebox.askyesno
        messagebox.askyesno = lambda *a, **k: True
        try:
            self.window._on_delete_clicked()
        finally:
            messagebox.askyesno = original_askyesno
        self.window.update()
        self.assertTrue(self.window.calendar_page.winfo_ismapped())

    def test_calendar_color_palette_boundaries(self):
        self.assertEqual(EmotionCalendarFrame._color_for_score(None), EmotionCalendarFrame._COLOR_NO_DATA)
        self.assertEqual(EmotionCalendarFrame._color_for_score(0), EmotionCalendarFrame._COLOR_NEUTRAL)
        self.assertEqual(
            EmotionCalendarFrame._color_for_score(5),
            EmotionCalendarFrame._blend(
                EmotionCalendarFrame._COLOR_POSITIVE_MILD, EmotionCalendarFrame._COLOR_POSITIVE_EXTREME, 1.0
            ),
        )
        self.assertEqual(
            EmotionCalendarFrame._color_for_score(-5),
            EmotionCalendarFrame._blend(
                EmotionCalendarFrame._COLOR_NEGATIVE_MILD, EmotionCalendarFrame._COLOR_NEGATIVE_EXTREME, 1.0
            ),
        )

    def test_calendar_canvas_click_dispatches_correct_date(self):
        self._save_diary("2026-04-01")
        self.window.emotion_calendar.set_emotion_scores(
            self.window._diary_service.get_emotion_scores_by_date()
        )
        self.window.update()
        cal = self.window.emotion_calendar
        self.assertGreater(len(cal._cell_bounds), 0)
        clicked = []
        cal._on_date_click = lambda d: clicked.append(d)
        x0, y0, x1, y1, date_str = cal._cell_bounds[0]

        class FakeEvent:
            x = (x0 + x1) / 2
            y = (y0 + y1) / 2

        cal._on_canvas_click(FakeEvent())
        self.assertEqual(clicked, [date_str])

    def test_emotion_graph_button_opens_dialog_without_crash(self):
        self._save_diary("2026-06-01")
        self.window.btn_emotion_graph.invoke()
        self.window.update()
        # 열린 Toplevel(그래프 다이얼로그)을 정리한다
        for child in self.window.winfo_children():
            if isinstance(child, __import__("tkinter").Toplevel):
                child.destroy()


if __name__ == "__main__":
    unittest.main()
