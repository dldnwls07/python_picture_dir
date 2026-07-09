# Project Review — 감정 일기장 (Emotion Diary)

Reviewed: 2026-07-09, commit `a6b4830` on `main`.

A dual-GUI (Tkinter + PyQt5) personal diary app with CSV persistence, an
optional drawing canvas, weather/emotion tagging, keyword/wordcloud analysis,
and Gemini-powered "AI empathy" summaries. The domain layer was recently
refactored toward DDD (`domain/`, `application/`, `infrastructure/`). Overall
the new layering is clean and the two GUIs now share it, but a few
repository-hygiene issues and some leftover legacy code should be addressed
before this goes further.

## Critical

### 1. `data/diary_data.csv` is committed to git, containing real diary content and a plaintext password
`.gitignore` lists `data/diary_data.csv`, but it was already tracked before
the rule was added (`git log -- data/diary_data.csv` shows it changing across
6 commits, including the most recent DDD refactor). `git status` shows it
clean, meaning **whatever is in the working copy right now is also in the
commit history** — right now that's a real-looking diary entry plus a
password field containing `12345678910` in plaintext (pre-dates the SHA-256
hashing change, but it's still sitting in the repo history and current tip).

Since `is_hidden`/`password` is meant to keep diary entries private, having
that value in git — and pushed to any remote — defeats the feature entirely
and leaks the user's actual password.

**Fix:** `git rm --cached data/diary_data.csv` (keep the working file), then
consider scrubbing it from history (`git filter-repo` / BFG) if this has ever
been pushed anywhere. Same applies to anything under `data/images/`.

### 2. `.venv/` (7,751 files) is committed to git
`.gitignore` has `.venv/`, but `git ls-files | grep '^\.venv/'` returns
thousands of PyQt5/matplotlib site-package files. This bloats every clone and
diff, and risks committing platform-specific compiled binaries.

**Fix:** `git rm -r --cached .venv` and commit; verify with `git status` that
it's now ignored.

## Security / Privacy

### 3. Password protection is cosmetic, not real encryption
`Diary.verify_password` gates the *GUI*, but `content`, `title`, and all
metadata are stored as plain CSV text (`csv_diary_repository.py`). Anyone
opening `data/diary_data.csv` directly reads every "hidden" diary in full —
only the password itself is hashed. That may be an acceptable trade-off for a
local single-user app, but it's worth being explicit about (e.g. in the UI
copy) so the "🔒 비밀 일기" checkbox doesn't imply more protection than it
delivers.

### 4. Backward-compatible plaintext password comparison
`domain/model/diary.py:53-55` falls back to comparing `self.password ==
input_password.strip()` when the stored value isn't a 64-char hex string.
This is a deliberate migration shim (per the recent hashing commit) but means
any diary saved before the hashing change stays in plaintext forever unless
re-saved — worth a one-time migration pass over the CSV, or at least a
comment noting it's intentional and temporary.

## Dead code

### 5. `engine/emotion_engine.py` and `data/emotion_dict.py` are unused
No import path reaches either file anymore (`grep` across the repo confirms
it) — the only references are within the files themselves and a stale
comment in `app_tkinter.py:317` ("PyQt5 스타일과 동일하게 emotion_engine의
get_score_label을 이용") that no longer matches what the code does. Both the
engine and the (~90 line) emotion word dictionary can be deleted.

### 6. `manager/file_manager.py` duplicates `CSVDiaryRepository`
`FileManager` is a near byte-for-byte copy of
`infrastructure/persistence/csv_diary_repository.py` (same `HEADERS`, same
atomic-save logic, same CSV read/write). It's no longer used by either GUI —
only by tests (`test_file_manager.py`, `test_refactoring.py`,
`test_app_gui.py`). Keeping two parallel CSV implementations means every
schema change (e.g. the recent header-sanitization fix) has to be applied
twice or they silently drift. Either delete `FileManager` and port its tests
to `CSVDiaryRepository`, or delete the tests that only exist to prove the two
are equivalent (`test_refactoring.py`'s whole premise is "legacy vs new
produce the same output" — once you trust the new code, the legacy path can
go).

### 7. `AppGUI._file_manager` property/setter in `app_gui.py:152-160`
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
This only exists so `test_app_gui.py` can do
`self.window._file_manager = FileManager(temp_path)` and get a repository
pointed at the temp file. It's a test seam smuggled into production code via
a legacy attribute name, reaching into `DiaryService`'s private `_repository`
field. Simplest fix: give `DiaryService`/`AppGUI` a real
`repository`/constructor parameter for tests to use, and drop the property
entirely.

## Portability / correctness

### 8. Tests hardcode a macOS-only temp path
`tests/test_app_gui.py:20`, `test_file_manager.py:14`, `test_refactoring.py:19`,
and `test_runtime_and_weather.py:12` all call
`tempfile.mkdtemp(..., dir="/private/tmp")`. `/private/tmp` doesn't exist on
Windows or plain Linux, so these tests fail immediately off macOS (verified:
they error with a directory-not-found on this Windows checkout before even
reaching the module-not-found errors from missing deps). Drop the `dir=`
argument and let `tempfile` pick the platform default.

### 9. `runtime_env.configure_runtime` unconditionally sets a macOS font path
```python
os.environ.setdefault("FONTCONFIG_PATH", "/System/Library/Fonts")
```
This runs on every platform (it's called unconditionally from `main.py`).
It's a `setdefault` so it won't clobber an explicit setting, but on
Windows/Linux it seeds `FONTCONFIG_PATH` with a directory that doesn't exist,
which could confuse any fontconfig-based rendering (matplotlib's wordcloud
figure uses its own font discovery, so this happens to be harmless today, but
it's a latent trap). Gate it behind a `sys.platform == "darwin"` check.

### 10. Tests can't currently run on this machine
`python -m unittest discover -s tests` fails for most modules with
`ModuleNotFoundError: No module named 'PyQt5'` / `'requests'` — the checked-in
`.venv` isn't the one being used, and there's no root-level venv activated.
Once issue #2 is resolved, document how to set up/activate the dev
environment (e.g. in a short `README.md`) so `python -m unittest discover -s
tests` works out of the box.

## Minor / nice-to-have

- **`implementation_plan.md`** still describes a pre-DDD architecture and
  links to `/Users/woojin/Developer/dir_py/...` (another contributor's local
  Mac path). It predates the two most recent refactor commits and is now
  actively misleading about the current file layout — either update it or
  delete it.
- **`smoke_check.py`** shells out to run the test suite and Qt-offscreen
  checks; not wired into CI as far as this repo shows. Worth a one-line
  mention in a README if it's meant to be the local pre-flight check.
- `screenshot.png` is tracked in git even though `*.png` and `screenshot.png`
  are both in `.gitignore` — same "tracked-before-ignored" situation as
  findings #1/#2; harmless here but confirms the pattern is worth a repo-wide
  sweep (`git ls-files` vs `.gitignore`) rather than one-off fixes.
- `csv_diary_repository.py:109` has a dead/confusing expression:
  `EmotionScore(0).EMOTION_LABEL_TO_SCORE.get(l, 0) if hasattr(EmotionScore(0), 'EMOTION_LABEL_TO_SCORE') else EMOTION_LABEL_TO_SCORE.get(l, 0)`
  — `EmotionScore` never had an `EMOTION_LABEL_TO_SCORE` attribute, so the
  `hasattr` branch is always false and this always falls through to the
  `else`. Simplify to just `EMOTION_LABEL_TO_SCORE.get(l, 0)`.

## What's working well

- The `domain` / `application` / `infrastructure` split is a real improvement
  over the earlier flat-file structure, and both GUIs (`app_gui.py`,
  `app_tkinter.py`) now drive the same `DiaryService`, so weather/emotion/
  scoring logic isn't duplicated between the two front ends anymore.
- `CSVDiaryRepository._save_all_atomic` writes to a `.tmp` file and
  `os.replace`s it — a correct atomic-write pattern that avoids truncating
  the CSV on a crash mid-write.
- `DiaryService.save_diary` defers deleting the old image file until *after*
  the CSV write succeeds, and rolls back a newly-saved image if the CSV write
  fails — sensible failure-mode handling for the image/CSV two-step.
- The `d027530` CSV-sanitization fix (restrict row updates to defined schema
  headers) is a good defensive fix against silently corrupting the CSV shape.
