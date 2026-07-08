"""
로컬 실행 전 스모크 체크 스크립트.

이 스크립트는 다음을 빠르게 점검한다.
1. .env / 환경 변수 로딩
2. 현재 날씨 조회 경로
3. Tk 모듈 import 가능 여부
4. Qt 오프스크린 GUI 생성 가능 여부
5. 기본 테스트 스위트 실행
"""

import json
import os
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_weather() -> int:
    print_section("Weather")
    cmd = [sys.executable, "main.py", "--check-weather", "--json"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:", result.stderr.strip())
    return result.returncode


def check_tk_import() -> int:
    print_section("Tk Import")
    cmd = [sys.executable, "-c", "import tkinter; print('tk-ok')"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:", result.stderr.strip())
    return result.returncode


def check_qt_offscreen() -> int:
    print_section("Qt Offscreen")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = (
        "from PyQt5.QtWidgets import QApplication; "
        "from app_gui import AppGUI; "
        "app = QApplication([]); "
        "win = AppGUI(start_weather_thread=False); "
        "print('qt-offscreen-ok', win.editorTabs.count())"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:", result.stderr.strip())
    return result.returncode


def run_tests() -> int:
    print_section("Tests")
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:", result.stderr.strip())
    return result.returncode


def main() -> int:
    summary = {
        "weather": check_weather(),
        "tk_import": check_tk_import(),
        "qt_offscreen": check_qt_offscreen(),
        "tests": run_tests(),
    }
    print_section("Summary")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(code == 0 for code in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
