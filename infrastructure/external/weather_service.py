from domain.model.value_objects import Weather
from engine.weather_engine import WeatherEngine

class WeatherService:
    """외부 기상 정보 조회 서비스 구현체."""

    def __init__(self):
        self._engine = WeatherEngine()

    def get_current_weather(self) -> Weather:
        data = self._engine.get_current_weather()
        return Weather(
            emoji=data.get("emoji", "⛅"),
            text=data.get("text", "알 수 없음"),
            source=data.get("source", "fallback"),
            location=data.get("location", ""),
            actual_weather=data.get("emoji", "⛅"),
            actual_weather_text=data.get("text", "알 수 없음")
        )
