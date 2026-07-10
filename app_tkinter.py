"""
AppGUI — Tkinter 기반 메인 GUI 클래스
현대적인 플랫 디자인을 적용하여 감정 일기장 화면을 구성한다.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from io import BytesIO

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from runtime_env import configure_runtime

configure_runtime(PROJECT_ROOT)

# Pillow 라이브러리 사용 (WordCloud 이미지 변환 및 GUI 로드용)
from PIL import Image, ImageTk, ImageDraw

# matplotlib 임포트 (통계 그래프 그리기용)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import collections

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


# 색상 정의 (모던 플랫 테마)
COLOR_BG = "#F8F9FA"          # 기본 배경 (Soft Warm Gray)
COLOR_CARD = "#FFFFFF"        # 일기장 및 리스트 카드 배경 (Pure White)
COLOR_BORDER = "#E9ECEF"      # 테두리 및 구분선
COLOR_TEXT_MAIN = "#212529"   # 주 텍스트 (Charcoal)
COLOR_TEXT_SUB = "#6C757D"    # 보조 텍스트 (Muted Gray)

COLOR_PRIMARY = "#4D96FF"     # 블루 (저장 / 분석)
COLOR_SECONDARY = "#6C757D"   # 그레이 (새 일기)
COLOR_DANGER = "#FF6B6B"      # 레드 (삭제)
COLOR_SUCCESS = "#6BCB77"     # 그린 (성공 메시지 등)
COLOR_AI = "#9B5DE5"          # 퍼플 (AI 기능)


def adjust_color_brightness(hex_color, factor=0.9):
    """색상 코드의 밝기를 조절하여 호버 효과 구현."""
    hex_color = hex_color.lstrip('#')
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    new_rgb = [min(255, max(0, int(c * factor))) for c in rgb]
    return '#{:02x}{:02x}{:02x}'.format(*new_rgb)


def style_flat_button(btn, bg, fg="white", font_size=10):
    """Tkinter 버튼을 현대적인 플랫 스타일로 리디자인."""
    btn.configure(
        bg=bg,
        fg=fg,
        activebackground=adjust_color_brightness(bg, 0.85),
        activeforeground=fg,
        relief="flat",
        bd=0,
        font=("Malgun Gothic", font_size, "bold"),
        cursor="hand2",
        padx=12,
        pady=6
    )
    
    # 호버 애니메이션 추가
    hover_bg = adjust_color_brightness(bg, 0.9)
    btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
    btn.bind("<Leave>", lambda e: btn.configure(bg=bg))


class EmotionCalendarFrame(ttk.Frame):
    """날짜별 평균 감정 점수를 배경색 히트맵 + 주간 미니 선그래프로 보여주는 캘린더.

    7-11: tkcalendar 없이 직접 그리드로 구현. 8-4: 셀마다 별도 위젯을 grid()로 배치하지 않고
    단일 tk.Canvas 안에 격자 전체를 렌더링(grid/pack 혼용 TclError 이력 회피). 8-2: 같은 Canvas
    위에 한 주(행) 단위로 감정 점수를 잇는 미니 선을 함께 그린다.
    """

    CELL_PADDING = 3

    # 라이트 테마용 히트맵 색상(Qt의 8-3 다크 팔레트와 같은 4단계 구조를 라이트 테마에 맞게 적용)
    _COLOR_NO_DATA = COLOR_CARD
    _COLOR_NEUTRAL = COLOR_BORDER
    _COLOR_POSITIVE_MILD = (255, 224, 178)
    _COLOR_POSITIVE_EXTREME = (255, 159, 67)
    _COLOR_NEGATIVE_MILD = (214, 222, 235)
    _COLOR_NEGATIVE_EXTREME = (173, 189, 216)

    def __init__(self, parent, on_date_click=None, **kwargs):
        super().__init__(parent, style="TFrame", **kwargs)
        self._on_date_click = on_date_click
        self._scores_by_date = {}
        today = datetime.now()
        self._current_year = today.year
        self._current_month = today.month
        self._cell_bounds = []  # [(x0, y0, x1, y1, date_str), ...] 클릭 히트테스트용

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", pady=(0, 8))

        self._prev_btn = tk.Button(header, text="◀", command=self._go_prev_month)
        self._prev_btn.pack(side="left")
        style_flat_button(self._prev_btn, COLOR_SECONDARY, font_size=9)

        self._month_label = ttk.Label(header, text="", style="Header.TLabel", anchor="center")
        self._month_label.pack(side="left", expand=True, fill="x")

        self._next_btn = tk.Button(header, text="▶", command=self._go_next_month)
        self._next_btn.pack(side="right")
        style_flat_button(self._next_btn, COLOR_SECONDARY, font_size=9)

        weekday_row = ttk.Frame(self, style="TFrame")
        weekday_row.pack(fill="x")
        for i, name in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            ttk.Label(weekday_row, text=name, style="TLabel", anchor="center").grid(row=0, column=i, sticky="nsew")
            weekday_row.columnconfigure(i, weight=1)

        self._canvas = tk.Canvas(self, bg=COLOR_CARD, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda e: self._render_calendar())
        self._canvas.bind("<Button-1>", self._on_canvas_click)

    def set_emotion_scores(self, scores_by_date: dict):
        """{"yyyy-MM-dd": 평균 점수} 형태의 딕셔너리로 히트맵/미니 선그래프 데이터를 갱신한다."""
        self._scores_by_date = scores_by_date
        self._render_calendar()

    def _go_prev_month(self):
        self._current_month -= 1
        if self._current_month < 1:
            self._current_month = 12
            self._current_year -= 1
        self._render_calendar()

    def _go_next_month(self):
        self._current_month += 1
        if self._current_month > 12:
            self._current_month = 1
            self._current_year += 1
        self._render_calendar()

    def _render_calendar(self):
        self._canvas.delete("all")
        self._cell_bounds = []
        self._month_label.config(text=f"{self._current_year}년 {self._current_month}월")

        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()
        if width <= 1 or height <= 1:
            # 최초 pack() 직후에는 아직 실제 크기가 배정되지 않음 — 다음 <Configure>에서 다시 그림
            return

        import calendar as calendar_module
        cal = calendar_module.Calendar(firstweekday=0)  # 월요일 시작
        weeks = cal.monthdayscalendar(self._current_year, self._current_month)

        rows = len(weeks)
        cols = 7
        cell_w = width / cols
        cell_h = height / rows
        pad = self.CELL_PADDING

        for row_idx, week in enumerate(weeks):
            y0 = row_idx * cell_h
            y1 = y0 + cell_h
            week_points = []  # (x, score) — 8-2 미니 선그래프용

            for col_idx, day in enumerate(week):
                x0 = col_idx * cell_w
                x1 = x0 + cell_w

                if day == 0:
                    week_points.append(None)
                    continue

                date_str = f"{self._current_year:04d}-{self._current_month:02d}-{day:02d}"
                score = self._scores_by_date.get(date_str)
                fill = self._color_for_score(score)

                self._canvas.create_rectangle(
                    x0 + pad, y0 + pad, x1 - pad, y1 - pad,
                    fill=fill, outline=COLOR_BORDER, width=1,
                )
                self._canvas.create_text(
                    x0 + pad + 6, y0 + pad + 4, anchor="nw",
                    text=str(day), fill=self._text_color_for(fill),
                    font=("Malgun Gothic", 10),
                )
                self._cell_bounds.append((x0, y0, x1, y1, date_str))
                week_points.append((x0 + cell_w / 2, score))

            self._draw_week_trend_line(week_points, y0, y1)

    def _draw_week_trend_line(self, week_points, y0: float, y1: float):
        """한 주(행) 안에서만 이어지는 미니 선을 그린다 — 축 고정(-5~5), 데이터 공백은 끊는다(8-2)."""
        segment = []
        for entry in week_points:
            if entry is None or entry[1] is None:
                if len(segment) >= 2:
                    self._canvas.create_line(*[c for p in segment for c in p], fill="#495057", width=2)
                segment = []
                continue
            x, score = entry
            ratio = (max(-5.0, min(5.0, score)) + 5.0) / 10.0
            y = y1 - ratio * (y1 - y0)
            segment.append((x, y))
        if len(segment) >= 2:
            self._canvas.create_line(*[c for p in segment for c in p], fill="#495057", width=2)

    def _on_canvas_click(self, event):
        for (x0, y0, x1, y1, date_str) in self._cell_bounds:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                if self._on_date_click:
                    self._on_date_click(date_str)
                return

    @classmethod
    def _color_for_score(cls, score) -> str:
        """점수(-5~5)를 라이트 테마 히트맵 팔레트로 매핑한다(무데이터/중립/긍정/부정 4단계, 8-3 구조 준용)."""
        if score is None:
            return cls._COLOR_NO_DATA
        score = max(-5.0, min(5.0, score))
        if score == 0:
            return cls._COLOR_NEUTRAL
        if score > 0:
            return cls._blend(cls._COLOR_POSITIVE_MILD, cls._COLOR_POSITIVE_EXTREME, score / 5.0)
        return cls._blend(cls._COLOR_NEGATIVE_MILD, cls._COLOR_NEGATIVE_EXTREME, (-score) / 5.0)

    @staticmethod
    def _blend(c1, c2, t: float) -> str:
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _text_color_for(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return COLOR_TEXT_MAIN if luminance > 150 else "#FFFFFF"


class AppGUI(tk.Tk):
    """Tkinter 기반의 감정 일기장 메인 윈도우."""

    def __init__(self):
        super().__init__()

        self.title("내 감정은 오늘도 F등급 ☀️⛅🌧️")
        self.geometry("960x650")
        self.configure(bg=COLOR_BG)

        # 백엔드 서비스 초기화
        self._diary_service = DiaryService()

        # 현재 선택된 일기 ID (수정 모드 식별용)
        self._current_diary_id = None
        self._list_diary_ids = []  # 리스트박스 항목 매핑용 ID 리스트
        
        # 그림판 상태 관리용
        self._last_x = None
        self._last_y = None
        self._draw_image = None
        self._draw_tool = None
        self.canvas_image_ref = None # GC 방지
        self._canvas_dirty = False
        self._existing_image_path = ""
        self._remove_existing_image = False
        self._secret_mode = False
        self._secret_color_job = None
        self._secret_color_state = {}
        # UI 위젯 초기화 및 배치
        self._init_ui()
        self._connect_events()
        self._load_diary_list()
        self._on_new_clicked()
        self._show_calendar_page()  # 앱은 항상 캘린더(MAIN) 페이지로 시작한다(7-2)

    def _init_ui(self):
        """메인 화면 레이아웃 구성."""
        # 1. ttk 스타일 정의 (일부 테마 및 폰트 설정)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Card.TFrame", background=COLOR_CARD, relief="flat", borderwidth=1)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT_MAIN, font=("Malgun Gothic", 10))
        style.configure("Card.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT_MAIN)
        style.configure("Header.TLabel", font=("Malgun Gothic", 12, "bold"))

        # ttk.Combobox는 지금까지 별도 스타일이 없어 OS/Tcl-Tk 기본값을 그대로 썼다. 특히 드롭다운
        # 목록(팝다운)은 ttk 테마가 아니라 순수 Tk Listbox라서 시스템이 다크 모드일 때 배경색이
        # 앱의 밝은 테마와 어긋나 글자가 잘 안 보일 수 있다 — 필드/팝다운 색을 명시적으로 지정한다.
        style.configure(
            "TCombobox",
            fieldbackground=COLOR_CARD,
            background=COLOR_CARD,
            foreground=COLOR_TEXT_MAIN,
            arrowcolor=COLOR_TEXT_MAIN,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLOR_CARD), ("disabled", COLOR_BORDER)],
            foreground=[("disabled", COLOR_TEXT_SUB)],
        )
        self.option_add("*TCombobox*Listbox.background", COLOR_CARD)
        self.option_add("*TCombobox*Listbox.foreground", COLOR_TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.selectBackground", COLOR_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.font", ("Malgun Gothic", 10))

        # 2. 메인 화면 좌우 분할 — PanedWindow로 구성해 좌측 패널 폭을 드래그로 조절할 수 있게 함
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.mainPaned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief="flat",
            bg=COLOR_BORDER, bd=0, opaqueresize=True,
        )
        self.mainPaned.grid(row=0, column=0, sticky="nsew")

        # ────────────────────────────────────────────────────────
        # LEFT PANEL: 일기 목록
        # ────────────────────────────────────────────────────────
        left_panel = ttk.Frame(self.mainPaned, style="TFrame", padding=15)
        self.mainPaned.add(left_panel, minsize=260, width=300)

        lbl_list = ttk.Label(left_panel, text="일기 히스토리", style="Header.TLabel")
        lbl_list.pack(anchor="w", pady=(0, 5))
        
        # 필터(카테고리/학점/위치/키워드 3종/기간) — 한 곳에 모아서 접었다 펼 수 있는 영역
        self._location_filter_combos = []
        self._advanced_filter_shown = False
        self.advanced_filter_toggle = tk.Button(left_panel, text="🔍 필터 ▾")
        self.advanced_filter_toggle.pack(fill="x", pady=(0, 6))
        style_flat_button(self.advanced_filter_toggle, COLOR_SECONDARY, font_size=9)

        self.advanced_filter_frame = ttk.Frame(left_panel, style="TFrame")
        # 처음엔 숨겨둠 — 토글 버튼을 눌러야 pack()으로 표시됨

        self._main_filter_vars = self._create_filter_vars()
        self.filter_var = self._main_filter_vars["category"]
        self.tier_filter_var = self._main_filter_vars["tier"]
        self.location_filter_var = self._main_filter_vars["location"]
        self.title_keyword_var = self._main_filter_vars["title_keyword"]
        self.content_keyword_var = self._main_filter_vars["content_keyword"]
        self.summary_keyword_var = self._main_filter_vars["summary_keyword"]
        self._build_filter_widgets(self.advanced_filter_frame, self._main_filter_vars)

        date_filter_row = ttk.Frame(self.advanced_filter_frame, style="TFrame")
        date_filter_row.pack(fill="x", pady=(0, 4))
        self.date_filter_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(date_filter_row, text="기간", variable=self.date_filter_enabled_var).pack(side="left")
        self.filter_start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(date_filter_row, textvariable=self.filter_start_date_var, width=10, font=("Malgun Gothic", 9)).pack(side="left", padx=(4, 2))
        ttk.Label(date_filter_row, text="~", font=("Malgun Gothic", 9)).pack(side="left")
        self.filter_end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_filter_row, textvariable=self.filter_end_date_var, width=10, font=("Malgun Gothic", 9)).pack(side="left", padx=(2, 0))

        # 카드 형태의 컨테이너 안에 리스트박스 배치
        list_card = ttk.Frame(left_panel, style="Card.TFrame", padding=1)
        list_card.pack(fill="both", expand=True)
        self._diary_list_card = list_card

        self.diary_listbox = tk.Listbox(
            list_card,
            bg=COLOR_CARD,
            fg=COLOR_TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="white",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Malgun Gothic", 12),
            activestyle="none",
            exportselection=False
        )
        # 스크롤바 위젯 없이 꽉 채운다 — 마우스 휠 스크롤은 별도 위젯 없이도 그대로 동작한다.
        self.diary_listbox.pack(fill="both", expand=True)

        # ────────────────────────────────────────────────────────
        # RIGHT PANEL: 일기 에디터 및 감정 정보
        # ────────────────────────────────────────────────────────
        right_panel = ttk.Frame(self.mainPaned, style="TFrame", padding=15)
        self.mainPaned.add(right_panel, minsize=400)

        # rightPanel 내부를 캘린더(MAIN)/일기 편집 두 페이지로 나누고, pack()/pack_forget()으로
        # 서로 전환한다(7-2/7-3, Qt의 QStackedWidget과 동일한 역할).
        self.calendar_page = ttk.Frame(right_panel, style="TFrame")
        self.emotion_calendar = EmotionCalendarFrame(self.calendar_page, on_date_click=self._on_calendar_date_clicked)
        self.emotion_calendar.pack(fill="both", expand=True, pady=(0, 12))

        # 카드 프레임 (Editor Card) — 이 프레임 자체가 "편집 페이지"가 된다.
        self.editor_page = ttk.Frame(right_panel, style="TFrame")
        editor_card = ttk.Frame(self.editor_page, style="Card.TFrame", padding=20)
        editor_card.pack(fill="both", expand=True)

        # 날짜 및 제목 입력 레이아웃
        meta_frame = ttk.Frame(editor_card, style="Card.TFrame")
        meta_frame.pack(fill="x", pady=(0, 15))

        # 날짜
        ttk.Label(meta_frame, text="날짜 (YYYY-MM-DD)", style="Card.TLabel", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = ttk.Entry(meta_frame, textvariable=self.date_var, width=15, font=("Malgun Gothic", 10))
        self.date_entry.grid(row=1, column=0, sticky="w", pady=(5, 0), padx=(0, 20))

        # 제목
        ttk.Label(meta_frame, text="제목", style="Card.TLabel", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=1, sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(meta_frame, textvariable=self.title_var, font=("Malgun Gothic", 10))
        self.title_entry.grid(row=1, column=1, sticky="ew", pady=(5, 0))
        
        self.hide_var = tk.BooleanVar(value=False)
        self.hide_check = ttk.Checkbutton(meta_frame, text="🔒 비밀 일기(숨기기)", variable=self.hide_var)
        self.hide_check.grid(row=1, column=2, sticky="w", pady=(5, 0), padx=(10, 0))
        
        meta_frame.columnconfigure(1, weight=1)

        # 위치 / 현재 날씨 / 오늘 감정
        context_frame = ttk.Frame(editor_card, style="Card.TFrame")
        context_frame.pack(fill="x", pady=(0, 12))
        for idx in range(5):
            context_frame.columnconfigure(idx, weight=1)

        ttk.Label(context_frame, text="위치", style="Card.TLabel", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(context_frame, text="날씨", style="Card.TLabel", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=1, columnspan=2, sticky="w", padx=(0, 10))
        ttk.Label(context_frame, text="감정", style="Card.TLabel", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=3, columnspan=2, sticky="w")

        self.location_var = tk.StringVar()
        self.location_entry = ttk.Combobox(
            context_frame,
            textvariable=self.location_var,
            values=self._diary_service.get_location_presets(),
            font=("Malgun Gothic", 10),
        )
        self.location_entry.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(5, 0))

        # 날씨는 하루에 하나만 고르면 충분해서 콤보박스 하나로 통합했다(7-9-2).
        self.actual_weather_var = tk.StringVar(value=MANUAL_WEATHER_OPTIONS[0])
        self.actual_weather_combo = ttk.Combobox(
            context_frame,
            textvariable=self.actual_weather_var,
            state="readonly",
            values=MANUAL_WEATHER_OPTIONS,
            font=("Malgun Gothic", 10),
        )
        self.actual_weather_combo.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 12), pady=(5, 0))

        self.emotion_var = tk.StringVar(value=DEFAULT_EMOTION)
        self.emotion_combo = ttk.Combobox(
            context_frame,
            textvariable=self.emotion_var,
            state="readonly",
            values=MANUAL_EMOTION_OPTIONS,
            font=("Malgun Gothic", 10),
        )
        self.emotion_combo.grid(row=1, column=3, sticky="ew", padx=(0, 6), pady=(5, 0))

        self.emotion_var2 = tk.StringVar(value="선택안함")
        self.emotion_combo2 = ttk.Combobox(
            context_frame,
            textvariable=self.emotion_var2,
            state="readonly",
            values=["선택안함"] + list(MANUAL_EMOTION_OPTIONS),
            font=("Malgun Gothic", 10),
        )
        self.emotion_combo2.grid(row=1, column=4, sticky="ew", pady=(5, 0))

        # 본문 입력 영역 (탭 분리: 텍스트 / 그림판)
        self.editor_notebook = ttk.Notebook(editor_card)
        self.editor_notebook.pack(fill="both", expand=True, pady=(0, 15))
        
        # 1. 텍스트 일기 탭
        text_tab = ttk.Frame(self.editor_notebook, style="TFrame")
        self.editor_notebook.add(text_tab, text="📝 텍스트 일기")
        
        text_border_frame = tk.Frame(text_tab, bg=COLOR_BORDER, bd=1)
        text_border_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.content_text = tk.Text(
            text_border_frame,
            bg=COLOR_CARD,
            fg=COLOR_TEXT_MAIN,
            relief="flat",
            bd=0,
            font=("Malgun Gothic", 11),
            undo=True,
            padx=10,
            pady=10
        )
        self.content_text.pack(fill="both", expand=True)

        # 2. 그림판 일기 탭
        draw_tab = ttk.Frame(self.editor_notebook, style="TFrame")
        self.editor_notebook.add(draw_tab, text="🎨 그림판 일기")
        
        draw_control = ttk.Frame(draw_tab, style="TFrame")
        draw_control.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(draw_control, text="펜 색상:", font=("Malgun Gothic", 9)).pack(side="left", padx=5)
        self.color_var = tk.StringVar(value="black")
        color_combo = ttk.Combobox(draw_control, textvariable=self.color_var, state="readonly", width=8, font=("Malgun Gothic", 9))
        color_combo['values'] = ("black", "red", "blue", "green", "yellow", "white")
        color_combo.pack(side="left", padx=5)
        
        btn_clear = tk.Button(draw_control, text="전체 지우기", command=self._clear_canvas)
        btn_clear.pack(side="right", padx=5)
        style_flat_button(btn_clear, COLOR_SECONDARY, font_size=9)
        
        canvas_border_frame = tk.Frame(draw_tab, bg=COLOR_BORDER, bd=1)
        canvas_border_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(canvas_border_frame, bg="white", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<B1-Motion>", self._paint)
        self.canvas.bind("<ButtonRelease-1>", self._reset_paint)

        # 감정 날씨 결과 카드
        analysis_card = tk.Frame(editor_card, bg=COLOR_BG, bd=0, padx=15, pady=15)
        analysis_card.pack(fill="x", pady=(0, 15))

        # 이모지와 분석 결과 텍스트가 가로로 배치됨
        self.weather_label = tk.Label(analysis_card, text="⛅", font=("Segoe UI Emoji", 48), bg=COLOR_BG)
        self.weather_label.pack(side="left", padx=(0, 20))

        result_txt_frame = ttk.Frame(analysis_card, style="TFrame")
        result_txt_frame.pack(side="left", fill="both", expand=True)

        # PyQt5 스타일과 동일하게 emotion_engine의 get_score_label을 이용
        self.score_label = tk.Label(
            result_txt_frame,
            text="감정 점수: -",
            font=("Malgun Gothic", 12, "bold"),
            bg=COLOR_BG,
            fg=COLOR_TEXT_MAIN
        )
        self.score_label.pack(anchor="w", pady=(5, 2))

        self.detail_label = tk.Label(
            result_txt_frame,
            text="일기를 작성하면 감정 날씨가 나타납니다.",
            font=("Malgun Gothic", 9),
            bg=COLOR_BG,
            fg=COLOR_TEXT_SUB
        )
        self.detail_label.pack(anchor="w")

        # 버튼 영역
        btn_frame = ttk.Frame(editor_card, style="Card.TFrame")
        btn_frame.pack(fill="x")

        # "새 일기" 버튼은 편집 페이지가 아니라 캘린더 페이지 전용이다(7-10) — btn_frame에는
        # 두지 않고 calendar_page에 붙인다.
        self.btn_new = tk.Button(self.calendar_page, text="📝 새 일기")
        self.btn_new.pack(fill="x")
        style_flat_button(self.btn_new, COLOR_SECONDARY)

        self.btn_emotion_graph = tk.Button(self.calendar_page, text="📈 감정 그래프")
        self.btn_emotion_graph.pack(fill="x", pady=(6, 0))
        style_flat_button(self.btn_emotion_graph, COLOR_AI, font_size=9)

        self.btn_save = tk.Button(btn_frame, text="일기 저장")
        self.btn_save.pack(side="left", padx=(0, 10))
        style_flat_button(self.btn_save, COLOR_PRIMARY)

        self.btn_delete = tk.Button(btn_frame, text="일기 삭제")
        self.btn_delete.pack(side="left", padx=(0, 10))
        style_flat_button(self.btn_delete, COLOR_DANGER)

        self.btn_mindmap = tk.Button(btn_frame, text="주간 마인드맵")
        self.btn_mindmap.pack(side="right", padx=(10, 0))
        style_flat_button(self.btn_mindmap, COLOR_PRIMARY)

        self.btn_monthly_stats = tk.Button(btn_frame, text="월간 통계")
        self.btn_monthly_stats.pack(side="right")
        style_flat_button(self.btn_monthly_stats, COLOR_SECONDARY)

        # 목록과 하단 내비게이션 버튼 그룹을 시각적으로 분리하는 얇은 구분선(7-7).
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=(8, 0))

        # 캘린더 페이지에서 편집 페이지로 돌아가는 버튼 — 좌측 내비게이션은 항상 고정 표시이므로
        # 여기 두면 어느 페이지에 있든 접근 가능하다.
        self.btn_back_to_calendar = tk.Button(left_panel, text="🗓️ 캘린더로", command=self._show_calendar_page)
        self.btn_back_to_calendar.pack(fill="x", pady=(8, 4))
        style_flat_button(self.btn_back_to_calendar, COLOR_SECONDARY, font_size=9)

        # 비밀 일기장 진입/나가기 버튼 — 캘린더/편집 페이지 전환과 무관하게 항상 접근 가능해야
        # 하는 전역 모드 전환이므로, 우측 스택이 아니라 좌측 내비게이션에 둔다(7번 확정).
        self.btn_secret_diary = tk.Button(left_panel, text="🔒 비밀일기 찾기")
        self.btn_secret_diary.pack(fill="x", pady=(0, 4))
        style_flat_button(self.btn_secret_diary, COLOR_AI, font_size=9)

        self.btn_exit_secret = tk.Button(left_panel, text="🚪 나가기")
        style_flat_button(self.btn_exit_secret, COLOR_DANGER, font_size=9)
        # 처음엔 숨김 상태 — 비밀 일기장 모드에 들어갔을 때만 pack()으로 표시

        # ────────────────────────────────────────────────────────
        # STATUS BAR: 상태 표시줄
        # ────────────────────────────────────────────────────────
        self.statusbar = tk.Label(
            self,
            text="환영합니다! 오늘의 일기를 작성해 보세요. 📝",
            bd=1,
            relief="flat",
            anchor="w",
            bg=COLOR_CARD,
            fg=COLOR_TEXT_SUB,
            font=("Malgun Gothic", 9),
            padx=10,
            pady=4
        )
        self.statusbar.grid(row=1, column=0, sticky="ew")

    def _connect_events(self):
        """이벤트 연결."""
        self.btn_new.configure(command=self._on_new_diary_requested)
        self.btn_emotion_graph.configure(command=self.show_emotion_graph_window)
        self.btn_save.configure(command=self.on_save_clicked)
        self.btn_delete.configure(command=self._on_delete_clicked)
        self.btn_mindmap.configure(command=self.show_mindmap_window)
        self.btn_monthly_stats.configure(command=self.show_monthly_stats_window)
        self.btn_secret_diary.configure(command=self._on_open_secret_diary_clicked)
        self.btn_exit_secret.configure(command=self._exit_secret_mode)

        # 리스트박스 선택 바인드
        self.diary_listbox.bind("<<ListboxSelect>>", self._on_diary_selected)

        # 필터 접기/펼치기 및 값 변경 시 목록 재조회
        self.advanced_filter_toggle.configure(command=self._toggle_advanced_filter)
        self.filter_var.trace_add("write", lambda *args: self._load_diary_list())
        self.tier_filter_var.trace_add("write", lambda *args: self._load_diary_list())
        self.location_filter_var.trace_add("write", lambda *args: self._load_diary_list())
        self.title_keyword_var.trace_add("write", lambda *args: self._load_diary_list())
        self.content_keyword_var.trace_add("write", lambda *args: self._load_diary_list())
        self.summary_keyword_var.trace_add("write", lambda *args: self._load_diary_list())
        self.date_filter_enabled_var.trace_add("write", lambda *args: self._load_diary_list())
        self.filter_start_date_var.trace_add("write", lambda *args: self._load_diary_list())
        self.filter_end_date_var.trace_add("write", lambda *args: self._load_diary_list())


        # 윈도우 크기 변경 시 캔버스 이미지 초기화용
        self.canvas.bind("<Configure>", self._init_draw_image_if_needed)

    # ── 비밀 일기장 모드 ────────────────────────────────────

    def _on_open_secret_diary_clicked(self):
        """'비밀일기 찾기' 버튼 클릭: 비밀번호 확인 후 비밀 일기장 모드로 전환한다."""
        if not self._diary_service.has_secret_password():
            self.display_alert("아직 설정된 비밀 일기가 없습니다.")
            return

        pwd = simpledialog.askstring(
            "🔒 비밀 일기장",
            "비밀번호를 입력해주세요:",
            show="*"
        )
        if pwd is None:
            return
        if not self._diary_service.verify_secret_password(pwd):
            self.display_alert("비밀번호가 올바르지 않습니다.")
            return

        self._enter_secret_mode()

    def _enter_secret_mode(self):
        """비밀 일기장 모드로 전환: 목록을 숨겨진 일기로 바꾸고, 편집을 읽기 전용으로 잠그고, 색상 연출을 시작한다."""
        self._secret_mode = True
        self._on_new_clicked()
        self.btn_secret_diary.pack_forget()
        self.btn_exit_secret.pack(fill="x", pady=(0, 4))
        self.btn_new.configure(state="disabled")
        self.btn_save.configure(state="disabled")
        self._set_form_read_only(True)
        self._load_diary_list()
        self._start_secret_color_pulse()
        self._show_editor_page()

    def _exit_secret_mode(self):
        """'나가기' 버튼 클릭: 일반 목록/테마로 복귀한다."""
        self._secret_mode = False
        self._stop_secret_color_pulse()
        self.btn_exit_secret.pack_forget()
        self.btn_secret_diary.pack(fill="x", pady=(0, 4))
        self.btn_new.configure(state="normal")
        self.btn_save.configure(state="normal")
        self._set_form_read_only(False)
        self._on_new_clicked()
        self._load_diary_list()
        self._show_calendar_page()

    def _set_form_read_only(self, read_only: bool):
        """비밀 일기장 모드에서는 선택한 일기를 읽기 전용으로만 보여준다 (삭제는 계속 허용)."""
        entry_state = "disabled" if read_only else "normal"
        combo_state = "disabled" if read_only else "readonly"
        self.date_entry.configure(state=entry_state)
        self.title_entry.configure(state=entry_state)
        self.location_entry.configure(state=entry_state)
        self.actual_weather_combo.configure(state=combo_state)
        self.emotion_combo.configure(state=combo_state)
        self.emotion_combo2.configure(state=combo_state)
        self.hide_check.configure(state=entry_state)
        self.content_text.configure(state=entry_state)

    def _start_secret_color_pulse(self):
        """불안한 느낌을 주기 위해 좌우 패널 배경색이 두 색 사이를 천천히 왕복하는 연출을 시작한다."""
        if self._secret_color_job is not None:
            return
        self._secret_color_state = {"step": 0, "direction": 1, "total_steps": 24}
        self._tick_secret_color_pulse()

    def _tick_secret_color_pulse(self):
        state = self._secret_color_state
        t = state["step"] / state["total_steps"]
        # 진홍 → 짙은 보라 → 짙은 파랑을 차례로 거치게 해서 색 변화가 크고 극적으로 느껴지게 한다.
        if t < 0.5:
            color = self._interpolate_color("#7a0a26", "#3d0a6e", t * 2)
        else:
            color = self._interpolate_color("#3d0a6e", "#0a1e7a", (t - 0.5) * 2)
        style = ttk.Style(self)
        style.configure("TFrame", background=color)

        state["step"] += state["direction"]
        if state["step"] >= state["total_steps"]:
            state["step"] = state["total_steps"]
            state["direction"] = -1
        elif state["step"] <= 0:
            state["step"] = 0
            state["direction"] = 1

        self._secret_color_job = self.after(100, self._tick_secret_color_pulse)

    def _stop_secret_color_pulse(self):
        if self._secret_color_job is not None:
            self.after_cancel(self._secret_color_job)
            self._secret_color_job = None
        style = ttk.Style(self)
        style.configure("TFrame", background=COLOR_BG)

    def _interpolate_color(self, hex1: str, hex2: str, t: float) -> str:
        """0~1 사이 t 비율로 두 hex 색상을 보간한다."""
        c1 = self.winfo_rgb(hex1)
        c2 = self.winfo_rgb(hex2)
        r = int(c1[0] + (c2[0] - c1[0]) * t) >> 8
        g = int(c1[1] + (c2[1] - c1[1]) * t) >> 8
        b = int(c1[2] + (c2[2] - c1[2]) * t) >> 8
        return f"#{r:02x}{g:02x}{b:02x}"

    def _play_tear_effect(self, on_finished=None):
        """Qt의 지그재그 찢기 연출 대신, 가벼운 대체 연출(이모지 플래시)을 재생한다."""
        overlay = tk.Label(self, text="📄💨", font=("Segoe UI Emoji", 64), bg=COLOR_BG)
        overlay.place(relx=0.5, rely=0.5, anchor="center")

        def _remove():
            overlay.destroy()
            if on_finished:
                on_finished()

        self.after(700, _remove)

    # ── 비즈니스 로직 및 이벤트 핸들러 ───────────────────────

    def _toggle_advanced_filter(self):
        """'필터' 버튼을 눌러 카테고리/학점/위치/키워드/기간 필터 영역을 접거나 편다."""
        self._advanced_filter_shown = not self._advanced_filter_shown
        if self._advanced_filter_shown:
            self.advanced_filter_frame.pack(fill="x", pady=(0, 8), before=self._diary_list_card)
            self.advanced_filter_toggle.configure(text="🔍 필터 ▴")
        else:
            self.advanced_filter_frame.pack_forget()
            self.advanced_filter_toggle.configure(text="🔍 필터 ▾")

    def _create_filter_vars(self) -> dict:
        """카테고리/학점/위치/제목·본문·요약 키워드 필터용 StringVar를 새로 만들어 딕셔너리로 반환한다."""
        return {
            "category": tk.StringVar(value="전체보기"),
            "tier": tk.StringVar(value="전체"),
            "location": tk.StringVar(),
            "title_keyword": tk.StringVar(),
            "content_keyword": tk.StringVar(),
            "summary_keyword": tk.StringVar(),
        }

    def _build_filter_widgets(self, parent, variables: dict, register_location_combo: bool = True):
        """variables에 담긴 StringVar들로 카테고리/학점/위치/키워드 필터 위젯을 parent에 배치한다.

        메인 목록의 필터 영역과 키워드 분석 다이얼로그가 이 메서드를 공유해서 쓴다.
        register_location_combo=False로 호출하면(예: 팝업 다이얼로그) 위치 콤보박스를
        _location_filter_combos에 등록하지 않는다 — 다이얼로그가 닫혀 위젯이 파괴된 뒤
        _refresh_location_presets()가 죽은 위젯을 건드리는 것을 막기 위함이다.
        """
        ttk.Label(parent, text="카테고리(날씨/감정)", font=("Malgun Gothic", 9)).pack(anchor="w")
        category_combo = ttk.Combobox(parent, textvariable=variables["category"], state="readonly", font=("Malgun Gothic", 9))
        category_combo['values'] = ALL_FILTER_OPTIONS
        category_combo.pack(fill="x", pady=(0, 6))

        ttk.Label(parent, text="학점", font=("Malgun Gothic", 9)).pack(anchor="w")
        tier_combo = ttk.Combobox(parent, textvariable=variables["tier"], state="readonly", font=("Malgun Gothic", 9))
        tier_combo['values'] = EMOTION_TIER_OPTIONS
        tier_combo.pack(fill="x", pady=(0, 6))

        ttk.Label(parent, text="위치", font=("Malgun Gothic", 9)).pack(anchor="w")
        location_combo = ttk.Combobox(
            parent, textvariable=variables["location"], values=self._diary_service.get_location_presets(), font=("Malgun Gothic", 9)
        )
        location_combo.pack(fill="x", pady=(0, 6))
        if register_location_combo:
            self._location_filter_combos.append(location_combo)

        ttk.Label(parent, text="제목 키워드", font=("Malgun Gothic", 9)).pack(anchor="w")
        ttk.Entry(parent, textvariable=variables["title_keyword"], font=("Malgun Gothic", 9)).pack(fill="x", pady=(0, 6))

        ttk.Label(parent, text="본문 키워드", font=("Malgun Gothic", 9)).pack(anchor="w")
        ttk.Entry(parent, textvariable=variables["content_keyword"], font=("Malgun Gothic", 9)).pack(fill="x", pady=(0, 6))

        ttk.Label(parent, text="요약 키워드", font=("Malgun Gothic", 9)).pack(anchor="w")
        ttk.Entry(parent, textvariable=variables["summary_keyword"], font=("Malgun Gothic", 9)).pack(fill="x", pady=(0, 6))

    def _diary_filter_from_vars(self, variables: dict) -> DiaryFilter:
        """_create_filter_vars()가 만든 StringVar들의 현재 값으로 DiaryFilter를 구성한다."""
        return DiaryFilter(
            category=variables["category"].get(),
            tier=variables["tier"].get(),
            location=variables["location"].get(),
            title_keyword=variables["title_keyword"].get(),
            content_keyword=variables["content_keyword"].get(),
            summary_keyword=variables["summary_keyword"].get(),
        )

    def _parse_filter_date(self, text: str) -> str:
        """상세 필터의 날짜 입력값을 검증한다. 형식이 잘못됐으면 빈 문자열(필터 무시)을 반환한다."""
        text = (text or "").strip()
        if not text:
            return ""
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError:
            return ""

    def _build_diary_filter(self) -> DiaryFilter:
        """필터 위젯의 현재 값으로 DiaryFilter를 구성한다."""
        return self._diary_filter_from_vars(self._main_filter_vars)

    def _refresh_location_presets(self):
        """새로 추가된 위치 프리셋을 위치 입력/필터 콤보박스에 반영한다."""
        presets = self._diary_service.get_location_presets()
        self.location_entry['values'] = presets
        for combo in self._location_filter_combos:
            combo['values'] = presets

    def _load_diary_list(self):
        """CSV에서 일기를 불러와 리스트박스 채우기 (카테고리·상세 필터링 포함)."""
        self.diary_listbox.delete(0, tk.END)
        self._list_diary_ids.clear()
        self._refresh_calendar_scores()

        filter_val = self.filter_var.get()
        diary_filter = self._build_diary_filter()
        date_from = ""
        date_to = ""
        if self.date_filter_enabled_var.get():
            date_from = self._parse_filter_date(self.filter_start_date_var.get())
            date_to = self._parse_filter_date(self.filter_end_date_var.get())

        if self._secret_mode:
            diaries = self._diary_service.get_hidden_diaries(diary_filter, date_from, date_to)
        else:
            diaries = self._diary_service.get_all_diaries(diary_filter, date_from, date_to)
        # 최신 날짜 순으로 정렬
        diaries.sort(key=lambda x: x.date, reverse=True)

        for diary in diaries:
            date_str = diary.date
            title = diary.title or "제목 없음"
            weather = diary.weather.actual_weather or diary.weather.emoji
            tier = diary.emotion_score.tier
            diary_id = diary.id

            display_text = f" {weather}  {date_str}  [{tier}]  |  {title}"
            if diary.summary:
                display_text += f"  📝 {truncate_summary(diary.summary)}"
            self.diary_listbox.insert(tk.END, display_text)
            self._list_diary_ids.append(diary_id)

        has_active_filter = bool(
            (filter_val and filter_val != "전체보기")
            or diary_filter.tier
            or diary_filter.location
            or diary_filter.title_keyword
            or diary_filter.content_keyword
            or diary_filter.summary_keyword
            or date_from or date_to
        )
        if not self._list_diary_ids and has_active_filter:
            self.statusbar.config(text="선택한 필터 조건에 해당하는 일기가 없습니다.", fg=COLOR_TEXT_SUB)
        elif not has_active_filter and self._secret_mode:
            self.statusbar.config(text="🔒 비밀 일기장 — 읽기 전용입니다. 나가려면 '나가기'를 눌러주세요.", fg=COLOR_TEXT_SUB)

    def _on_diary_selected(self, event=None):
        """리스트 항목 선택 시 상세 데이터 렌더링."""
        selection = self.diary_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        diary_id = self._list_diary_ids[index]

        diary = self._diary_service.get_diary_by_id(diary_id)
        if diary:
            self._load_diary_into_form(diary)

    def _load_diary_into_form(self, diary):
        """일기 엔티티를 편집 폼에 채우고 편집 페이지로 전환한다 (목록 선택/캘린더 날짜 클릭이 공유, 7-8)."""
        self._current_diary_id = diary.id
        self.date_var.set(diary.date)
        self.title_var.set(diary.title)
        self.location_var.set(diary.weather.location)
        saved_actual_weather = diary.weather.actual_weather
        saved_actual_weather_text = diary.weather.actual_weather_text

        # 날씨 1, 2 로드
        # 날씨 로드 (레거시 데이터에 콤마로 여러 날씨가 저장돼 있어도 첫 번째만 사용, 7-9-2)
        weathers_emoji = [w.strip() for w in saved_actual_weather.split(",") if w.strip()]
        weathers_text = [w.strip() for w in saved_actual_weather_text.split(",") if w.strip()]

        def find_weather_label(emoji, text):
            label = f"{emoji} {text}".strip()
            for opt in MANUAL_WEATHER_OPTIONS:
                if opt.strip() == label:
                    return opt
            return None

        if len(weathers_emoji) >= 1:
            lbl1 = find_weather_label(weathers_emoji[0], weathers_text[0] if len(weathers_text) >= 1 else "")
            self.actual_weather_var.set(lbl1 or MANUAL_WEATHER_OPTIONS[0])
        else:
            self.actual_weather_var.set(MANUAL_WEATHER_OPTIONS[0])

        # 감정 1, 2 로드
        saved_emotion_label = diary.emotion_label or DEFAULT_EMOTION
        emotions = [e.strip() for e in saved_emotion_label.split(",") if e.strip()]

        if len(emotions) >= 1:
            if emotions[0] in MANUAL_EMOTION_OPTIONS:
                self.emotion_var.set(emotions[0])
            else:
                self.emotion_var.set(DEFAULT_EMOTION)
        else:
            self.emotion_var.set(DEFAULT_EMOTION)

        if len(emotions) >= 2:
            if emotions[1] in MANUAL_EMOTION_OPTIONS:
                self.emotion_var2.set(emotions[1])
            else:
                self.emotion_var2.set("선택안함")
        else:
            self.emotion_var2.set("선택안함")

        # Text 위젯 클리어 후 텍스트 세팅 (읽기 전용 상태에서도 프로그램적으로는 갱신되도록 임시 활성화)
        was_read_only = str(self.content_text.cget("state")) == "disabled"
        if was_read_only:
            self.content_text.configure(state="normal")
        self.content_text.delete("1.0", tk.END)
        self.content_text.insert(tk.END, diary.content)
        if was_read_only:
            self.content_text.configure(state="disabled")

        # 이미지 세팅
        self._existing_image_path = ""
        self._remove_existing_image = False
        self._clear_canvas(mark_removed=False)
        img_path = diary.image_path
        if img_path and os.path.exists(img_path):
            try:
                loaded_img = Image.open(img_path)
                self.canvas_image_ref = ImageTk.PhotoImage(loaded_img)
                self.canvas.create_image(0, 0, anchor="nw", image=self.canvas_image_ref)
                self._draw_image = loaded_img.copy()
                self._draw_tool = ImageDraw.Draw(self._draw_image)
                self._existing_image_path = img_path
                self._remove_existing_image = False
                self._canvas_dirty = False
            except Exception as e:
                print(f"이미지 로드 실패: {e}")

        # 날씨 & 스코어 렌더링
        weather = diary.weather.emoji
        score = int(diary.emotion_score.value)
        tier = diary.emotion_score.tier
        self.weather_label.config(text=weather)
        emotion_label = diary.emotion_label or DEFAULT_EMOTION
        self.score_label.config(text=f"감정 상태: {emotion_label} ({score}점, 티어: {tier})")
        self.hide_var.set(diary.is_hidden)
        actual_weather_line = saved_actual_weather or "미입력"
        location_line = diary.weather.location or "미입력"
        self.detail_label.config(text=f"현재 날씨: {actual_weather_line}\n위치: {location_line}")

        self.btn_delete.config(state="normal")
        self.btn_delete.configure(bg=COLOR_DANGER)
        status_text = f"📖 {diary.date} — {diary.title or ''}"
        if diary.summary:
            status_text += f" · 📝 {diary.summary}"
        self.statusbar.config(text=status_text)
        self._show_editor_page()

    # ── 캘린더(MAIN) 페이지 ────────────────────────────────────

    def _show_calendar_page(self):
        """캘린더(MAIN) 페이지를 보여준다."""
        self.editor_page.pack_forget()
        self.calendar_page.pack(fill="both", expand=True)

    def _show_editor_page(self):
        """일기 편집 페이지를 보여준다."""
        self.calendar_page.pack_forget()
        self.editor_page.pack(fill="both", expand=True)

    def _on_new_diary_requested(self):
        """캘린더 페이지의 '새 일기' 버튼: 폼을 초기화하고 편집 페이지로 전환한다."""
        self._on_new_clicked()
        self._show_editor_page()

    def _refresh_calendar_scores(self):
        """감정 점수 히트맵 데이터를 다시 조회해 캘린더에 반영한다."""
        self.emotion_calendar.set_emotion_scores(self._diary_service.get_emotion_scores_by_date())

    def _on_calendar_date_clicked(self, date_str: str):
        """캘린더에서 날짜를 클릭했을 때의 진입 동선을 처리한다(7-8).

        빈 날짜 → 그 날짜로 새 일기 작성. 일기가 있는 날짜 → 목록에서 선택한 것과 동일하게 편집
        페이지로 로드. 단, 그 일기가 비밀 일기면 선택 자체를 막고 안내만 띄운다.
        """
        diary = self._diary_service.find_diary_for_date(date_str)
        if diary is None:
            self._on_new_clicked()
            self.date_var.set(date_str)
            self._show_editor_page()
            return
        if diary.is_hidden:
            self.display_alert("비밀 일기는 캘린더에서 선택할 수 없습니다.")
            return
        self._load_diary_into_form(diary)

    def on_save_clicked(self):
        """'저장' 버튼 클릭: 일기를 저장하고 이어서 AI 한 줄 요약/공감/그림분석을 진행한다."""
        if self._secret_mode:
            return
        date_str = self.date_var.get().strip()
        title = self.title_var.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        location_name = self.location_var.get().strip()
        # 날씨 처리 (하루 하나만 선택, 7-9-2)
        w_val1 = self.actual_weather_var.get().strip()
        w_val2 = ""

        # 감정 1, 2 처리
        e_label1 = self.emotion_var.get().strip()
        e_label2 = self.emotion_var2.get().strip()

        # 3. 그림판 이미지 저장 로직
        image_data = None
        if self._draw_image and self._is_canvas_modified():
            image_data = self._draw_image

        remove_existing_image = False
        if self._current_diary_id is not None and self._remove_existing_image:
            remove_existing_image = True

        # 비밀 일기(숨기기): 전역 비밀번호를 최초 1회만 설정
        is_hidden_val = False
        if self.hide_var.get():
            is_hidden_val = True
            if not self._diary_service.has_secret_password():
                pwd = simpledialog.askstring(
                    "🔒 비밀번호 설정",
                    "비밀 일기 기능을 사용하려면 비밀번호를 설정해주세요:",
                    show="*"
                )
                if pwd and pwd.strip():
                    self._diary_service.set_secret_password(pwd.strip())
                else:
                    self.hide_var.set(False)
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

        if is_hidden_val:
            # 비밀 일기는 저장/AI 처리를 시작하기 전에 먼저 찢는 연출을 보여준다
            def _after_tear():
                self._on_new_clicked()
                self._run_save_and_analyze(save_kwargs, image_base64, w_val1, w_val2)

            self._play_tear_effect(on_finished=_after_tear)
        else:
            self._run_save_and_analyze(save_kwargs, image_base64, w_val1, w_val2)

    def _on_delete_clicked(self):
        """선택된 일기 삭제."""
        if self._current_diary_id is None:
            self.display_alert("삭제할 일기를 선택해 주세요.")
            return

        reply = messagebox.askyesno("삭제 확인", "정말 이 일기를 삭제하시겠습니까?")
        if reply:
            success = self._diary_service.delete_diary(self._current_diary_id)
            if success:
                self._on_new_clicked()
                self._load_diary_list()
                self.statusbar.config(text="🗑️ 일기가 삭제되었습니다.", fg=COLOR_TEXT_SUB)
                self._show_calendar_page()
            else:
                self.display_alert("삭제에 실패했습니다.")

    def _on_new_clicked(self):
        """입력 필드 초기화 (신규 일기 모드)."""
        self._current_diary_id = None
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.title_var.set("")
        self.location_var.set("")
        self.actual_weather_var.set(MANUAL_WEATHER_OPTIONS[0])
        self.emotion_var.set(DEFAULT_EMOTION)
        self.emotion_var2.set("선택안함")
        self.content_text.delete("1.0", tk.END)
        self._existing_image_path = ""
        self._remove_existing_image = False
        self._clear_canvas(mark_removed=False)
        self.hide_var.set(False)
        
        self.weather_label.config(text="⛅")
        self.score_label.config(text=f"감정 상태: {DEFAULT_EMOTION} (0점, 티어: C)")
        self.detail_label.config(text="현재 날씨와 위치를 입력해 주세요.")
        
        # 삭제 버튼 비활성화
        self.btn_delete.config(state="disabled")
        self.btn_delete.configure(bg=COLOR_BORDER)
        
        self.diary_listbox.selection_clear(0, tk.END)
        self.statusbar.config(text="새 일기를 작성해 보세요. ✍️", fg=COLOR_TEXT_SUB)

    def _update_weather_ui(self, result: dict):
        """사용자 선택 감정/날씨 결과를 UI에 반영한다."""
        self.weather_label.config(text=result["weather_emoji"])
        self.score_label.config(text=f"감정 상태: {result['emotion_label']} ({result['score']}점)")
        actual_weather_line = f"{result.get('actual_weather', '')} {result.get('actual_weather_text', '')}".strip() or "미입력"
        location_line = result.get("location_name", "") or "미입력"
        self.detail_label.config(text=f"현재 날씨: {actual_weather_line}\n위치: {location_line}")

    def display_alert(self, msg: str):
        """경고창 표시."""
        messagebox.showinfo("알림", msg)

    # ── 그림판 캔버스 관련 로직 ──────────────────────

    def _init_draw_image_if_needed(self, event=None):
        """처음 캔버스 크기가 정해지면 이미지를 생성한다."""
        if self._draw_image is None:
            self.canvas.update()
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()
            if width <= 1: width = 600
            if height <= 1: height = 400
            self._draw_image = Image.new("RGB", (width, height), "white")
            self._draw_tool = ImageDraw.Draw(self._draw_image)

    def _paint(self, event):
        if self._secret_mode:
            return
        self._init_draw_image_if_needed()
        x, y = event.x, event.y
        if self._last_x is not None and self._last_y is not None:
            color = self.color_var.get()
            self.canvas.create_line(self._last_x, self._last_y, x, y, width=3, fill=color, capstyle=tk.ROUND, smooth=True)
            if self._draw_tool:
                self._draw_tool.line([self._last_x, self._last_y, x, y], fill=color, width=3)
            self._canvas_dirty = True
        self._last_x = x
        self._last_y = y

    def _reset_paint(self, event):
        self._last_x = None
        self._last_y = None

    def _clear_canvas(self, mark_removed: bool = True):
        self.canvas.delete("all")
        if mark_removed and self._existing_image_path:
            self._remove_existing_image = True
        self._draw_image = None
        self._draw_tool = None
        self.canvas_image_ref = None
        self._canvas_dirty = False
        self._init_draw_image_if_needed()

    def _is_canvas_modified(self) -> bool:
        """사용자가 실제로 캔버스를 수정했는지 반환한다."""
        return self._canvas_dirty

    # ── 마인드맵 (키워드 팝업 다이얼로그) ────────────────

    def show_mindmap_window(self):
        """주간 마인드맵 분석 창 생성."""
        dialog = tk.Toplevel(self)
        dialog.title("기간별 키워드 분석 및 마인드맵 📊")
        dialog.geometry("700x820")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self)
        dialog.grab_set()

        # 기간 입력 프레임
        period_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        period_frame.pack(fill="x")

        # 기본 기간: 오늘 ~ 7일 전
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        ttk.Label(period_frame, text="시작 날짜:", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        start_var = tk.StringVar(value=week_ago.strftime("%Y-%m-%d"))
        start_entry = ttk.Entry(period_frame, textvariable=start_var, width=12, font=("Malgun Gothic", 10))
        start_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(period_frame, text="종료 날짜:", font=("Malgun Gothic", 10, "bold")).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        end_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        end_entry = ttk.Entry(period_frame, textvariable=end_var, width=12, font=("Malgun Gothic", 10))
        end_entry.grid(row=0, column=3, padx=5, pady=5)

        btn_analyze = tk.Button(period_frame, text="키워드 분석")
        btn_analyze.grid(row=0, column=4, padx=15, pady=5)
        style_flat_button(btn_analyze, COLOR_PRIMARY)

        # 카테고리/학점/위치/제목·본문·요약 키워드 필터 — 메인 목록과 동일한 위젯 생성 함수를 재사용
        filter_row = ttk.Frame(dialog, style="TFrame", padding=(15, 0, 15, 15))
        filter_row.pack(fill="x")
        dialog_filter_vars = self._create_filter_vars()
        self._build_filter_widgets(filter_row, dialog_filter_vars, register_location_combo=False)

        # 결과 영역 (Grid 1 row, 2 columns)
        result_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        result_frame.pack(fill="both", expand=True)
        result_frame.grid_columnconfigure(0, weight=4)  # Table
        result_frame.grid_columnconfigure(1, weight=6)  # WordCloud
        result_frame.grid_rowconfigure(0, weight=1)

        # 1. 왼쪽: 키워드 빈도 테이블 (Treeview 사용)
        table_frame = ttk.Frame(result_frame, style="TFrame")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ttk.Label(table_frame, text="🔥 인기 키워드 순위", font=("Malgun Gothic", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        # Treeview 설정
        columns = ("rank", "word", "count")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        tree.heading("rank", text="순위")
        tree.heading("word", text="단어")
        tree.heading("count", text="빈도")
        
        tree.column("rank", width=50, anchor="center")
        tree.column("word", width=100, anchor="center")
        tree.column("count", width=60, anchor="center")
        tree.pack(fill="both", expand=True)

        # 2. 오른쪽: 워드클라우드 뷰어
        wc_frame = ttk.Frame(result_frame, style="TFrame")
        wc_frame.grid(row=0, column=1, sticky="nsew")

        ttk.Label(wc_frame, text="☁️ 단어 마인드맵 (WordCloud)", font=("Malgun Gothic", 10, "bold")).pack(anchor="w", pady=(0, 5))

        wc_border = tk.Frame(wc_frame, bg=COLOR_BORDER, bd=1)
        wc_border.pack(fill="both", expand=True)

        wc_display_label = tk.Label(wc_border, text="일기를 분석하면\n마인드맵이 여기에 표시됩니다.", bg=COLOR_CARD, fg=COLOR_TEXT_SUB, font=("Malgun Gothic", 10))
        wc_display_label.pack(fill="both", expand=True)

        # 정보바
        info_label = tk.Label(dialog, text="분석 기간을 선택한 뒤 버튼을 클릭해 주세요.", bg=COLOR_CARD, fg=COLOR_TEXT_SUB, font=("Malgun Gothic", 9), anchor="w", padx=10, pady=5)
        info_label.pack(side="bottom", fill="x")

        # 분석 작동 헬퍼
        def run_analysis():
            start = start_var.get().strip()
            end = end_var.get().strip()

            try:
                datetime.strptime(start, "%Y-%m-%d")
                datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("오류", "날짜 형식이 잘못되었습니다. (YYYY-MM-DD)")
                return

            diary_filter = self._diary_filter_from_vars(dialog_filter_vars)
            entries = self._diary_service.get_all_diaries(diary_filter, start, end)
            if not entries:
                wc_display_label.config(text="해당 기간(및 필터 조건)에 작성된 일기가 없습니다.", image="")
                # 테이블 비우기
                for item in tree.get_children():
                    tree.delete(item)
                info_label.config(text="검색된 일기 없음")
                return

            # 일기 내용 병합 및 토큰 분석
            words = self._diary_service.get_word_list_from_diaries(entries)

            if not words:
                wc_display_label.config(text="분석할 수 있는 키워드가 없습니다.", image="")
                for item in tree.get_children():
                    tree.delete(item)
                info_label.config(text="분석 가능 단어 없음")
                return

            # 1. 키워드 테이블 채우기
            for item in tree.get_children():
                tree.delete(item)
                
            top_keywords, wc_bytes = self._diary_service.analyze_keywords(entries, wordcloud_width=380, wordcloud_height=280)
            for idx, (word, count) in enumerate(top_keywords):
                tree.insert("", "end", values=(idx + 1, word, count))

            # 2. 워드클라우드 이미지 렌더링
            try:
                if wc_bytes:
                    img = Image.open(BytesIO(wc_bytes))
                    photo = ImageTk.PhotoImage(img)
                    
                    # 라벨에 이미지 주입
                    wc_display_label.config(image=photo, text="")
                    # 가비지 컬렉터 방지용 참조 저장
                    wc_display_label.image = photo
                else:
                    wc_display_label.config(text="이미지 생성 실패", image="")
            except Exception as e:
                wc_display_label.config(text=f"오류 발생:\n{str(e)}", image="")

            # 정보 갱신
            info_label.config(text=f"📊 분석 결과: 총 일기 {len(entries)}개 | 추출된 총 단어 {len(words)}개")

        # 버튼 커맨드 설정 및 첫 분석 자동 기동
        btn_analyze.config(command=run_analysis)
        run_analysis()

    def _get_image_base64(self) -> str:
        """캔버스/기존 이미지에서 Base64 인코딩된 그림 데이터를 추출한다."""
        has_drawing = bool(self._existing_image_path) or self._is_canvas_modified()
        if not has_drawing:
            return ""

        import base64
        if self._existing_image_path and not self._is_canvas_modified() and os.path.exists(self._existing_image_path):
            try:
                with open(self._existing_image_path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode("utf-8")
            except Exception as e:
                print(f"디스크에서 이미지 읽기 실패: {e}")
                return ""
        elif self._draw_image:
            try:
                buffered = BytesIO()
                self._draw_image.save(buffered, format="PNG")
                img_bytes = buffered.getvalue()
                return base64.b64encode(img_bytes).decode("utf-8")
            except Exception as e:
                print(f"PIL 이미지 Base64 변환 실패: {e}")
        return ""

    def _run_save_and_analyze(self, save_kwargs: dict, image_base64: str, w_val1: str, w_val2: str):
        """저장 → AI 한 줄 요약 → AI 공감/그림분석을 한 다이얼로그 안에서 순서대로 보여준다."""
        import threading

        dialog = tk.Toplevel(self)
        dialog.title("🤖 AI 공감 일기 도우미")
        dialog.geometry("500x380")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self)
        dialog.grab_set()

        # 메인 컨테이너 프레임
        container = ttk.Frame(dialog, padding=20, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=15, pady=15)

        title_label = ttk.Label(
            container,
            text="🤖 AI 일기 분석 및 공감",
            font=("Malgun Gothic", 14, "bold"),
            foreground=COLOR_AI
        )
        title_label.pack(anchor="w", pady=(0, 15))

        status_var = tk.StringVar(value="💾 일기를 저장하는 중입니다...\n잠시만 기다려주세요.")
        status_label = ttk.Label(
            container,
            textvariable=status_var,
            font=("Malgun Gothic", 11),
            justify="center",
            anchor="center"
        )
        status_label.pack(fill="both", expand=True, pady=20)

        saved_diary_holder = {}
        summary_var = tk.StringVar(value="")

        def _on_confirm():
            diary = saved_diary_holder.get("diary")
            if diary is not None:
                new_summary = summary_var.get().strip()
                if new_summary != (diary.summary or ""):
                    self._diary_service.update_summary(diary.id, new_summary)
                    self._load_diary_list()
            dialog.destroy()

        # 확인 버튼
        ok_button = tk.Button(container, text="확인", command=_on_confirm)
        style_flat_button(ok_button, COLOR_PRIMARY)
        ok_button.pack(side="bottom", anchor="center", pady=(15, 0))
        ok_button.configure(state="disabled")

        def _show_results(result):
            """AI 공감/그림분석 결과를 GUI 메인 스레드에서 안전하게 렌더링."""
            if not dialog.winfo_exists():
                return

            status_label.pack_forget()

            # 요약 섹션 (수정 가능)
            summary_frame = ttk.LabelFrame(container, text="📝 AI 한 줄 요약 (수정 가능)", padding=10)
            summary_frame.pack(fill="x", pady=(0, 15))
            summary_entry = ttk.Entry(summary_frame, textvariable=summary_var, font=("Malgun Gothic", 10))
            summary_entry.pack(fill="x", expand=True)

            # 공감 섹션
            empathy_frame = ttk.LabelFrame(container, text="💖 AI의 공감과 한마디", padding=10)
            empathy_frame.pack(fill="x", pady=(0, 15))
            ttk.Label(
                empathy_frame,
                text=result.get("empathy", ""),
                wraplength=420,
                justify="left",
                font=("Malgun Gothic", 10)
            ).pack(fill="x", expand=True)

            # 그림 분석 섹션
            drawing_frame = ttk.LabelFrame(container, text="🎨 그림 분석", padding=10)
            drawing_frame.pack(fill="x")
            ttk.Label(
                drawing_frame,
                text=result.get("drawing_analysis", ""),
                wraplength=420,
                justify="left",
                font=("Malgun Gothic", 10)
            ).pack(fill="x", expand=True)

            ok_button.configure(state="normal")

            # 동적 창 크기 조절
            dialog.update_idletasks()
            required_height = container.winfo_reqheight() + 50
            dialog.geometry(f"500x{required_height}")

        def _on_error(exc):
            """오류 발생 시 GUI 메인 스레드에서 안전하게 표시."""
            import traceback
            traceback.print_exc()
            if not dialog.winfo_exists():
                return
            status_label.pack(fill="both", expand=True, pady=20)
            status_var.set(f"❌ AI 분석에 실패했습니다:\n\n{str(exc)}")
            status_label.configure(foreground=COLOR_DANGER)
            ok_button.configure(state="normal")
            dialog.update_idletasks()
            required_height = container.winfo_reqheight() + 50
            dialog.geometry(f"500x{required_height}")

        def _on_save_failed():
            if not dialog.winfo_exists():
                return
            action = "수정" if save_kwargs.get("diary_id") is not None else "저장"
            status_var.set(f"❌ 일기 {action}에 실패했습니다.")
            status_label.configure(foreground=COLOR_DANGER)
            ok_button.configure(state="normal")

        def _on_save_success(diary):
            saved_diary_holder["diary"] = diary
            summary_var.set(diary.summary or "")
            self._refresh_location_presets()

            if diary.is_hidden:
                # 찢기 연출과 함께 편집 폼이 이미 초기화됐으므로, 메인 화면에 내용을 다시 반영하지 않는다
                self._load_diary_list()
                self.statusbar.config(text="✅ 비밀 일기가 저장되었습니다.", fg=COLOR_SUCCESS)
            else:
                self._current_diary_id = diary.id
                if save_kwargs.get("image_data"):
                    self._existing_image_path = diary.image_path
                    self._remove_existing_image = False
                    self._canvas_dirty = False
                elif save_kwargs.get("remove_image"):
                    self._existing_image_path = ""
                    self._remove_existing_image = False

                self._update_weather_ui({
                    "weather_emoji": diary.weather.emoji,
                    "emotion_label": diary.emotion_label,
                    "score": int(diary.emotion_score.value),
                    "actual_weather": diary.weather.actual_weather,
                    "actual_weather_text": diary.weather.actual_weather_text,
                    "location_name": diary.weather.location,
                })
                self._load_diary_list()

                action = "수정" if save_kwargs.get("diary_id") is not None else "저장"
                actual_weather_value = f"{w_val1}, {w_val2}" if w_val2 and w_val2 != "선택안함" else w_val1
                self.statusbar.config(
                    text=f"✅ 일기가 {action}되었습니다! 감정: {diary.emotion_label} | 현재 날씨: {actual_weather_value}",
                    fg=COLOR_SUCCESS
                )
                # 신규 작성의 경우 바로 새 일기 모드로 전환
                if action == "저장":
                    self._on_new_clicked()

            if dialog.winfo_exists():
                status_var.set("🤖 AI가 조언 중입니다...\n잠시만 기다려주세요. ✨")

        def _worker():
            """백그라운드 스레드: 저장(+요약 대기) → 공감/그림분석 순서로 실행."""
            try:
                success, diary = self._diary_service.save_diary(**save_kwargs)
            except Exception as exc:
                _captured = exc
                self.after(0, lambda e=_captured: _on_error(e))
                return

            if success and diary:
                self.after(0, lambda: _on_save_success(diary))
            else:
                self.after(0, _on_save_failed)
                return

            try:
                result = self._diary_service.analyze_empathy(
                    date=diary.date,
                    content=diary.content,
                    location=diary.weather.location,
                    weather=diary.weather.actual_weather_text,
                    emotion=diary.emotion_label,
                    image_base64=image_base64,
                )
                self.after(0, lambda: _show_results(result))
            except Exception as exc:
                _captured = exc
                self.after(0, lambda e=_captured: _on_error(e))

        # 백그라운드 스레드로 저장 및 AI 분석 실행 (GUI 이벤트 루프 비차단)
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


    # ── 감정 그래프(매크로 뷰) ──────────────────────

    def show_emotion_graph_window(self):
        """캘린더 페이지의 '감정 그래프' 버튼: 기간을 선택해 감정 점수 추이 매크로 뷰를 보여준다(8-5)."""
        dialog = tk.Toplevel(self)
        dialog.title("📈 감정 그래프")
        dialog.geometry("780x520")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self)
        dialog.grab_set()

        control_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        control_frame.pack(fill="x")

        today = datetime.now()
        ttk.Label(control_frame, text="시작 날짜:", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)
        start_var = tk.StringVar(value=(today - timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(control_frame, textvariable=start_var, width=12, font=("Malgun Gothic", 10)).pack(side="left", padx=5)

        ttk.Label(control_frame, text="종료 날짜:", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)
        end_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        ttk.Entry(control_frame, textvariable=end_var, width=12, font=("Malgun Gothic", 10)).pack(side="left", padx=5)

        btn_draw = tk.Button(control_frame, text="그래프 그리기")
        btn_draw.pack(side="left", padx=15)
        style_flat_button(btn_draw, COLOR_PRIMARY)

        chart_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        chart_frame.pack(fill="both", expand=True)

        info_label = tk.Label(dialog, text="기간을 입력한 뒤 그래프 그리기 버튼을 클릭해 주세요.", bg=COLOR_CARD, fg=COLOR_TEXT_SUB, font=("Malgun Gothic", 9), anchor="w", padx=10, pady=5)
        info_label.pack(side="bottom", fill="x")

        def draw_graph():
            start_str = start_var.get().strip()
            end_str = end_var.get().strip()
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("오류", "날짜 형식이 잘못되었습니다. (YYYY-MM-DD)")
                return
            if end_date < start_date:
                start_date, end_date = end_date, start_date

            scores_by_date = self._diary_service.get_emotion_scores_by_date(
                date_from=start_date.strftime("%Y-%m-%d"), date_to=end_date.strftime("%Y-%m-%d")
            )

            for widget in chart_frame.winfo_children():
                widget.destroy()

            if not scores_by_date:
                info_label.config(text="해당 기간에 작성된 일기가 없습니다.")
                tk.Label(chart_frame, text="해당 기간 데이터 없음", font=("Malgun Gothic", 12), bg=COLOR_BG, fg=COLOR_TEXT_SUB).pack(expand=True)
                return

            # 기간 내 매일을 순회하며 일기 없는 날은 None으로 남겨 선이 자연스럽게 끊기게 한다(8-2/8-5).
            dates = []
            scores = []
            current = start_date
            while current <= end_date:
                date_str = current.strftime("%Y-%m-%d")
                dates.append(current)
                scores.append(scores_by_date.get(date_str))
                current += timedelta(days=1)

            import matplotlib.pyplot as plt
            plt.rcParams['font.family'] = 'Malgun Gothic'
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(6.5, 4), dpi=100)
            fig.patch.set_facecolor(COLOR_BG)
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLOR_CARD)

            plot_scores = [s if s is not None else float("nan") for s in scores]
            ax.plot(dates, plot_scores, marker='o', linestyle='-', color=COLOR_PRIMARY,
                    linewidth=2, markersize=5, markerfacecolor=COLOR_DANGER, markeredgecolor=COLOR_DANGER)

            ax.set_title("감정 점수 변화 추이", fontsize=13, fontweight='bold', color=COLOR_TEXT_MAIN, pad=12)
            ax.set_ylabel("감정 점수", fontsize=10, color=COLOR_TEXT_SUB, labelpad=8)
            ax.set_ylim(-5.5, 5.5)
            ax.axhline(0, color=COLOR_BORDER, linewidth=1.5, linestyle='--')
            ax.grid(True, linestyle='--', alpha=0.5, color=COLOR_BORDER)
            ax.tick_params(colors=COLOR_TEXT_SUB, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(COLOR_BORDER)
            fig.autofmt_xdate(rotation=30)

            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

            info_label.config(text=f"📊 {start_str} ~ {end_str} 기간 중 일기 작성일 {len(scores_by_date)}일 렌더링 완료")

        btn_draw.config(command=draw_graph)
        draw_graph()

    # ── 월간 감정 통계 창 ──────────────────────────

    def show_monthly_stats_window(self):
        """월간 감정 통계 창 생성."""
        dialog = tk.Toplevel(self)
        dialog.title("월간 감정 통계 📈")
        dialog.geometry("800x600")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self)
        dialog.grab_set()

        # 상단 설정 프레임
        control_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        control_frame.pack(fill="x")

        today = datetime.now()
        
        ttk.Label(control_frame, text="연도:", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)
        year_var = tk.StringVar(value=str(today.year))
        ttk.Entry(control_frame, textvariable=year_var, width=8, font=("Malgun Gothic", 10)).pack(side="left", padx=5)
        
        ttk.Label(control_frame, text="월:", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=5)
        month_var = tk.StringVar(value=str(today.month).zfill(2))
        ttk.Entry(control_frame, textvariable=month_var, width=5, font=("Malgun Gothic", 10)).pack(side="left", padx=5)
        
        btn_analyze = tk.Button(control_frame, text="그래프 보기")
        btn_analyze.pack(side="left", padx=15)
        style_flat_button(btn_analyze, COLOR_PRIMARY)

        # 차트가 렌더링될 프레임
        chart_frame = ttk.Frame(dialog, style="TFrame", padding=15)
        chart_frame.pack(fill="both", expand=True)

        info_label = tk.Label(dialog, text="연도와 월을 입력한 뒤 그래프 보기 버튼을 클릭해 주세요.", bg=COLOR_CARD, fg=COLOR_TEXT_SUB, font=("Malgun Gothic", 9), anchor="w", padx=10, pady=5)
        info_label.pack(side="bottom", fill="x")

        def run_analysis():
            year_str = year_var.get().strip()
            month_str = month_var.get().strip()
            
            try:
                year = int(year_str)
                month = int(month_str)
                if not (1 <= month <= 12):
                    raise ValueError("월은 1~12 사이여야 합니다.")
            except ValueError:
                messagebox.showerror("오류", "연도와 월을 올바른 숫자로 입력해 주세요.")
                return

            # 해당 월의 시작일과 마지막일 계산
            start_date = f"{year:04d}-{month:02d}-01"
            if month == 12:
                next_month_1st = datetime(year + 1, 1, 1)
            else:
                next_month_1st = datetime(year, month + 1, 1)
            end_date = (next_month_1st - timedelta(days=1)).strftime("%Y-%m-%d")

            entries = self._diary_service.get_diaries_by_date_range(start_date, end_date)
            
            # 기존 위젯 정리
            for widget in chart_frame.winfo_children():
                widget.destroy()

            if not entries:
                info_label.config(text=f"{year}년 {month}월에 작성된 일기가 없습니다.")
                tk.Label(chart_frame, text="해당 기간 데이터 없음", font=("Malgun Gothic", 12), bg=COLOR_BG, fg=COLOR_TEXT_SUB).pack(expand=True)
                return

            # 날짜순 정렬
            entries.sort(key=lambda x: x.date)
            
            dates = []
            scores = []
            
            # 같은 날짜에 여러 일기가 있을 경우 평균을 내거나 단순 나열. 여기서는 단순 나열 및 일(Day) 추출.
            # 중복 일자는 딕셔너리로 평균화 (예외 처리 원칙)
            day_score_map = collections.defaultdict(list)
            
            for diary in entries:
                date_val = diary.date
                score = diary.emotion_score.value
                    
                if len(date_val) >= 10:
                    day_str = date_val[8:10]
                    day_score_map[day_str].append(score)
            
            for d_str in sorted(day_score_map.keys()):
                dates.append(d_str)
                # 하루에 여러 일기가 있으면 평균 스코어
                avg_score = sum(day_score_map[d_str]) / len(day_score_map[d_str])
                scores.append(avg_score)

            # matplotlib 한글 폰트 설정 (윈도우/맥 호환을 위해 폰트 설정, 미지원 시 경고는 무시)
            import matplotlib.pyplot as plt
            plt.rcParams['font.family'] = 'Malgun Gothic'
            plt.rcParams['axes.unicode_minus'] = False
            
            fig = Figure(figsize=(6, 4), dpi=100)
            fig.patch.set_facecolor(COLOR_BG)
            
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLOR_CARD)
            
            # 꺾은선 그래프 플롯
            ax.plot(dates, scores, marker='o', linestyle='-', color=COLOR_PRIMARY, linewidth=2, markersize=8)
            
            ax.set_title(f"{year}년 {month}월 감정 점수 변화 추이", fontsize=14, fontweight='bold', color=COLOR_TEXT_MAIN, pad=15)
            ax.set_xlabel("일 (Day)", fontsize=10, color=COLOR_TEXT_SUB, labelpad=10)
            ax.set_ylabel("감정 점수 (-100 ~ 100)", fontsize=10, color=COLOR_TEXT_SUB, labelpad=10)
            
            ax.set_ylim(-110, 110)
            ax.axhline(0, color=COLOR_BORDER, linewidth=1.5, linestyle='--') # 0점 기준선
            ax.grid(True, linestyle='--', alpha=0.5, color=COLOR_BORDER)
            
            # 텍스트와 테두리 색상
            ax.tick_params(colors=COLOR_TEXT_SUB)
            for spine in ax.spines.values():
                spine.set_edgecolor(COLOR_BORDER)

            # Tkinter 캔버스 임베딩
            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            
            info_label.config(text=f"📊 분석 결과: 총 일기 {len(entries)}일 분량의 데이터 렌더링 완료")

        btn_analyze.config(command=run_analysis)
        run_analysis()
