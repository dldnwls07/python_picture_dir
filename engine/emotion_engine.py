"""
EmotionEngine — 감정 분석 엔진 클래스
감정 사전 대조를 통해 가중치 기반 감정 점수를 산출하고, 날씨를 매핑한다.
"""

from data.emotion_dict import get_all_emotion_words


class EmotionEngine:
    """가중치 기반 감정 분석 엔진."""

    # 날씨 매핑 테이블 (점수 범위 → 날씨)
    WEATHER_MAP = [
        (5, "☀️", "맑음"),       # score >= 5
        (2, "🌤️", "대체로 맑음"),  # 2 <= score < 5
        (0, "⛅", "보통"),        # 0 <= score < 2
        (-3, "☁️", "흐림"),       # -3 <= score < 0
        (-999, "🌧️", "비"),       # score < -3
    ]

    def __init__(self):
        self._emotion_dict = get_all_emotion_words()
        # 어근 길이 내림차순 정렬 (긴 것 우선 매칭 → "행복하다"가 "행복"보다 먼저)
        self._sorted_keys = sorted(self._emotion_dict.keys(),
                                   key=len, reverse=True)

    def _match_emotion(self, word: str):
        """단어를 감정 사전과 대조한다. 정확 매칭 → 부분 매칭 순서.

        Args:
            word: 검사할 단어

        Returns:
            (matched_key, score) 또는 None
        """
        # 1) 정확 매칭
        if word in self._emotion_dict:
            return word, self._emotion_dict[word]

        # 2) 부분 매칭: 단어 안에 감정 어근이 포함되어 있는지 확인
        #    예) "행복한" → "행복" 포함, "기뻤어" → "기뻤" 포함
        for key in self._sorted_keys:
            if len(key) >= 2 and key in word:
                return key, self._emotion_dict[key]

        return None

    def analyze_emotion(self, word_list: list) -> dict:
        """단어 리스트를 감정 사전과 대조하여 감정 분석 결과를 반환한다.

        Args:
            word_list: 전처리된 단어 리스트

        Returns:
            result: {
                "score": int,           # 총 감정 점수
                "weather_emoji": str,   # 날씨 이모지
                "weather_text": str,    # 날씨 텍스트
                "positive_count": int,  # 긍정 단어 수
                "negative_count": int,  # 부정 단어 수
                "matched_words": list,  # 매칭된 단어와 점수
            }
        """
        total_score = 0
        positive_count = 0
        negative_count = 0
        matched_words = []

        if not word_list or not isinstance(word_list, list):
            weather_emoji, weather_text = self._score_to_weather(0)
            return {
                "score": 0,
                "weather_emoji": weather_emoji,
                "weather_text": weather_text,
                "positive_count": 0,
                "negative_count": 0,
                "matched_words": [],
            }

        for word in word_list:
            if not word or not isinstance(word, str):
                continue
            match = self._match_emotion(word)
            if match:
                matched_key, score = match
                total_score += score
                matched_words.append((word, score))
                if score > 0:
                    positive_count += 1
                elif score < 0:
                    negative_count += 1

        weather_emoji, weather_text = self._score_to_weather(total_score)

        return {
            "score": total_score,
            "weather_emoji": weather_emoji,
            "weather_text": weather_text,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "matched_words": matched_words,
        }

    def _score_to_weather(self, score: int) -> tuple:
        """감정 점수를 날씨 이모지와 텍스트로 변환한다.

        Args:
            score: 감정 점수

        Returns:
            (emoji, text) 튜플
        """
        for threshold, emoji, text in self.WEATHER_MAP:
            if score >= threshold:
                return emoji, text
        # fallback
        return "🌧️", "비"

    def get_score_label(self, score: int) -> str:
        """점수에 대한 설명 라벨을 반환한다."""
        if score >= 5:
            return "매우 긍정적"
        elif score >= 2:
            return "긍정적"
        elif score >= 0:
            return "보통"
        elif score >= -3:
            return "부정적"
        else:
            return "매우 부정적"
