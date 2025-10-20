import pandas as pd
import requests_cache
from retry_requests import retry
import openmeteo_requests

from django.core.management.base import BaseCommand
from main.models import WeatherDaily

class Command(BaseCommand):
    help = "Sync past weather data for Seoul using Open-Meteo kma_seamless model"

    def handle(self, *args, **options):
        # Setup Open-Meteo API client with cache and retry
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        client = openmeteo_requests.Client(session=retry_session)

        # API 요청 파라미터
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 37.56,          # 서울 위도
            "longitude": 127.0,         # 서울 경도
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "rain_sum"],
            "models": "kma_seamless",
            "past_days": 92,             # 과거 92일치
            "timezone": "Asia/Seoul"
        }

        # API 호출
        responses = client.weather_api(url, params=params)
        response = responses[0]  # 단일 좌표만 사용

        # Daily 데이터 처리
        daily = response.Daily()
        dates = pd.to_datetime(daily.Time(), unit="s")  # pandas Timestamp
        temp_max = daily.Variables(1).ValuesAsNumpy()
        temp_min = daily.Variables(2).ValuesAsNumpy()
        rain_sum = daily.Variables(3).ValuesAsNumpy()

        # DataFrame 생성
        df = pd.DataFrame({
            "date": dates,
            "avg_temp": (temp_max + temp_min) / 2,
            "rain_mm": rain_sum
        })
        # 결측치 처리
        df["rain_mm"] = df["rain_mm"].fillna(0)
        df["is_rainy"] = df["rain_mm"] > 0

        # 날짜 타입 변환 (Django DateField 호환)
        df["date"] = df["date"].dt.date

        # DB 저장
        for _, row in df.iterrows():
            WeatherDaily.objects.update_or_create(
                date=row["date"],
                city_code="SEOUL",
                defaults={
                    "avg_temp": row["avg_temp"],
                    "rain_mm": row["rain_mm"],
                    "is_rainy": row["is_rainy"]
                }
            )

        self.stdout.write(self.style.SUCCESS(f"Successfully synced {len(df)} days of weather data for Seoul"))
