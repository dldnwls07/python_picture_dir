"""
일기 카테고리/필터 공용 정의. (DDD 도메인 모델 위임 버전)
"""

from domain.model.value_objects import (
    ALL_FILTER_OPTIONS,
    DEFAULT_EMOTION,
    MANUAL_EMOTION_OPTIONS,
    MANUAL_WEATHER_OPTIONS,
)

SUMMARY_PREVIEW_LIMIT = 18


def truncate_summary(text: str, limit: int = SUMMARY_PREVIEW_LIMIT) -> str:
    """목록에 보여줄 요약 미리보기를 만든다. 길면 잘라서 말줄임표를 붙인다."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."
