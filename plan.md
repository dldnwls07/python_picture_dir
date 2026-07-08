
PM / 백엔드

프로젝트 일정 관리, 감정 분석 로직 및 단어 빈도수 추출 로직 구현



프론트엔드

GUI 화면 설계 및 구현 (Tkinter 또는 PyQt 활용), 이벤트 연동


데이터 관리

긍정/부정 감정 사전(데이터 딕셔너리) 구축, 파일(CSV/TXT) 입출력 관리

프로젝트 설명
사용자가 작성한 일기 텍스트를 기반으로 하루의 감정 상태를 분석하여 날씨 이모티콘(☀️, 🌧️, ☁️ 등)으로 시각화하고, 주간/월간 단위로 자주 사용한 단어를 추출하여 마인드 맵 형태로 제공하는 데스크톱 GUI 일기장 프로그램입니다.

필요기능

일기 작성 및 관리: 날짜별 일기 작성, 수정, 읽기, 저장 기능 (로컬 CSV 또는 TXT 파일 활용)

감정 분석 엔진: 내장된 긍정/부정 단어 사전을 바탕으로 일기 본문의 단어를 대조하여 감정 점수 산출

감정 시각화: 산출된 감정 점수에 따라 오늘의 감정 날씨(이모티콘 또는 이미지)를 화면에 출력

키워드 추출 (마인드맵): 주간/월간 저장된 일기 데이터를 모아 형태소/단어 단위로 분리한 뒤, 가장 많이 쓰인 단어 순위를 제공 (collections.Counter 활용)

기대효과

사용자 측면: 자신의 최근 관심사와 스트레스 원인을 시각적으로 확인하고 객관적인 감정 상태를 돌아보며 멘탈 케어에 도움을 받을 수 있습니다.

개발 측면: 외부 통신(네트워크/API) 없이 파이썬 내장 라이브러리만으로 문자열 처리와 데이터 분석의 기초를 탄탄히 다지고, 안정적으로 완성도 높은 데스크톱 애플리케이션을 개발할 수 있습니다.

관련(유사) 기술 & 시스템 현황
기존 감정 분석 일기장(예: 세줄일기, 무다 등)은 대부분 모바일 기반이거나 복잡한 AI 클라우드 API를 요구합니다. 본 프로젝트는 무거운 딥러닝 모델 대신 직관적인 '단어 사전 매칭 방식'과 '빈도수 분석'을 사용하여 가볍고 빠르게 동작하며, 오프라인 환경에서도 개인정보 유출 걱정 없이 안전하게 사용할 수 있다는 차별점을 가집니다.

2. 시스템 아키텍처 및 클래스 API 명세서

본 프로젝트는 파이썬 내장 라이브러리(Tkinter, csv, collections 등)를 효율적으로 활용하기 위해 객체 지향 프로그래밍(OOP) 기반의 클래스 구조로 설계합니다.

2.1. 전체 클래스 API 명세서 (Class Structure)

클래스명

역할

주요 사용 모듈

AppGUI

윈도우 창 생성, 위젯 배치, 사용자 이벤트(클릭 등) 처리

tkinter 또는 PyQt5

TextProcessor

작성된 일기의 특수문자 제거, 공백 분리 등 데이터 전처리

re, string

EmotionEngine

긍정/부정 사전 대조, 감정 점수 산출 로직

dict, list

FileManager

일기 데이터 로컬 파일(CSV) 입출력 관리

csv, os

KeywordAnalyzer

특정 기간 데이터의 단어 빈도수 추출

collections.Counter

2.2. GUI API 명세서 (AppGUI 클래스)

프론트엔드 화면과 사용자의 상호작용을 담당하는 명세입니다.

함수명 (Method)

역할

이벤트 트리거 / 파라미터

반환값 (Response)

init_ui()

메인 화면 렌더링 및 위젯(텍스트박스, 버튼 등) 초기화

프로그램 실행 시

None

on_save_clicked()

'저장' 버튼 클릭 시 일기 데이터를 백엔드로 전달

'저장' 버튼 Click Event

None

update_weather_icon(score)

계산된 감정 점수(score)에 따라 날씨 아이콘 갱신

score (Integer)

None (UI Update)

show_mindmap_window()

'주간 마인드맵' 버튼 클릭 시 팝업 창 생성 및 렌더링

'마인드맵' 버튼 Click Event

None (Window Open)

display_alert(msg)

안내 사항이나 예외 발생 시 메시지 팝업 출력

msg (String)

None (MessageBox)

2.3. 데이터 전처리 API 명세서 (TextProcessor 클래스)

문자열을 분석 가능한 형태로 가공하는 명세입니다.

함수명 (Method)

역할

입력 파라미터

반환값 (Response)

clean_text(raw_text)

문장부호, 특수기호 제거 및 소문자 변환

raw_text (String)

cleaned_text (String)

tokenize(cleaned_text)

텍스트를 공백 기준으로 분리하여 토큰화(리스트화)

cleaned_text (String)

word_list (List[String])

remove_stopwords(word_list)

'나', '오늘', '너무' 등 분석에 불필요한 불용어 제거

word_list (List[String])

filtered_words (List[String])

2.4. 파일 처리 API 명세서 (FileManager 클래스)

데이터베이스를 대신하여 로컬 파일(CSV)에 데이터를 읽고 쓰는 명세입니다.

함수명 (Method)

역할

입력 파라미터

반환값 (Response)

check_and_create_file()

구동 시 diary_data.csv 파일 및 헤더 존재 여부 확인 후 생성

없음

Boolean (파일 유무)

append_to_csv(data_dict)

새로운 일기(날짜, 내용, 점수, 날씨)를 CSV에 추가 기록

data_dict (Dictionary)

success (Boolean)

read_all_csv()

CSV 파일 전체를 읽어와 딕셔너리 리스트로 반환

없음

data_list (List[Dictionary])

read_by_date_range(start, end)

특정 기간(start~end)의 일기 데이터만 필터링하여 반환

start (String), end (String)

filtered_list (List[Dict])

3. 데이터 파이프라인 구조 (Data Pipeline)

데이터가 사용자로부터 입력되어 로컬 파일에 저장되고, 다시 분석되어 시각화되기까지의 전체 흐름도입니다.

[Phase 1: 일기 저장 및 감정 분석 파이프라인]

[사용자 입력]: AppGUI에서 날짜를 선택하고 일기를 작성한 후 on_save_clicked() 이벤트 발생.

[데이터 전처리]: TextProcessor.clean_text() ➡️ tokenize()를 순차적으로 실행하여 정제된 단어 리스트(word_list) 생성.

[감정 스코어링]: EmotionEngine이 정제된 단어 리스트를 내부의 '긍정/부정 사전'과 대조하여 최종 감정 점수(Emotion Score) 산출.

[날씨 매칭]: 점수에 따라 날씨 속성(☀️/☁️/🌧️) 부여.

[파일 파이프라인 - 쓰기]: FileManager.append_to_csv() 호출. 메모리에 있는 데이터를 diary_data.csv 파일의 제일 마지막 줄에 Append(추가) 모드로 I/O 처리.

[GUI 업데이트]: AppGUI.update_weather_icon()을 호출하여 화면 상단의 날씨 아이콘 즉시 갱신.

[Phase 2: 키워드 분석 마인드맵 파이프라인 (조회)]

[분석 요청]: 사용자가 GUI에서 '주간 마인드맵 보기'를 클릭하여 show_mindmap_window() 호출.

[파일 파이프라인 - 읽기]: FileManager.read_by_date_range() 호출. diary_data.csv를 읽기(Read) 모드로 열어 최근 N일간의 Row 데이터만 필터링하여 메모리로 로드.

[데이터 병합 및 전처리]: 로드된 일기 데이터의 content 컬럼만 하나의 긴 문자열로 병합한 후, TextProcessor.remove_stopwords()를 거쳐 의미 없는 조사/부사 제거.

[빈도수 계산]: KeywordAnalyzer가 파이썬 내장 collections.Counter 모듈을 사용하여 각 단어별 등장 횟수 집계 및 정렬(Sort).

[결과 시각화]: 추출된 상위 5~10개 [(단어, 횟수), ...] 데이터를 GUI 팝업 창에 크기별 텍스트 혹은 순위 표로 렌더링.