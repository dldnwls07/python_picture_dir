"""
감정 일기장 — Emotion Diary
메인 엔트리포인트
"""

import argparse
import json
import os
import sys

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from runtime_env import configure_runtime

configure_runtime(PROJECT_ROOT)


def run_tk() -> None:
    from app_tkinter import AppGUI

    app = AppGUI(start_weather_thread=False)
    app.mainloop()


def run_qt() -> None:
    from PyQt5.QtWidgets import QApplication
    from app_gui import AppGUI

    qt_app = QApplication(sys.argv)
    window = AppGUI(start_weather_thread=False)
    window.show()
    qt_app.exec_()


def check_weather(as_json: bool = False) -> None:
    from engine.weather_engine import WeatherEngine

    weather = WeatherEngine().get_current_weather()
    if as_json:
        print(json.dumps(weather, ensure_ascii=False))
        return
    print("provider:", weather.get("source", ""))
    print("location:", weather.get("location", ""))
    print("weather:", f"{weather.get('emoji', '')} {weather.get('text', '')}".strip())
    if weather.get("error"):
        print("error:", weather["error"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gui",
        choices=("tk", "qt"),
        default=os.environ.get("EMOTION_DIARY_GUI", "tk"),
        help="실행할 GUI 백엔드 선택",
    )
    parser.add_argument(
        "--check-weather",
        action="store_true",
        help="GUI 실행 없이 현재 날씨 조회 결과만 출력",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="--check-weather 결과를 JSON으로 출력",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.check_weather:
        check_weather(as_json=args.json)
        return
    if args.gui == "qt":
        run_qt()
        return
    run_tk()


if __name__ == "__main__":
    main()
