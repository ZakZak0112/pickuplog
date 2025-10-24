import pandas as pd
import requests_cache
from retry_requests import retry
import openmeteo_requests
from datetime import datetime

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
        
        # 데이터 추출
        temp_max = daily.Variables(1).ValuesAsNumpy()
        temp_min = daily.Variables(2).ValuesAsNumpy()
        rain_sum = daily.Variables(3).ValuesAsNumpy()
        
        # 실제 데이터 길이 확인
        num_days = len(temp_max)
        start_timestamp = daily.Time()
        
        self.stdout.write(f"Start timestamp: {start_timestamp}")
        self.stdout.write(f"Start date: {datetime.fromtimestamp(start_timestamp)}")
        self.stdout.write(f"Number of data points: {num_days}")
        self.stdout.write(f"temp_max length: {len(temp_max)}")
        self.stdout.write(f"temp_min length: {len(temp_min)}")
        self.stdout.write(f"rain_sum length: {len(rain_sum)}")
        
        # 날짜 범위 생성
        dates = pd.date_range(
            start=pd.Timestamp(start_timestamp, unit="s"),
            periods=num_days,
            freq="D"
        )
        
        self.stdout.write(f"\nFirst 5 dates:")
        for d in dates[:5]:
            self.stdout.write(f"  {d.date()}")

        # DataFrame 생성
        df = pd.DataFrame({
            "date": [d.date() for d in dates],
            "avg_temp": (temp_max + temp_min) / 2,
            "rain_mm": rain_sum
        })
        
        # 결측치 처리
        df["rain_mm"] = df["rain_mm"].fillna(0)
        df["is_rainy"] = df["rain_mm"] > 0

        # DB 저장
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            weather_obj, created = WeatherDaily.objects.update_or_create(
                date=row["date"],
                city_code="SEOUL",
                defaults={
                    "avg_temp": float(row["avg_temp"]),
                    "rain_mm": float(row["rain_mm"]),
                    "is_rainy": bool(row["is_rainy"])
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ Created: {weather_obj.date}")
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully synced {len(df)} days of weather data for Seoul"))
        self.stdout.write(self.style.SUCCESS(f"Created: {created_count}, Updated: {updated_count}"))