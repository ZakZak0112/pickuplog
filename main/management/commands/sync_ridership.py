# main/management/commands/sync_ridership.py (기간 옵션 처리 로직 완성)

import re
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from main.models import StationDict, RidershipDaily, LostItem
from django.utils import timezone

load_dotenv()
API_KEY = os.getenv("SEOUL_API_KEY", "sample")
API_BASE_URL = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/CardSubwayStatsNew/'

def normalize_line_code(line_name):
    if '호선' in line_name:
        match = re.search(r'(\d+)호선', line_name)
        if match:
            return f"LINE{match.group(1)}"
    return line_name.upper().replace(' ', '').replace('-', '')

def normalize_station_name(raw_name):
    return re.sub(r'\(.*?\)', '', raw_name).strip()


class Command(BaseCommand):
    help = '서울시 지하철 승하차 인원 데이터를 API에서 조회하여 적재합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None)
        parser.add_argument('--from', dest='start_date', type=str, default=None)
        parser.add_argument('--to', dest='end_date', type=str, default=None)

    def handle(self, *args, **options):
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        target_date_str = options['date']

        dates_to_check = []

        try:
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y%m%d').date()
                end_date = datetime.strptime(end_date_str, '%Y%m%d').date()

                current_date = end_date
                while current_date >= start_date:
                    dates_to_check.append(current_date.strftime('%Y%m%d'))
                    current_date -= timedelta(days=1)

            elif target_date_str:
                dates_to_check.append(target_date_str)

            else:
                today = timezone.now().date()
                three_months_ago = today - timedelta(days=90)

                current_date = today
                while current_date >= three_months_ago:
                    dates_to_check.append(current_date.strftime('%Y%m%d'))
                    current_date -= timedelta(days=1)

        except ValueError:
            raise CommandError("날짜 형식이 잘못되었습니다. YYYYMMDD 형식으로 입력하세요.")

        # --- 로그 간소화 ---
        success_dates = []
        error_dates = 0

        for target_date in dates_to_check:
            API_URL = f'{API_BASE_URL}1/1000/{target_date}'

            try:
                response = requests.get(API_URL)
                response.raise_for_status()
                data = response.json()

                if 'CardSubwayStatsNew' in data:
                    rows = data['CardSubwayStatsNew']['row']
                    if rows:
                        success_dates.append(target_date)

                        self._sync_station_dict(rows)
                        self._sync_ridership_data(rows)
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

    # ---------------------------------------------    
    @transaction.atomic
    def _sync_station_dict(self, rows):
        added, skipped = 0, 0
        if isinstance(rows, dict):
            rows = [rows]

        for row in rows:
            raw_name = row.get('SBWY_STNS_NM')
            line_name = row.get('SBWY_ROUT_LN_NM')

            if not raw_name or not line_name:
                skipped += 1
                continue

            try:
                std_name = normalize_station_name(raw_name)
                line_code = normalize_line_code(line_name)

                obj, created = StationDict.objects.get_or_create(
                    station_name_raw=raw_name,
                    line_code=line_code,
                    defaults={
                        'station_name_std': std_name,
                        'is_transfer': False,
                    },
                )

                if created:
                    added += 1
            except:
                skipped += 1
                continue

        for std_name in StationDict.objects.values_list('station_name_std', flat=True).distinct():
            lines = StationDict.objects.filter(station_name_std=std_name)
            if lines.count() > 1:
                lines.update(is_transfer=True)

    # ---------------------------------------------    
    @transaction.atomic
    def _sync_ridership_data(self, rows):
        added, skipped = 0, 0

        for row in rows:
            raw_name = row.get('SBWY_STNS_NM')
            line_name = row.get('SBWY_ROUT_LN_NM')
            ride_date = row.get('USE_YMD')
            on_count = row.get('GTON_TNOPE')
            off_count = row.get('GTOFF_TNOPE')

            if not (raw_name and line_name and ride_date):
                skipped += 1
                continue

            try:
                line_code = normalize_line_code(line_name)
                station_std = StationDict.objects.filter(
                    station_name_raw=raw_name,
                    line_code=line_code
                ).values_list('station_name_std', flat=True).first()

                if not station_std:
                    skipped += 1
                    continue

                date_obj = datetime.strptime(ride_date, '%Y%m%d').date()
                boardings = int(on_count) if on_count else 0
                alightings = int(off_count) if off_count else 0
                total = boardings + alightings

                RidershipDaily.objects.update_or_create(
                    date=date_obj,
                    line_code=line_code,
                    station_name_std=station_std,
                    defaults={
                        'boardings': boardings,
                        'alightings': alightings,
                        'total': total
                    },
                )

            except:
                skipped += 1
                continue
