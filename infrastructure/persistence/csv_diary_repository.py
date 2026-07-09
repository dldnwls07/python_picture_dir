import csv
import os
import uuid
from datetime import datetime
from typing import List, Optional
from domain.model.diary import Diary
from domain.model.value_objects import EmotionScore, Weather, EMOTION_LABEL_TO_SCORE
from domain.repository.diary_repository import DiaryRepository


class CSVDiaryRepository(DiaryRepository):
    """CSV 파일 기반의 일기 저장소 구현체."""

    HEADERS = [
        "id",
        "date",
        "title",
        "content",
        "score",
        "emotion_label",
        "weather",
        "actual_weather",
        "actual_weather_text",
        "weather_source",
        "location_name",
        "image_path",
        "created_at",
        "is_hidden",
        "password",
    ]

    def __init__(self, filepath: Optional[str] = None):
        """
        Args:
            filepath: CSV 파일 경로. 기본값은 프로젝트 루트의 data/diary_data.csv
        """
        if filepath is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "diary_data.csv")
        self._filepath = filepath

    @property
    def image_dir(self) -> str:
        return os.path.join(os.path.dirname(self._filepath), "images")

    def _check_and_create_file(self) -> bool:
        """CSV 파일 및 헤더 존재 여부를 확인하고, 없으면 생성한다."""
        if os.path.exists(self._filepath):
            return True

        with open(self._filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            writer.writeheader()
        return False

    def _read_all_rows(self) -> List[dict]:
        self._check_and_create_file()
        data_list = []
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 누락 필드 보정
                    normalized = {header: "" for header in self.HEADERS}
                    for k, v in row.items():
                        if k in normalized:
                            normalized[k] = v
                    data_list.append(normalized)
        except Exception as e:
            print(f"Error reading CSV: {e}")
        return data_list

    def _save_all_atomic(self, data_list: List[dict]) -> bool:
        temp_filepath = self._filepath + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(temp_filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()
                writer.writerows(data_list)
            
            if os.path.exists(temp_filepath):
                os.replace(temp_filepath, self._filepath)
                return True
            return False
        except Exception as e:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
            print(f"Error saving data atomically: {e}")
            return False

    def _row_to_entity(self, row: dict) -> Diary:
        score_val = None
        if row.get("score"):
            try:
                score_val = float(row["score"])
            except ValueError:
                pass
        
        if score_val is None:
            emotion_label = row.get("emotion_label", "")
            labels = [l.strip() for l in emotion_label.split(",") if l.strip()]
            if labels:
                scores = [EMOTION_LABEL_TO_SCORE.get(l, 0) for l in labels]
                score_val = sum(scores) / len(scores)
            else:
                score_val = 0.0

        weather_obj = Weather(
            emoji=row.get("weather", "⛅"),
            text=row.get("actual_weather_text", "알 수 없음"),
            source=row.get("weather_source", "fallback"),
            location=row.get("location_name", ""),
            actual_weather=row.get("actual_weather", ""),
            actual_weather_text=row.get("actual_weather_text", "")
        )

        return Diary(
            diary_id=int(row["id"]) if row.get("id") else None,
            date=row.get("date", ""),
            title=row.get("title", ""),
            content=row.get("content", ""),
            emotion_score=EmotionScore(score_val),
            emotion_label=row.get("emotion_label", ""),
            weather=weather_obj,
            image_path=row.get("image_path", ""),
            created_at=row.get("created_at", ""),
            is_hidden=row.get("is_hidden", "False") == "True",
            password=row.get("password", "")
        )

    def _entity_to_row(self, diary: Diary) -> dict:
        return {
            "id": str(diary.id) if diary.id is not None else "",
            "date": diary.date,
            "title": diary.title,
            "content": diary.content,
            "score": str(diary.emotion_score.value),
            "emotion_label": diary.emotion_label,
            "weather": diary.weather.emoji,
            "actual_weather": diary.weather.actual_weather,
            "actual_weather_text": diary.weather.actual_weather_text,
            "weather_source": diary.weather.source,
            "location_name": diary.weather.location,
            "image_path": diary.image_path,
            "created_at": diary.created_at,
            "is_hidden": str(diary.is_hidden),
            "password": diary.password,
        }

    def save(self, diary: Diary) -> bool:
        self._check_and_create_file()
        try:
            all_rows = self._read_all_rows()
            
            if diary.id is None:
                # 신규 일기 추가: 다음 ID 계산
                max_id = 0
                if all_rows:
                    max_id = max(int(row.get("id", 0)) for row in all_rows)
                diary.id = max_id + 1
                all_rows.append(self._entity_to_row(diary))
            else:
                # 기존 일기 업데이트
                found = False
                for i, row in enumerate(all_rows):
                    if int(row.get("id", 0)) == diary.id:
                        all_rows[i] = self._entity_to_row(diary)
                        found = True
                        break
                if not found:
                    return False

            return self._save_all_atomic(all_rows)
        except Exception as e:
            print(f"Error saving diary in CSV: {e}")
            return False

    def find_all(self) -> List[Diary]:
        rows = self._read_all_rows()
        return [self._row_to_entity(row) for row in rows]

    def find_by_id(self, diary_id: int) -> Optional[Diary]:
        rows = self._read_all_rows()
        for row in rows:
            if int(row.get("id", 0)) == diary_id:
                return self._row_to_entity(row)
        return None

    def find_by_date_range(self, start: str, end: str) -> List[Diary]:
        rows = self._read_all_rows()
        filtered = []
        for row in rows:
            date_str = row.get("date", "")
            if date_str and start <= date_str <= end:
                filtered.append(self._row_to_entity(row))
        return filtered

    def delete_by_id(self, diary_id: int) -> bool:
        try:
            all_rows = self._read_all_rows()
            target_row = None
            new_rows = []
            for row in all_rows:
                if int(row.get("id", 0)) == diary_id:
                    target_row = row
                    continue
                new_rows.append(row)
            
            if len(new_rows) == len(all_rows):
                return False  # 해당 ID 없음

            if not self._save_all_atomic(new_rows):
                return False

            if target_row and target_row.get("image_path"):
                self.delete_image(target_row["image_path"])
            return True
        except Exception as e:
            print(f"Error deleting entry {diary_id}: {e}")
            return False

    def save_image(self, image, filename: Optional[str] = None) -> str:
        os.makedirs(self.image_dir, exist_ok=True)
        if filename is None:
            filename = f"diary_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}.png"

        full_path = os.path.join(self.image_dir, filename)
        image.save(full_path)
        return full_path

    def delete_image(self, image_path: str) -> bool:
        if not image_path:
            return True
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
            return True
        except Exception as e:
            print(f"Error deleting image {image_path}: {e}")
            return False

    def read_all_csv(self) -> list:
        """Compatibility method for legacy tests."""
        return self._read_all_rows()
