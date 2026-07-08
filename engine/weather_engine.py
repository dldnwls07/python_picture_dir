import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote

import requests


DEFAULT_WEATHER = {
    "emoji": "⛅",
    "text": "알 수 없음",
    "source": "fallback",
    "location": "",
    "error": "",
}


class WeatherEngine:
    """
    현재 위치 기반 날씨 정보를 조회한다.

    현재는 Open-Meteo를 안정 fallback으로 사용한다.
    `KMA_SERVICE_KEY`가 제공되면 기상청 API 연동을 우선 시도할 수 있도록
    엔진 구조를 분리해 둔다.
    """

    def __init__(self):
        self.location_url = "http://ip-api.com/json/"
        self.open_meteo_url = "https://api.open-meteo.com/v1/forecast"
        self.kma_url = os.environ.get(
            "KMA_WEATHER_URL",
            "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst",
        ).strip()
        self.kma_service_key = unquote(os.environ.get("KMA_SERVICE_KEY", "").strip())
        self.provider = os.environ.get("WEATHER_PROVIDER", "auto").strip().lower()
        self.manual_latitude = os.environ.get("WEATHER_LATITUDE", "").strip()
        self.manual_longitude = os.environ.get("WEATHER_LONGITUDE", "").strip()
        self.manual_location_name = os.environ.get("WEATHER_LOCATION_NAME", "").strip()

    def get_current_location(self) -> Tuple[Optional[float], Optional[float], str]:
        """현재 IP 기반 위경도와 지역명을 반환한다."""
        manual_location = self._get_manual_location()
        if manual_location is not None:
            return manual_location

        try:
            resp = requests.get(self.location_url, timeout=3)
            resp.raise_for_status()
            data = resp.json()
            location = " ".join(
                part for part in [data.get("city", ""), data.get("regionName", "")] if part
            ).strip()
            return data.get("lat"), data.get("lon"), location
        except Exception as e:
            print(f"위치 조회 실패: {e}")
            return None, None, ""

    def _get_manual_location(self) -> Optional[Tuple[float, float, str]]:
        """환경 변수로 지정된 수동 좌표가 있으면 반환한다."""
        if not self.manual_latitude or not self.manual_longitude:
            return None

        try:
            lat = float(self.manual_latitude)
            lon = float(self.manual_longitude)
        except ValueError:
            return None

        location_name = self.manual_location_name or "Manual Location"
        return lat, lon, location_name

    def get_current_weather(self) -> Dict[str, Any]:
        """현재 위치의 날씨를 조회한다."""
        lat, lon, location = self.get_current_location()
        if lat is None or lon is None:
            return {**DEFAULT_WEATHER, "error": "위치 조회 실패"}

        if self.provider in ("kma", "auto") and self.kma_service_key:
            kma_result = self._get_weather_from_kma(lat, lon, location)
            if not kma_result.get("error"):
                return kma_result

        return self._get_weather_from_open_meteo(lat, lon, location)

    def _get_weather_from_kma(
        self, lat: float, lon: float, location: str
    ) -> Dict[str, Any]:
        """
        기상청 API 연동용 엔트리 포인트.
        """
        try:
            nx, ny = self._to_kma_grid(lat, lon)
            base_date, base_time = self._get_kma_base_datetime()
            params = {
                "serviceKey": self.kma_service_key,
                "pageNo": "1",
                "numOfRows": "1000",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": str(nx),
                "ny": str(ny),
            }
            resp = requests.get(self.kma_url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            weather = self._parse_kma_items(items)
            return {
                **weather,
                "source": "kma",
                "location": location,
                "error": "",
            }
        except Exception as e:
            return {
                **DEFAULT_WEATHER,
                "source": "kma",
                "location": location,
                "error": f"기상청 조회 실패: {e}",
            }

    def _get_weather_from_open_meteo(
        self, lat: float, lon: float, location: str
    ) -> Dict[str, Any]:
        """Open-Meteo 기반 현재 날씨 조회."""
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
            }
            resp = requests.get(self.open_meteo_url, params=params, timeout=3)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current_weather", {})
            weather = self._map_open_meteo_code(current.get("weathercode", 0))
            return {
                **weather,
                "source": "open-meteo",
                "location": location,
                "error": "",
            }
        except Exception as e:
            print(f"날씨 조회 실패: {e}")
            return {**DEFAULT_WEATHER, "location": location, "error": str(e)}

    def _map_open_meteo_code(self, weather_code: int) -> Dict[str, str]:
        """Open-Meteo WMO code를 앱 카테고리로 매핑한다."""
        if weather_code == 0:
            return {"emoji": "☀️", "text": "맑음"}
        if weather_code in [1, 2, 3, 45, 48]:
            return {"emoji": "⛅", "text": "흐림"}
        if weather_code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]:
            return {"emoji": "🌧️", "text": "비"}
        if weather_code in [71, 73, 75, 77, 85, 86]:
            return {"emoji": "❄️", "text": "눈"}
        return {"emoji": "⛅", "text": "흐림"}

    def _to_kma_grid(self, lat: float, lon: float) -> Tuple[int, int]:
        """
        위경도를 기상청 격자 좌표로 변환한다.

        기상청 DFS 격자 변환 공식을 그대로 사용한다.
        """
        import math

        re = 6371.00877 / 5.0
        slat1 = math.radians(30.0)
        slat2 = math.radians(60.0)
        olon = math.radians(126.0)
        olat = math.radians(38.0)
        xo = 43
        yo = 136

        sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
        sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
        sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
        sf = math.pow(sf, sn) * math.cos(slat1) / sn
        ro = math.tan(math.pi * 0.25 + olat * 0.5)
        ro = re * sf / math.pow(ro, sn)

        ra = math.tan(math.pi * 0.25 + math.radians(lat) * 0.5)
        ra = re * sf / math.pow(ra, sn)
        theta = math.radians(lon) - olon
        if theta > math.pi:
            theta -= 2.0 * math.pi
        if theta < -math.pi:
            theta += 2.0 * math.pi
        theta *= sn

        x = int(ra * math.sin(theta) + xo + 0.5)
        y = int(ro - ra * math.cos(theta) + yo + 0.5)
        return x, y

    def _get_kma_base_datetime(self) -> Tuple[str, str]:
        """
        기상청 초단기예보 기준 발표 시각을 계산한다.

        30분 단위 발표를 가정하고, 안정적으로 이전 슬롯을 사용한다.
        """
        now = datetime.now() - timedelta(minutes=45)
        minute = 30 if now.minute >= 30 else 0
        base = now.replace(minute=minute, second=0, microsecond=0)
        return base.strftime("%Y%m%d"), base.strftime("%H%M")

    def _parse_kma_items(self, items: list) -> Dict[str, str]:
        """기상청 예보 item 목록에서 현재와 가장 가까운 SKY/PTY를 읽는다."""
        if not items:
            raise ValueError("기상청 응답 item이 비어 있습니다.")

        grouped: Dict[Tuple[str, str], Dict[str, str]] = {}
        for item in items:
            fcst_date = item.get("fcstDate", "")
            fcst_time = item.get("fcstTime", "")
            category = item.get("category", "")
            fcst_value = str(item.get("fcstValue", ""))
            key = (fcst_date, fcst_time)
            grouped.setdefault(key, {})[category] = fcst_value

        now_key = datetime.now().strftime("%Y%m%d%H%M")
        ordered_keys = sorted(grouped.keys(), key=lambda key: f"{key[0]}{key[1]}")

        selected_key = ordered_keys[0]
        for key in ordered_keys:
            if f"{key[0]}{key[1]}" >= now_key:
                selected_key = key
                break

        selected = grouped[selected_key]
        pty = selected.get("PTY", "0")
        sky = selected.get("SKY", "")
        return self._map_kma_forecast(pty, sky)

    def _map_kma_forecast(self, pty: str, sky: str) -> Dict[str, str]:
        """기상청 PTY/SKY 값을 앱 카테고리로 매핑한다."""
        if pty in {"1", "2", "4", "5", "6"}:
            return {"emoji": "🌧️", "text": "비"}
        if pty in {"3", "7"}:
            return {"emoji": "❄️", "text": "눈"}
        if sky == "1":
            return {"emoji": "☀️", "text": "맑음"}
        if sky in {"3", "4"}:
            return {"emoji": "⛅", "text": "흐림"}
        return {"emoji": "⛅", "text": "흐림"}
