from engine.ai_helper import AIHelper

class AIService:
    """외부 Gemini AI 분석 서비스 구현체."""

    def __init__(self):
        self._helper = AIHelper()

    def summarize(
        self,
        date: str,
        content: str,
        location: str = "",
        weather: str = "",
        emotion: str = "",
    ) -> str:
        return self._helper.summarize_diary(
            date=date,
            content=content,
            location=location,
            weather=weather,
            emotion=emotion,
        )

    def analyze_empathy(
        self,
        date: str,
        content: str,
        location: str = "",
        weather: str = "",
        emotion: str = "",
        image_base64: str = ""
    ) -> dict:
        return self._helper.analyze_empathy(
            date=date,
            content=content,
            location=location,
            weather=weather,
            emotion=emotion,
            image_base64=image_base64
        )
