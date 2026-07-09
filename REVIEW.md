# 프로젝트 리뷰 — 감정 일기장 (Emotion Diary)

리뷰 시점: 2026-07-09, `main` 브랜치 HEAD `0d12861` (원격 `origin/main`과 동일).
이전 리뷰(커밋 `a6b4830` 기준) 이후 4개 커밋이 추가로 반영되어 재검토함.

## 이전 리뷰 이후 달라진 점 요약

지난 리뷰에서 지적한 항목 대부분이 실제로 처리되었다:

| # | 이전 지적 사항 | 현재 상태 |
|---|---|---|
| 5 | `engine/emotion_engine.py`, `data/emotion_dict.py` 죽은 코드 | ✅ 삭제됨 (`0d12861`) |
| 6 | `manager/file_manager.py`가 `CSVDiaryRepository`와 중복 | ✅ 삭제됨, `tests/test_csv_diary_repository.py`로 대체 (`0d12861`) |
| 7 | `AppGUI._file_manager` property/setter가 테스트용 우회 통로 | ✅ 제거됨. 테스트는 이제 `self.window._diary_service = DiaryService(repository=...)`로 직접 주입 |
| 8 | 테스트가 macOS 전용 `/private/tmp` 하드코딩 | ✅ `test_app_gui.py`, `test_runtime_and_weather.py`에서 제거됨 |
| — | AI 분석이 수동 `threading.Thread` + `QTimer.singleShot`으로 결과를 메인 스레드에 전달 | ✅ `QThread`/`pyqtSignal` 기반 `AIWorker`로 교체 (`6f03d9e`) — 더 관용적인 PyQt 패턴 |
| — | `ai_helper.py`의 Gemini 모델 목록에 중복 가능성, 마크다운 코드펜스로 감싸진 JSON 응답 파싱 실패 가능성 | ✅ 모델 목록 중복 제거 로직 추가, ` ```json ` 코드펜스 스트리핑 추가 (`6f03d9e`) |

이 부분들은 다시 짚을 필요 없이 잘 처리된 것으로 판단한다.

## 아직 남아있는 문제 (재확인 필요)

### 1. [심각·미해결] git 히스토리에 실제 일기 내용 + 평문 비밀번호가 남아있고, 이미 GitHub에 push되어 있음
`data/diary_data.csv`의 민감한 행(row)은 `6f03d9e` 커밋에서 **현재 HEAD 기준으로는** 삭제되어 지금 파일은 헤더만 남아있다. 좋은 방향이지만, 이것만으로는 문제가 끝나지 않는다:

- `git remote -v` 확인 결과 `origin`이 `https://github.com/dldnwls07/python_picture_dir`이고, `git branch -vv`에서 로컬 `main`이 `origin/main`과 완전히 동일하다 — 즉 **`data/diary_data.csv`에 평문 비밀번호(`12345678910`)와 실제 일기 본문이 들어있던 이전 커밋들이 지금 이 순간 GitHub에 공개(혹은 최소한 원격 저장소에 존재)되어 있다.**
- CSV 파일을 지운 것은 "새 커밋"일 뿐, 과거 커밋의 blob은 여전히 히스토리에 남아 `git show a6b4830:data/diary_data.csv`처럼 누구나 접근할 수 있다.

**조치:** 단순히 파일을 지우는 커밋으로는 부족하다. `git filter-repo` 또는 BFG Repo-Cleaner로 `data/diary_data.csv`(및 `data/images/`) 전체를 히스토리에서 제거하고 강제 push해야 하며, 이미 유출된 비밀번호(`12345678910`)는 어딘가에서 재사용 중이라면 즉시 변경을 권장한다. 이 저장소가 private가 아니라면 특히 시급하다.

### 2. [심각·부분 해결] `.venv/`가 여전히 `origin/main`에 커밋되어 있음
`git ls-tree -r origin/main --name-only | grep '^\.venv/'`로 확인한 결과 여전히 7,751개 파일(pack 크기 73.81 MiB)이 원격에 남아있다. 로컬에서는 `git rm -r --cached .venv`가 **실행되어 스테이징까지는 되어 있지만 아직 커밋되지 않은 상태**다 (`git status`에 "Changes to be committed"로 표시됨). 이 스테이징을 커밋하고 push해야 실제로 반영된다. (단, 이 방법으로는 과거 커밋에 남아있는 `.venv` blob은 지워지지 않는다 — 저장소 용량 문제까지 해결하려면 위 1번과 함께 히스토리 재작성이 필요하다.)

**조치:**
```
git commit -m "chore: stop tracking .venv"
git push
```
그 후 저장소 용량까지 줄이고 싶다면 filter-repo/BFG로 히스토리에서도 제거.

### 3. [미해결] `runtime_env.configure_runtime`이 모든 플랫폼에서 macOS 폰트 경로를 설정
`runtime_env.py:46`의 `os.environ.setdefault("FONTCONFIG_PATH", "/System/Library/Fonts")`는 여전히 플랫폼 체크 없이 무조건 실행된다. 지난 리뷰와 동일하게 `sys.platform == "darwin"` 조건으로 감싸는 것을 권장한다.

### 4. [미해결] `csv_diary_repository.py:109`의 죽은 분기
```python
scores = [EmotionScore(0).EMOTION_LABEL_TO_SCORE.get(l, 0) if hasattr(EmotionScore(0), 'EMOTION_LABEL_TO_SCORE') else EMOTION_LABEL_TO_SCORE.get(l, 0) for l in labels]
```
`EmotionScore`에는 `EMOTION_LABEL_TO_SCORE` 속성이 없으므로 `hasattr` 분기는 항상 거짓이다. `EMOTION_LABEL_TO_SCORE.get(l, 0)`로 단순화 가능. (지난 리뷰 이후 변경 없음.)

### 5. [미해결] `implementation_plan.md`가 여전히 낡은 상태
DDD 리팩터링 이전 구조를 설명하고 다른 개발자의 로컬 macOS 경로(`/Users/woojin/Developer/dir_py/...`)를 링크하고 있다. 갱신하거나 삭제 필요.

### 6. [미해결] `screenshot.png`가 `.gitignore`에도 불구하고 여전히 추적됨
`git ls-files`에 여전히 남아있음 — `.venv` 정리 시 함께 `git rm --cached` 하면 좋다.

### 7. [정보/설계 트레이드오프, 재확인] 비밀번호 보호는 여전히 UI 단 전용
`Diary.verify_password`가 접근을 막을 뿐, CSV에는 제목/본문이 평문으로 저장된다는 점은 이전과 동일하다. 개인용 로컬 앱이라는 성격을 감안하면 당장 고칠 필요는 없지만, 위 1번 사고를 계기로 "숨김 일기 = 파일 자체 암호화"가 아니라는 점을 사용자에게 명확히 알리는 문구를 추가하는 것을 고려해볼 만하다.

## 새로 확인한 사항 (이번 변경분)

### 8. [경미] AI 요청 도중 다이얼로그를 닫으면 `QThread` 참조가 위험해질 수 있음
`app_gui.py`의 `show_ai_empathy_window`는 `self._ai_worker`에 실행 중인 `QThread`를 저장한다. 콜백(`_on_finished`/`_on_error`)에서 `dialog.isVisible()`을 체크해 다이얼로그가 닫힌 뒤의 위젯 접근은 잘 막고 있지만, 사용자가 같은 창에서 "AI 공감"을 다시 빠르게 여러 번 열면(예: 이전 다이얼로그를 닫자마자) `self._ai_worker`가 아직 실행 중인 이전 `QThread`를 덮어쓰게 되어 "QThread: Destroyed while thread is still running" 경고/크래시로 이어질 가능성이 있다. 다이얼로그가 모달(`exec_()`)이라 일반적인 사용 흐름에서는 발생하기 어렵지만, 이전 워커가 끝나기 전에 새 워커를 만들지 않도록 가드(`if self._ai_worker and self._ai_worker.isRunning(): return`)를 추가하면 더 안전하다.

## 잘 되어 있는 부분 (변경분 포함)

- `QThread` 기반 `AIWorker`로의 전환은 이전의 `threading.Thread` + `QTimer.singleShot` 조합보다 PyQt 관용구에 맞고, 시그널/슬롯이 스레드 경계를 명확히 해준다.
- `ai_helper.py`가 Gemini 응답이 ` ```json ... ``` ` 코드펜스로 감싸져 오는 경우를 스트리핑하는 방어 로직을 추가한 것은 실제로 겪을 법한 API 응답 변형에 대한 합리적인 보강이다.
- 레거시/신규 구현이 "동일한 결과를 내는지"를 검증하던 `test_refactoring.py`를 삭제하고, `CSVDiaryRepository` 자체를 검증하는 `test_csv_diary_repository.py`로 교체한 것은 신뢰할 수 있는 방향의 정리다.
- 테스트가 더 이상 macOS 전용 경로에 의존하지 않아 Windows/Linux에서도 (의존성만 설치되어 있다면) 동작할 수 있게 되었다.

## 우선순위 정리

1. **지금 바로:** `.venv` 삭제를 커밋 + push (스테이징만 되어 있고 아직 반영 안 됨).
2. **가능한 빨리:** 저장소가 공개 상태라면 `data/diary_data.csv` 히스토리 재작성(filter-repo/BFG) + 강제 push, 그리고 유출된 비밀번호(`12345678910`)를 다른 곳에서 재사용 중이라면 교체.
3. **여유 있을 때:** `runtime_env.py`의 플랫폼 체크, `csv_diary_repository.py`의 죽은 분기, `implementation_plan.md`/`screenshot.png` 정리.