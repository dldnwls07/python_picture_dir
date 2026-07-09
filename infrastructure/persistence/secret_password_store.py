import os
from typing import Optional


class SecretPasswordStore:
    """비밀 일기장 전역 비밀번호를 평문 텍스트 파일 하나에 저장/조회하는 저장소."""

    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            filepath = os.path.join(data_dir, "password.txt")
        self._filepath = filepath

    def has_password(self) -> bool:
        """비밀번호가 이미 설정되어 있는지 확인한다."""
        if not os.path.exists(self._filepath):
            return False
        with open(self._filepath, "r", encoding="utf-8") as f:
            return bool(f.read().strip())

    def set_password(self, password: str) -> None:
        """비밀번호를 평문으로 저장한다 (최초 1회 설정)."""
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            f.write(password.strip())
