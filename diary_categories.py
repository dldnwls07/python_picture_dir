"""
일기 카테고리/필터 공용 정의.
"""

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


def matches_filter(row: dict, filter_value: str) -> bool:
    """일기 row가 주어진 필터에 포함되는지 반환한다."""
    if not filter_value or filter_value == "전체보기":
        return True

    weather = row.get("actual_weather") or row.get("weather", "⛅")

    emotion_label = row.get("emotion_label", "")
    try:
        score = int(row.get("score", ""))
    except (TypeError, ValueError):
        # 콤마로 구분된 복수 감정 레이블 처리
        labels = [l.strip() for l in emotion_label.split(",") if l.strip()]
        if labels:
            scores = [EMOTION_LABEL_TO_SCORE.get(l, 0) for l in labels]
            score = sum(scores) / len(scores)
        else:
            score = 0

    if filter_value in WEATHER_LABEL_TO_EMOJI:
        target_emoji = WEATHER_LABEL_TO_EMOJI[filter_value]
        # 날씨에 다중 매칭 지원
        emojis = [w.strip() for w in weather.split(",")]
        return target_emoji in emojis

    if filter_value == "긍정 일기":
        return score > 0
    if filter_value == "중립 일기":
        return score == 0
    if filter_value == "부정 일기":
        return score < 0

    return True
