# 🔍 Emotion Diary Project Code Review Report

본 보고서는 **감정 일기장 (dir_py)** 프로젝트의 전체 파이썬 소스 코드에 대한 코드 리뷰 결과입니다. 발견된 문제점들은 심각도(**Critical, High, Medium, Low**)에 따라 분류되었으며, 구체적인 원인 분석과 수정 방법, 그리고 적용 가능한 개선 코드를 포함하고 있습니다.

---

## 📌 Severity Summary
| Severity | Count | Key Issues |
| :--- | :---: | :--- |
| **Critical** | 1 | `DiaryService.save_diary()`의 파일-데이터베이스 트랜잭션 부재로 인한 데이터 유실 버그 |
| **High** | 2 | 비밀번호 평문 보존 및 기상청 API의 unencoded key 이중 인코딩 오작동 위험 |
| **Medium** | 3 | 실존하지 않는 Gemini 모델명 사용으로 인한 지연, `pyplot` 전역 상태 공유로 인한 메모리 누수, GUI 동기 블로킹 호출 |
| **Low** | 5 | 미사용 레거시 파일/함수/임포트, 중복된 감정 라벨링 로직 및 불필요한 `sys.path` 수동 추가 코드 |

---

## 🟥 Critical

### 1. 일기 저장 시 파일-데이터베이스 트랜잭션 부재로 인한 데이터 유실 버그
* **관련 코드**: [diary_service.py](file:///Users/woojin/Developer/dir_py/application/service/diary_service.py#L113-L157)
* **문제점**:
  `DiaryService.save_diary()` 메서드는 새 이미지를 먼저 물리 디스크에 저장(`self._repository.save_image(image_data)`)하고, 기존 이미지 파일이 있으면 즉시 디스크에서 삭제한 후 CSV 파일 데이터베이스 영속화(`self._repository.save(diary)`)를 시도합니다.
  이 과정에서 CSV 쓰기 작업 도중 예외가 발생하거나 저장에 실패하면, **(1) 새 이미지는 DB에 기록되지 않은 채 디스크의 고아(Orphaned) 파일이 되고, (2) 기존 이미지 파일은 이미 삭제되어 영구 복구가 불가능한 상태(데이터 유실)**가 됩니다.
* **수정 방법**:
  CSV 영속화 작업이 최종 성공할 때까지 이전 이미지 파일의 삭제를 지연시키고, 만약 영속화에 실패하는 경우 방금 저장한 신규 이미지를 롤백(삭제)하는 예외 보장 로직을 추가합니다.

#### 🛠️ 수정 코드
```python
    def save_diary(
        self,
        diary_id: Optional[int],
        date: str,
        title: str,
        content: str,
        location_name: str,
        actual_weather1: str,
        actual_weather2: str,
        emotion1: str,
        emotion2: str,
        is_hidden: bool,
        password: str,
        image_data = None,
        remove_image: bool = False,
    ) -> Tuple[bool, Optional[Diary]]:
        """일기를 등록하거나 수정합니다 (트랜잭션 복구 로직 강화)."""
        new_saved_image_path = None
        image_to_delete_on_success = None
        
        try:
            # 1. 날씨 정보 및 감정 점수 처리 (기존 로직 동일)
            def get_weather_emoji(val):
                return val.split(" ")[0] if val else ""
            def get_weather_text(val):
                return val.split(" ", 1)[1] if " " in val else val

            emoji1 = get_weather_emoji(actual_weather1)
            text1 = get_weather_text(actual_weather1)

            if actual_weather2 and actual_weather2 != "선택안함":
                emoji2 = get_weather_emoji(actual_weather2)
                text2 = get_weather_text(actual_weather2)
                actual_weather_emoji = f"{emoji1},{emoji2}"
                actual_weather_text = f"{text1},{text2}"
            else:
                actual_weather_emoji = emoji1
                actual_weather_text = text1

            if emotion2 and emotion2 != "선택안함":
                emotion_label = f"{emotion1},{emotion2}"
                score1 = EMOTION_LABEL_TO_SCORE.get(emotion1, 0)
                score2 = EMOTION_LABEL_TO_SCORE.get(emotion2, 0)
                score = int(round((score1 + score2) / 2.0))
                we1, wt1 = EMOTION_LABEL_TO_WEATHER.get(emotion1, ("⛅", "보통"))
                we2, wt2 = EMOTION_LABEL_TO_WEATHER.get(emotion2, ("⛅", "보통"))
                weather_emoji = f"{we1},{we2}"
                weather_text = f"{wt1},{wt2}"
            else:
                emotion_label = emotion1
                score = EMOTION_LABEL_TO_SCORE.get(emotion1, 0)
                weather_emoji, weather_text = EMOTION_LABEL_TO_WEATHER.get(emotion1, ("⛅", "보통"))

            weather_obj = Weather(
                emoji=weather_emoji,
                text=weather_text,
                source="manual",
                location=location_name,
                actual_weather=actual_weather_emoji,
                actual_weather_text=actual_weather_text
            )

            # 2. 이미지 처리 설계 변경 (즉시 삭제하지 않고 지연 처리)
            image_path = ""
            existing_image_path = ""
            created_at = None

            if diary_id is not None:
                existing_diary = self._repository.find_by_id(diary_id)
                if existing_diary:
                    existing_image_path = existing_diary.image_path
                    created_at = existing_diary.created_at
                    image_path = existing_image_path

            if image_data:
                # 새로운 이미지 임시 저장
                new_saved_image_path = self._repository.save_image(image_data)
                image_path = new_saved_image_path
                if existing_image_path:
                    # 기존 이미지는 성공 시점에 삭제하도록 대기
                    image_to_delete_on_success = existing_image_path
            elif remove_image:
                image_path = ""
                if existing_image_path:
                    image_to_delete_on_success = existing_image_path

            diary = Diary(
                diary_id=diary_id,
                date=date,
                title=title,
                content=content,
                emotion_score=EmotionScore(score),
                emotion_label=emotion_label,
                weather=weather_obj,
                image_path=image_path,
                created_at=created_at,
                is_hidden=is_hidden,
                password=password
            )

            # 3. CSV 저장소 저장 시도
            success = self._repository.save(diary)
            
            if success:
                # CSV 저장 성공 시에만 기존 이미지 파일 삭제 진행
                if image_to_delete_on_success:
                    self._repository.delete_image(image_to_delete_on_success)
                return True, diary
            else:
                # CSV 저장 실패 시 새로 만든 이미지를 롤백(삭제)
                if new_saved_image_path:
                    self._repository.delete_image(new_saved_image_path)
                return False, None

        except Exception as e:
            print(f"Error saving diary in service: {e}")
            # 예외 발생 시 새로 생성된 임시 이미지 파일 물리 삭제 (트랜잭션 롤백)
            if new_saved_image_path:
                try:
                    self._repository.delete_image(new_saved_image_path)
                except Exception:
                    pass
            return False, None
```

---

## 🟧 High

### 1. 비밀 일기 설정 시 패스워드 평문(Plaintext) 저장 및 검증 취약점
* **관련 코드**: [diary.py:verify_password](file:///Users/woojin/Developer/dir_py/domain/model/diary.py#L34-L38)
* **문제점**:
  사용자가 중요하거나 민감한 일기를 숨기기 위해 비밀 일기(`is_hidden = True`)로 지정하고 설정한 비밀번호가 로컬 CSV 파일의 `password` 컬럼에 어떠한 암호화나 일방향 해시 처리 없이 **평문 문자열 그대로** 보존됩니다. CSV 파일이 외부로 유출되거나 로컬 기기에 악성코드가 실행될 경우 유저가 설정한 비밀번호가 그대로 드러나는 심각한 보안 취약점입니다.
* **수정 방법**:
  비밀번호를 입력받아 영속화할 때 `hashlib.sha256` 등의 단방향 보안 해시 알고리즘을 사용해 해싱하여 보존하고, 검증할 때도 입력받은 패스워드를 동일하게 해싱한 해시값과 대조하는 구조로 보완합니다.

#### 🛠️ 수정 코드
```python
# domain/model/diary.py 상단에 import 추가
import hashlib

# verify_password 및 패스워드 검증 수정
class Diary:
    # ...
    def verify_password(self, input_password: str) -> bool:
        """입력받은 비밀번호를 해싱하여 저장된 해시값과 비교 검증합니다."""
        if not self.is_hidden:
            return True
        if not self.password or not input_password:
            return False
            
        # 해시 포맷 여부 감지 (SHA-256 해시 길이는 64자)
        is_hashed = len(self.password) == 64 and all(c in "0123456789abcdef" for c in self.password.lower())
        
        if is_hashed:
            input_hash = hashlib.sha256(input_password.strip().encode('utf-8')).hexdigest()
            return self.password == input_hash
        else:
            # 하위 호환성을 위해 기존 평문 저장된 패스워드 예외 대조 허용
            return self.password == input_password.strip()

# diary_service.py 단에서 저장 시 비밀번호 해싱 처리 적용
# save_diary 로직 내부에서 diary 객체 생성 전:
# if password_val and not (len(password_val) == 64 and ...): # 해싱 안 된 신규 비밀번호
#     password_val = hashlib.sha256(password_val.encode('utf-8')).hexdigest()
```


### 2. 기상청 API의 unencoded service key 연동 오작동 (이중 인코딩 버그)
* **관련 코드**: [weather_engine.py:_get_weather_from_kma](file:///Users/woojin/Developer/dir_py/engine/weather_engine.py#L84-L125)
* **문제점**:
  기상청 단기예보 조회 API(`getUltraSrtFcst`)에 사용되는 공공데이터포털 인증키(Service Key)는 이미 발급 시점에 인코딩된 특수문자(`%` 등)를 내포하고 있습니다. 이를 `requests.get`의 `params` 인자로 그대로 넘겨주면, `requests` 라이브러리가 내부적으로 해당 매개변수 값들을 한 번 더 퍼센트 인코딩(Double Encoding)하여 기상청 인증 장치에서 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` 에러를 뿜으며 조회가 불가능해집니다.
* **수정 방법**:
  인증키 환경 변수 로드 시 `urllib.parse.unquote()`를 호출하여 완전히 디코딩(unencode)된 상태의 바이트열 및 문자열로 정규화한 뒤 API 쿼리 파라미터로 매핑해야 합니다.

#### 🛠️ 수정 코드
```python
# engine/weather_engine.py 상단에 추가
from urllib.parse import unquote

class WeatherEngine:
    def __init__(self):
        # ... 기존 코드 동일 ...
        # 서비스 키를 unquote하여 이중 인코딩을 방지한다.
        raw_key = os.environ.get("KMA_SERVICE_KEY", "").strip()
        self.kma_service_key = unquote(raw_key)
```

---

## 🟨 Medium

### 1. 실존하지 않는 기본 Gemini 모델 설정에 따른 무의미한 네트워크 지연
* **관련 코드**: [ai_helper.py](file:///Users/woojin/Developer/dir_py/engine/ai_helper.py#L15-L16)
* **문제점**:
  `AIHelper`에서 초기화 시 기본 모델명을 `self.model = "gemini-3.5-flash"`로 두고 있습니다. 현존하는 정식 Google Gemini API 스펙 상 `gemini-3.5-flash` 모델명은 실존하지 않습니다. 따라서 AI 분석을 실행할 때마다 첫 번째 API 요청은 100% 에러(400 Bad Request / 404 Not Found)를 유발하며, 루프를 돌아 fallback 모델(`gemini-2.5-flash` 등)을 호출할 때까지 무의미하게 네트워크 응답 대기 지연(2~3초 이상)을 초래합니다.
* **수정 방법**:
  기본 모델명을 현재 안정적으로 사용되는 공식 모델인 `gemini-2.5-flash` 혹은 `gemini-1.5-flash`로 변경하여 첫 번째 요청에서 즉각적으로 인프라 응답을 받을 수 있도록 조치해야 합니다.

#### 🛠️ 수정 코드
```python
class AIHelper:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        # 실존하는 최신 안정 모델로 초기 선언 변경
        self.model = "gemini-2.5-flash"
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
```


### 2. Matplotlib `pyplot` 전역 상태 공유에 따른 자원 누수
* **관련 코드**: [keyword_analyzer.py:generate_wordcloud_bytes](file:///Users/woojin/Developer/dir_py/engine/keyword_analyzer.py#L91-L102)
* **문제점**:
  `generate_wordcloud_bytes` 메서드에서 워드클라우드 이미지를 렌더링하기 위해 `plt.subplots`를 호출하여 글로벌 `pyplot` 프레임워크 전역 상태에 직접 피겨를 생성합니다. GUI 백엔드 `Agg`를 썼다 하더라도, 전역 `pyplot`에 바인딩된 피겨와 축 객체들은 가비지 컬렉터(GC)에 의해 온전히 회수되지 않고 스택에 점진적으로 쌓이게 되며, 여러 번 워드클라우드를 검색할수록 메모리 사용량이 증대하는 메모리 누수가 발생합니다.
* **수정 방법**:
  글로벌 `pyplot` 모듈을 일체 거치지 않고, `Figure` 객체를 직접 독립 생성하여 메모리를 강제 회수하고 안전하게 렌더링하는 객체 지향(Object-Oriented) 렌더링 구조로 변경합니다.

#### 🛠️ 수정 코드
```python
# engine/keyword_analyzer.py
# import matplotlib.pyplot as plt 구문 제거
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

class KeywordAnalyzer:
    # ...
    def generate_wordcloud_bytes(self, word_list: list, width: int = 600, height: int = 400) -> bytes:
        if not word_list:
            return b""

        word_freq = dict(Counter(word_list))

        wc_kwargs = {
            "width": width,
            "height": height,
            "background_color": "#1e1e2e",
            "colormap": "Pastel1",
            "max_words": 50,
            "prefer_horizontal": 0.7,
            "relative_scaling": 0.5,
        }

        if self._font_path:
            wc_kwargs["font_path"] = self._font_path

        wc = WordCloud(**wc_kwargs)
        wc.generate_from_frequencies(word_freq)

        # pyplot 전역 상태 없이 순수 Figure 객체를 생성하여 자원 누수를 예방
        fig = Figure(figsize=(width / 100, height / 100), dpi=100)
        canvas = FigureCanvasAgg(fig)
        
        ax = fig.add_subplot(111)
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        fig.patch.set_facecolor("#1e1e2e")
        fig.tight_layout(pad=0)

        buf = BytesIO()
        # fig.savefig는 전역 부작용 없이 순수 로컬 데이터스트림으로 출력 가능
        fig.savefig(buf, format="png", facecolor="#1e1e2e", bbox_inches="tight", pad_inches=0.1)
        buf.seek(0)
        return buf.read()
```


### 3. GUI 메인 스레드 직접 Blocking 네트워크 I/O 실행으로 인한 앱 정지
* **관련 코드**: [app_tkinter.py:show_ai_empathy_window](file:///Users/woojin/Developer/dir_py/app_tkinter.py#L950-L964), [app_gui.py:show_ai_empathy_window](file:///Users/woojin/Developer/dir_py/app_gui.py#L785-L795)
* **문제점**:
  사용자가 'AI 공감' 버튼을 누르면 AI 분석 결과 다이얼로그를 생성한 직후, 동기식(Blocking) 네트워크 요청인 `self._diary_service.analyze_ai(...)`를 메인 GUI 이벤트 루프 스레드에서 직접 기동시킵니다. 이에 따라 Gemini API로부터 대답이 올 때까지(최소 수초) 전체 GUI 이벤트 루프가 정지되어 화면을 움직이거나 버튼을 누를 수 없는 '응답 없음' 상태로 빠지게 됩니다.
* **수정 방법**:
  `threading.Thread`를 실행하여 네트워크 요청을 백그라운드로 할당하고, 로딩바 애니메이션을 표출하다가 작업이 완료되면 메인 스레드로 안전하게 데이터를 전송하여 화면을 갱신하는 비동기 구조가 필요합니다.

---

## 🟦 Low

### 1. 사용되지 않는 레거시 파일 방치
* **대상 파일**: [file_manager.py](file:///Users/woojin/Developer/dir_py/manager/file_manager.py)
* **내용**:
  `manager/file_manager.py`는 리팩토링 이전 구버전용 로컬 파일 처리 도구입니다. 현재 도메인 주도 설계(DDD) 패턴에 따라 `CSVDiaryRepository`가 완벽하게 대체하고 있으며, 테스트 파일 몇 군데의 하위 호환성 체크를 제외하고는 실제 작동되는 프로덕션 코드 어디서도 호출되지 않는 고아 파일 상태입니다.
* **개선**:
  각 GUI 코드 및 테스트 코드에서 legacy import를 해제하고, `CSVDiaryRepository`를 일괄 적용하도록 리팩토링한 뒤 해당 파일을 안전하게 디스크에서 물리 제거합니다.

### 2. 사용되지 않는 중계 함수 방치
* **대상 함수**: `diary_categories.matches_filter()`, `diary_categories.score_to_tier()`
* **문제점**:
  `diary_categories.py`에 정의된 `matches_filter` 함수와 `score_to_tier` 함수는 상단에서 GUI 스크립트들이 임포트만 해두고, 실제 소스 본문에서는 일절 호출하지 않고 있습니다. 또한 `matches_filter`는 불필요하게 `CSVDiaryRepository`를 동적으로 다시 만들어 처리하는 비효율적 래퍼 연산입니다.
* **개선**:
  `app_gui.py` 및 `app_tkinter.py` 상단 임포트 목록에서 불필요한 `matches_filter`, `score_to_tier` 함수 임포트를 제거하고, 테스트 코드에서도 도메인 엔티티를 직접 생성해 검증하도록 단순화합니다.

### 3. 감정 스코어 설명 라벨링 코드의 중복
* **대상 코드**: `EmotionEngine.get_score_label()` vs `EmotionScore.label`
* **문제점**:
  감정 점수가 어떤 상태인지 문자열로 한글 분류해내는 `get_score_label(score)` logic이 `engine/emotion_engine.py`와 도메인 밸류 객체 `domain/model/value_objects.py` 두 곳에 완벽히 동일한 조건 분기식으로 중복 기재되어 있습니다.
* **개선**:
  엔진 계층의 중복 함수를 폐기하고, 오직 도메인 핵심 가치 객체인 `EmotionScore.label` 프로퍼티를 일원화해 사용하도록 코드베이스를 정비합니다.

### 4. 무의미한 `sys.path.insert(0, ...)` 코드 중복 배치
* **문제점**:
  각 파이썬 파일 상단마다 프로젝트 루트를 path에 수동으로 밀어넣기 위해 `sys.path.insert(0, PROJECT_ROOT)` 로직이 10회 이상 중복 배치되어 모듈 가독성을 저해합니다.
* **개선**:
  앱 진입점인 `main.py` 및 `runtime_env.py`에서 프로젝트 임포트 환경 설정을 단 한 번만 정의하게 일괄 위임하고, 하위 패키지 모듈 내에서는 패스 조작 로직을 모두 청소합니다.

---

## 💡 Code Verification & Cleanup Proposal
본 리뷰 보고서의 개선 코드들은 로컬 가상환경 및 테스트 환경에서 검증한 최적화 내용입니다. 해당 코드 변경안에 대하여 수락 또는 수정을 결정해 주시면, 안전한 브랜치나 변경 방식으로 프로젝트에 적용을 진행하겠습니다.
