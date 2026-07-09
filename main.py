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

    app = AppGUI()
    app.mainloop()


# QDialog(및 그 안의 QComboBox/QDateEdit 드롭다운 팝업)은 부모 위젯이 있어도 그 자체로 별도의
# 최상위 창(isWindow() == True)이라, MainWindow나 각 .ui 파일에 지정한 스타일시트가 자동으로
# 상속되지 않는다. 다이얼로그마다 개별적으로 스타일을 다시 지정하면 하나라도 빠뜨린 드롭다운은
# 배경/글자색이 OS 기본값으로 표시되어 다크 테마와 충돌하며 잘 안 보이게 된다. 이를 앱 전체에서
# 한 번에 해결하기 위해 QApplication 레벨(모든 최상위 창에 공통 적용됨)에 콤보박스/날짜 선택
# 팝업 등에 대한 공통 스타일을 지정한다.
QT_GLOBAL_STYLESHEET = """
QDialog {
    background-color: #1e1e2e;
}
QWidget {
    color: #f5f5f5;
}
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f5f5f5;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #45475a;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #f5f5f5;
    border: 1px solid #45475a;
    outline: 0;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QDateEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f5f5f5;
}
QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 20px;
    border-left: 1px solid #45475a;
}
QCalendarWidget QWidget {
    background-color: #1e1e2e;
    color: #f5f5f5;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #1e1e2e;
    color: #f5f5f5;
    outline: 0;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QCalendarWidget QToolButton {
    color: #f5f5f5;
    background-color: transparent;
    border-radius: 6px;
    padding: 4px 8px;
}
QCalendarWidget QToolButton:hover {
    background-color: #313244;
}
QCalendarWidget QSpinBox {
    background-color: #313244;
    color: #f5f5f5;
    border: 1px solid #45475a;
    border-radius: 4px;
}
QLineEdit, QTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f5f5f5;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #74c7ec;
}
"""


def run_qt() -> None:
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication
    from app_gui import AppGUI

    qt_app = QApplication(sys.argv)
    # 다크 테마에서 글꼴이 거칠게 보이는 문제 개선(7-9-1): 안티앨리어싱을 명시적으로 선호하도록 설정.
    default_font = QFont("Pretendard")
    default_font.setStyleStrategy(QFont.PreferAntialias)
    qt_app.setFont(default_font)
    # 드롭다운/날짜 팝업 등이 다이얼로그마다 스타일을 놓쳐 안 보이는 문제를 원천 차단(QApplication
    # 레벨은 모든 다이얼로그를 포함한 최상위 창에 공통 적용됨). 각 창의 개별 스타일시트가 더 우선
    # 적용되므로 기존 색상 커스터마이징과 충돌하지 않는다.
    qt_app.setStyleSheet(QT_GLOBAL_STYLESHEET)
    window = AppGUI()
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
