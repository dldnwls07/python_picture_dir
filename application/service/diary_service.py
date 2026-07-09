from typing import Dict, List, Optional, Tuple
from domain.model.diary import Diary
from domain.model.value_objects import (
    EMOTION_LABEL_TO_SCORE,
    EMOTION_LABEL_TO_WEATHER,
    DiaryFilter,
    EmotionScore,
    Weather,
)
from domain.repository.diary_repository import DiaryRepository
from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
from infrastructure.persistence.secret_password_store import SecretPasswordStore
from infrastructure.persistence.location_preset_store import LocationPresetStore
from infrastructure.external.ai_service import AIService
from engine.text_processor import TextProcessor
from engine.keyword_analyzer import KeywordAnalyzer


class DiaryService:
    """일기 관리 및 분석 비즈니스 시나리오를 지휘하는 응용 서비스."""

    def __init__(
        self,
        repository: Optional[DiaryRepository] = None,
        ai_service: Optional[AIService] = None,
        password_store: Optional[SecretPasswordStore] = None,
        location_store: Optional[LocationPresetStore] = None,
    ):
        self._repository = repository or CSVDiaryRepository()
        self._ai_service = ai_service or AIService()
        self._password_store = password_store or SecretPasswordStore()
        self._location_store = location_store or LocationPresetStore()
        self._text_processor = TextProcessor()
        self._keyword_analyzer = KeywordAnalyzer()

    def _apply_date_range(self, diaries: List[Diary], date_from: str, date_to: str) -> List[Diary]:
        if not date_from and not date_to:
            return diaries
        return [
            d for d in diaries
            if (not date_from or d.date >= date_from) and (not date_to or d.date <= date_to)
        ]

    def get_all_diaries(
        self,
        diary_filter: Optional[DiaryFilter] = None,
        date_from: str = "",
        date_to: str = "",
    ) -> List[Diary]:
        """모든 일기를 조회하며 필터/기간 조건에 부합하는 일기 목록을 반환합니다 (비밀 일기 제외)."""
        f = diary_filter or DiaryFilter()
        diaries = self._repository.find_all()
        result = [d for d in diaries if not d.is_hidden and d.matches_filter(f)]
        return self._apply_date_range(result, date_from, date_to)

    def get_hidden_diaries(
        self,
        diary_filter: Optional[DiaryFilter] = None,
        date_from: str = "",
        date_to: str = "",
    ) -> List[Diary]:
        """비밀 일기장 모드 전용 조회 — 숨겨진 일기만 필터/기간 조건에 맞춰 반환합니다."""
        f = diary_filter or DiaryFilter()
        diaries = self._repository.find_all()
        result = [d for d in diaries if d.is_hidden and d.matches_filter(f)]
        return self._apply_date_range(result, date_from, date_to)

    def get_emotion_scores_by_date(self) -> Dict[str, float]:
        """날짜별 평균 감정 점수를 반환합니다(캘린더 히트맵용, 비밀 일기 제외)."""
        diaries = self.get_all_diaries()
        scores_by_date: Dict[str, List[float]] = {}
        for d in diaries:
            scores_by_date.setdefault(d.date, []).append(d.emotion_score.value)
        return {date: sum(values) / len(values) for date, values in scores_by_date.items()}

    def get_location_presets(self) -> List[str]:
        """위치 입력 콤보박스에 채울 프리셋 목록(기본값 + 사용자 추가분)을 반환합니다."""
        return self._location_store.get_all()

    def get_diary_by_id(self, diary_id: int) -> Optional[Diary]:
        """ID로 특정 일기를 조회합니다."""
        return self._repository.find_by_id(diary_id)

    def find_diary_for_date(self, date: str) -> Optional[Diary]:
        """해당 날짜의 일기를 하나 반환합니다(비밀 일기 포함, 캘린더 날짜 클릭 용도).

        같은 날짜에 여러 건이 있으면 가장 최근에 작성/수정된 것을 반환합니다.
        """
        diaries = [d for d in self._repository.find_all() if d.date == date]
        if not diaries:
            return None
        diaries.sort(key=lambda d: d.created_at, reverse=True)
        return diaries[0]

    def get_diaries_by_date_range(self, start: str, end: str) -> List[Diary]:
        """특정 기간 동안의 일기를 조회합니다 (비밀 일기 제외)."""
        diaries = self._repository.find_by_date_range(start, end)
        return [d for d in diaries if not d.is_hidden]

    def delete_diary(self, diary_id: int) -> bool:
        """ID로 특정 일기를 삭제합니다."""
        return self._repository.delete_by_id(diary_id)

    def has_secret_password(self) -> bool:
        """비밀 일기장 비밀번호가 이미 설정되어 있는지 확인합니다."""
        return self._password_store.has_password()

    def verify_secret_password(self, password: str) -> bool:
        """입력한 비밀번호가 비밀 일기장 비밀번호와 일치하는지 확인합니다."""
        return self._password_store.verify_password(password)

    def set_secret_password(self, password: str) -> None:
        """비밀 일기장 비밀번호를 최초 1회 설정합니다."""
        self._password_store.set_password(password)

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
        image_data = None,  # PIL Image
        remove_image: bool = False,
    ) -> Tuple[bool, Optional[Diary]]:
        """일기를 등록하거나 수정합니다 (트랜잭션 복구 로직 강화)."""
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

            # 3. 이미지 처리 설계 변경 (즉시 삭제하지 않고 지연 처리)
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

            # 4. AI 한 줄 요약 생성 (실패해도 저장은 계속 진행 — 빈 값으로 대체)
            try:
                summary = self.generate_summary(
                    date=date,
                    content=content,
                    location=location_name,
                    weather=actual_weather_text,
                    emotion=emotion_label,
                )
            except Exception as e:
                print(f"AI 요약 생성 실패, 빈 값으로 대체합니다: {e}")
                summary = ""

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
                summary=summary
            )

            # 6. CSV 저장소 저장 시도
            success = self._repository.save(diary)

            if success:
                # CSV 저장 성공 시에만 기존 이미지 파일 삭제 진행
                if image_to_delete_on_success:
                    self._repository.delete_image(image_to_delete_on_success)
                if location_name:
                    self._location_store.add(location_name)
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

    def update_summary(self, diary_id: int, summary: str) -> bool:
        """사용자가 수정한 1줄 요약을 기존 일기에 반영합니다."""
        diary = self._repository.find_by_id(diary_id)
        if not diary:
            return False
        diary.summary = summary
        return self._repository.save(diary)

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

    def generate_summary(
        self,
        date: str,
        content: str,
        location: str = "",
        weather: str = "",
        emotion: str = "",
    ) -> str:
        """AI로 일기 본문의 1줄 요약을 생성합니다."""
        return self._ai_service.summarize(
            date=date,
            content=content,
            location=location,
            weather=weather,
            emotion=emotion,
        )

    def analyze_empathy(
        self,
        date: str,
        content: str,
        location: str = "",
        weather: str = "",
        emotion: str = "",
        image_base64: str = ""
    ) -> dict:
        """AI 공감 멘트와 그림 분석을 수행합니다."""
        return self._ai_service.analyze_empathy(
            date=date,
            content=content,
            location=location,
            weather=weather,
            emotion=emotion,
            image_base64=image_base64
        )
