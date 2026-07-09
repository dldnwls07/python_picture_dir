> 코드 기준: `main`. `PLAN.md`에 남아있는 항목은 **7번(UI 대폭 개편)** 뿐입니다.
>
> **3번(위치 프리셋), 5번(필터링 함수), 6번(필터링 적용) 모두 구현 완료되어 이 파일에서 제거했습니다.**
> 구현 요약은 아래를 참고하세요.

## 구현 요약 (2026-07-09)

- **위치 프리셋(3번)**: `infrastructure/persistence/location_preset_store.py`의 `LocationPresetStore` —
  `data/location.txt`(`.gitignore` 등록됨)에 한 줄씩 저장, 최초 실행 시 기본값(학교/직장/집)으로 파일 생성.
  `DiaryService.get_location_presets()`로 조회, `save_diary()` 성공 시 새 위치를 자동으로 프리셋에 추가.
  일기 작성 폼의 위치 입력(`locationLineEdit`/`location_entry`)을 편집 가능한 콤보박스로 교체.
- **필터 함수(5번)**: `domain/model/value_objects.py`에 `DiaryFilter` 값 객체 추가
  (`category`/`location`/`title_keyword`/`content_keyword`/`summary_keyword`, 전부 AND 조합).
  `Diary.matches_filter(diary_filter)`가 새 시그니처로 교체됨(기존 문자열 카테고리 로직은
  `_matches_category()`로 분리 보존). 위치/제목/본문/요약 매칭은 단순 부분 문자열 검색(대소문자 무시).
  날짜 기간은 `DiaryFilter`에 넣지 않고 `DiaryService.get_all_diaries()`/`get_hidden_diaries()`가
  `date_from`/`date_to`를 별도 인자로 받아 교집합으로 추가 적용.
- **필터 적용(6번)**: 좌측 목록 패널에 "🔍 상세 필터" 접기/펼치기 버튼 + 위치 콤보박스 + 제목/본문/요약
  키워드 입력창 3개 + 기간 체크박스·날짜 2개를 추가(Qt/Tk 동일 구성). 값이 바뀔 때마다 실시간으로
  `_load_diary_list()`가 재조회됨. 키워드 분석 다이얼로그(`keyword_dialog.ui`/Tk 마인드맵 창)에도
  카테고리·위치 필터를 추가해서 같은 `DiaryFilter`/`get_all_diaries()`를 재사용하도록 통일함
  (기존 `get_diaries_by_date_range` 직접 호출은 키워드 분석에서는 제거하고, 월간 통계(Tk)에서만 그대로 사용).

**테스트**: `tests/test_diary_filter.py` 신규 추가(DiaryFilter AND 조합, LocationPresetStore). 전체
28개 중 26개 통과(나머지 2개는 이번 작업과 무관한 기존 cp949 콘솔 인코딩 이슈). 두 GUI 모두 필터
패널·위치 콤보박스·키워드 분석 필터를 직접 조작해 정상 동작을 확인함.

## 추가 구현 요약 (2026-07-09, 학점 필터링 + 필터 UI 통합)

CSV에는 이미 `emotion_tier`가 저장되고 있었으나(직접 확인해서 사실이 아님을 밝힘), 아래 4가지
실제 누락 사항을 확인하고 수정함.

- **목록에 학점 미표시**: `_load_diary_list()`가 각 항목에 `[티어]`를 표시하도록 수정(Qt: `f"{weather} {date_str} [{tier}]\n     {title}"`, Tk: `f" {weather}  {date_str}  [{tier}]  |  {title}"`).
- **필터에 학점 미반영**: `EMOTION_TIER_OPTIONS = ("전체", "A+", "A", "B", "C", "D", "F")` 추가(`domain/model/value_objects.py`),
  `DiaryFilter.tier` 필드 추가, `Diary.matches_filter()`가 티어 일치 여부를 검사하도록 수정.
- **카테고리 필터(날씨/감정)가 상세 필터 밖에 별도 노출되던 문제**: Qt의 `filterComboBox`, Tk의 `filter_combo`를
  더 이상 항상 보이는 위치에 두지 않고, 다른 필터들과 함께 하나의 접기/펼치기 영역(Qt: `filterToggle`/`filterContainer`,
  Tk: `advanced_filter_toggle`/`advanced_filter_frame`, 버튼 텍스트를 "🔍 필터"로 통일)에 통합함.
- **키워드 분석 다이얼로그가 필터 구성 함수를 재사용하지 않던 문제**: 필터 위젯 생성/`DiaryFilter` 구성 로직을
  공용 헬퍼로 추출해서 메인 목록과 키워드 분석 다이얼로그가 동일 코드를 공유하도록 리팩터링:
  - Qt: `_create_filter_widgets()`(위젯 dict 생성) / `_diary_filter_from_widgets()`(dict → `DiaryFilter`).
    `show_mindmap_window()`가 더 이상 `categoryFilterComboBox`/`locationFilterLineEdit`를 직접 만들지 않고
    이 헬퍼로 카테고리/학점/위치/제목·본문·요약 키워드 전체 세트를 노출.
  - Tk: `_create_filter_vars()`(StringVar dict 생성) / `_build_filter_widgets(parent, variables, register_location_combo=True)`
    (위젯 배치) / `_diary_filter_from_vars()`(dict → `DiaryFilter`). 마인드맵 창은
    `register_location_combo=False`로 호출해서, 다이얼로그가 닫힌 뒤 위치 프리셋 새로고침이 파괴된
    위젯을 건드리지 않도록 함.
  - 키워드 분석 필터 세트를 기존 카테고리+위치 2개에서 메인 목록과 동일한 전체 6개(카테고리/학점/위치/
    제목·본문·요약 키워드)로 확장(사용자가 "메인 목록과 동일한 전체 세트로 확장" 선택).

**테스트**: `tests/test_diary_filter.py`에 티어 필터 테스트 3건 추가(단일 매치, `전체`/빈 값이 전체 매치,
다른 조건과의 AND 조합). 전체 31개 중 29개 통과(나머지 2개는 여전히 무관한 cp949 이슈). 두 GUI 모두
헤드리스로 기동해 필터 패널 토글, 학점 콤보박스 옵션, 키워드 분석 다이얼로그의 확장된 필터 세트가
정상 동작함을 확인함.
