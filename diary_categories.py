"""
일기 카테고리/필터 공용 정의. (DDD 도메인 모델 위임 버전)
"""

from typing import Dict
from domain.model.value_objects import (
    WEATHER_FILTERS as DOMAIN_WEATHER_FILTERS,
    EMOTION_FILTERS as DOMAIN_EMOTION_FILTERS,
    MANUAL_WEATHER_OPTIONS as DOMAIN_MANUAL_WEATHER_OPTIONS,
    MANUAL_EMOTION_OPTIONS as DOMAIN_MANUAL_EMOTION_OPTIONS,
    DEFAULT_EMOTION as DOMAIN_DEFAULT_EMOTION,
    EMOTION_LABEL_TO_SCORE as DOMAIN_EMOTION_LABEL_TO_SCORE,
    EMOTION_LABEL_TO_WEATHER as DOMAIN_EMOTION_LABEL_TO_WEATHER,
    ALL_FILTER_OPTIONS as DOMAIN_ALL_FILTER_OPTIONS,
    WEATHER_LABEL_TO_EMOJI as DOMAIN_WEATHER_LABEL_TO_EMOJI,
)

WEATHER_FILTERS = DOMAIN_WEATHER_FILTERS
EMOTION_FILTERS = DOMAIN_EMOTION_FILTERS
MANUAL_WEATHER_OPTIONS = DOMAIN_MANUAL_WEATHER_OPTIONS
MANUAL_EMOTION_OPTIONS = DOMAIN_MANUAL_EMOTION_OPTIONS
DEFAULT_EMOTION = DOMAIN_DEFAULT_EMOTION
EMOTION_LABEL_TO_SCORE = DOMAIN_EMOTION_LABEL_TO_SCORE
EMOTION_LABEL_TO_WEATHER = DOMAIN_EMOTION_LABEL_TO_WEATHER
ALL_FILTER_OPTIONS = DOMAIN_ALL_FILTER_OPTIONS
WEATHER_LABEL_TO_EMOJI = DOMAIN_WEATHER_LABEL_TO_EMOJI

def matches_filter(row: dict, filter_value: str) -> bool:
    """일기 row가 주어진 필터에 포함되는지 반환한다."""
    from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
    repo = CSVDiaryRepository()
    diary = repo._row_to_entity(row)
    return diary.matches_filter(filter_value)

def score_to_tier(score: float) -> str:
    """점수를 기반으로 감정 등급(A+ ~ F) 티어를 반환한다."""
    from domain.model.value_objects import EmotionScore
    return EmotionScore(score).tier
