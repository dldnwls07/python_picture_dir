from abc import ABC, abstractmethod
from typing import List, Optional
from domain.model.diary import Diary

class DiaryRepository(ABC):
    """일기 저장소 추상 인터페이스 (DIP용)"""

    @abstractmethod
    def save(self, diary: Diary) -> bool:
        """새로운 일기를 추가하거나 기존 일기를 업데이트합니다."""
        pass

    @abstractmethod
    def find_all(self) -> List[Diary]:
        """모든 일기를 조회합니다."""
        pass

    @abstractmethod
    def find_by_id(self, diary_id: int) -> Optional[Diary]:
        """ID로 특정 일기를 조회합니다."""
        pass

    @abstractmethod
    def find_by_date_range(self, start: str, end: str) -> List[Diary]:
        """특정 기간 동안의 일기를 조회합니다."""
        pass

    @abstractmethod
    def delete_by_id(self, diary_id: int) -> bool:
        """ID로 특정 일기를 삭제합니다."""
        pass

    @abstractmethod
    def save_image(self, image, filename: Optional[str] = None) -> str:
        """일기 이미지를 저장하고 저장된 절대 경로를 반환합니다."""
        pass

    @abstractmethod
    def delete_image(self, image_path: str) -> bool:
        """일기 이미지를 삭제합니다."""
        pass
