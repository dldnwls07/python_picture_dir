"""
AIHelper — Gemini API 연동을 통한 일기 공감 및 요약 기능 처리
"""

import os
import requests
import json

class AIHelper:
    """Gemini API를 호출하여 일기에 공감하고 요약해주는 헬퍼 클래스."""

    def __init__(self):
        # 환경 변수에서 API 키 로드
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.model = "gemini-2.5-flash"
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

    def analyze_diary(self, date: str, content: str, location: str = "", weather: str = "", emotion: str = "", image_base64: str = "") -> dict:
        """일기와 그림을 분석하여 요약, 공감 멘트, 그림 분석을 JSON으로 반환한다.

        Args:
            date: 일기 날짜
            content: 일기 본문
            location: 위치 정보 (선택)
            weather: 날씨 정보 (선택)
            emotion: 사용자가 고른 오늘 감정 (선택)
            image_base64: Base64 인코딩된 그림 이미지 데이터 (선택)

        Returns:
            dict: {"summary": "요약", "empathy": "공감 멘트", "drawing_analysis": "그림 분석"}
        """
        if not self.api_key:
            # 실시간으로 환경 변수를 다시 조회해 봄 (예: 사용자 .env 작성 후 갱신 대응)
            self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY가 존재하지 않습니다.\n"
                "프로젝트 루트에 .env 파일을 생성하고 아래와 같이 등록해주세요:\n"
                "GEMINI_API_KEY=your_api_key_here"
            )

        if not content.strip():
            raise ValueError("분석할 일기 내용이 비어있습니다.")

        # 프롬프트 작성
        prompt = (
            f"일기 날짜: {date}\n"
            f"일기 작성 위치: {location if location else '알 수 없음'}\n"
            f"오늘의 날씨: {weather if weather else '알 수 없음'}\n"
            f"작성자가 선택한 오늘의 감정: {emotion if emotion else '알 수 없음'}\n"
            f"일기 본문:\n{content}\n\n"
            "위의 일기 내용과 첨부된 그림(있는 경우)을 친근하고 따뜻한 톤앤매너로 분석해 주세요.\n"
            "1. 일기 본문의 핵심 내용을 1~2문장으로 요약해주고(summary),\n"
            "2. 사용자의 상황과 감정에 공감하며 격려하거나 기쁨을 나누는 위로/조언의 멘트를 3~4문장으로 작성해주세요(empathy).\n"
            "   특히 오늘의 감정에 '슬펐어요', '피곤했어요', '화났어요', '고독', '집에가고싶어!' 등 부정적인 감정이 포함되어 있다면,\n"
            "   사용자의 슬픔이나 스트레스를 위로하고 기분 전환을 도울 수 있는 따뜻한 힐링 명언이나 격려의 글귀를 공감 멘트(empathy) 마지막 줄에 꼭 한 줄 추가해 주세요.\n"
            "3. 첨부된 그림 일기를 분석하여 사용자의 심리 상태, 색채 표현, 선의 형태 등을 분석해 주세요(drawing_analysis). "
            "만약 그림이 첨부되지 않았거나 흰 캔버스라면 '그림 일기가 비어있습니다. 다음에는 오늘의 기분을 캔버스에 표현해보세요!' 라는 메시지를 작성해주세요.\n\n"
            "공감 및 그림 분석 멘트는 한국어 반말이나 다정한 높임말(예: '~했군요!', '~해보세요.')을 섞어서 따뜻한 심리 상담가처럼 친근하게 작성해주세요."
        )

        url = self.endpoint.format(self.model) + f"?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        parts = [{"text": prompt}]
        if image_base64:
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": image_base64
                }
            })

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {
                            "type": "STRING",
                            "description": "일기 내용의 1-2문장 요약"
                        },
                        "empathy": {
                            "type": "STRING",
                            "description": "일기 내용에 대한 따뜻한 공감과 위로/조언"
                        },
                        "drawing_analysis": {
                            "type": "STRING",
                            "description": "그림 분석 내용 또는 그림 미첨부 안내"
                        }
                    },
                    "required": ["summary", "empathy", "drawing_analysis"]
                }
            }
        }

        models_to_try = [self.model, "gemini-2.5-flash", "gemini-flash-latest"]
        last_error = None

        for model_name in models_to_try:
            url = self.endpoint.format(model_name) + f"?key={self.api_key}"
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=20)
                response.raise_for_status()
                res_data = response.json()
                
                # 응답 본문 파싱
                candidates = res_data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini API가 빈 응답을 반환했습니다.")
                    
                text_response = candidates[0].get("content", {}).get("parts", [])[0].get("text", "{}")
                result = json.loads(text_response.strip())
                
                # 안전하게 포맷 확인
                if "summary" not in result or "empathy" not in result or "drawing_analysis" not in result:
                    raise KeyError("API 응답 형식이 올바르지 않습니다.")
                    
                return result
            except requests.exceptions.RequestException as e:
                last_error = e
                print(f"⚠️ 모델 {model_name} 호출 실패: {e}. 다음 모델로 대체를 시도합니다...")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = e
                print(f"⚠️ 모델 {model_name} 응답 파싱 실패: {e}. 다음 모델로 대체를 시도합니다...")

        # 모든 모델 시도 실패 시 최종 에러 발생
        if isinstance(last_error, requests.exceptions.RequestException):
            # 429 할도 초과 에러 여부 판별
            if hasattr(last_error, "response") and last_error.response is not None:
                if last_error.response.status_code == 429:
                    raise RuntimeError(
                        "⚠️ API 호출 한도(Rate Limit)를 초과했습니다.\n"
                        "무료 요금제의 분당 또는 하루 요청량 제한에 도달했으니 잠시 후 다시 시도해 주세요."
                    )
            raise RuntimeError(f"네트워크 오류가 발생했습니다: {str(last_error)}")
        else:
            raise RuntimeError(f"AI 응답 분석 중 오류가 발생했습니다: {str(last_error)}")
