"""
FileManager — 파일(CSV) 입출력 관리 클래스
diary_data.csv 파일에 일기 데이터를 읽고 쓴다.
CSV 컬럼: id, date, title, content, score, weather, created_at
"""

import csv
import os
from datetime import datetime
from typing import Optional


class FileManager:
    """로컬 CSV 파일 기반의 일기 데이터 관리 클래스."""

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

    def __init__(self, filepath: str = None):
        """
        Args:
            filepath: CSV 파일 경로. 기본값은 프로젝트 루트의 data/diary_data.csv
        """
        if filepath is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "diary_data.csv")
        self._filepath = filepath

    @property
    def filepath(self) -> str:
        return self._filepath

    @property
    def image_dir(self) -> str:
        return os.path.join(os.path.dirname(self._filepath), "images")

    def check_and_create_file(self) -> bool:
        """CSV 파일 및 헤더 존재 여부를 확인하고, 없으면 생성한다.

        Returns:
            True: 파일이 이미 존재했음
            False: 새로 생성함
        """
        if os.path.exists(self._filepath):
            return True

        with open(self._filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.HEADERS)
            writer.writeheader()
        return False

    def _get_next_id(self) -> int:
        """다음 ID 값을 계산한다."""
        data = self.read_all_csv()
        if not data:
            return 1
        max_id = max(int(row.get("id", 0)) for row in data)
        return max_id + 1

    def _save_all_atomic(self, data_list: list) -> bool:
        """모든 데이터를 임시 파일에 먼저 쓰고 원본 파일과 교체하는 방식으로 안전하게 저장한다."""
        temp_filepath = self._filepath + ".tmp"
        try:
            # 데이터 디렉토리 존재 확인
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            
            # 임시 파일에 쓰기
            with open(temp_filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.HEADERS)
                writer.writeheader()
                writer.writerows(data_list)
            
            # 원본 파일과 교체 (atomic replace)
            if os.path.exists(temp_filepath):
                os.replace(temp_filepath, self._filepath)
                return True
            return False
        except Exception as e:
            # 실패 시 임시 파일 삭제
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
            print(f"Error saving data atomically: {e}")
            return False

    def _normalize_row(self, row: dict) -> dict:
        """확장된 CSV 스키마 기준으로 누락 필드를 빈 값으로 보정한다."""
        normalized = {header: "" for header in self.HEADERS}
        for k, v in row.items():
            if k in normalized:
                normalized[k] = v
        return normalized

    def save_diary_image(self, image, filename: Optional[str] = None) -> str:
        """PIL 이미지를 저장하고 절대 경로를 반환한다."""
        import uuid

        os.makedirs(self.image_dir, exist_ok=True)
        if filename is None:
            filename = f"diary_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}.png"

        full_path = os.path.join(self.image_dir, filename)
        image.save(full_path)
        return full_path

    def delete_diary_image(self, image_path: str) -> bool:
        """일기 이미지 파일을 삭제한다."""
        if not image_path:
            return True
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
            return True
        except Exception as e:
            print(f"Error deleting image {image_path}: {e}")
            return False

    def append_to_csv(self, data_dict: dict) -> bool:
        """새로운 일기 데이터를 CSV에 추가 기록한다.

        Args:
            data_dict: {
                "date": "2025-07-08",
                "title": "오늘의 일기",
                "content": "일기 본문...",
                "score": 5,
                "weather": "☀️"
            }

        Returns:
            success: 성공 여부
        """
        self.check_and_create_file()
        try:
            all_data = self.read_all_csv()
            next_id = 1
            if all_data:
                next_id = max(int(row.get("id", 0)) for row in all_data) + 1
            
            row = {
                "id": next_id,
                "date": data_dict.get("date", ""),
                "title": data_dict.get("title", ""),
                "content": data_dict.get("content", ""),
                "score": data_dict.get("score", 0),
                "emotion_label": data_dict.get("emotion_label", ""),
                "weather": data_dict.get("weather", ""),
                "actual_weather": data_dict.get("actual_weather", ""),
                "actual_weather_text": data_dict.get("actual_weather_text", ""),
                "weather_source": data_dict.get("weather_source", ""),
                "location_name": data_dict.get("location_name", ""),
                "image_path": data_dict.get("image_path", ""),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_hidden": data_dict.get("is_hidden", "False"),
                "password": data_dict.get("password", ""),
            }
            all_data.append(row)
            return self._save_all_atomic(all_data)
        except Exception as e:
            print(f"Error appending to CSV: {e}")
            return False

    def read_all_csv(self) -> list:
        """CSV 파일 전체를 읽어와 딕셔너리 리스트로 반환한다.

        Returns:
            data_list: [{id, date, title, content, score, weather, created_at}, ...]
        """
        self.check_and_create_file()
        data_list = []
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data_list.append(self._normalize_row(dict(row)))
        except Exception as e:
            print(f"Error reading CSV: {e}")
        return data_list

    def read_by_date_range(self, start: str, end: str) -> list:
        """특정 기간(start~end)의 일기 데이터만 필터링하여 반환한다.

        Args:
            start: 시작 날짜 ("YYYY-MM-DD")
            end: 종료 날짜 ("YYYY-MM-DD")

        Returns:
            filtered_list: 해당 기간의 일기 리스트
        """
        try:
            all_data = self.read_all_csv()
            filtered = []
            for row in all_data:
                date_str = row.get("date", "")
                if date_str and start <= date_str <= end:
                    filtered.append(row)
            return filtered
        except Exception as e:
            print(f"Error reading by date range: {e}")
            return []

    def delete_by_id(self, diary_id: int) -> bool:
        """특정 ID의 일기를 삭제한다.

        Args:
            diary_id: 삭제할 일기의 ID

        Returns:
            success: 삭제 성공 여부
        """
        try:
            all_data = self.read_all_csv()
            target_row = None
            new_data = []
            for row in all_data:
                if int(row.get("id", 0)) == diary_id:
                    target_row = row
                    continue
                new_data.append(row)
            if len(new_data) == len(all_data):
                return False  # 해당 ID가 없음

            if not self._save_all_atomic(new_data):
                return False

            if target_row:
                self.delete_diary_image(target_row.get("image_path", ""))
            return True
        except Exception as e:
            print(f"Error deleting entry {diary_id}: {e}")
            return False

    def update_by_id(self, diary_id: int, data_dict: dict) -> bool:
        """특정 ID의 일기를 수정한다.

        Args:
            diary_id: 수정할 일기의 ID
            data_dict: 수정할 데이터

        Returns:
            success: 수정 성공 여부
        """
        try:
            all_data = self.read_all_csv()
            found = False
            previous_image_path = ""
            for row in all_data:
                if int(row.get("id", 0)) == diary_id:
                    previous_image_path = row.get("image_path", "")
                    # id와 created_at은 변경하지 않음
                    for k, v in data_dict.items():
                        if k not in ["id", "created_at", "remove_image"]:
                            row[k] = v
                    found = True
                    break

            if not found:
                return False

            if not self._save_all_atomic(all_data):
                return False

            new_image_path = data_dict.get("image_path")
            remove_existing_image = data_dict.get("remove_image", False)
            if remove_existing_image and previous_image_path and previous_image_path != new_image_path:
                self.delete_diary_image(previous_image_path)
            elif new_image_path and previous_image_path and previous_image_path != new_image_path:
                self.delete_diary_image(previous_image_path)

            return True
        except Exception as e:
            print(f"Error updating entry {diary_id}: {e}")
            return False
