"""
AppGUI — 메인 GUI 클래스
Qt Designer .ui 파일을 로드하고, 사용자 이벤트를 처리한다.
"""

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QDialog, QMessageBox, QListWidgetItem,
    QLabel, QComboBox, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidgetItem, QHeaderView, QScrollArea,
    QCheckBox, QInputDialog,
)
from PyQt5.QtCore import QDate, Qt, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QPixmap, QColor, QPainter, QPen, QImage
from PyQt5 import uic

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from runtime_env import configure_runtime

configure_runtime(PROJECT_ROOT)

from diary_categories import (
    ALL_FILTER_OPTIONS,
    DEFAULT_EMOTION,
    MANUAL_EMOTION_OPTIONS,
    MANUAL_WEATHER_OPTIONS,
    truncate_summary,
)
from application.service.diary_service import DiaryService

# .ui 파일 경로
UI_DIR = os.path.join(PROJECT_ROOT, "ui")
MAIN_UI = os.path.join(UI_DIR, "main_window.ui")
KEYWORD_UI = os.path.join(UI_DIR, "keyword_dialog.ui")


class DrawingCanvas(QWidget):
    """PyQt 기반 그림 일기 캔버스."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: white; border: 1px solid #45475a; border-radius: 8px;")
        self._image = QImage(self.size(), QImage.Format_RGB32)
        self._image.fill(Qt.white)
        self._last_point = None
        self._pen_color = QColor("black")
        self._dirty = False
        self._has_content = False

    def resizeEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
        if self._image.size() == self.size():
            return

        new_image = QImage(self.size(), QImage.Format_RGB32)
        new_image.fill(Qt.white)
        painter = QPainter(new_image)
        painter.drawImage(0, 0, self._image)
        painter.end()
        self._image = new_image
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(self.rect(), self._image)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._last_point is not None:
            painter = QPainter(self._image)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(self._pen_color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self._last_point, event.pos())
            painter.end()
            self._last_point = event.pos()
            self._dirty = True
            self._has_content = True
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_point = None

    def set_pen_color(self, color_name: str):
        self._pen_color = QColor(color_name)

    def clear(self):
        self._image.fill(Qt.white)
        self._dirty = False
        self._has_content = False
        self._last_point = None
        self.update()

    def load_image(self, image_path: str):
        image = QImage(image_path)
        if image.isNull():
            raise ValueError("이미지를 불러오지 못했습니다.")
        scaled = image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image.fill(Qt.white)
        painter = QPainter(self._image)
        x = max((self.width() - scaled.width()) // 2, 0)
        y = max((self.height() - scaled.height()) // 2, 0)
        painter.drawImage(x, y, scaled)
        painter.end()
        self._dirty = False
        self._has_content = True
        self.update()

    def export_image(self) -> QImage:
        return self._image.copy()

    def has_image_content(self) -> bool:
        return self._has_content or self._dirty

    def is_modified(self) -> bool:
        return self._dirty


class SaveWorker(QThread):
    """저장(+AI 한 줄 요약) → AI 공감/그림분석을 순서대로 실행하는 백그라운드 워커."""

    save_finished = pyqtSignal(bool, object)  # success, diary(or None)
    status_changed = pyqtSignal(str)
    empathy_finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, service, save_kwargs, image_base64):
        super().__init__()
        self.service = service
        self.save_kwargs = save_kwargs
        self.image_base64 = image_base64

    def run(self):
        try:
            success, diary = self.service.save_diary(**self.save_kwargs)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.error.emit(str(exc))
            return

        self.save_finished.emit(success, diary)
        if not success or diary is None:
            return

        self.status_changed.emit("🤖 AI가 조언 중입니다...\n잠시만 기다려주세요. ✨")
        try:
            result = self.service.analyze_empathy(
                date=diary.date,
                content=diary.content,
                location=diary.weather.location,
                weather=diary.weather.actual_weather_text,
                emotion=diary.emotion_label,
                image_base64=self.image_base64,
            )
            self.empathy_finished.emit(result)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.error.emit(str(exc))


class AppGUI(QMainWindow):
    """감정 일기장 메인 윈도우 클래스."""

    def __init__(self):
        super().__init__()

        # .ui 파일 로드
        uic.loadUi(MAIN_UI, self)
        self.setWindowTitle("내 감정은 오늘도 F등급 ☀️⛅🌧️")

        # 서비스 초기화
        self._diary_service = DiaryService()

        # 현재 선택된 일기 ID (수정 모드용)
        self._current_diary_id = None
        self._existing_image_path = ""
        self._remove_existing_image = False
        self._hovered_diary_item = None
        # UI 초기화
        self._init_ui()
        self._connect_events()
        self._load_diary_list()

    @property
    def _ai_helper(self):
        return self._diary_service._ai_service._helper

    @property
    def _keyword_analyzer(self):
        return self._diary_service._keyword_analyzer

    @property
    def _text_processor(self):
        return self._diary_service._text_processor

    def _init_ui(self):
        """메인 화면 초기 설정."""
        # 오늘 날짜 설정
        self.dateEdit.setDate(QDate.currentDate())

        # 상태바 초기 메시지
        self._set_status_message("환영합니다! 오늘의 일기를 작성해 보세요. 📝")

        # 삭제 버튼 초기 비활성화
        self.deleteButton.setEnabled(False)

        # Tk 버전과 동일한 필터 UI를 왼쪽 목록 상단에 추가한다.
        filter_label = QLabel("  필터")
        self.filterComboBox = QComboBox()
        self.filterComboBox.addItems(ALL_FILTER_OPTIONS)
        self.leftLayout.insertWidget(1, filter_label)
        self.leftLayout.insertWidget(2, self.filterComboBox)

        # 위치 / 현재 날씨 / 오늘 감정 입력
        self.locationLineEdit = QLineEdit()
        self.locationLineEdit.setPlaceholderText("위치를 입력하세요")
        self.actualWeatherComboBox = QComboBox()
        self.actualWeatherComboBox.addItems(MANUAL_WEATHER_OPTIONS)
        self.actualWeatherComboBox2 = QComboBox()
        self.actualWeatherComboBox2.addItems(["선택안함"] + list(MANUAL_WEATHER_OPTIONS))

        self.emotionComboBox = QComboBox()
        self.emotionComboBox.addItems(MANUAL_EMOTION_OPTIONS)
        self.emotionComboBox2 = QComboBox()
        self.emotionComboBox2.addItems(["선택안함"] + list(MANUAL_EMOTION_OPTIONS))

        context_row = QHBoxLayout()
        context_row.addWidget(QLabel("위치"))
        context_row.addWidget(self.locationLineEdit, 1)
        context_row.addWidget(QLabel("날씨"))
        context_row.addWidget(self.actualWeatherComboBox, 1)
        context_row.addWidget(self.actualWeatherComboBox2, 1)
        context_row.addWidget(QLabel("감정"))
        context_row.addWidget(self.emotionComboBox, 1)
        context_row.addWidget(self.emotionComboBox2, 1)
        self.rightLayout.insertLayout(1, context_row)

        # 1. headerLayout에서 titleEdit 분리 (제목을 그림판 아래로 이동)
        self.headerLayout.removeWidget(self.titleEdit)

        # 2. 그림판 영역 구성
        draw_layout = QVBoxLayout()
        draw_layout.setContentsMargins(0, 0, 0, 0)
        draw_controls = QHBoxLayout()
        draw_controls.addWidget(QLabel("🎨 펜 색상"))
        self.colorComboBox = QComboBox()
        self.colorComboBox.addItems(["black", "red", "blue", "green", "yellow", "white"])
        draw_controls.addWidget(self.colorComboBox)
        draw_controls.addStretch(1)
        self.clearCanvasButton = QPushButton("지우기")
        draw_controls.addWidget(self.clearCanvasButton)
        draw_layout.addLayout(draw_controls)

        self.drawingCanvas = DrawingCanvas()
        draw_layout.addWidget(self.drawingCanvas)

        # 3. 텍스트 입력 영역 (제목 + 내용)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_label = QLabel("제목:")
        title_label.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 14px;")
        title_row.addWidget(title_label)
        title_row.addWidget(self.titleEdit, 1)

        self.hideCheckBox = QCheckBox("🔒 비밀 일기(숨기기)")
        self.hideCheckBox.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 13px;")
        title_row.addWidget(self.hideCheckBox)

        text_layout.addLayout(title_row)

        # 원래 레이아웃에서 contentEdit를 떼어내어 text_layout에 추가
        index = self.rightLayout.indexOf(self.contentEdit)
        if index != -1:
            self.rightLayout.takeAt(index)
        text_layout.addWidget(self.contentEdit)

        # 4. 오른쪽 패널 수직 레이아웃(rightLayout) 재배치
        if index != -1:
            self.rightLayout.insertLayout(index, draw_layout)
            self.rightLayout.insertLayout(index + 1, text_layout)
        else:
            self.rightLayout.addLayout(draw_layout)
            self.rightLayout.addLayout(text_layout)

        # 비율(Stretch) 설정: 캔버스 3, 텍스트 2
        self.rightLayout.setStretchFactor(draw_layout, 3)
        self.rightLayout.setStretchFactor(text_layout, 2)

        # QComboBox 스타일을 다크 모드에 맞게 전역 추가 (QTabWidget 스타일 제거)
        extra_style = """
        QComboBox {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 6px 10px;
            color: #cdd6f4;
            font-size: 13px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #45475a;
        }
        QComboBox QAbstractItemView {
            background-color: #313244;
            color: #cdd6f4;
            selection-background-color: #89b4fa;
            selection-color: #1e1e2e;
        }
        QTextEdit {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 12px;
            color: #cdd6f4;
            font-size: 14px;
            line-height: 1.6;
        }
        QTextEdit:focus {
            border: 1px solid #89b4fa;
        }
        """
        self.setStyleSheet(self.styleSheet() + extra_style)

    def _connect_events(self):
        """버튼 클릭 등 이벤트 핸들러를 연결한다."""
        self.saveButton.clicked.connect(self.on_save_clicked)
        self.deleteButton.clicked.connect(self._on_delete_clicked)
        self.mindmapButton.clicked.connect(self.show_mindmap_window)
        self.newButton.clicked.connect(self._on_new_clicked)
        self.diaryListWidget.currentItemChanged.connect(self._on_diary_selected)
        self.filterComboBox.currentTextChanged.connect(self._load_diary_list)
        self.colorComboBox.currentTextChanged.connect(self.drawingCanvas.set_pen_color)
        self.clearCanvasButton.clicked.connect(self._clear_canvas)

        # 목록 항목에 마우스를 올리면 잘린 요약 대신 전문이 보이도록 확장
        self.diaryListWidget.setWordWrap(True)
        self.diaryListWidget.setMouseTracking(True)
        self.diaryListWidget.itemEntered.connect(self._on_diary_item_hovered)
        self.diaryListWidget.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.diaryListWidget.viewport() and event.type() == QEvent.Leave:
            self._reset_hovered_diary_item()
        return super().eventFilter(obj, event)

    def _on_diary_item_hovered(self, item: QListWidgetItem):
        """목록 항목에 마우스가 올라가면 잘린 요약 대신 전문을 보여주고, item 높이를 늘린다."""
        if item is self._hovered_diary_item:
            return
        self._reset_hovered_diary_item()
        full_text = item.data(Qt.UserRole + 1)
        if full_text:
            item.setText(full_text)
            self._hovered_diary_item = item

    def _reset_hovered_diary_item(self):
        """마우스가 목록을 벗어나거나 다른 항목으로 옮겨가면 이전 항목을 원래 미리보기로 되돌린다."""
        if self._hovered_diary_item is not None:
            preview_text = self._hovered_diary_item.data(Qt.UserRole + 2)
            if preview_text is not None:
                self._hovered_diary_item.setText(preview_text)
            self._hovered_diary_item = None

    # ── 이벤트 핸들러 ────────────────────────────────────────────

    def on_save_clicked(self):
        """'저장' 버튼 클릭: 일기를 저장하고 이어서 AI 한 줄 요약/공감/그림분석을 진행한다."""
        date_str = self.dateEdit.date().toString("yyyy-MM-dd")
        title = self.titleEdit.text().strip()
        content = self.contentEdit.toPlainText().strip()
        location_name = self.locationLineEdit.text().strip()

        # 날씨 1, 2 처리
        w_val1 = self.actualWeatherComboBox.currentText().strip()
        w_val2 = self.actualWeatherComboBox2.currentText().strip()

        # 감정 1, 2 처리
        e_label1 = self.emotionComboBox.currentText().strip()
        e_label2 = self.emotionComboBox2.currentText().strip()

        # 입력 검증
        if not content and not self._has_drawn_content():
            self.display_alert("일기 내용이나 그림을 입력해 주세요.")
            return
        if not title:
            title = f"{date_str} 일기"

        # 그림 이미지 저장 로직
        image_data = None
        if self.drawingCanvas.is_modified():
            image_data = self.drawingCanvas.export_image()

        remove_existing_image = False
        if self._current_diary_id is not None and self._remove_existing_image:
            remove_existing_image = True

        # 비밀 일기(숨기기): 전역 비밀번호를 최초 1회만 설정
        is_hidden_val = False
        if self.hideCheckBox.isChecked():
            is_hidden_val = True
            if not self._diary_service.has_secret_password():
                pwd, ok = QInputDialog.getText(
                    self, "🔒 비밀번호 설정",
                    "비밀 일기 기능을 사용하려면 비밀번호를 설정해주세요:",
                    QLineEdit.Password
                )
                if ok and pwd.strip():
                    self._diary_service.set_secret_password(pwd.strip())
                else:
                    self.hideCheckBox.setChecked(False)
                    is_hidden_val = False

        image_base64 = self._get_image_base64()

        save_kwargs = dict(
            diary_id=self._current_diary_id,
            date=date_str,
            title=title,
            content=content,
            location_name=location_name,
            actual_weather1=w_val1,
            actual_weather2=w_val2,
            emotion1=e_label1,
            emotion2=e_label2,
            is_hidden=is_hidden_val,
            image_data=image_data,
            remove_image=remove_existing_image,
        )

        self._run_save_and_analyze(save_kwargs, image_base64, w_val1, w_val2)

    def _on_delete_clicked(self):
        """'삭제' 버튼 클릭: 선택된 일기를 삭제한다."""
        if self._current_diary_id is None:
            self.display_alert("삭제할 일기를 선택해 주세요.")
            return

        reply = QMessageBox.question(
            self, "삭제 확인",
            "정말 이 일기를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            success = self._diary_service.delete_diary(self._current_diary_id)
            if success:
                self._on_new_clicked()
                self._load_diary_list()
                self._set_status_message("🗑️ 일기가 삭제되었습니다.")
            else:
                self.display_alert("삭제에 실패했습니다.")

    def _on_new_clicked(self):
        """'새 일기' 버튼 클릭: 입력 필드를 초기화한다."""
        self._current_diary_id = None
        self.dateEdit.setDate(QDate.currentDate())
        self.titleEdit.clear()
        self.locationLineEdit.clear()
        self.actualWeatherComboBox.setCurrentText(MANUAL_WEATHER_OPTIONS[0])
        self.actualWeatherComboBox2.setCurrentText("선택안함")
        self.emotionComboBox.setCurrentText(DEFAULT_EMOTION)
        self.emotionComboBox2.setCurrentText("선택안함")
        self.contentEdit.clear()
        self._existing_image_path = ""
        self._remove_existing_image = False
        self._clear_canvas(mark_removed=False)
        self.hideCheckBox.setChecked(False)
        self.weatherLabel.setText("⛅")
        self.scoreLabel.setText(f"감정 상태: {DEFAULT_EMOTION} (0점, 티어: C)")
        self.deleteButton.setEnabled(False)
        self.diaryListWidget.clearSelection()
        self._set_status_message("새 일기를 작성해 보세요. ✍️")

    def _on_diary_selected(self, current: QListWidgetItem, previous):
        """일기 목록에서 항목 선택 시 내용을 표시한다."""
        if current is None:
            return

        diary_id = current.data(Qt.UserRole)
        if diary_id is None:
            return

        # 서비스에서 해당 일기 조회
        diary = self._diary_service.get_diary_by_id(diary_id)
        if diary:
            self._current_diary_id = diary_id
            self.dateEdit.setDate(QDate.fromString(diary.date, "yyyy-MM-dd"))
            self.titleEdit.setText(diary.title)
            self.locationLineEdit.setText(diary.weather.location)
            actual_weather_val = diary.weather.actual_weather
            actual_weather_text_val = diary.weather.actual_weather_text

            # 날씨 1, 2 로드
            weathers_emoji = [w.strip() for w in actual_weather_val.split(",") if w.strip()]
            weathers_text = [w.strip() for w in actual_weather_text_val.split(",") if w.strip()]

            def find_weather_label(emoji, text):
                label = f"{emoji} {text}".strip()
                for opt in MANUAL_WEATHER_OPTIONS:
                    if opt.strip() == label:
                        return opt
                return None

            if len(weathers_emoji) >= 1:
                lbl1 = find_weather_label(weathers_emoji[0], weathers_text[0] if len(weathers_text) >= 1 else "")
                self.actualWeatherComboBox.setCurrentText(lbl1 or MANUAL_WEATHER_OPTIONS[0])
            else:
                self.actualWeatherComboBox.setCurrentText(MANUAL_WEATHER_OPTIONS[0])

            if len(weathers_emoji) >= 2:
                lbl2 = find_weather_label(weathers_emoji[1], weathers_text[1] if len(weathers_text) >= 2 else "")
                self.actualWeatherComboBox2.setCurrentText(lbl2 or "선택안함")
            else:
                self.actualWeatherComboBox2.setCurrentText("선택안함")

            emotion_label_val = diary.emotion_label or DEFAULT_EMOTION
            emotion_label = emotion_label_val
            emotions = [e.strip() for e in emotion_label_val.split(",") if e.strip()]

            if len(emotions) >= 1:
                if emotions[0] in MANUAL_EMOTION_OPTIONS:
                    self.emotionComboBox.setCurrentText(emotions[0])
                else:
                    self.emotionComboBox.setCurrentText(DEFAULT_EMOTION)
            else:
                self.emotionComboBox.setCurrentText(DEFAULT_EMOTION)

            if len(emotions) >= 2:
                if emotions[1] in MANUAL_EMOTION_OPTIONS:
                    self.emotionComboBox2.setCurrentText(emotions[1])
                else:
                    self.emotionComboBox2.setCurrentText("선택안함")
            else:
                self.emotionComboBox2.setCurrentText("선택안함")
            self.contentEdit.setPlainText(diary.content)
            self._existing_image_path = ""
            self._remove_existing_image = False
            self._clear_canvas(mark_removed=False)

            image_path = diary.image_path
            if image_path and os.path.exists(image_path):
                try:
                    self.drawingCanvas.load_image(image_path)
                    self._existing_image_path = image_path
                except Exception as e:
                    print(f"이미지 로드 실패: {e}")

            # 날씨 표시
            weather = diary.weather.emoji
            score = int(diary.emotion_score.value)
            tier = diary.emotion_score.tier
            self.weatherLabel.setText(weather)
            self.scoreLabel.setText(f"감정 상태: {emotion_label} ({score}점, 티어: {tier})")
            self.hideCheckBox.setChecked(diary.is_hidden)

            self.deleteButton.setEnabled(True)
            self._set_status_message(
                f"📖 {diary.date} — {diary.title or ''}"
            )

    # ── UI 업데이트 ────────────────────────────────────────────

    def update_weather_icon(self, result: dict):
        """사용자 선택 감정 상태에 따라 아이콘과 요약을 갱신한다."""
        self.weatherLabel.setText(result["weather_emoji"])
        self.scoreLabel.setText(f"감정 상태: {result['emotion_label']} ({result['score']}점)")

    def _load_diary_list(self):
        """CSV에서 일기 목록을 읽어 왼쪽 리스트에 표시한다 (비밀 일기는 제외됨)."""
        self._reset_hovered_diary_item()
        self.diaryListWidget.clear()
        filter_value = self.filterComboBox.currentText() if hasattr(self, "filterComboBox") else "전체보기"

        diaries = self._diary_service.get_all_diaries(filter_value=filter_value)
        # 최신순 정렬
        diaries.sort(key=lambda x: x.date, reverse=True)

        for diary in diaries:
            date_str = diary.date
            title = diary.title or "제목 없음"
            weather = diary.weather.actual_weather or diary.weather.emoji
            diary_id = diary.id

            base_text = f"{weather} {date_str}\n     {title}"
            preview_text = base_text
            full_text = base_text
            if diary.summary:
                preview_text += f"\n     📝 {truncate_summary(diary.summary)}"
                full_text += f"\n     📝 {diary.summary}"

            item = QListWidgetItem(preview_text)
            item.setData(Qt.UserRole, diary_id)
            # 마우스를 올렸을 때(hover) 보여줄 전문과, 원래대로 되돌릴 미리보기를 저장해둔다
            item.setData(Qt.UserRole + 1, full_text)
            item.setData(Qt.UserRole + 2, preview_text)
            self.diaryListWidget.addItem(item)

        if self.diaryListWidget.count() == 0 and filter_value != "전체보기":
            self._set_status_message(
                f"선택한 필터 '{filter_value}'에 해당하는 일기가 없습니다."
            )
        elif filter_value == "전체보기":
            self._set_status_message("환영합니다! 오늘의 일기를 작성해 보세요. 📝")

    def _set_status_message(self, base_message: str):
        """기본 상태 메시지를 표시한다."""
        self.statusbar.showMessage(base_message)

    def _clear_canvas(self, mark_removed: bool = True):
        """그림 캔버스를 초기화한다."""
        if mark_removed and self._existing_image_path:
            self._remove_existing_image = True
        self.drawingCanvas.clear()

    def _has_drawn_content(self) -> bool:
        """현재 그림 일기 내용이 존재하는지 반환한다."""
        return self.drawingCanvas.has_image_content() or bool(self._existing_image_path)

    def _get_image_base64(self) -> str:
        """캔버스/기존 이미지에서 Base64 인코딩된 그림 데이터를 추출한다."""
        if not self._has_drawn_content():
            return ""

        import base64
        # 만약 기존 저장된 이미지가 존재하고 새로 그리지 않았다면 디스크의 이미지 파일에서 바로 읽음
        if self._existing_image_path and not self.drawingCanvas._dirty and os.path.exists(self._existing_image_path):
            try:
                with open(self._existing_image_path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode("utf-8")
            except Exception as e:
                print(f"디스크에서 이미지 읽기 실패: {e}")
                return ""

        # 새롭게 그렸거나 수정된 경우 캔버스에서 직접 이미지 데이터 추출
        try:
            from PyQt5.QtCore import QBuffer
            qimage = self.drawingCanvas.export_image()
            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            qimage.save(buffer, "PNG")
            img_bytes = bytes(buffer.data())
            return base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            print(f"캔버스 이미지 Base64 변환 실패: {e}")
            return ""

    def _run_save_and_analyze(self, save_kwargs: dict, image_base64: str, w_val1: str, w_val2: str):
        """저장 → AI 한 줄 요약 → AI 공감/그림분석을 한 모달 다이얼로그 안에서 순서대로 보여준다."""
        dialog = QDialog(self)
        dialog.setWindowTitle("🤖 AI 공감 일기 도우미")
        dialog.resize(540, 520)
        dialog.setMinimumSize(500, 300)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-family: "Apple SD Gothic Neo", "Helvetica Neue", sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 10px;
                color: #cdd6f4;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("🤖 AI 일기 분석 및 공감")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #c6a0f6;")
        main_layout.addWidget(title_label)

        # 스크롤 영역 설정
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(15)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # 1. 로딩/상태 메시지 (저장 중... → AI가 조언 중... 순서로 전환됨)
        status_label = QLabel("💾 일기를 저장하는 중입니다...\n잠시만 기다려주세요.")
        status_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #a6adc8;")
        status_label.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(status_label)

        # 2. 결과 위젯들 (처음엔 숨김)
        summary_title = QLabel("📝 AI 한 줄 요약 (수정 가능)")
        summary_title.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 14px;")
        summary_title.setVisible(False)
        scroll_layout.addWidget(summary_title)

        summary_edit = QLineEdit()
        summary_edit.setVisible(False)
        scroll_layout.addWidget(summary_edit)

        empathy_title = QLabel("💖 AI의 공감과 한마디")
        empathy_title.setStyleSheet("font-weight: bold; color: #a6e3a1; font-size: 14px;")
        empathy_title.setVisible(False)
        scroll_layout.addWidget(empathy_title)

        empathy_text = QLabel()
        empathy_text.setWordWrap(True)
        empathy_text.setStyleSheet("background-color: #313244; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.5;")
        empathy_text.setVisible(False)
        scroll_layout.addWidget(empathy_text)

        drawing_title = QLabel("🎨 그림 분석")
        drawing_title.setStyleSheet("font-weight: bold; color: #f9e2af; font-size: 14px;")
        drawing_title.setVisible(False)
        scroll_layout.addWidget(drawing_title)

        drawing_text = QLabel()
        drawing_text.setWordWrap(True)
        drawing_text.setStyleSheet("background-color: #313244; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.5;")
        drawing_text.setVisible(False)
        scroll_layout.addWidget(drawing_text)

        # 하단 확인 버튼
        ok_button = QPushButton("확인")
        ok_button.setEnabled(False)
        main_layout.addWidget(ok_button, 0, Qt.AlignCenter)

        saved_diary_holder = {}

        def _on_save_finished(success, diary):
            action = "수정" if save_kwargs.get("diary_id") is not None else "저장"
            if success and diary:
                saved_diary_holder["diary"] = diary
                self._current_diary_id = diary.id
                if save_kwargs.get("image_data"):
                    self._existing_image_path = diary.image_path
                    self._remove_existing_image = False
                elif save_kwargs.get("remove_image"):
                    self._existing_image_path = ""
                    self._remove_existing_image = False

                self.update_weather_icon({
                    "weather_emoji": diary.weather.emoji,
                    "emotion_label": diary.emotion_label,
                    "score": int(diary.emotion_score.value),
                    "actual_weather": diary.weather.actual_weather,
                    "actual_weather_text": diary.weather.actual_weather_text,
                    "location_name": diary.weather.location,
                })
                self._load_diary_list()
                actual_weather_value = f"{w_val1}, {w_val2}" if w_val2 and w_val2 != "선택안함" else w_val1
                self._set_status_message(
                    f"✅ 일기가 {action}되었습니다! 감정: {diary.emotion_label} | 현재 날씨: {actual_weather_value}"
                )
                summary_edit.setText(diary.summary or "")
            else:
                if not dialog.isVisible():
                    return
                status_label.setText(f"❌ 일기 {action}에 실패했습니다.")
                status_label.setStyleSheet("color: #f38ba8; font-size: 13px; line-height: 1.5;")
                ok_button.setEnabled(True)

        def _on_status_changed(text):
            if not dialog.isVisible():
                return
            status_label.setText(text)

        def _on_empathy_finished(result):
            if not dialog.isVisible():
                return
            status_label.setVisible(False)

            summary_title.setVisible(True)
            summary_edit.setVisible(True)

            empathy_text.setText(result.get("empathy", ""))
            empathy_text.setVisible(True)
            empathy_title.setVisible(True)

            drawing_text.setText(result.get("drawing_analysis", ""))
            if result.get("drawing_analysis"):
                drawing_text.setVisible(True)
                drawing_title.setVisible(True)

            ok_button.setEnabled(True)

        def _on_error(err_str):
            if not dialog.isVisible():
                return
            status_label.setVisible(True)
            status_label.setText(f"❌ AI 분석에 실패했습니다:\n\n{err_str}")
            status_label.setStyleSheet("color: #f38ba8; font-size: 13px; line-height: 1.5;")
            if "diary" in saved_diary_holder:
                summary_title.setVisible(True)
                summary_edit.setVisible(True)
            ok_button.setEnabled(True)

        def _on_confirm_clicked():
            diary = saved_diary_holder.get("diary")
            if diary is not None:
                new_summary = summary_edit.text().strip()
                if new_summary != (diary.summary or ""):
                    self._diary_service.update_summary(diary.id, new_summary)
                    self._load_diary_list()
                if diary.is_hidden:
                    # 비밀 일기는 목록에서 완전히 제외되므로 편집 폼을 초기화한다
                    self._on_new_clicked()
            dialog.accept()

        ok_button.clicked.connect(_on_confirm_clicked)

        self._save_worker = SaveWorker(self._diary_service, save_kwargs, image_base64)
        self._save_worker.save_finished.connect(_on_save_finished)
        self._save_worker.status_changed.connect(_on_status_changed)
        self._save_worker.empathy_finished.connect(_on_empathy_finished)
        self._save_worker.error.connect(_on_error)
        self._save_worker.start()

        dialog.exec_()

    def show_mindmap_window(self):
        """키워드 분석(마인드맵) 팝업 창을 띄운다."""
        dialog = QDialog(self)
        uic.loadUi(KEYWORD_UI, dialog)

        # 기본 기간: 최근 7일
        today = QDate.currentDate()
        dialog.startDateEdit.setDate(today.addDays(-7))
        dialog.endDateEdit.setDate(today)

        # 분석 버튼 이벤트
        dialog.analyzeButton.clicked.connect(
            lambda: self._run_keyword_analysis(dialog)
        )

        dialog.exec_()

    def _run_keyword_analysis(self, dialog: QDialog):
        """키워드 분석을 실행하고 결과를 다이얼로그에 표시한다."""
        start = dialog.startDateEdit.date().toString("yyyy-MM-dd")
        end = dialog.endDateEdit.date().toString("yyyy-MM-dd")

        # 기간 내 일기 데이터 읽기
        entries = self._diary_service.get_diaries_by_date_range(start, end)

        if not entries:
            dialog.wordcloudLabel.setText("해당 기간에 작성된 일기가 없습니다.")
            dialog.keywordTable.setRowCount(0)
            return

        # 모든 일기 내용 병합 후 전처리
        words = self._diary_service.get_word_list_from_diaries(entries)

        if not words:
            dialog.wordcloudLabel.setText("분석할 키워드가 없습니다.")
            dialog.keywordTable.setRowCount(0)
            return

        # 키워드 순위
        top_keywords, wc_bytes = self._diary_service.analyze_keywords(entries)

        # 테이블 업데이트
        dialog.keywordTable.setRowCount(len(top_keywords))
        dialog.keywordTable.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        for i, (word, count) in enumerate(top_keywords):
            rank_item = QTableWidgetItem(str(i + 1))
            rank_item.setTextAlignment(Qt.AlignCenter)
            word_item = QTableWidgetItem(word)
            word_item.setTextAlignment(Qt.AlignCenter)
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)

            dialog.keywordTable.setItem(i, 0, rank_item)
            dialog.keywordTable.setItem(i, 1, word_item)
            dialog.keywordTable.setItem(i, 2, count_item)

        # 워드클라우드 생성 및 표시
        try:
            if wc_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(wc_bytes)
                scaled = pixmap.scaled(
                    dialog.wordcloudLabel.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                dialog.wordcloudLabel.setPixmap(scaled)
            else:
                dialog.wordcloudLabel.setText("워드클라우드 생성에 실패했습니다.")
        except Exception as e:
            dialog.wordcloudLabel.setText(f"워드클라우드 오류: {str(e)}")

        # 정보 라벨 업데이트
        dialog.infoLabel.setText(
            f"📊 {start} ~ {end} | 일기 {len(entries)}개 | "
            f"총 키워드 {len(words)}개"
        )

    def display_alert(self, msg: str):
        """안내 사항이나 예외 발생 시 메시지 팝업을 출력한다.

        Args:
            msg: 표시할 메시지
        """
        QMessageBox.information(self, "알림", msg)
