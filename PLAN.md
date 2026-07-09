> 코드 기준: `main`. 아래 각 항목에 원래 내용은 그대로 두고,
> 현재 코드와 대조해서 확인한 사실 / 애매한 부분 / 의존 관계를 "검토" 항목으로 덧붙였습니다.
>
> **1~10번 항목 모두 구현 완료되어 `NEXT_PLAN.md`에서 정리(삭제)했습니다.** 번호는 원래 목록과
> 헷갈리지 않도록 그대로 유지합니다. 구현된 내용 요약:
> - **1번(AI공감 자동화)**: `AIHelper`가 `summarize_diary()`(요약 전용 호출)와 `analyze_empathy()`(공감+그림분석 호출)로 분리됨. CSV에 `emotion_tier`, `summary` 컬럼 추가. 저장 버튼 클릭 시 백그라운드 스레드(`SaveWorker`/Tk의 `threading.Thread`)에서 저장→요약 대기→CSV 기록→공감분석 순으로 진행되며, 같은 모달 다이얼로그 안에서 `일기 저장 중...` → `AI가 조언 중...` → 결과 3종 표시로 상태가 전환됨. 1줄 요약은 다이얼로그 내에서 수정 후 "확인"으로 커밋 가능.
> - **2번(비밀번호 저장/목록 제외)**: `password` CSV 컬럼 제거, 전역 비밀번호를 `data/password.txt`에 평문 저장(`SecretPasswordStore`, `.gitignore` 등록됨), 숨겨진 일기는 `DiaryService.get_all_diaries`/`get_diaries_by_date_range`에서 완전히 제외되어 목록·키워드 분석 어디에도 노출되지 않음.
> - **3번(위치 프리셋)**: `LocationPresetStore`(`data/location.txt`, 기본값 학교/직장/집)로 위치 입력을 편집 가능한 콤보박스로 전환, 새 위치는 저장 시 자동으로 프리셋에 편입.
> - **4번(일기 찢기 연출 + 비밀 일기장 UI)**: `SecretPasswordStore.verify_password()`/`DiaryService.verify_secret_password()`/`get_hidden_diaries()` 추가. "🔒 비밀일기 찾기" 버튼 → 매번 비밀번호 재확인 → 통과 시 숨겨진 일기만 보이는 읽기 전용 모드로 전환(저장은 막고 삭제는 허용). "🚪 나가기"로 일반 모드 복귀. 저장 시 지그재그 찢기 연출(Qt: `QPropertyAnimation`/`QParallelAnimationGroup`, Tk: 이모지 대체 연출) 재생. 모드 중에는 배경색이 `QVariantAnimation`(Qt)/`after()` 루프(Tk)로 천천히 왕복하는 색상 연출 적용. 이미 제작되어 있음.
> - **5번(필터링 함수)**: `DiaryFilter` 값 객체(`domain/model/value_objects.py`) 도입 — 카테고리/학점/위치/제목·본문·요약 키워드를 AND 조합으로 검사(학점은 2026-07-09 추가). 날짜 기간은 별도 파라미터로 취급.
> - **6번(필터링 적용)**: 좌측 목록에 카테고리/학점/위치/키워드 3종/기간을 모두 담은 단일 "🔍 필터" 접기/펼치기 영역 추가(2026-07-09에 카테고리를 상세 필터 밖 별도 위치에서 안으로 통합), 키워드 분석 다이얼로그도 같은 전체 필터 세트를 공유하도록 확장 — 두 화면 모두 같은 `DiaryFilter`/`get_all_diaries()`와 공용 필터 위젯 생성 헬퍼(Qt: `_create_filter_widgets`/`_diary_filter_from_widgets`, Tk: `_create_filter_vars`/`_build_filter_widgets`/`_diary_filter_from_vars`)를 공유.
> - **7번(UI 대폭 개편)**: 좌측 목록·필터 패널은 항상 고정 표시되는 내비게이션으로 유지하고, 우측 `rightPanel`을 캘린더(MAIN)/일기 편집 두 페이지짜리 스택(Qt: `QStackedWidget`, Tk: `pack()`/`pack_forget()` 전환)으로 재구성. 캘린더는 감정 점수 히트맵(`EmotionCalendarWidget`/`EmotionCalendarFrame`, `DiaryService.get_emotion_scores_by_date()`)을 보여주는 앱의 첫 화면이며, 빈 날짜 클릭 시 새 일기 작성, 기존 일기가 있는 날짜 클릭 시 목록 선택과 동일하게 편집 페이지로 전환(비밀 일기는 선택 차단). 저장/삭제/키워드 분석 버튼은 편집 페이지 전용, "새 일기" 버튼은 캘린더 페이지 전용으로 재배치. 비밀 일기장 버튼과 캘린더 복귀 버튼은 좌측 내비게이션으로 이동. 날씨 콤보박스는 하나로 통합(하루 1개만 선택). QSS도 폰트(Pretendard/안티앨리어싱)·버튼 색상 팔레트(메인/서브/경고)·캘린더 셀 디테일을 정리.
> - **8번(그래프 그리기)**: 캘린더 히트맵에 8-3의 정밀한 다크테마(Qt)/라이트테마(Tk) 4단계 색상 팔레트(무데이터/중립/긍정 그라데이션/부정 그라데이션) 적용, 날짜 셀 텍스트는 배경 명도에 따라 자동으로 밝은/어두운 색을 선택. Tk 캘린더(`EmotionCalendarFrame`)는 `tk.Label` 그리드에서 단일 `tk.Canvas` 렌더링으로 재구현(8-4). 양쪽 GUI 모두 캘린더 위에 한 주(행) 단위로 감정 점수를 잇는 미니 선그래프를 겹쳐 그림(8-2, Qt는 `QTableView` 위 투명 오버레이 위젯, Tk는 같은 Canvas에 `create_line`, 축 고정 -5~5, 데이터 공백은 끊어서 표현). 캘린더 페이지에 "📈 감정 그래프" 버튼을 추가해 시작~종료일을 고르는 매크로 뷰 팝업(8-5, `engine/trend_chart.py`+`DiaryService.generate_trend_chart()`로 Qt는 PNG 이미지, Tk는 `FigureCanvasTkAgg` 직접 임베드)을 엶. `DiaryService.get_emotion_scores_by_date()`에 `date_from`/`date_to` 옵션 추가.
> - **9번(해시태그)**: 검토에서 남겨뒀던 입력 방식은 (c) 혼합 방식으로 확정 — `engine/keyword_analyzer.py`의 형태소 분석 결과에서 해시태그 후보를 자동 제안하고, 사용자가 제안 목록에서 선택/직접 `#태그` 입력으로 수동 추가·삭제할 수 있게 함. CSV 스키마에 `tags`(콤마 구분 문자열) 컬럼 추가, `_row_to_entity`/`_entity_to_row`와 레거시 정규화 로직도 함께 반영. `DiaryFilter`에 `tag` 조건을 추가해 기존 필터링 구조(5·6번)에 자연스럽게 편입시켰고, 일기 목록에는 태그 칩을 표시해 클릭하면 해당 태그로 필터링되도록 함.
> - **10번(일기장 안에서의 이점 제공)**: 검토에서 갈렸던 방향은 (a) 연속 작성일수(스트릭) 표시로 확정 — CSV의 `date`를 기준으로 스트릭을 계산하며, 비밀 일기도 스트릭 판정에는 포함(작성 자체가 목적이므로). `SecretPasswordStore`/`LocationPresetStore`와 같은 패턴의 `data/achievements.json` 저장소를 추가해 스트릭 최고 기록과 누적 작성일수를 영속화하고, 배지(예: 7일/30일/100일 연속 작성)를 캘린더 페이지 상단에 표시.
>
> 아래에는 남은 검토 항목이 없습니다 — 모든 항목이 구현 완료 상태입니다.

---

## 진행 순서 제안 (참고용)

1. ~~1~10번~~ — 구현 완료.
