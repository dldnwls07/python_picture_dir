from typing import Dict

WEATHER_FILTERS = (
    "☀️ 맑음",
    "⛅ 흐림",
    "☁️ 구름많음",
    "🌧️ 비",
    "❄️ 눈",
    "⚡ 번개",
)

EMOTION_FILTERS = (
    "긍정 일기",
    "중립 일기",
    "부정 일기",
)

MANUAL_WEATHER_OPTIONS = WEATHER_FILTERS

MANUAL_EMOTION_OPTIONS = (
    "재미있었어요",
    "행복했어요",
    "슬펐어요",
    "피곤했어요",
    "화났어요",
    "사랑에 빠졌어요",
    "고독",
    "집에가고싶어!",
    "심심해요",
)

DEFAULT_EMOTION = "심심해요"

EMOTION_LABEL_TO_SCORE = {
    "재미있었어요": 3,
    "행복했어요": 5,
    "슬펐어요": -4,
    "피곤했어요": -1,
    "화났어요": -5,
    "사랑에 빠졌어요": 5,
    "고독": -2,
    "집에가고싶어!": -3,
    "심심해요": 0,
}

EMOTION_LABEL_TO_WEATHER = {
    "재미있었어요": ("🌤️", "대체로 맑음"),
    "행복했어요": ("☀️", "맑음"),
    "슬펐어요": ("🌧️", "비"),
    "피곤했어요": ("☁️", "흐림"),
    "화났어요": ("⛈️", "번개"),
    "사랑에 빠졌어요": ("☀️", "맑음"),
    "고독": ("☁️", "흐림"),
    "집에가고싶어!": ("🌧️", "비"),
    "심심해요": ("⛅", "보통"),
}

ALL_FILTER_OPTIONS = ("전체보기",) + WEATHER_FILTERS + EMOTION_FILTERS

WEATHER_LABEL_TO_EMOJI: Dict[str, str] = {
    "☀️ 맑음": "☀️",
    "⛅ 흐림": "⛅",
    "☁️ 구름많음": "☁️",
    "🌧️ 비": "🌧️",
    "❄️ 눈": "❄️",
    "⚡ 번개": "⚡",
}


class EmotionScore:
    """감정 점수 밸류 객체."""
    
    def __init__(self, score: float):
        self._score = float(score)

    @property
    def value(self) -> float:
        return self._score

    @property
    def tier(self) -> str:
        """점수를 기반으로 감정 등급(A+ ~ F) 티어를 반환한다."""
        if self._score >= 5:
            return "A+"
        elif self._score >= 3:
            return "A"
        elif self._score >= 1:
            return "B"
        elif self._score >= 0:
            return "C"
        elif self._score >= -2:
            return "D"
        else:
            return "F"

    @property
    def label(self) -> str:
        """점수에 대한 설명 라벨을 반환한다."""
        if self._score >= 5:
            return "매우 긍정적"
        elif self._score >= 2:
            return "긍정적"
        elif self._score >= 0:
            return "보통"
        elif self._score >= -3:
            return "부정적"
        else:
            return "매우 부정적"

    def __eq__(self, other):
        if not isinstance(other, EmotionScore):
            return False
        return self._score == other._score

    def __repr__(self):
        return f"EmotionScore({self._score})"


class Weather:
    """날씨 정보 밸류 객체."""

    def __init__(
        self,
        emoji: str = "⛅",
        text: str = "알 수 없음",
        source: str = "fallback",
        location: str = "",
        actual_weather: str = "",
        actual_weather_text: str = ""
    ):
        self.emoji = emoji
        self.text = text
        self.source = source
        self.location = location
        self.actual_weather = actual_weather or emoji
        self.actual_weather_text = actual_weather_text or text

    def __eq__(self, other):
        if not isinstance(other, Weather):
            return False
        return (
            self.emoji == other.emoji
            and self.text == other.text
            and self.source == other.source
            and self.location == other.location
            and self.actual_weather == other.actual_weather
            and self.actual_weather_text == other.actual_weather_text
        )

    def __repr__(self):
        return f"Weather(emoji={self.emoji}, text={self.text}, location={self.location})"
