# 마인드웨더 확장 구현 계획서

요청 기능은 다음 3가지입니다.

1. 그림판 일기 기능
2. 현재 날씨/위치/감정을 사용자 입력으로 저장하는 기능
3. 카테고리에서 날씨 또는 감정을 선택해 해당 일기를 모아보는 기능

현재 코드베이스를 기준으로 보면, 세 기능 모두 뼈대나 일부 구현은 이미 들어가 있습니다. 따라서 이번 계획은 신규 설계 문서가 아니라, 현 상태를 기준으로 남은 구현과 정리 작업을 끝까지 완료하기 위한 실행 계획입니다.

## 현재 상태 요약

### 이미 들어가 있는 부분
- 그림판 탭, `tk.Canvas`, 색상 선택, 전체 지우기, 이미지 저장 경로 처리: [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- CSV에 `image_path` 저장 컬럼 반영: [manager/file_manager.py](/Users/woojin/Developer/dir_py/manager/file_manager.py)
- 날씨/감정 필터 드롭다운과 리스트 필터링 로직: [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- 현재 날씨/위치/감정 사용자 입력 UI와 저장 경로

### 현재 구현 진행 상황
- `Tk` GUI: 그림 일기, 필터, 현재 위치 날씨, 이미지 저장/교체/삭제 반영 완료
- `PyQt` GUI: 필터, 현재 위치 날씨, 그림 일기 탭/캔버스/저장 플로우 반영 완료
- 공통 필터 규칙 분리: [diary_categories.py](/Users/woojin/Developer/dir_py/diary_categories.py)
- `.env` 자동 로드 및 기상청 키 주입 경로 반영: [runtime_env.py](/Users/woojin/Developer/dir_py/runtime_env.py)
- 자동 테스트 추가:
  - [tests/test_diary_categories.py](/Users/woojin/Developer/dir_py/tests/test_diary_categories.py)
  - [tests/test_file_manager.py](/Users/woojin/Developer/dir_py/tests/test_file_manager.py)
  - [tests/test_runtime_and_weather.py](/Users/woojin/Developer/dir_py/tests/test_runtime_and_weather.py)
  - [tests/test_app_gui.py](/Users/woojin/Developer/dir_py/tests/test_app_gui.py)

### 아직 부족한 부분
- 실제 `KMA_SERVICE_KEY`로 기상청 라이브 응답을 검증하지 못함
- 실제 데스크톱 GUI 세션에서 Tk/Qt 상호작용을 아직 확인하지 못함
- 위치 조회는 기본적으로 IP 기반이라 정확도 한계가 남아 있음

## 현재 검증 상태

### 자동 검증 완료
- `python3 -m unittest discover -s tests -v`
- `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v`
- Qt 오프스크린 생성/탭/저장 플로우 검증
- 위치 기반 날씨 fallback 실네트워크 검증

### 아직 수동 검증이 필요한 항목
1. 실제 `KMA_SERVICE_KEY`를 `.env`에 넣고 기상청 응답 확인
2. 실제 데스크톱 환경에서 `python3 main.py --gui tk` 실행
3. 실제 데스크톱 환경에서 `python3 main.py --gui qt` 실행
4. 두 GUI에서 그림판 드로잉, 저장, 수정, 삭제 확인

### 권장 스모크 체크 명령
0. 전체 로컬 스모크 체크
   - `python3 smoke_check.py`
1. 날씨 provider만 단독 확인
   - `python3 main.py --check-weather`
   - `python3 main.py --check-weather --json`
2. Tk GUI 실행
   - `python3 main.py --gui tk`
3. Qt GUI 실행
   - `python3 main.py --gui qt`

## 구현 목표

### 1. 그림판 일기 기능을 실제 저장/조회 기준으로 안정화
목표는 “그릴 수 있다”가 아니라 “저장, 수정, 조회, 삭제까지 데이터가 일관되게 유지된다”입니다.

### 2. 현재 날씨/위치/감정을 수동 입력으로 단순화
자동 현재 위치/날씨 조회보다 사용자가 직접 위치, 현재 날씨, 오늘 감정을 선택하는 흐름이 현재 요구사항과 더 잘 맞습니다.

### 3. 카테고리 모아보기를 Tk/Qt 공통 기능으로 정리
현재 Tk 버전만 필터가 있고, PyQt GUI에는 동일 기능이 빠져 있습니다.

## 사용자 확인 필요 사항

### 1. 그림 저장 정책
수정 시 새 이미지를 저장하면 이전 이미지 파일 정리 정책이 필요합니다.
- 유지: 이력 보존은 되지만 파일 누적
- 교체: 저장공간 관리에 유리

기본 계획은 “새 이미지 저장 후 기존 파일 교체 정리”입니다.

## 작업 계획

### 1. 사용자 입력 메타데이터 기반 저장 흐름 정리
대상 파일:
- [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- [app_gui.py](/Users/woojin/Developer/dir_py/app_gui.py)
- [manager/file_manager.py](/Users/woojin/Developer/dir_py/manager/file_manager.py)

작업 내용:
- 위치 입력 필드 추가
- 현재 날씨 선택 콤보박스 추가
- 오늘 감정 선택 콤보박스 추가
- 감정 선택값을 저장 점수/표시 상태로 매핑
- 실제 날씨와 감정 날씨를 분리 저장

완료 기준:
- GUI에서 입력한 위치/현재 날씨/감정이 저장된다
- 저장된 값이 다시 열었을 때 정확히 복원된다

### 2. 그림판 일기 저장/조회 플로우 정리
대상 파일:
- [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- [manager/file_manager.py](/Users/woojin/Developer/dir_py/manager/file_manager.py)

작업 내용:
- 현재 `_is_canvas_modified()`의 단순 판정 로직 보강
- 캔버스 최초 배경 이미지와 실제 사용자 드로잉을 구분
- 수정 저장 시 새 그림이 있으면 `image_path` 교체
- 수정 저장 시 그림을 지운 경우 `image_path` 제거 여부 명시
- 삭제 시 연결된 이미지 파일 정리 여부 결정 및 구현
- 이미지 저장을 파일 매니저 책임으로 옮겨 UI와 저장 정책 분리

권장 구조:
- `FileManager.save_diary_image(...)`
- `FileManager.delete_diary_image(...)`
- `FileManager.update_by_id(...)` 안에서 이미지 경로 갱신 규칙 통일

완료 기준:
- 텍스트만 저장 가능
- 그림만 저장 가능
- 텍스트+그림 동시 저장 가능
- 기존 그림 수정/삭제 시 CSV와 실제 파일 상태가 일치

### 3. 카테고리 필터를 공통 기능으로 정리
대상 파일:
- [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- [app_gui.py](/Users/woojin/Developer/dir_py/app_gui.py)
- [ui/main_window.ui](/Users/woojin/Developer/dir_py/ui/main_window.ui)

작업 내용:
- 현재 Tk 필터 로직을 별도 헬퍼로 추출
- 날씨 카테고리와 감정 카테고리 정의를 상수화
- PyQt UI에도 동일 필터 컴포넌트 추가
- 필터 선택 시 목록 reload 및 선택 상태 초기화 규칙 정리

권장 카테고리:
- `전체보기`
- `☀️ 맑음`
- `⛅ 흐림`
- `🌧️ 비`
- `❄️ 눈`
- `긍정 일기`
- `부정 일기`
- `중립 일기`

완료 기준:
- Tk/Qt 모두 동일한 필터 체계를 사용
- 점수 0 처리 기준이 명확함
- 필터 후 목록/상세 선택 동작이 꼬이지 않음

### 4. 저장 데이터 스키마 명확화
대상 파일:
- [manager/file_manager.py](/Users/woojin/Developer/dir_py/manager/file_manager.py)
- [data/diary_data.csv](/Users/woojin/Developer/dir_py/data/diary_data.csv)

작업 내용:
- 현재 CSV 헤더를 기준 스키마로 문서화
- 실제 날씨 저장 필드 반영
  - `actual_weather`
  - `actual_weather_text`
  - `weather_source`
  - `location_name`
- 기존 레코드와의 하위 호환 처리
  - 누락 컬럼은 읽기 시 빈 값으로 정규화

완료 기준:
- 새 기능 때문에 CSV가 깨지지 않음
- 기존 저장 데이터도 계속 읽힘

### 5. UI 상태 메시지와 예외 처리 보강
대상 파일:
- [app_tkinter.py](/Users/woojin/Developer/dir_py/app_tkinter.py)
- [app_gui.py](/Users/woojin/Developer/dir_py/app_gui.py)

작업 내용:
- 현재 날씨 조회 중/성공/실패 메시지 분리
- 네트워크 실패 시 사용자에게 간단한 원인 표시
- 저장 실패 시 이미지 저장 실패와 CSV 저장 실패를 구분
- 필터 결과 0건일 때 빈 상태 메시지 표시

완료 기준:
- 실패가 발생해도 앱은 유지
- 사용자 입장에서 왜 비어 있는지, 왜 실패했는지 구분 가능

## 구현 순서

1. 수동 입력 메타데이터 흐름 정리
2. `FileManager`에 이미지 저장/삭제 책임 이관
3. `app_tkinter.py`의 그림판 저장 판정 및 수정 플로우 정리
4. 필터 로직을 공통화하고 `app_gui.py`/`main_window.ui`에 반영
5. 예외 처리 및 상태 메시지 보강
6. 수동 검증

## 검증 계획

### 기능 검증
1. 텍스트만 작성 후 저장
2. 그림만 작성 후 저장
3. 텍스트+그림 작성 후 저장
4. 기존 그림 일기 수정
5. 그림 제거 후 수정
6. 날씨 API 성공 시 현재 날씨 노출
7. 날씨 API 실패 시 기본값으로 복구
8. 날씨별 필터 정상 동작
9. 감정별 필터 정상 동작

### 회귀 검증
1. 기존 CSV 데이터가 그대로 열리는지 확인
2. 마인드맵 기능이 이미지 일기 추가 이후에도 동작하는지 확인
3. 월간 감정 통계가 기존처럼 동작하는지 확인

## 리스크

### 1. 기상청 API 의존성
서비스 키, 호출 제한, 응답 형식 변경에 영향을 받습니다.

### 2. 데스크톱 위치 정확도
IP 기반 위치는 실제 사용자 위치와 다를 수 있습니다. 지역 수동 선택 fallback이 필요할 수 있습니다.

### 3. 이미지 파일 누적
수정/삭제 정책이 느슨하면 `data/images` 아래에 고아 파일이 쌓입니다.

### 4. GUI 이중 구현 비용
Tk와 Qt를 둘 다 유지하면 동일 기능을 두 번 반영해야 합니다. 장기적으로는 하나를 기본 GUI로 정하는 것이 맞습니다.

## 권장 결정

현재 기준으로는 Tk 버전이 요청 기능을 더 많이 포함하고 있습니다. 따라서 우선순위는 아래가 맞습니다.

1. Tk 버전을 기능 기준본으로 완성
2. 기상청 API 연동과 이미지 저장 정합성 해결
3. 이후 PyQt 버전에 필터 기능만 이식

이 순서가 가장 적은 수정으로 요구사항을 충족합니다.
