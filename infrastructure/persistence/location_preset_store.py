import os
from typing import List, Optional

DEFAULT_PRESETS = ["학교", "직장", "집"]


class LocationPresetStore:
    """사용자가 추가한 위치 프리셋을 텍스트 파일(한 줄에 하나)로 저장/조회하는 저장소."""

    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "location.txt")
        self._filepath = filepath
        self._ensure_default_file()

    def _ensure_default_file(self) -> None:
        if os.path.exists(self._filepath):
            return
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(DEFAULT_PRESETS) + "\n")

    def get_all(self) -> List[str]:
        """기본 프리셋 + 사용자가 추가한 값을 순서대로, 중복 없이 반환한다."""
        self._ensure_default_file()
        with open(self._filepath, "r", encoding="utf-8") as f:
            saved = [line.strip() for line in f if line.strip()]

        result = []
        for name in DEFAULT_PRESETS + saved:
            if name not in result:
                result.append(name)
        return result

    def add(self, name: str) -> None:
        """새 위치 이름을 프리셋에 추가한다 (이미 있으면 아무 것도 하지 않음)."""
        name = (name or "").strip()
        if not name or name in self.get_all():
            return
        with open(self._filepath, "a", encoding="utf-8") as f:
            f.write(name + "\n")
