"""
TrendChartRenderer — 기간별 감정 점수 추이(매크로 뷰) 꺾은선 그래프 생성 (8-5).
"""

import os
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, Optional

import matplotlib
import matplotlib.font_manager as font_manager
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


class TrendChartRenderer:
    """{"yyyy-MM-dd": 평균 점수} 딕셔너리로부터 기간 꺾은선 그래프(PNG 바이트)를 생성한다."""

    def __init__(self):
        self._font_applied = False

    def _find_korean_font(self) -> str:
        candidates = [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/Library/Fonts/NanumGothic.ttf",
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/gulim.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""

    def _ensure_korean_font(self):
        """matplotlib 전역 폰트를 한글 지원 폰트로 한 번만 설정한다."""
        if self._font_applied:
            return
        self._font_applied = True
        font_path = self._find_korean_font()
        if font_path:
            font_manager.fontManager.addfont(font_path)
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            matplotlib.rcParams["font.family"] = font_name
        matplotlib.rcParams["axes.unicode_minus"] = False

    def generate_trend_chart_bytes(
        self,
        scores_by_date: Dict[str, float],
        date_from: str,
        date_to: str,
        width: int = 700,
        height: int = 350,
        dark_theme: bool = True,
    ) -> bytes:
        """date_from~date_to(포함) 매일의 평균 점수를 이은 꺾은선 그래프 PNG 바이트를 반환한다.

        일기가 없는 날은 값 없이(NaN) 넘겨 matplotlib이 그 구간의 선을 자동으로 끊도록 한다
        (8-2/8-5에서 정한 "데이터 공백은 보간하지 않고 끊는다" 정책과 동일하게 적용).
        """
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d")
            end = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            return b""
        if end < start:
            start, end = end, start

        dates = []
        scores = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            dates.append(current)
            scores.append(scores_by_date.get(date_str))
            current += timedelta(days=1)

        if not any(s is not None for s in scores):
            return b""

        self._ensure_korean_font()

        if dark_theme:
            bg_color = "#1e1e2e"
            grid_color = "#313244"
            text_color = "#f5f5f5"
            line_color = "#89b4fa"
            marker_color = "#f38ba8"
        else:
            bg_color = "#FFFFFF"
            grid_color = "#E9ECEF"
            text_color = "#212529"
            line_color = "#4D96FF"
            marker_color = "#FF6B6B"

        fig = Figure(figsize=(width / 100, height / 100), dpi=100)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        plot_scores = [s if s is not None else float("nan") for s in scores]
        ax.plot(
            dates, plot_scores, color=line_color, linewidth=2, marker="o",
            markersize=4, markerfacecolor=marker_color, markeredgecolor=marker_color,
        )

        ax.set_ylim(-5.5, 5.5)
        ax.axhline(0, color=grid_color, linewidth=1, linestyle="--")
        ax.grid(True, color=grid_color, linewidth=0.5, alpha=0.6)
        ax.set_facecolor(bg_color)
        fig.patch.set_facecolor(bg_color)
        ax.tick_params(colors=text_color, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
        ax.set_ylabel("감정 점수", color=text_color, fontsize=9)
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout(pad=1.2)

        buf = BytesIO()
        fig.savefig(buf, format="png", facecolor=bg_color)
        buf.seek(0)
        return buf.read()
