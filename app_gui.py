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
    QCheckBox, QInputDialog, QGraphicsOpacityEffect, QDateEdit,
    QCalendarWidget, QStackedWidget, QFrame, QTableView, QSplitter,
)
from PyQt5.QtCore import (
    QDate, Qt, QThread, pyqtSignal, QEvent, QVariantAnimation, QPropertyAnimation,
    QParallelAnimationGroup, QEasingCurve, QAbstractAnimation, QRect, QPoint, QPointF,
    QTimer,
)
from PyQt5.QtGui import QPixmap, QColor, QPainter, QPen, QImage, QPainterPath, QPolygonF
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
    EMOTION_TIER_OPTIONS,
    MANUAL_EMOTION_OPTIONS,
    MANUAL_WEATHER_OPTIONS,
    truncate_summary,
)
from domain.model.value_objects import DiaryFilter
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


class _WeeklyTrendOverlay(QWidget):
    """QCalendarWidget 내부 날짜 그리드(QTableView) 위에 겹쳐서, 한 주(행) 단위로 감정 점수
    추이를 잇는 미니 선을 그리는 투명 오버레이(8-2). 공식 API는 아니고 QCalendarWidget의 내부
    구조(QTableView)에 의존하는 우회법이라, table_view를 못 찾으면 이 위젯 자체를 만들지 않는다."""

    def __init__(self, calendar_widget: "EmotionCalendarWidget", table_view: QTableView):
        super().__init__(table_view.viewport())
        self._calendar = calendar_widget
        self._table_view = table_view
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        # 흰색 선은 히트맵의 밝은 피치/코랄 계열 셀 위에서 명도 대비가 약해 묻히므로, 히트맵
        # 팔레트에 없는 민트(포인트 컬러)로 바꾸고 두께를 키워 어떤 배경 위에서도 눈에 띄게 한다.
        pen = QPen(QColor("#94e2d5"))
        pen.setWidth(3)
        painter.setPen(pen)

        for week in self._calendar._current_month_weeks():
            points = []
            for date in week:
                date_str = date.toString("yyyy-MM-dd")
                score = self._calendar._scores_by_date.get(date_str)
                rect = self._calendar._last_cell_rects.get(date_str)
                if score is None or rect is None:
                    points.append(None)
                    continue
                ratio = (max(-5.0, min(5.0, score)) + 5.0) / 10.0  # 0(-5점) ~ 1(+5점), 축 고정
                x = rect.center().x()
                y = rect.bottom() - ratio * rect.height()
                points.append(QPointF(x, y))

            # 데이터가 있는 구간만 이어 그리고, 일기가 없는 요일에서는 선을 끊는다.
            segment = []
            for p in points:
                if p is None:
                    if len(segment) >= 2:
                        painter.drawPolyline(QPolygonF(segment))
                    segment = []
                else:
                    segment.append(p)
            if len(segment) >= 2:
                painter.drawPolyline(QPolygonF(segment))
        painter.end()


class EmotionCalendarWidget(QCalendarWidget):
    """날짜별 평균 감정 점수를 배경색 히트맵 + 주간 미니 선그래프로 보여주는 캘린더(8-1/8-2/8-3)."""

    # 8-3: 다크 테마 히트맵 색상 스케일
    _COLOR_NO_DATA = QColor("#1e1e2e")
    _COLOR_NEUTRAL = QColor("#45475a")
    _COLOR_POSITIVE_MILD = QColor("#fab387")
    _COLOR_POSITIVE_EXTREME = QColor("#f38ba8")
    _COLOR_NEGATIVE_MILD = QColor("#b4befe")
    _COLOR_NEGATIVE_EXTREME = QColor("#89b4fa")
    # 비밀 일기 날짜 강조 — 히트맵 팔레트에 없는 보라(mauve) 계열이라 어떤 셀 위에서도 구분된다
    _COLOR_SECRET_BORDER = QColor("#cba6f7")
    _COLOR_SECRET_NO_DATA = QColor("#2a1a3a")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scores_by_date = {}
        self._secret_dates = set()
        self._last_cell_rects = {}
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        # 네이티브 요일(월~일) 헤더는 QSS/팔레트 어느 쪽으로도 다크 테마 색을 입힐 수 없는 내부
        # 위젯이라(라이트 모드 배경 고정, 7-9-4) 아예 끄고, 호출부(_init_right_stack)에서 직접
        # 그린 헤더 라벨 줄로 대체한다.
        self.setHorizontalHeaderFormat(QCalendarWidget.NoHorizontalHeader)
        # 기본값(일요일 시작)로 두면 _current_month_weeks()(월요일 시작 가정, 8-2 미니 선그래프가
        # 사용)와 실제 그리드의 주 경계가 어긋나서 미니 선이 서로 다른 시각적 행을 가로질러
        # 이어지는 톱니 버그가 생긴다 — Tk 쪽(EmotionCalendarFrame)도 월요일 시작이라 통일한다.
        self.setFirstDayOfWeek(Qt.Monday)
        # 무데이터 셀이 메인 배경색에 자연스럽게 묻히도록 캘린더 뷰 배경도 맞춘다(8-3).
        # 7-9-4: 선택 날짜의 각진 점선 포커스 테두리 제거 + 그리드 셀 내부 여백 확보
        self.setStyleSheet("""
            QCalendarWidget QAbstractItemView:enabled {
                outline: 0;
                background-color: #1e1e2e;
                selection-background-color: transparent;
                padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #f5f5f5;
                background-color: transparent;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #313244;
            }
        """)

        self._line_overlay = None
        table_view = self.findChild(QTableView)
        if table_view is not None:
            self._line_overlay = _WeeklyTrendOverlay(self, table_view)
            self._line_overlay.setGeometry(table_view.viewport().rect())
            self._line_overlay.raise_()
            table_view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            self._line_overlay is not None
            and obj is self._line_overlay.parent()
            and event.type() == QEvent.Resize
        ):
            self._line_overlay.setGeometry(obj.rect())
            self._line_overlay.update()
        return super().eventFilter(obj, event)

    def set_emotion_scores(self, scores_by_date: dict, secret_dates=None):
        """{"yyyy-MM-dd": 평균 점수} 딕셔너리와 비밀 일기 날짜 목록으로 캘린더 표시를 갱신한다."""
        self._scores_by_date = scores_by_date
        self._secret_dates = set(secret_dates or [])
        self.updateCells()
        if self._line_overlay is not None:
            self._line_overlay.update()

    def _current_month_weeks(self):
        """현재 표시 중인 달을 QCalendarWidget과 동일한 규칙(월요일 시작)으로 주 단위 그리드화한다."""
        import calendar as calendar_module
        cal = calendar_module.Calendar(firstweekday=0)
        weeks = []
        for week in cal.monthdatescalendar(self.yearShown(), self.monthShown()):
            weeks.append([QDate(d.year, d.month, d.day) for d in week])
        return weeks

    # 셀 안쪽 여백 — 셀 사이로 메인 배경색이 자연스러운 그리드 선처럼 드러나도록 함
    CELL_PADDING = 4

    def paintCell(self, painter: QPainter, rect, date: QDate):
        date_str = date.toString("yyyy-MM-dd")
        pad = self.CELL_PADDING
        padded_rect = rect.adjusted(pad, pad, -pad, -pad)
        # 미니 선(오버레이)도 이 패딩된 영역 안에서만 그려지도록, 꽉 찬 rect가 아니라
        # padded_rect를 저장한다 — 그래야 선이 셀 배경 바깥(그리드 여백)으로 삐져나가지 않는다.
        self._last_cell_rects[date_str] = QRect(padded_rect)
        score = self._scores_by_date.get(date_str)
        is_secret = date_str in self._secret_dates

        if score is None and not is_secret:
            super().paintCell(painter, rect, date)
            return

        painter.save()
        bg_color = self._color_for_score(score) if score is not None else QColor(self._COLOR_SECRET_NO_DATA)
        painter.fillRect(padded_rect, bg_color)

        text_color = QColor("#1e1e2e") if bg_color.lightnessF() > 0.6 else QColor("#f5f5f5")
        painter.setPen(text_color)
        bold_font = painter.font()
        bold_font.setBold(True)
        painter.setFont(bold_font)
        painter.drawText(padded_rect, Qt.AlignCenter, str(date.day()))

        if is_secret:
            # 비밀 일기 날짜: 보라 테두리 + 🔒 배지로 특별하게 표시 (내용은 여전히 잠김)
            secret_pen = QPen(self._COLOR_SECRET_BORDER)
            secret_pen.setWidth(2)
            painter.setPen(secret_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(padded_rect.adjusted(1, 1, -1, -1), 4, 4)
            lock_font = painter.font()
            lock_font.setBold(False)
            lock_font.setPointSize(max(7, lock_font.pointSize() - 2))
            painter.setFont(lock_font)
            painter.drawText(padded_rect.adjusted(0, 2, -4, 0), Qt.AlignTop | Qt.AlignRight, "🔒")

        if date == QDate.currentDate():
            today_pen = QPen(QColor("#f5f5f5"))
            today_pen.setWidth(1)
            painter.setPen(today_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(padded_rect.adjusted(0, 0, -1, -1))

        if date == self.selectedDate():
            sel_pen = QPen(QColor("#f5f5f5"))
            sel_pen.setWidth(2)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(padded_rect.adjusted(1, 1, -1, -1), 4, 4)

        painter.restore()

    @classmethod
    def _color_for_score(cls, score: float) -> QColor:
        """점수(-5~5)를 8-3에서 정한 다크 테마 팔레트로 매핑한다."""
        score = max(-5.0, min(5.0, score))
        if score == 0:
            return QColor(cls._COLOR_NEUTRAL)
        if score > 0:
            return cls._blend(cls._COLOR_POSITIVE_MILD, cls._COLOR_POSITIVE_EXTREME, score / 5.0)
        return cls._blend(cls._COLOR_NEGATIVE_MILD, cls._COLOR_NEGATIVE_EXTREME, (-score) / 5.0)

    @staticmethod
    def _blend(c1: QColor, c2: QColor, t: float) -> QColor:
        r = int(c1.red() + (c2.red() - c1.red()) * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
        return QColor(r, g, b)


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
        self._secret_mode = False
        self._secret_color_anim = None
        self._tear_animation_group = None
        # 편집 폼 날짜 내비게이션(하루 1개 원칙): 프로그램이 dateEdit 값을 바꿀 때
        # dateChanged 내비게이션이 재귀 발동하지 않도록 막는 플래그와, 비밀 일기가 있는
        # 날짜로 이동했을 때 되돌아갈 마지막 유효 날짜.
        self._syncing_editor_date = False
        self._last_editor_date = QDate.currentDate()
        # 날짜를 키보드로 입력하는 도중의 중간 값(예: 연도 한 자리씩)마다 폼이 바뀌지 않도록
        # 짧게 모아서 한 번만 내비게이션한다.
        self._date_nav_timer = QTimer(self)
        self._date_nav_timer.setSingleShot(True)
        self._date_nav_timer.setInterval(350)
        self._date_nav_timer.timeout.connect(
            lambda: self._on_editor_date_changed(self.dateEdit.date())
        )
        # QListWidget은 창이 처음 화면에 표시될 때 내부적으로 0번 항목을 한 번 자동 선택하는
        # 습성이 있어(사용자 조작이 아님), 그로 인한 최초 1회의 currentItemChanged를 걸러내기
        # 위한 플래그. _on_diary_selected에서 소비된다.
        self._suppress_next_diary_selection = True
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

    def _init_right_stack(self):
        """rightPanel을 캘린더(MAIN)/일기 편집 두 페이지짜리 QStackedWidget으로 재구성한다(7-2/7-3).

        .ui에서 로드된 rightLayout(및 그 안의 모든 위젯)은 그대로 editorPage로 옮겨 붙이므로,
        이 메서드 이후의 _init_ui() 코드는 지금까지와 동일하게 self.rightLayout/self.headerLayout/
        self.buttonLayout 등을 그대로 참조해도 된다.
        """
        # rightLayout을 rightPanel에서 editorPage로 옮겨 붙인다. Qt에서 위젯의 레이아웃을 다른
        # 위젯으로 직접 옮기는 API는 없어서, 참조를 유지하는 임시 홀더 위젯에 한 번 옮겼다가
        # editorPage로 다시 옮기는 2단계 홉이 필요하다(홀더가 파이썬 참조 없이 즉시 GC되면
        # 레이아웃까지 같이 삭제되므로 반드시 지역 변수로 참조를 들고 있어야 한다).
        layout_move_holder = QWidget()
        layout_move_holder.setLayout(self.rightPanel.layout())
        self.editorPage = QWidget()
        self.editorPage.setLayout(layout_move_holder.layout())

        # 캘린더(MAIN) 페이지 구성. "새 일기" 버튼은 새로 만들지 않고 .ui의 buttonLayout에 있던
        # newButton을 그대로 옮겨와 재사용한다 — 캘린더 페이지에만 존재해야 하므로(7-10) 편집
        # 페이지의 버튼 줄에서는 제거한다.
        self.buttonLayout.removeWidget(self.newButton)
        self.calendarPage = QWidget()
        calendar_layout = QVBoxLayout(self.calendarPage)
        calendar_layout.setContentsMargins(24, 20, 24, 16)
        calendar_layout.setSpacing(12)

        # QCalendarWidget의 네이티브 요일(월~일) 헤더는 QSS/팔레트로 다크 테마 색을 입힐 수 없는
        # 내부 위젯이라(라이트 모드 배경이 고정으로 남음, 7-9-4), 헤더 자체를 끄고 직접 그린
        # 라벨 줄로 대체한다.
        weekday_row = QHBoxLayout()
        weekday_row.setSpacing(0)
        for name in ["월", "화", "수", "목", "금", "토", "일"]:
            weekday_label = QLabel(name)
            weekday_label.setAlignment(Qt.AlignCenter)
            weekday_label.setStyleSheet(
                "background-color: #313244; color: #cdd6f4; font-weight: bold; padding: 6px 0;"
            )
            weekday_row.addWidget(weekday_label, 1)
        calendar_layout.addLayout(weekday_row)

        self.emotionCalendar = EmotionCalendarWidget()
        calendar_layout.addWidget(self.emotionCalendar)

        calendar_button_row = QHBoxLayout()
        self.newButton.setMinimumHeight(40)
        calendar_button_row.addWidget(self.newButton)
        self.emotionGraphButton = QPushButton("📈 감정 그래프")
        self.emotionGraphButton.setObjectName("emotionGraphButton")
        self.emotionGraphButton.setMinimumHeight(40)
        calendar_button_row.addWidget(self.emotionGraphButton)
        calendar_layout.addLayout(calendar_button_row)

        self.rightStack = QStackedWidget()
        self.rightStack.addWidget(self.calendarPage)  # index 0: 캘린더(MAIN)
        self.rightStack.addWidget(self.editorPage)    # index 1: 일기 편집

        right_panel_layout = QVBoxLayout(self.rightPanel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.addWidget(self.rightStack)

        self.rightStack.setCurrentIndex(0)

    def _init_left_right_splitter(self):
        """좌측 내비게이션 패널의 폭을 사용자가 드래그로 조절할 수 있도록 mainLayout을 QSplitter로 재구성한다.

        .ui에서는 leftPanel/rightPanel이 고정 QHBoxLayout(mainLayout)의 아이템이라 폭 조절이 불가능했다.
        두 패널을 layout에서 떼어내 QSplitter에 다시 얹는 방식으로, leftPanel/rightPanel 자체와 그
        내부 레이아웃(leftLayout 등)은 건드리지 않고 부모만 바꾼다.
        """
        self.mainLayout.removeWidget(self.leftPanel)
        self.mainLayout.removeWidget(self.rightPanel)

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.setChildrenCollapsible(False)
        self.mainSplitter.setHandleWidth(6)
        self.mainSplitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #313244;
            }
            QSplitter::handle:hover {
                background-color: #89b4fa;
            }
        """)
        self.mainSplitter.addWidget(self.leftPanel)
        self.mainSplitter.addWidget(self.rightPanel)
        self.mainSplitter.setStretchFactor(0, 0)
        self.mainSplitter.setStretchFactor(1, 1)
        self.mainSplitter.setSizes([280, 720])

        self.mainLayout.addWidget(self.mainSplitter)

    def _init_ui(self):
        """메인 화면 초기 설정."""
        # 좌측 내비게이션 패널을 드래그로 폭 조절 가능하게 만든다.
        self._init_left_right_splitter()

        # rightPanel 내부를 "캘린더(MAIN)"/"일기 편집" 두 페이지를 오가는 스택으로 재구성한다(7-2/7-3).
        # 기존 rightLayout(및 그 안의 모든 위젯)은 그대로 editorPage로 옮기고, rightPanel 자체는
        # 새 QVBoxLayout 하나로 QStackedWidget만 담도록 바꾼다.
        self._init_right_stack()

        # 오늘 날짜 설정
        self.dateEdit.setDate(QDate.currentDate())

        # 상태바 초기 메시지
        self._set_status_message("환영합니다! 오늘의 일기를 작성해 보세요. 📝")

        # 삭제 버튼 초기 비활성화
        self.deleteButton.setEnabled(False)

        # 필터(카테고리/학점/위치/키워드 3종/기간) — 한 곳에 모아서 접었다 펼 수 있는 영역
        self.filterToggle = QPushButton("🔍 필터 ▾")
        self.filterToggle.setCheckable(True)
        self.leftLayout.insertWidget(1, self.filterToggle)

        self.filterContainer = QWidget()
        filter_layout = QVBoxLayout(self.filterContainer)
        filter_layout.setContentsMargins(0, 4, 0, 4)
        filter_layout.setSpacing(4)

        self._mainFilterWidgets = self._create_filter_widgets()
        self.filterComboBox = self._mainFilterWidgets["category"]
        self.tierFilterComboBox = self._mainFilterWidgets["tier"]
        self.locationFilterComboBox = self._mainFilterWidgets["location"]
        self.titleKeywordEdit = self._mainFilterWidgets["title_keyword"]
        self.contentKeywordEdit = self._mainFilterWidgets["content_keyword"]
        self.summaryKeywordEdit = self._mainFilterWidgets["summary_keyword"]

        filter_layout.addWidget(QLabel("카테고리(날씨/감정)"))
        filter_layout.addWidget(self.filterComboBox)
        filter_layout.addWidget(QLabel("학점"))
        filter_layout.addWidget(self.tierFilterComboBox)
        filter_layout.addWidget(QLabel("위치"))
        filter_layout.addWidget(self.locationFilterComboBox)
        filter_layout.addWidget(self.titleKeywordEdit)
        filter_layout.addWidget(self.contentKeywordEdit)
        filter_layout.addWidget(self.summaryKeywordEdit)

        date_filter_row = QHBoxLayout()
        self.dateFilterCheckBox = QCheckBox("기간")
        self.filterStartDateEdit = QDateEdit()
        self.filterStartDateEdit.setCalendarPopup(True)
        self.filterStartDateEdit.setDisplayFormat("yyyy-MM-dd")
        self.filterStartDateEdit.setDate(QDate.currentDate().addMonths(-1))
        self.filterEndDateEdit = QDateEdit()
        self.filterEndDateEdit.setCalendarPopup(True)
        self.filterEndDateEdit.setDisplayFormat("yyyy-MM-dd")
        self.filterEndDateEdit.setDate(QDate.currentDate())
        date_filter_row.addWidget(self.dateFilterCheckBox)
        date_filter_row.addWidget(self.filterStartDateEdit, 1)
        date_filter_row.addWidget(QLabel("~"))
        date_filter_row.addWidget(self.filterEndDateEdit, 1)
        filter_layout.addLayout(date_filter_row)

        self.filterContainer.setVisible(False)
        self.leftLayout.insertWidget(2, self.filterContainer)

        # 위치 / 현재 날씨 / 오늘 감정 입력
        self.locationLineEdit = QComboBox()
        self.locationLineEdit.setEditable(True)
        self.locationLineEdit.setPlaceholderText("위치를 입력하세요")
        self.locationLineEdit.addItems(self._diary_service.get_location_presets())
        self.locationLineEdit.setCurrentText("")
        # 날씨는 하루에 하나만 고르면 충분해서 콤보박스 하나로 통합했다(7-9-2).
        self.actualWeatherComboBox = QComboBox()
        self.actualWeatherComboBox.addItems(MANUAL_WEATHER_OPTIONS)

        self.emotionComboBox = QComboBox()
        self.emotionComboBox.addItems(MANUAL_EMOTION_OPTIONS)
        self.emotionComboBox2 = QComboBox()
        self.emotionComboBox2.addItems(["선택안함"] + list(MANUAL_EMOTION_OPTIONS))

        context_row = QHBoxLayout()
        context_row.addWidget(QLabel("위치"))
        context_row.addWidget(self.locationLineEdit, 1)
        context_row.addWidget(QLabel("날씨"))
        context_row.addWidget(self.actualWeatherComboBox, 1)
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

        # 목록과 하단 내비게이션 버튼 그룹을 시각적으로 분리하는 얇은 구분선(7-7).
        nav_separator = QFrame()
        nav_separator.setFrameShape(QFrame.HLine)
        nav_separator.setStyleSheet("background-color: #313244; max-height: 1px; border: none;")
        self.leftLayout.addWidget(nav_separator)

        # 편집 페이지에서 캘린더(MAIN)로 돌아가는 버튼 — 좌측 내비게이션은 항상 고정 표시이므로
        # 여기 두면 어느 페이지에 있든 접근 가능하다.
        self.backToCalendarButton = QPushButton("🗓️ 캘린더로")
        self.backToCalendarButton.setObjectName("backToCalendarButton")
        self.leftLayout.addWidget(self.backToCalendarButton)

        # 비밀 일기장 진입/나가기 버튼 — 캘린더/편집 페이지 전환과 무관하게 항상 접근 가능해야 하는
        # 전역 모드 전환이므로, 우측 스택이 아니라 항상 고정 표시되는 좌측 내비게이션에 둔다(7번 확정).
        self.secretDiaryButton = QPushButton("🔒 비밀일기 찾기")
        self.secretDiaryButton.setObjectName("secretDiaryButton")
        self.leftLayout.addWidget(self.secretDiaryButton)

        self.exitSecretModeButton = QPushButton("🚪 나가기")
        self.exitSecretModeButton.setVisible(False)
        self.leftLayout.addWidget(self.exitSecretModeButton)

        # QComboBox 스타일을 다크 모드에 맞게 전역 추가 (QTabWidget 스타일 제거).
        # main.py의 QT_GLOBAL_STYLESHEET(QApplication 레벨)도 같은 규칙을 갖고 있지만, 여기서도
        # 직접 지정해두어야 main.py를 거치지 않고 AppGUI를 생성하는 경우(예: 테스트)에도 메인
        # 창의 드롭다운이 OS 기본값으로 안 보이는 문제 없이 항상 일관되게 보인다.
        extra_style = """
        QComboBox {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 6px 10px;
            color: #f5f5f5;
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
            color: #f5f5f5;
            border: 1px solid #45475a;
            outline: 0;
            selection-background-color: #89b4fa;
            selection-color: #1e1e2e;
        }
        QTextEdit {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 8px;
            padding: 12px;
            color: #f5f5f5;
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
        self.newButton.clicked.connect(self._on_new_diary_requested)
        self.emotionGraphButton.clicked.connect(self.show_emotion_graph_window)
        self.backToCalendarButton.clicked.connect(self._show_calendar_page)
        self.secretDiaryButton.clicked.connect(self._on_open_secret_diary_clicked)
        self.exitSecretModeButton.clicked.connect(self._exit_secret_mode)
        self.emotionCalendar.clicked.connect(self._on_calendar_date_clicked)
        # 편집 폼의 날짜를 바꾸면 그 날짜의 일기로 폼을 전환한다(하루 1개 원칙)
        self.dateEdit.dateChanged.connect(self._on_editor_date_edited)
        self.emotionCalendar.currentPageChanged.connect(self._refresh_calendar_scores)
        self.diaryListWidget.currentItemChanged.connect(self._on_diary_selected)
        self.colorComboBox.currentTextChanged.connect(self.drawingCanvas.set_pen_color)
        self.clearCanvasButton.clicked.connect(self._clear_canvas)

        # 필터 접기/펼치기 및 값 변경 시 목록 재조회
        self.filterToggle.toggled.connect(self._on_filter_toggled)
        self.filterComboBox.currentTextChanged.connect(self._load_diary_list)
        self.tierFilterComboBox.currentTextChanged.connect(self._load_diary_list)
        self.locationFilterComboBox.currentTextChanged.connect(self._load_diary_list)
        self.titleKeywordEdit.textChanged.connect(self._load_diary_list)
        self.contentKeywordEdit.textChanged.connect(self._load_diary_list)
        self.summaryKeywordEdit.textChanged.connect(self._load_diary_list)
        self.dateFilterCheckBox.toggled.connect(self._load_diary_list)
        self.filterStartDateEdit.dateChanged.connect(self._load_diary_list)
        self.filterEndDateEdit.dateChanged.connect(self._load_diary_list)

        # 목록 항목의 요약은 미리보기로 잘라서 표시하고, 전문은 툴팁으로 보여준다(마우스를 올려도
        # 항목 높이가 늘어나지 않으므로 그 때문에 스크롤바가 나타났다 사라졌다 하지 않는다).
        self.diaryListWidget.setWordWrap(True)
        # 세로 스크롤바를 아예 표시하지 않는다 — 스크롤 자체는 마우스 휠로 계속 가능하다.
        self.diaryListWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.diaryListWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # ── 비밀 일기장 모드 ────────────────────────────────────────

    def _on_open_secret_diary_clicked(self):
        """'비밀일기 찾기' 버튼 클릭: 비밀번호 확인 후 비밀 일기장 모드로 전환한다."""
        if not self._diary_service.has_secret_password():
            self.display_alert("아직 설정된 비밀 일기가 없습니다.")
            return

        pwd, ok = QInputDialog.getText(
            self, "🔒 비밀 일기장",
            "비밀번호를 입력해주세요:",
            QLineEdit.Password
        )
        if not ok:
            return
        if not self._diary_service.verify_secret_password(pwd):
            self.display_alert("비밀번호가 올바르지 않습니다.")
            return

        self._enter_secret_mode()

    def _enter_secret_mode(self):
        """비밀 일기장 모드로 전환: 목록을 숨겨진 일기로 바꾸고, 편집을 읽기 전용으로 잠그고, 색상 연출을 시작한다."""
        self._secret_mode = True
        self._clear_editor_form()
        self.secretDiaryButton.setVisible(False)
        self.exitSecretModeButton.setVisible(True)
        self.newButton.setEnabled(False)
        self.saveButton.setEnabled(False)
        self._set_form_read_only(True)
        self._load_diary_list()
        self._start_secret_color_animation()
        self.rightStack.setCurrentIndex(1)

    def _exit_secret_mode(self):
        """'나가기' 버튼 클릭: 일반 목록/테마로 복귀한다."""
        self._secret_mode = False
        self._stop_secret_color_animation()
        self.secretDiaryButton.setVisible(True)
        self.exitSecretModeButton.setVisible(False)
        self.newButton.setEnabled(True)
        self.saveButton.setEnabled(True)
        self._set_form_read_only(False)
        self._clear_editor_form()
        self._load_diary_list()
        self.rightStack.setCurrentIndex(0)

    def _set_form_read_only(self, read_only: bool):
        """비밀 일기장 모드에서는 선택한 일기를 읽기 전용으로만 보여준다 (삭제는 계속 허용)."""
        editable = not read_only
        self.titleEdit.setEnabled(editable)
        self.contentEdit.setEnabled(editable)
        self.locationLineEdit.setEnabled(editable)
        self.actualWeatherComboBox.setEnabled(editable)
        self.emotionComboBox.setEnabled(editable)
        self.emotionComboBox2.setEnabled(editable)
        self.dateEdit.setEnabled(editable)
        self.hideCheckBox.setEnabled(editable)
        self.drawingCanvas.setEnabled(editable)

    def _start_secret_color_animation(self):
        """불안한 느낌을 주기 위해 배경색이 두 색 사이를 천천히 왕복하는 연출을 시작한다."""
        if self._secret_color_anim is not None:
            return
        anim = QVariantAnimation(self)
        anim.setStartValue(QColor("#7a0a26"))
        # 중간에 짙은 보라를 거치게 해서 단순 왕복보다 색 변화가 크고 극적으로 느껴지게 한다.
        anim.setKeyValueAt(0.5, QColor("#3d0a6e"))
        anim.setEndValue(QColor("#0a1e7a"))
        anim.setDuration(2500)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.valueChanged.connect(self._on_secret_color_changed)
        anim.finished.connect(self._flip_secret_color_direction)
        self._secret_color_anim = anim
        anim.start()

    def _on_secret_color_changed(self, color: QColor):
        hex_color = color.name()
        # 셀렉터 없이 "background-color"만 주면 하위 QPushButton들의 고유 배경/글자색 규칙까지
        # 덮어써서 버튼이 배경에 파묻혀 안 보이게 되므로, QFrame/QPushButton을 명시해서 지정한다.
        style = f"""
        QFrame {{ background-color: {hex_color}; }}
        QPushButton {{ color: white; }}
        """
        self.leftPanel.setStyleSheet(style)
        self.rightPanel.setStyleSheet(style)

    def _flip_secret_color_direction(self):
        anim = self._secret_color_anim
        if anim is None:
            return
        anim.setDirection(
            QAbstractAnimation.Backward if anim.direction() == QAbstractAnimation.Forward
            else QAbstractAnimation.Forward
        )
        anim.start()

    def _stop_secret_color_animation(self):
        if self._secret_color_anim is not None:
            self._secret_color_anim.finished.disconnect(self._flip_secret_color_direction)
            self._secret_color_anim.stop()
            self._secret_color_anim = None
        self.leftPanel.setStyleSheet("")
        self.rightPanel.setStyleSheet("")

    def _split_pixmap_zigzag(self, pixmap: QPixmap):
        """스냅샷 이미지를 지그재그 선을 기준으로 위/아래 두 조각으로 나눈다."""
        # DPR을 반영한 논리 좌표 기준으로 경로를 계산해야 고배율 화면에서도 어긋나지 않는다
        dpr = pixmap.devicePixelRatio()
        width = pixmap.width() / dpr
        height = pixmap.height() / dpr
        mid = height / 2
        amplitude = 12
        step = 24

        top_path = QPainterPath()
        top_path.moveTo(0, 0)
        top_path.lineTo(width, 0)
        top_path.lineTo(width, mid)
        x = width
        up = True
        while x > 0:
            next_x = max(x - step, 0)
            y = mid - amplitude if up else mid + amplitude
            top_path.lineTo(next_x, y)
            x = next_x
            up = not up
        top_path.lineTo(0, mid)
        top_path.closeSubpath()

        top_pixmap = QPixmap(pixmap.size())
        top_pixmap.setDevicePixelRatio(pixmap.devicePixelRatio())
        top_pixmap.fill(Qt.transparent)
        painter = QPainter(top_pixmap)
        painter.setClipPath(top_path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        full_path = QPainterPath()
        full_path.addRect(0, 0, width, height)
        bottom_path = full_path.subtracted(top_path)

        bottom_pixmap = QPixmap(pixmap.size())
        bottom_pixmap.setDevicePixelRatio(pixmap.devicePixelRatio())
        bottom_pixmap.fill(Qt.transparent)
        painter = QPainter(bottom_pixmap)
        painter.setClipPath(bottom_path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return top_pixmap, bottom_pixmap

    def _play_tear_animation(self, on_finished=None):
        """편집 폼을 지그재그로 찢어 반대 방향으로 날아가며 사라지는 연출을 재생한다."""
        widget = self.rightPanel
        # 부모가 QSplitter라 QLabel을 그 자식으로 만들면 새 구획으로 편입되어 레이아웃이 깨진다.
        # 레이아웃 관리를 받지 않는 centralWidget을 오버레이 부모로 쓰고 좌표를 변환한다.
        parent = self.centralWidget()
        pixmap = widget.grab()
        top_pixmap, bottom_pixmap = self._split_pixmap_zigzag(pixmap)
        geom = QRect(widget.mapTo(parent, QPoint(0, 0)), widget.size())
        duration = 650

        top_label = QLabel(parent)
        top_label.setPixmap(top_pixmap)
        top_label.setGeometry(geom)
        top_label.show()
        top_label.raise_()

        bottom_label = QLabel(parent)
        bottom_label.setPixmap(bottom_pixmap)
        bottom_label.setGeometry(geom)
        bottom_label.show()
        bottom_label.raise_()

        top_opacity = QGraphicsOpacityEffect(top_label)
        top_label.setGraphicsEffect(top_opacity)
        bottom_opacity = QGraphicsOpacityEffect(bottom_label)
        bottom_label.setGraphicsEffect(bottom_opacity)

        top_move = QPropertyAnimation(top_label, b"geometry", self)
        top_move.setDuration(duration)
        top_move.setStartValue(geom)
        top_move.setEndValue(QRect(geom.x() - 50, geom.y() - 90, geom.width(), geom.height()))
        top_move.setEasingCurve(QEasingCurve.InQuad)

        top_fade = QPropertyAnimation(top_opacity, b"opacity", self)
        top_fade.setDuration(duration)
        top_fade.setStartValue(1.0)
        top_fade.setEndValue(0.0)

        bottom_move = QPropertyAnimation(bottom_label, b"geometry", self)
        bottom_move.setDuration(duration)
        bottom_move.setStartValue(geom)
        bottom_move.setEndValue(QRect(geom.x() + 50, geom.y() + 90, geom.width(), geom.height()))
        bottom_move.setEasingCurve(QEasingCurve.InQuad)

        bottom_fade = QPropertyAnimation(bottom_opacity, b"opacity", self)
        bottom_fade.setDuration(duration)
        bottom_fade.setStartValue(1.0)
        bottom_fade.setEndValue(0.0)

        group = QParallelAnimationGroup(self)
        group.addAnimation(top_move)
        group.addAnimation(top_fade)
        group.addAnimation(bottom_move)
        group.addAnimation(bottom_fade)

        def _cleanup():
            top_label.deleteLater()
            bottom_label.deleteLater()
            self._tear_animation_group = None
            if on_finished:
                on_finished()

        group.finished.connect(_cleanup)
        self._tear_animation_group = group
        group.start()

    # ── 이벤트 핸들러 ────────────────────────────────────────────

    def on_save_clicked(self):
        """'저장' 버튼 클릭: 일기를 저장하고 이어서 AI 한 줄 요약/공감/그림분석을 진행한다."""
        if self._secret_mode:
            return
        date_str = self.dateEdit.date().toString("yyyy-MM-dd")
        title = self.titleEdit.text().strip()
        content = self.contentEdit.toPlainText().strip()
        location_name = self.locationLineEdit.currentText().strip()

        # 날씨 처리 (하루 하나만 선택, 7-9-2)
        w_val = self.actualWeatherComboBox.currentText().strip()

        # 감정 1, 2 처리
        e_label1 = self.emotionComboBox.currentText().strip()
        e_label2 = self.emotionComboBox2.currentText().strip()

        # 입력 검증
        if not content and not self._has_drawn_content():
            self.display_alert("일기 내용이나 그림을 입력해 주세요.")
            return
        if not title:
            title = f"{date_str} 일기"

        # 하루 1개 원칙: 그 날짜에 비밀 일기가 있으면 일반 저장으로 덮어쓰지 않는다
        existing_same_date = self._diary_service.find_diary_for_date(date_str)
        if (
            existing_same_date is not None
            and existing_same_date.is_hidden
            and existing_same_date.id != self._current_diary_id
        ):
            self.display_alert("그 날짜에는 이미 비밀 일기가 있어 저장할 수 없습니다.")
            return

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
            actual_weather=w_val,
            emotion1=e_label1,
            emotion2=e_label2,
            is_hidden=is_hidden_val,
            image_data=image_data,
            remove_image=remove_existing_image,
        )

        if is_hidden_val:
            # 비밀 일기는 저장/AI 처리를 시작하기 전에 먼저 찢는 연출을 보여준다
            def _after_tear():
                self._clear_editor_form()
                self._run_save_and_analyze(save_kwargs, image_base64, w_val)

            self._play_tear_animation(on_finished=_after_tear)
        else:
            self._run_save_and_analyze(save_kwargs, image_base64, w_val)

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
                self._clear_editor_form()
                self._load_diary_list()
                self._set_status_message("🗑️ 일기가 삭제되었습니다.")
                self.rightStack.setCurrentIndex(0)
            else:
                self.display_alert("삭제에 실패했습니다.")

    def _on_new_clicked(self):
        """'새 일기' 버튼 클릭: 입력 필드를 초기화한다.

        하루 1개 원칙이라 오늘 일기가 이미 있으면 그 일기를 이어서 편집하도록 불러온다.
        """
        self._clear_editor_form()
        self._sync_form_to_date(QDate.currentDate())

    def _clear_editor_form(self):
        """편집 폼을 오늘 날짜의 빈 새 일기 상태로 비운다(일기 자동 로드 없음)."""
        self._reset_form_fields()
        self._set_editor_date(QDate.currentDate())
        self._set_status_message("새 일기를 작성해 보세요. ✍️")

    def _reset_form_fields(self):
        """날짜를 제외한 편집 폼 입력값을 새 일기 상태로 초기화한다."""
        self._current_diary_id = None
        self.titleEdit.clear()
        self.locationLineEdit.setCurrentText("")
        self.actualWeatherComboBox.setCurrentText(MANUAL_WEATHER_OPTIONS[0])
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

    def _set_editor_date(self, date: QDate):
        """날짜 변경 내비게이션을 발동시키지 않고 dateEdit 값을 바꾼다."""
        self._date_nav_timer.stop()
        self._syncing_editor_date = True
        try:
            self.dateEdit.setDate(date)
        finally:
            self._syncing_editor_date = False
        self._last_editor_date = date

    def _sync_form_to_date(self, date: QDate) -> bool:
        """편집 폼이 해당 날짜의 일기를 보여주도록 맞춘다(하루 1개 원칙).

        일기가 있으면 불러오고, 없으면 작성 중이던 입력은 유지한 채 새 일기 모드가 된다.
        비밀 일기가 있는 날짜면 폼을 건드리지 않고 False를 반환한다(알림/되돌리기는 호출자 몫).
        """
        diary = self._diary_service.find_diary_for_date(date.toString("yyyy-MM-dd"))
        if diary is None:
            if self._current_diary_id is not None:
                self._reset_form_fields()
                self._set_status_message("새 일기를 작성해 보세요. ✍️")
            return True
        if diary.is_hidden:
            return False
        if diary.id != self._current_diary_id:
            self._load_diary_into_form(diary)
        return True

    def _on_editor_date_edited(self, _date: QDate):
        """dateEdit의 dateChanged: 키 입력 도중의 중간 값을 걸러내기 위해 잠시 모았다가 내비게이션한다."""
        if self._syncing_editor_date or self._secret_mode:
            return
        self._date_nav_timer.start()

    def _on_editor_date_changed(self, date: QDate):
        """편집 폼의 날짜가 확정되면 그 날짜의 일기로 폼을 전환한다."""
        if self._secret_mode:
            return
        if self._sync_form_to_date(date):
            self._last_editor_date = date
        else:
            self.display_alert("그 날짜에는 비밀 일기가 있어요. 비밀 일기장에서 확인해 주세요.")
            self._set_editor_date(self._last_editor_date)

    def _on_diary_selected(self, current: QListWidgetItem, previous):
        """일기 목록에서 항목 선택 시 내용을 표시한다."""
        if self._suppress_next_diary_selection:
            self._suppress_next_diary_selection = False
            # QListWidget이 자동으로 잡아버린 "현재 항목"(row 0)을 시각적으로도 완전히 지운다.
            # 그냥 return만 하면 폼 로딩/페이지 전환은 막히지만, 목록에는 여전히 맨 위 항목이
            # 포커스/선택된 것처럼 보여서 "자동으로 펼쳐진 것 같다"는 착시가 남는다.
            self.diaryListWidget.clearSelection()
            self.diaryListWidget.setCurrentRow(-1)
            return
        if current is None:
            return

        diary_id = current.data(Qt.UserRole)
        if diary_id is None:
            return

        # 서비스에서 해당 일기 조회
        diary = self._diary_service.get_diary_by_id(diary_id)
        if diary:
            self._load_diary_into_form(diary)

    def _load_diary_into_form(self, diary):
        """일기 엔티티를 편집 폼에 채우고 편집 페이지로 전환한다 (목록 선택/캘린더 날짜 클릭이 공유, 7-8)."""
        self._current_diary_id = diary.id
        self._set_editor_date(QDate.fromString(diary.date, "yyyy-MM-dd"))
        self.titleEdit.setText(diary.title)
        self.locationLineEdit.setCurrentText(diary.weather.location)
        # 날씨 로드 (하루 하나만 저장, 7-9-2)
        weather_label = f"{diary.weather.actual_weather} {diary.weather.actual_weather_text}".strip()
        matched = next(
            (opt for opt in MANUAL_WEATHER_OPTIONS if opt.strip() == weather_label), None
        )
        self.actualWeatherComboBox.setCurrentText(matched or MANUAL_WEATHER_OPTIONS[0])

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
        self.rightStack.setCurrentIndex(1)

    # ── 캘린더(MAIN) 페이지 ────────────────────────────────────

    def _show_calendar_page(self):
        """좌측 '캘린더로' 버튼: 편집 페이지에서 캘린더(MAIN) 페이지로 돌아간다."""
        self.rightStack.setCurrentIndex(0)

    def _on_new_diary_requested(self):
        """캘린더 페이지의 '새 일기' 버튼: 폼을 초기화하고 편집 페이지로 전환한다."""
        self._on_new_clicked()
        self.rightStack.setCurrentIndex(1)

    def _refresh_calendar_scores(self):
        """감정 점수 히트맵 데이터와 비밀 일기 날짜를 다시 조회해 캘린더에 반영한다."""
        self.emotionCalendar.set_emotion_scores(
            self._diary_service.get_emotion_scores_by_date(),
            self._diary_service.get_secret_diary_dates(),
        )

    def _on_calendar_date_clicked(self, date: QDate):
        """캘린더에서 날짜를 클릭했을 때의 진입 동선을 처리한다(7-8).

        빈 날짜 → 그 날짜로 새 일기 작성. 일기가 있는 날짜 → 목록에서 선택한 것과 동일하게 편집
        페이지로 로드. 비밀 일기는 비밀 일기장 모드에서만 열 수 있고(읽기 전용), 평소에는
        선택 자체를 막고 안내만 띄운다.
        """
        date_str = date.toString("yyyy-MM-dd")
        diary = self._diary_service.find_diary_for_date(date_str)
        if self._secret_mode:
            # 비밀 일기장 모드: 캘린더에서도 비밀 일기를 열람할 수 있다. 새 일기 작성과
            # 일반 일기 열람은 이 모드의 목적이 아니므로 막는다.
            if diary is not None and diary.is_hidden:
                self._load_diary_into_form(diary)
                self._set_status_message("🔒 비밀 일기장 — 읽기 전용입니다. 나가려면 '나가기'를 눌러주세요.")
            else:
                self.display_alert("비밀 일기장 모드에서는 비밀 일기만 열 수 있습니다.")
            return
        if diary is None:
            # _on_new_clicked는 오늘 일기가 있으면 그걸 로드해버리므로, 클릭한 날짜의
            # 빈 폼이 필요할 때는 필드 초기화 + 날짜 지정만 직접 한다.
            self._reset_form_fields()
            self._set_editor_date(date)
            self._set_status_message("새 일기를 작성해 보세요. ✍️")
            self.rightStack.setCurrentIndex(1)
            return
        if diary.is_hidden:
            self.display_alert("비밀 일기는 캘린더에서 선택할 수 없습니다.")
            return
        self._load_diary_into_form(diary)

    # ── UI 업데이트 ────────────────────────────────────────────

    def update_weather_icon(self, result: dict):
        """사용자 선택 감정 상태에 따라 아이콘과 요약을 갱신한다."""
        self.weatherLabel.setText(result["weather_emoji"])
        self.scoreLabel.setText(f"감정 상태: {result['emotion_label']} ({result['score']}점)")

    def _on_filter_toggled(self, checked: bool):
        """'필터' 버튼을 눌러 카테고리/학점/위치/키워드/기간 필터 영역을 접거나 편다."""
        self.filterContainer.setVisible(checked)
        self.filterToggle.setText("🔍 필터 ▴" if checked else "🔍 필터 ▾")

    def _create_filter_widgets(self) -> dict:
        """카테고리/학점/위치/제목·본문·요약 키워드 필터 위젯을 새로 만들어 딕셔너리로 반환한다.

        메인 목록의 필터 영역과 키워드 분석 다이얼로그가 이 메서드를 공유해서 쓴다.
        """
        widgets = {}

        widgets["category"] = QComboBox()
        widgets["category"].addItems(ALL_FILTER_OPTIONS)

        widgets["tier"] = QComboBox()
        widgets["tier"].addItems(EMOTION_TIER_OPTIONS)

        widgets["location"] = QComboBox()
        widgets["location"].setEditable(True)
        widgets["location"].addItem("")
        widgets["location"].addItems(self._diary_service.get_location_presets())
        widgets["location"].setCurrentText("")

        widgets["title_keyword"] = QLineEdit()
        widgets["title_keyword"].setPlaceholderText("제목 키워드")

        widgets["content_keyword"] = QLineEdit()
        widgets["content_keyword"].setPlaceholderText("본문 키워드")

        widgets["summary_keyword"] = QLineEdit()
        widgets["summary_keyword"].setPlaceholderText("요약 키워드")

        return widgets

    def _diary_filter_from_widgets(self, widgets: dict) -> DiaryFilter:
        """_create_filter_widgets()가 만든 위젯들의 현재 값으로 DiaryFilter를 구성한다."""
        return DiaryFilter(
            category=widgets["category"].currentText(),
            tier=widgets["tier"].currentText(),
            location=widgets["location"].currentText(),
            title_keyword=widgets["title_keyword"].text(),
            content_keyword=widgets["content_keyword"].text(),
            summary_keyword=widgets["summary_keyword"].text(),
        )

    def _refresh_location_presets(self):
        """새로 추가된 위치 프리셋을 위치 입력/필터 콤보박스에 반영한다."""
        presets = self._diary_service.get_location_presets()
        for combo in (self.locationLineEdit, self.locationFilterComboBox):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            if combo is self.locationFilterComboBox:
                combo.addItem("")
            combo.addItems(presets)
            combo.setCurrentText(current)
            combo.blockSignals(False)

    def _build_diary_filter(self) -> DiaryFilter:
        """메인 목록 필터 위젯의 현재 값으로 DiaryFilter를 구성한다."""
        return self._diary_filter_from_widgets(self._mainFilterWidgets)

    def _load_diary_list(self):
        """CSV에서 일기 목록을 읽어 왼쪽 리스트에 표시한다.

        평소에는 비밀 일기를 제외한 목록을, 비밀 일기장 모드에서는 반대로 숨겨진 일기만 보여준다.
        """
        self.diaryListWidget.clear()
        self._refresh_calendar_scores()

        diary_filter = self._build_diary_filter()
        date_from = ""
        date_to = ""
        if self.dateFilterCheckBox.isChecked():
            date_from = self.filterStartDateEdit.date().toString("yyyy-MM-dd")
            date_to = self.filterEndDateEdit.date().toString("yyyy-MM-dd")

        if self._secret_mode:
            diaries = self._diary_service.get_hidden_diaries(diary_filter, date_from, date_to)
        else:
            diaries = self._diary_service.get_all_diaries(diary_filter, date_from, date_to)
        # 최신순 정렬
        diaries.sort(key=lambda x: x.date, reverse=True)

        for diary in diaries:
            date_str = diary.date
            title = diary.title or "제목 없음"
            weather = diary.weather.actual_weather or diary.weather.emoji
            tier = diary.emotion_score.tier
            diary_id = diary.id

            base_text = f"{weather} {date_str} [{tier}]\n     {title}"
            preview_text = base_text
            full_text = base_text
            if diary.summary:
                preview_text += f"\n     📝 {truncate_summary(diary.summary)}"
                full_text += f"\n     📝 {diary.summary}"

            item = QListWidgetItem(preview_text)
            item.setData(Qt.UserRole, diary_id)
            # 전문을 항상 툴팁으로 보여준다(요약이 안 잘렸거나 아예 없는 항목도 마우스를 올리면
            # 반응이 있어야 함). 항목 높이 자체는 그대로 유지되어 스크롤바가 마우스오버 때문에
            # 나타났다 사라졌다 하지 않는다.
            item.setToolTip(full_text)
            self.diaryListWidget.addItem(item)

        has_active_filter = bool(
            (diary_filter.category and diary_filter.category != "전체보기")
            or diary_filter.tier
            or diary_filter.location
            or diary_filter.title_keyword
            or diary_filter.content_keyword
            or diary_filter.summary_keyword
            or date_from or date_to
        )
        if self.diaryListWidget.count() == 0 and has_active_filter:
            self._set_status_message("선택한 필터 조건에 해당하는 일기가 없습니다.")
        elif not has_active_filter:
            if self._secret_mode:
                self._set_status_message("🔒 비밀 일기장 — 읽기 전용입니다. 나가려면 '나가기'를 눌러주세요.")
            else:
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

    def _run_save_and_analyze(self, save_kwargs: dict, image_base64: str, w_val: str):
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
                color: #f5f5f5;
                font-family: "Pretendard", "Noto Sans KR", "Malgun Gothic", sans-serif;
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
                color: #f5f5f5;
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
                self._refresh_location_presets()
                if diary.is_hidden:
                    # 찢기 연출과 함께 편집 폼이 이미 초기화됐으므로, 메인 화면에 내용을 다시 반영하지 않는다
                    self._load_diary_list()
                    self._set_status_message("✅ 비밀 일기가 저장되었습니다.")
                else:
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
                    self._set_status_message(
                        f"✅ 일기가 {action}되었습니다! 감정: {diary.emotion_label} | 현재 날씨: {w_val}"
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
            dialog.accept()

        ok_button.clicked.connect(_on_confirm_clicked)

        self._save_worker = SaveWorker(self._diary_service, save_kwargs, image_base64)
        self._save_worker.save_finished.connect(_on_save_finished)
        self._save_worker.status_changed.connect(_on_status_changed)
        self._save_worker.empathy_finished.connect(_on_empathy_finished)
        self._save_worker.error.connect(_on_error)
        self._save_worker.start()

        dialog.exec_()

    def show_emotion_graph_window(self):
        """캘린더 페이지의 '감정 그래프' 버튼: 기간을 선택해 감정 점수 추이 매크로 뷰를 보여준다(8-5)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📈 감정 그래프")
        dialog.resize(760, 480)

        layout = QVBoxLayout(dialog)

        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("시작 날짜"))
        start_edit = QDateEdit()
        start_edit.setCalendarPopup(True)
        start_edit.setDisplayFormat("yyyy-MM-dd")
        start_edit.setDate(QDate.currentDate().addMonths(-1))
        period_row.addWidget(start_edit)
        period_row.addWidget(QLabel("종료 날짜"))
        end_edit = QDateEdit()
        end_edit.setCalendarPopup(True)
        end_edit.setDisplayFormat("yyyy-MM-dd")
        end_edit.setDate(QDate.currentDate())
        period_row.addWidget(end_edit)
        draw_button = QPushButton("그래프 그리기")
        period_row.addWidget(draw_button)
        layout.addLayout(period_row)

        image_label = QLabel("기간을 선택하고 '그래프 그리기'를 눌러주세요.")
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label, 1)

        def _draw():
            start = start_edit.date().toString("yyyy-MM-dd")
            end = end_edit.date().toString("yyyy-MM-dd")
            png_bytes = self._diary_service.generate_trend_chart(start, end, dark_theme=True)
            if not png_bytes:
                image_label.setText("해당 기간에 표시할 데이터가 없습니다.")
                image_label.setPixmap(QPixmap())
                return
            pixmap = QPixmap()
            pixmap.loadFromData(png_bytes)
            image_label.setText("")
            image_label.setPixmap(pixmap)

        draw_button.clicked.connect(_draw)
        _draw()
        dialog.exec_()

    def show_mindmap_window(self):
        """키워드 분석(마인드맵) 팝업 창을 띄운다."""
        dialog = QDialog(self)
        uic.loadUi(KEYWORD_UI, dialog)

        # 기본 기간: 최근 7일
        today = QDate.currentDate()
        dialog.startDateEdit.setDate(today.addDays(-7))
        dialog.endDateEdit.setDate(today)

        # 카테고리/학점/위치/제목·본문·요약 키워드 필터 — 메인 목록과 동일한 위젯 생성 함수를 재사용
        dialog.filterWidgets = self._create_filter_widgets()
        filter_layout = QVBoxLayout()

        category_row = QHBoxLayout()
        category_row.addWidget(QLabel("카테고리"))
        category_row.addWidget(dialog.filterWidgets["category"], 1)
        category_row.addWidget(QLabel("학점"))
        category_row.addWidget(dialog.filterWidgets["tier"], 1)
        category_row.addWidget(QLabel("위치"))
        category_row.addWidget(dialog.filterWidgets["location"], 1)
        filter_layout.addLayout(category_row)

        keyword_row = QHBoxLayout()
        keyword_row.addWidget(dialog.filterWidgets["title_keyword"])
        keyword_row.addWidget(dialog.filterWidgets["content_keyword"])
        keyword_row.addWidget(dialog.filterWidgets["summary_keyword"])
        filter_layout.addLayout(keyword_row)

        dialog.mainLayout.insertLayout(2, filter_layout)

        # 분석 버튼 이벤트
        dialog.analyzeButton.clicked.connect(
            lambda: self._run_keyword_analysis(dialog)
        )

        dialog.exec_()

    def _run_keyword_analysis(self, dialog: QDialog):
        """키워드 분석을 실행하고 결과를 다이얼로그에 표시한다."""
        start = dialog.startDateEdit.date().toString("yyyy-MM-dd")
        end = dialog.endDateEdit.date().toString("yyyy-MM-dd")
        diary_filter = self._diary_filter_from_widgets(dialog.filterWidgets)

        # 기간/필터 조건에 맞는 일기 데이터 읽기
        entries = self._diary_service.get_all_diaries(diary_filter, start, end)

        if not entries:
            dialog.wordcloudLabel.setText("해당 기간(및 필터 조건)에 작성된 일기가 없습니다.")
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
