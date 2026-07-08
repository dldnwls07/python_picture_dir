"""
KeywordAnalyzer — 키워드 빈도 분석 클래스
collections.Counter를 활용한 단어 빈도 추출 및 WordCloud 이미지 생성.
"""

import os
from collections import Counter
from io import BytesIO

from wordcloud import WordCloud
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


class KeywordAnalyzer:
    """일기 텍스트에서 키워드 빈도를 분석하고 워드클라우드를 생성하는 클래스."""

    def __init__(self):
        # macOS / Windows 한글 폰트 자동 탐색
        self._font_path = self._find_korean_font()

    def _find_korean_font(self) -> str:
        """시스템에 설치된 한글 폰트 경로를 탐색한다."""
        candidates = [
            # macOS
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/Library/Fonts/NanumGothic.ttf",
            "/Library/Fonts/NanumGothicBold.ttf",
            # Windows
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/gulim.ttc",
            # Linux
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""  # 폰트를 못 찾으면 빈 문자열 (WordCloud 기본 폰트 사용)

    def get_top_keywords(self, word_list: list, top_n: int = 10) -> list:
        """단어 빈도를 계산하여 상위 N개 키워드를 반환한다.

        Args:
            word_list: 전처리된 단어 리스트
            top_n: 상위 몇 개를 반환할지

        Returns:
            [(단어, 빈도수), ...] 리스트
        """
        if not word_list:
            return []
        counter = Counter(word_list)
        return counter.most_common(top_n)

    def generate_wordcloud_bytes(self, word_list: list,
                                  width: int = 600, height: int = 400) -> bytes:
        """단어 리스트로부터 워드클라우드 이미지를 생성하여 PNG 바이트로 반환한다.

        Args:
            word_list: 전처리된 단어 리스트
            width: 이미지 너비
            height: 이미지 높이

        Returns:
            PNG 이미지 바이트 데이터
        """
        if not word_list:
            return b""

        # Counter → 딕셔너리 변환
        word_freq = dict(Counter(word_list))

        wc_kwargs = {
            "width": width,
            "height": height,
            "background_color": "#1e1e2e",
            "colormap": "Pastel1",
            "max_words": 50,
            "prefer_horizontal": 0.7,
            "relative_scaling": 0.5,
        }

        if self._font_path:
            wc_kwargs["font_path"] = self._font_path

        wc = WordCloud(**wc_kwargs)
        wc.generate_from_frequencies(word_freq)

        # pyplot 전역 상태 없이 순수 Figure 객체를 생성하여 자원 누수를 예방
        fig = Figure(figsize=(width / 100, height / 100), dpi=100)
        FigureCanvasAgg(fig)  # 캔버스 연결 (렌더링에 필요)
        ax = fig.add_subplot(111)
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        fig.patch.set_facecolor("#1e1e2e")
        fig.tight_layout(pad=0)

        buf = BytesIO()
        fig.savefig(buf, format="png", facecolor="#1e1e2e",
                    bbox_inches="tight", pad_inches=0.1)
        buf.seek(0)
        return buf.read()
