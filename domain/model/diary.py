from datetime import datetime
from typing import Optional
from domain.model.value_objects import EmotionScore, Weather

class Diary:
    """일기 도메인 엔티티 (Aggregate Root)"""

    def __init__(
        self,
        diary_id: Optional[int],
        date: str,
        title: str,
        content: str,
        emotion_score: EmotionScore,
        emotion_label: str,
        weather: Weather,
        image_path: str = "",
        created_at: Optional[str] = None,
        is_hidden: bool = False,
        summary: str = ""
    ):
        self.id = diary_id
        self.date = date
        self.title = title
        self.content = content
        self.emotion_score = emotion_score
        self.emotion_label = emotion_label
        self.weather = weather
        self.image_path = image_path
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.is_hidden = is_hidden
        self.summary = summary

    def matches_filter(self, filter_value: str) -> bool:
        """일기가 필터 조건에 맞는지 확인."""
        if not filter_value or filter_value == "전체보기":
            return True

        # 날씨 필터 검사
        from domain.model.value_objects import WEATHER_LABEL_TO_EMOJI
        if filter_value in WEATHER_LABEL_TO_EMOJI:
            target_emoji = WEATHER_LABEL_TO_EMOJI[filter_value]
            # actual_weather에 콤마가 여러 개 들어갈 수 있으므로 split 처리
            emojis = [w.strip() for w in self.weather.actual_weather.split(",")]
            return target_emoji in emojis

        # 감정 필터 검사
        score = self.emotion_score.value
        if filter_value == "긍정 일기":
            return score > 0
        if filter_value == "중립 일기":
            return score == 0
        if filter_value == "부정 일기":
            return score < 0

        return True

    def __repr__(self):
        return f"Diary(id={self.id}, date={self.date}, title={self.title})"
