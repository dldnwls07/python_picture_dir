from datetime import datetime
from typing import Optional
from domain.model.value_objects import DiaryFilter, EmotionScore, Weather

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

    def matches_filter(self, diary_filter: DiaryFilter) -> bool:
        """일기가 다중 조건 필터(DiaryFilter)에 모두 부합하는지 확인한다 (AND 조합)."""
        if not self._matches_category(diary_filter.category):
            return False
        if diary_filter.tier and self.emotion_score.tier != diary_filter.tier:
            return False
        if diary_filter.location and diary_filter.location.lower() not in self.weather.location.lower():
            return False
        if diary_filter.title_keyword and diary_filter.title_keyword.lower() not in self.title.lower():
            return False
        if diary_filter.content_keyword and diary_filter.content_keyword.lower() not in self.content.lower():
            return False
        if diary_filter.summary_keyword and diary_filter.summary_keyword.lower() not in (self.summary or "").lower():
            return False
        return True

    def _matches_category(self, category: str) -> bool:
        """기존 filterComboBox 카테고리(날씨 이모지 라벨 / 긍정·중립·부정 / 전체보기) 조건을 검사한다."""
        if not category or category == "전체보기":
            return True

        # 날씨 필터 검사
        from domain.model.value_objects import WEATHER_LABEL_TO_EMOJI
        if category in WEATHER_LABEL_TO_EMOJI:
            return self.weather.actual_weather.strip() == WEATHER_LABEL_TO_EMOJI[category]

        # 감정 필터 검사
        score = self.emotion_score.value
        if category == "긍정 일기":
            return score > 0
        if category == "중립 일기":
            return score == 0
        if category == "부정 일기":
            return score < 0

        return True

    def __repr__(self):
        return f"Diary(id={self.id}, date={self.date}, title={self.title})"
