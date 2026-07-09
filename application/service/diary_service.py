from typing import List, Optional, Tuple
from domain.model.diary import Diary
from domain.model.value_objects import (
    EMOTION_LABEL_TO_SCORE,
    EMOTION_LABEL_TO_WEATHER,
    EmotionScore,
    Weather,
)
from domain.repository.diary_repository import DiaryRepository
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from infrastructure.external.ai_service import AIService
from engine.text_processor import TextProcessor
from engine.keyword_analyzer import KeywordAnalyzer


class DiaryService:
    """일기 관리 및 분석 비즈니스 시나리오를 지휘하는 응용 서비스."""

    def __init__(
        self,
        repository: Optional[DiaryRepository] = None,
        ai_service: Optional[AIService] = None,
    ):
        self._repository = repository or CSVDiaryRepository()
        self._ai_service = ai_service or AIService()
        self._text_processor = TextProcessor()
        self._keyword_analyzer = KeywordAnalyzer()

    def get_all_diaries(self, filter_value: str = "전체보기") -> List[Diary]:
        """모든 일기를 조회하며 필터 조건에 부합하는 일기 목록을 반환합니다."""
        diaries = self._repository.find_all()
        return [d for d in diaries if d.matches_filter(filter_value)]

    def get_diary_by_id(self, diary_id: int) -> Optional[Diary]:
        """ID로 특정 일기를 조회합니다."""
        return self._repository.find_by_id(diary_id)

    def get_diaries_by_date_range(self, start: str, end: str) -> List[Diary]:
        """특정 기간 동안의 일기를 조회합니다."""
        return self._repository.find_by_date_range(start, end)

    def delete_diary(self, diary_id: int) -> bool:
        """ID로 특정 일기를 삭제합니다."""
        return self._repository.delete_by_id(diary_id)

    def save_diary(
        self,
        diary_id: Optional[int],
        date: str,
        title: str,
        content: str,
        location_name: str,
        actual_weather1: str,
        actual_weather2: str,
        emotion1: str,
        emotion2: str,
        is_hidden: bool,
        password: str,
        image_data = None,  # PIL Image
        remove_image: bool = False,
    ) -> Tuple[bool, Optional[Diary]]:
        """일기를 등록하거나 수정합니다 (트랜잭션 복구 로직 강화)."""
        import hashlib
        new_saved_image_path = None
        image_to_delete_on_success = None

        try:
            # 1. 날씨 정보 처리
            def get_weather_emoji(val):
                return val.split(" ")[0] if val else ""
            def get_weather_text(val):
                return val.split(" ", 1)[1] if " " in val else val

            emoji1 = get_weather_emoji(actual_weather1)
            text1 = get_weather_text(actual_weather1)

            if actual_weather2 and actual_weather2 != "선택안함":
                emoji2 = get_weather_emoji(actual_weather2)
                text2 = get_weather_text(actual_weather2)
                actual_weather_emoji = f"{emoji1},{emoji2}"
                actual_weather_text = f"{text1},{text2}"
            else:
                actual_weather_emoji = emoji1
                actual_weather_text = text1

            # 2. 감정 및 감정 점수 산출
            if emotion2 and emotion2 != "선택안함":
                emotion_label = f"{emotion1},{emotion2}"
                score1 = EMOTION_LABEL_TO_SCORE.get(emotion1, 0)
                score2 = EMOTION_LABEL_TO_SCORE.get(emotion2, 0)
                score = int(round((score1 + score2) / 2.0))
                we1, wt1 = EMOTION_LABEL_TO_WEATHER.get(emotion1, ("⛅", "보통"))
                we2, wt2 = EMOTION_LABEL_TO_WEATHER.get(emotion2, ("⛅", "보통"))
                weather_emoji = f"{we1},{we2}"
                weather_text = f"{wt1},{wt2}"
            else:
                emotion_label = emotion1
                score = EMOTION_LABEL_TO_SCORE.get(emotion1, 0)
                weather_emoji, weather_text = EMOTION_LABEL_TO_WEATHER.get(emotion1, ("⛅", "보통"))

            weather_obj = Weather(
                emoji=weather_emoji,
                text=weather_text,
                source="manual",
                location=location_name,
                actual_weather=actual_weather_emoji,
                actual_weather_text=actual_weather_text
            )

            # 3. 비밀번호 해싱 처리 (신규 비밀번호인 경우만)
            password_to_save = password
            if password:
                is_already_hashed = (
                    len(password) == 64
                    and all(c in "0123456789abcdef" for c in password.lower())
                )
                if not is_already_hashed:
                    password_to_save = hashlib.sha256(
                        password.strip().encode("utf-8")
                    ).hexdigest()

            # 4. 이미지 처리 설계 변경 (즉시 삭제하지 않고 지연 처리)
            image_path = ""
            existing_image_path = ""
            created_at = None

            if diary_id is not None:
                existing_diary = self._repository.find_by_id(diary_id)
                if existing_diary:
                    existing_image_path = existing_diary.image_path
                    created_at = existing_diary.created_at
                    image_path = existing_image_path

            if image_data:
                # 새로운 이미지 임시 저장
                new_saved_image_path = self._repository.save_image(image_data)
                image_path = new_saved_image_path
                if existing_image_path:
                    # 기존 이미지는 CSV 저장 성공 시점에 삭제하도록 대기
                    image_to_delete_on_success = existing_image_path
            elif remove_image:
                image_path = ""
                if existing_image_path:
                    image_to_delete_on_success = existing_image_path

            # 5. 엔티티 인스턴스 생성
            diary = Diary(
                diary_id=diary_id,
                date=date,
                title=title,
                content=content,
                emotion_score=EmotionScore(score),
                emotion_label=emotion_label,
                weather=weather_obj,
                image_path=image_path,
                created_at=created_at,
                is_hidden=is_hidden,
                password=password_to_save
            )

            # 6. CSV 저장소 저장 시도
            success = self._repository.save(diary)

            if success:
                # CSV 저장 성공 시에만 기존 이미지 파일 삭제 진행
                if image_to_delete_on_success:
                    self._repository.delete_image(image_to_delete_on_success)
                return True, diary
            else:
                # CSV 저장 실패 시 새로 만든 이미지를 롤백(삭제)
                if new_saved_image_path:
                    try:
                        self._repository.delete_image(new_saved_image_path)
                    except Exception:
                        pass
                return False, None

        except Exception as e:
            print(f"Error saving diary in service: {e}")
            # 예외 발생 시 새로 생성된 임시 이미지 파일 물리 삭제 (트랜잭션 롤백)
            if new_saved_image_path:
                try:
                    self._repository.delete_image(new_saved_image_path)
                except Exception:
                    pass
            return False, None

    def analyze_keywords(self, diaries: List[Diary], wordcloud_width: int = 380, wordcloud_height: int = 280) -> Tuple[List[Tuple[str, int]], bytes]:
        """주어진 일기 목록의 텍스트에서 상위 키워드와 워드클라우드 바이트 데이터를 생성합니다."""
        if not diaries:
            return [], b""
        
        all_content = " ".join(d.content for d in diaries)
        words = self._text_processor.process(all_content)
        if not words:
            return [], b""

        top_keywords = self._keyword_analyzer.get_top_keywords(words, top_n=10)
        wc_bytes = self._keyword_analyzer.generate_wordcloud_bytes(words, width=wordcloud_width, height=wordcloud_height)
        return top_keywords, wc_bytes

    def get_word_list_from_diaries(self, diaries: List[Diary]) -> List[str]:
        """일기 목록으로부터 전처리된 단어 리스트를 추출합니다."""
        all_content = " ".join(d.content for d in diaries)
        return self._text_processor.process(all_content)

    def analyze_ai(
        self,
        date: str,
        content: str,
        location: str = "",
        weather: str = "",
        emotion: str = "",
        image_base64: str = ""
    ) -> dict:
        """AI 일기 감정 분석 및 공감을 수행합니다."""
        return self._ai_service.analyze_diary(
            date=date,
            content=content,
            location=location,
            weather=weather,
            emotion=emotion,
            image_base64=image_base64
        )
