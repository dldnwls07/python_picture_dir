# 프로젝트 리뷰 — 감정 일기장 (Emotion Diary)

리뷰 시점: 2026-07-09, `main` 브랜치 커밋 `a6b4830`.

Tkinter와 PyQt5를 모두 지원하는 듀얼 GUI 개인 일기장 앱으로, CSV 기반 저장,
선택적 그림판 캔버스, 날씨/감정 태깅, 키워드/워드클라우드 분석, Gemini 기반
"AI 공감" 요약 기능을 제공한다. 최근 도메인 계층이 DDD(`domain/`,
`application/`, `infrastructure/`) 방식으로 리팩터링되었다. 전반적으로 새
레이어링은 깔끔하고 두 GUI가 이를 공유하도록 잘 정리되었지만, 더 진행하기
전에 몇 가지 저장소(git) 위생 문제와 남아있는 레거시 코드를 정리할 필요가
있다.

## 심각(Critical)

### 1. `data/diary_data.csv`가 git에 커밋되어 있고, 실제 일기 내용과 평문 비밀번호가 들어있음
`.gitignore`에 `data/diary_data.csv`가 등록되어 있지만, 이 규칙이 추가되기
전에 이미 추적(tracked)되고 있던 파일이다 (`git log -- data/diary_data.csv`를
보면 최근 DDD 리팩터링을 포함해 6개 커밋에 걸쳐 변경되어 왔다). `git
status`는 해당 파일이 클린(clean) 상태라고 보여주는데, 이는 **현재 작업
사본에 들어있는 내용이 곧 커밋 히스토리에도 들어있다는 뜻**이다 — 지금
시점에는 실제로 작성된 것으로 보이는 일기 항목 하나와, `12345678910`이라는
평문 비밀번호 값이 들어있다 (SHA-256 해싱이 도입되기 이전 데이터이긴 하지만,
여전히 저장소 히스토리와 현재 HEAD에 그대로 남아있다).

`is_hidden`/`password`는 일기 항목을 비공개로 유지하기 위한 기능인데, 그
값이 git에 — 그리고 어딘가에 push된 적이 있다면 원격 저장소에도 — 남아있다면
해당 기능의 의미가 완전히 무력화되고 사용자의 실제 비밀번호가 유출된다.

**조치:** `git rm --cached data/diary_data.csv`로 작업 파일은 남기고 git
추적만 해제한다. 이 저장소가 어딘가에 push된 적이 있다면 히스토리에서도
완전히 제거하는 것을 고려한다 (`git filter-repo` / BFG). `data/images/` 하위
파일들도 동일하게 처리해야 한다.

### 2. `.venv/` (7,751개 파일)가 git에 커밋되어 있음
`.gitignore`에 `.venv/`가 있지만, `git ls-files | grep '^\.venv/'`를 실행하면
수천 개의 PyQt5/matplotlib site-package 파일이 나온다. 이는 클론과 diff마다
저장소 용량을 부풀리고, 플랫폼별 컴파일 바이너리가 커밋될 위험이 있다.

**조치:** `git rm -r --cached .venv`를 실행하고 커밋한다. 이후 `git
status`로 정상적으로 무시되는지 확인한다.

## 보안 / 개인정보

### 3. 비밀번호 보호는 실질적 암호화가 아니라 겉모습(cosmetic)에 가까움
`Diary.verify_password`는 *GUI 단*에서만 접근을 막을 뿐, `content`, `title`
등 모든 메타데이터는 CSV에 평문으로 저장된다 (`csv_diary_repository.py`).
`data/diary_data.csv` 파일을 직접 열어보면 "숨김" 처리된 일기라도 전체 내용을
그대로 읽을 수 있다 — 해싱되는 것은 비밀번호 값 자체뿐이다. 로컬 단일 사용자용
앱이라는 점을 감안하면 받아들일 수 있는 트레이드오프일 수도 있지만, "🔒 비밀
일기" 체크박스가 실제 제공하는 것보다 더 강한 보호를 암시하지 않도록 UI
문구에서라도 이를 명확히 하는 편이 좋다.

### 4. 하위 호환을 위한 평문 비밀번호 비교
`domain/model/diary.py:53-55`는 저장된 값이 64자리 hex 문자열이 아닐 경우
`self.password == input_password.strip()`로 평문 비교하는 폴백 로직을 갖고
있다. 이는 (최근 해싱 커밋에 따른) 의도된 마이그레이션 임시 조치이지만,
해싱 도입 이전에 저장된 일기는 다시 저장하지 않는 한 영구히 평문으로
남는다는 의미다. CSV 전체에 대해 한 번 마이그레이션을 돌리거나, 최소한 이
동작이 의도적이고 임시적이라는 주석을 남겨두는 것이 좋다.

## 죽은 코드(Dead code)

### 5. `engine/emotion_engine.py`와 `data/emotion_dict.py`는 더 이상 사용되지 않음
두 파일 모두 어디서도 import되지 않는다 (전체 저장소 `grep`으로 확인함) —
유일한 참조는 파일 자기 자신 내부와, `app_tkinter.py:317`의 오래된 주석
("PyQt5 스타일과 동일하게 emotion_engine의 get_score_label을 이용")뿐인데,
이 주석은 더 이상 실제 코드 동작과 맞지 않는다. 엔진 파일과 (~90줄짜리)
감정 단어 사전 모두 삭제해도 된다.

### 6. `manager/file_manager.py`가 `CSVDiaryRepository`와 중복됨
`FileManager`는 `infrastructure/persistence/csv_diary_repository.py`와
거의 동일한 복사본이다 (동일한 `HEADERS`, 동일한 원자적 저장 로직, 동일한
CSV 읽기/쓰기 로직). 더 이상 어느 GUI에서도 사용되지 않으며 — 테스트
(`test_file_manager.py`, `test_refactoring.py`, `test_app_gui.py`)에서만
쓰인다. 이렇게 두 개의 병렬 CSV 구현을 유지하면 스키마가 바뀔 때마다
(예: 최근의 헤더 검증 수정) 양쪽 모두에 반영해야 하며, 그렇지 않으면 조용히
서로 어긋나게 된다. `FileManager`를 삭제하고 테스트를
`CSVDiaryRepository` 기준으로 이식하거나, "레거시와 신규 구현이 동일한
결과를 낸다"는 것을 증명하는 것이 유일한 목적인 `test_refactoring.py`
자체를 — 새 코드를 신뢰한다면 — 삭제하는 것을 고려한다.

### 7. `app_gui.py:152-160`의 `AppGUI._file_manager` property/setter
```python
@property
def _file_manager(self):
    return self._diary_service._repository

@_file_manager.setter
def _file_manager(self, value):
    from infrastructure.persistence.csv_diary_repository import CSVDiaryRepository
    repo = CSVDiaryRepository(value.filepath)
    self._diary_service = DiaryService(repository=repo)
```
이 코드는 오직 `test_app_gui.py`가
`self.window._file_manager = FileManager(temp_path)`를 실행해서 임시
파일을 가리키는 repository를 얻을 수 있도록 존재한다. `DiaryService`의
private 필드인 `_repository`에 레거시 속성 이름을 통해 접근하는, 프로덕션
코드에 몰래 끼워 넣은 테스트용 우회 통로다. 가장 간단한 해결책은
`DiaryService`/`AppGUI`에 테스트가 사용할 수 있는 실제 `repository`
생성자 파라미터를 두고, 이 property는 완전히 제거하는 것이다.

## 이식성 / 정확성

### 8. 테스트가 macOS 전용 임시 경로를 하드코딩함
`tests/test_app_gui.py:20`, `test_file_manager.py:14`,
`test_refactoring.py:19`, `test_runtime_and_weather.py:12` 모두
`tempfile.mkdtemp(..., dir="/private/tmp")`를 호출한다. `/private/tmp`는
Windows나 일반 Linux에는 존재하지 않으므로, macOS가 아닌 환경에서는 이
테스트들이 즉시 실패한다 (확인 결과: 이 Windows 환경에서는 의존성 누락으로
인한 module-not-found 오류보다도 먼저 디렉터리 없음 오류로 실패한다).
`dir=` 인자를 제거하고 `tempfile`이 플랫폼 기본값을 사용하도록 둔다.

### 9. `runtime_env.configure_runtime`이 macOS 폰트 경로를 무조건 설정함
```python
os.environ.setdefault("FONTCONFIG_PATH", "/System/Library/Fonts")
```
이 코드는 (`main.py`에서 무조건 호출되므로) 모든 플랫폼에서 실행된다.
`setdefault`이기 때문에 이미 명시적으로 설정된 값을 덮어쓰지는 않지만,
Windows/Linux에서는 존재하지 않는 디렉터리로 `FONTCONFIG_PATH`를 시드하게
된다. 이는 fontconfig 기반 렌더링을 혼란스럽게 할 수 있다 (다만 워드클라우드
figure에 쓰이는 matplotlib은 자체 폰트 탐색 로직을 쓰므로 오늘 시점에는
우연히 무해하다). 잠재적 함정이므로 `sys.platform == "darwin"` 체크로 감싸는
것이 좋다.

### 10. 현재 이 환경에서는 테스트가 아예 실행되지 않음
`python -m unittest discover -s tests`를 실행하면 대부분의 모듈에서
`ModuleNotFoundError: No module named 'PyQt5'` / `'requests'` 오류가
발생한다 — 저장소에 커밋된 `.venv`가 실제로 사용 중인 인터프리터가 아니고,
루트 레벨에 활성화된 venv도 없기 때문이다. 2번 항목을 해결한 뒤에는,
`python -m unittest discover -s tests`가 바로 동작하도록 개발 환경
설정/활성화 방법을 (예: 짧은 `README.md`에) 문서화해두는 것이 좋다.

## 사소한 것들 / 있으면 좋은 것들

- **`implementation_plan.md`**가 여전히 DDD 리팩터링 이전 아키텍처를
  설명하고 있고, (다른 기여자의 로컬 macOS 경로인)
  `/Users/woojin/Developer/dir_py/...`를 링크하고 있다. 최근 두 번의
  리팩터링 커밋보다 이전 문서이며, 현재 파일 구조에 대해 적극적으로
  잘못된 정보를 주고 있다 — 업데이트하거나 삭제하는 것이 좋다.
- **`smoke_check.py`**는 테스트 스위트와 Qt-오프스크린 체크를 셸로 실행하는
  스크립트인데, 이 저장소 안에서는 CI에 연결되어 있지 않은 것으로 보인다.
  로컬 사전 점검용 스크립트로 의도된 것이라면 README에 한 줄 정도
  언급해두면 좋다.
- `screenshot.png`도 `.gitignore`에 `*.png`와 `screenshot.png` 둘 다
  등록되어 있음에도 git에 추적되고 있다 — 1번/2번 항목과 동일한
  "무시 규칙 추가 전에 이미 추적되던" 패턴이다. 여기서는 무해하지만, 이런
  패턴이 한두 곳이 아니라는 뜻이므로 하나씩 고치기보다
  (`git ls-files` vs `.gitignore` 비교로) 저장소 전체를 한 번 훑어보는
  것이 좋다.
- `csv_diary_repository.py:109`에 죽은/헷갈리는 표현이 있다:
  `EmotionScore(0).EMOTION_LABEL_TO_SCORE.get(l, 0) if hasattr(EmotionScore(0), 'EMOTION_LABEL_TO_SCORE') else EMOTION_LABEL_TO_SCORE.get(l, 0)`
  — `EmotionScore`는 애초에 `EMOTION_LABEL_TO_SCORE` 속성을 가진 적이
  없으므로 `hasattr` 분기는 항상 거짓이 되어 매번 `else`로 빠진다.
  그냥 `EMOTION_LABEL_TO_SCORE.get(l, 0)`으로 단순화하면 된다.

## 잘 되어 있는 부분

- `domain` / `application` / `infrastructure` 분리는 이전의 평면적인 파일
  구조에 비해 실질적인 개선이며, 두 GUI(`app_gui.py`, `app_tkinter.py`)가
  이제 동일한 `DiaryService`를 사용하므로 날씨/감정/점수 계산 로직이 두
  프론트엔드 사이에서 더 이상 중복되지 않는다.
- `CSVDiaryRepository._save_all_atomic`은 `.tmp` 파일에 먼저 쓴 뒤
  `os.replace`로 교체하는 방식을 쓰는데, 쓰는 도중 크래시가 나도 CSV가
  잘리지 않도록 하는 올바른 원자적 쓰기 패턴이다.
- `DiaryService.save_diary`는 CSV 저장이 *성공한 뒤*에만 기존 이미지
  파일을 삭제하도록 미루고, CSV 저장이 실패하면 새로 저장한 이미지를
  롤백(삭제)한다 — 이미지/CSV 2단계 저장의 실패 상황을 합리적으로
  처리하고 있다.
- `d027530` 커밋의 CSV 검증 수정(row 업데이트를 정의된 스키마 헤더로만
  제한)은 CSV 구조가 조용히 깨지는 것을 막는 좋은 방어적 수정이다.
