"""
TextProcessor — 텍스트 전처리 클래스
일기 본문의 특수문자 제거, 토큰화, 불용어 제거를 수행한다.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.stopwords import get_stopwords


class TextProcessor:
    """일기 텍스트를 분석 가능한 형태로 전처리하는 클래스."""

    def __init__(self):
        self._stopwords = get_stopwords()

    def clean_text(self, raw_text: str) -> str:
        """문장부호, 특수기호 제거. 한글/영문/숫자/공백만 남긴다.

        Args:
            raw_text: 원본 일기 텍스트

        Returns:
            cleaned_text: 정제된 텍스트
        """
        if not raw_text or not isinstance(raw_text, str):
            return ""
        # 한글, 영문, 숫자, 공백만 남기기
        cleaned = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", raw_text)
        # 연속 공백 제거
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # 영문은 소문자로 변환
        cleaned = cleaned.lower()
        return cleaned

    def tokenize(self, cleaned_text: str) -> list:
        """텍스트를 공백 기준으로 분리하여 토큰 리스트를 반환한다.

        Args:
            cleaned_text: 정제된 텍스트

        Returns:
            word_list: 단어 리스트
        """
        if not cleaned_text or not isinstance(cleaned_text, str):
            return []
        return cleaned_text.split()

    def remove_stopwords(self, word_list: list) -> list:
        """분석에 불필요한 불용어를 제거한다.

        Args:
            word_list: 단어 리스트

        Returns:
            filtered_words: 불용어가 제거된 단어 리스트
        """
        if not word_list or not isinstance(word_list, list):
            return []
        return [w for w in word_list if w and isinstance(w, str) and w not in self._stopwords and len(w) > 1]

    def process(self, raw_text: str) -> list:
        """전처리 파이프라인을 한번에 실행한다.
        clean_text → tokenize → remove_stopwords

        Args:
            raw_text: 원본 텍스트

        Returns:
            filtered_words: 전처리 완료된 단어 리스트
        """
        if not raw_text or not isinstance(raw_text, str):
            return []
        cleaned = self.clean_text(raw_text)
        tokens = self.tokenize(cleaned)
        filtered = self.remove_stopwords(tokens)
        return filtered
