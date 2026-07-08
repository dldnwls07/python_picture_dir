"""
런타임 환경 설정 유틸리티.

GUI와 matplotlib/fontconfig가 제한된 환경에서도
프로젝트 내부 writable 경로를 사용하도록 맞춘다.
"""

import os


def load_dotenv(project_root: str) -> None:
    """프로젝트 루트의 .env 파일을 읽어 환경 변수로 반영한다."""
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except Exception:
        # .env 로딩 실패는 앱 구동을 막지 않는다.
        return


def configure_runtime(project_root: str) -> None:
    """프로젝트 실행에 필요한 환경 변수를 설정한다."""
    load_dotenv(project_root)

    cache_root = os.path.join(project_root, ".cache")
    mpl_cache_dir = os.path.join(cache_root, "matplotlib")
    fontconfig_cache_dir = os.path.join(cache_root, "fontconfig")

    os.makedirs(mpl_cache_dir, exist_ok=True)
    os.makedirs(fontconfig_cache_dir, exist_ok=True)

    os.environ.setdefault("MPLCONFIGDIR", mpl_cache_dir)
    os.environ.setdefault("XDG_CACHE_HOME", cache_root)
    os.environ.setdefault("FONTCONFIG_PATH", "/System/Library/Fonts")
    os.environ.setdefault("FC_CACHEDIR", fontconfig_cache_dir)
