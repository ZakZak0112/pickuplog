from django.core.management.base import BaseCommand
from datetime import date, timedelta
import requests
import os

from main.models import BusDaily

from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SEOUL_API_KEY")
API_BASE_URL = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/CardBusStatisticsServiceNew/'


class Command(BaseCommand):
    help = '서울시 버스 승하차 인원 데이터를 API에서 조회하여 적재합니다.'

    def handle(self, *args, **options):

        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        dates_to_check = []

        d = start_date
        while d <= end_date:
            dates_to_check.append(d.strftime('%Y%m%d'))
            d += timedelta(days=1)

        #계산시작
        success_dates = []
        error_dates = 0

        for target_date in dates_to_check:
            API_URL = f'{API_BASE_URL}1/1000/{target_date}'

            try:
                response = requests.get(API_URL)
                response.raise_for_status()
                data = response.json()

                if 'CardBusStatisticsServiceNew' in data:
                    rows = data['CardBusStatisticsServiceNew']['row']
                    if rows:
                        success_dates.append(target_date)
                        self.sync_bus_data(rows)
                else:
                    error_dates += 1

            except Exception:
                error_dates += 1

        # --- 최종 요약 출력 ---
        if success_dates:
            self.stdout.write(self.style.SUCCESS(f"📊 총 {len(success_dates)}개 날짜에서 데이터 적재 성공"))
            first = min(success_dates)
            last = max(success_dates)
            self.stdout.write(self.style.SUCCESS(f"   기간: {first} ~ {last}"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ 적재된 데이터가 없습니다."))

        if error_dates > 0:
            self.stdout.write(self.style.WARNING(f"⚠️ {error_dates}개 날짜는 API 오류로 건너뜀"))

        self.stdout.write(self.style.SUCCESS("데이터 적재 완료"))

    def sync_bus_data(self, rows):
        for row in rows:
            BusDaily.objects.update_or_create(
                date=row.get('USE_YMD'),
                line_id=row.get('RTE_NO'),
                stops_id=row.get('STOPS_ID'),
                defaults={
                    'ride_on': row.get('GTON_TNOPE'),
                    'ride_off': row.get('GTOFF_TNOPE')
                }
            )