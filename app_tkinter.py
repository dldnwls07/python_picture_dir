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
    MANUAL_EMOTION_OPTIONS,
    MANUAL_WEATHER_OPTIONS,
    truncate_summary,
)
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
        # UI 위젯 초기화 및 배치
        self._init_ui()
        self._connect_events()
        self._load_diary_list()
        self._on_new_clicked()

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
        
        # 2. 메인 화면 Grid 분할 (Left Panel: 300px, Right Panel: 660px)
        self.grid_columnconfigure(0, weight=3, minsize=300)
        self.grid_columnconfigure(1, weight=7, minsize=600)
        self.grid_rowconfigure(0, weight=1)

        # ────────────────────────────────────────────────────────
        # LEFT PANEL: 일기 목록
        # ────────────────────────────────────────────────────────
        left_panel = ttk.Frame(self, style="TFrame", padding=15)
        left_panel.grid(row=0, column=0, sticky="nsew")

        lbl_list = ttk.Label(left_panel, text="일기 히스토리", style="Header.TLabel")
        lbl_list.pack(anchor="w", pady=(0, 5))
        
        # 카테고리 필터
        filter_frame = ttk.Frame(left_panel, style="TFrame")
        filter_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(filter_frame, text="필터:", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 5))
        self.filter_var = tk.StringVar(value="전체보기")
        self.filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var, state="readonly", width=12, font=("Malgun Gothic", 9))
        self.filter_combo['values'] = ALL_FILTER_OPTIONS
        self.filter_combo.pack(side="left")

        # 카드 형태의 컨테이너 안에 리스트박스 배치
        list_card = ttk.Frame(left_panel, style="Card.TFrame", padding=1)
        list_card.pack(fill="both", expand=True)

        self.diary_listbox = tk.Listbox(
            list_card,
            bg=COLOR_CARD,
            fg=COLOR_TEXT_MAIN,
            selectbackground=COLOR_PRIMARY,
            selectforeground="white",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Malgun Gothic", 10),
            activestyle="none",
            exportselection=False
        )
        self.diary_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_card, orient="vertical", command=self.diary_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.diary_listbox.config(yscrollcommand=scrollbar.set)

        # ────────────────────────────────────────────────────────
        # RIGHT PANEL: 일기 에디터 및 감정 정보
        # ────────────────────────────────────────────────────────
        right_panel = ttk.Frame(self, style="TFrame", padding=15)
        right_panel.grid(row=0, column=1, sticky="nsew")

        # 카드 프레임 (Editor Card)
        editor_card = ttk.Frame(right_panel, style="Card.TFrame", padding=20)
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
        self.location_entry = ttk.Entry(context_frame, textvariable=self.location_var, font=("Malgun Gothic", 10))
        self.location_entry.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(5, 0))

        self.actual_weather_var = tk.StringVar(value=MANUAL_WEATHER_OPTIONS[0])
        self.actual_weather_combo = ttk.Combobox(
            context_frame,
            textvariable=self.actual_weather_var,
            state="readonly",
            values=MANUAL_WEATHER_OPTIONS,
            font=("Malgun Gothic", 10),
        )
        self.actual_weather_combo.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(5, 0))

        self.actual_weather_var2 = tk.StringVar(value="선택안함")
        self.actual_weather_combo2 = ttk.Combobox(
            context_frame,
            textvariable=self.actual_weather_var2,
            state="readonly",
            values=["선택안함"] + list(MANUAL_WEATHER_OPTIONS),
            font=("Malgun Gothic", 10),
        )
        self.actual_weather_combo2.grid(row=1, column=2, sticky="ew", padx=(0, 12), pady=(5, 0))

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

        self.btn_new = tk.Button(btn_frame, text="새 일기")
        self.btn_new.pack(side="left", padx=(0, 10))
        style_flat_button(self.btn_new, COLOR_SECONDARY)

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
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _connect_events(self):
        """이벤트 연결."""
        self.btn_new.configure(command=self._on_new_clicked)
        self.btn_save.configure(command=self.on_save_clicked)
        self.btn_delete.configure(command=self._on_delete_clicked)
        self.btn_mindmap.configure(command=self.show_mindmap_window)
        self.btn_monthly_stats.configure(command=self.show_monthly_stats_window)

        # 리스트박스 선택 및 필터 콤보박스 바인드
        self.diary_listbox.bind("<<ListboxSelect>>", self._on_diary_selected)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._load_diary_list())
        
        # 윈도우 크기 변경 시 캔버스 이미지 초기화용
        self.canvas.bind("<Configure>", self._init_draw_image_if_needed)

    # ── 비즈니스 로직 및 이벤트 핸들러 ───────────────────────

    def _load_diary_list(self):
        """CSV에서 일기를 불러와 리스트박스 채우기 (카테고리 필터링 포함)."""
        self.diary_listbox.delete(0, tk.END)
        self._list_diary_ids.clear()

        filter_val = self.filter_var.get()
        diaries = self._diary_service.get_all_diaries(filter_value=filter_val)
        # 최신 날짜 순으로 정렬
        diaries.sort(key=lambda x: x.date, reverse=True)

        for diary in diaries:
            date_str = diary.date
            title = diary.title or "제목 없음"
            weather = diary.weather.actual_weather or diary.weather.emoji
            diary_id = diary.id

            display_text = f" {weather}  {date_str}  |  {title}"
            if diary.summary:
                display_text += f"  📝 {truncate_summary(diary.summary)}"
            self.diary_listbox.insert(tk.END, display_text)
            self._list_diary_ids.append(diary_id)

        if not self._list_diary_ids and filter_val != "전체보기":
            self.statusbar.config(text=f"선택한 필터 '{filter_val}'에 해당하는 일기가 없습니다.", fg=COLOR_TEXT_SUB)

    def _on_diary_selected(self, event=None):
        """리스트 항목 선택 시 상세 데이터 렌더링."""
        selection = self.diary_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        diary_id = self._list_diary_ids[index]

        diary = self._diary_service.get_diary_by_id(diary_id)
        if diary:
            self._current_diary_id = diary_id
            self.date_var.set(diary.date)
            self.title_var.set(diary.title)
            self.location_var.set(diary.weather.location)
            saved_actual_weather = diary.weather.actual_weather
            saved_actual_weather_text = diary.weather.actual_weather_text
            
            # 날씨 1, 2 로드
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
                
            if len(weathers_emoji) >= 2:
                lbl2 = find_weather_label(weathers_emoji[1], weathers_text[1] if len(weathers_text) >= 2 else "")
                self.actual_weather_var2.set(lbl2 or "선택안함")
            else:
                self.actual_weather_var2.set("선택안함")
                
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
            
            # Text 위젯 클리어 후 텍스트 세팅
            self.content_text.delete("1.0", tk.END)
            self.content_text.insert(tk.END, diary.content)

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

    def on_save_clicked(self):
        """'저장' 버튼 클릭: 일기를 저장하고 이어서 AI 한 줄 요약/공감/그림분석을 진행한다."""
        date_str = self.date_var.get().strip()
        title = self.title_var.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        location_name = self.location_var.get().strip()
        # 날씨 1, 2 처리
        w_val1 = self.actual_weather_var.get().strip()
        w_val2 = self.actual_weather_var2.get().strip()

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
            else:
                self.display_alert("삭제에 실패했습니다.")

    def _on_new_clicked(self):
        """입력 필드 초기화 (신규 일기 모드)."""
        self._current_diary_id = None
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.title_var.set("")
        self.location_var.set("")
        self.actual_weather_var.set(MANUAL_WEATHER_OPTIONS[0])
        self.actual_weather_var2.set("선택안함")
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
        dialog.geometry("700x550")
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

            entries = self._diary_service.get_diaries_by_date_range(start, end)
            if not entries:
                wc_display_label.config(text="해당 기간에 작성된 일기가 없습니다.", image="")
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
                if diary.is_hidden:
                    # 비밀 일기는 목록에서 완전히 제외되므로 편집 폼을 초기화한다
                    self._on_new_clicked()
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
            # 신규 작성(비밀 일기 제외)의 경우 바로 새 일기 모드로 전환
            if action == "저장" and not diary.is_hidden:
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
