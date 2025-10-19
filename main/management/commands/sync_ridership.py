# main/management/commands/sync_ridership.py

import re
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv # 'pip install python-dotenv' 필요

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from main.models import StationDict, RidershipDaily

# 환경 변수 로드 및 API 키 설정
load_dotenv() 
API_KEY = os.getenv("SEOUL_API_KEY", "sample") # 키가 없으면 'sample' 사용
API_BASE_URL = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/CardSubwayStatsNew/' 

# --- 데이터 정제 함수 (노선명, 역명 표준화) ---

def normalize_line_code(line_name):
    """노선명(예: 1호선)을 표준 코드(예: LINE1)로 변환"""
    if '호선' in line_name:
        match = re.search(r'(\d+)호선', line_name)
        if match:
            return f"LINE{match.group(1)}"
    return line_name.upper().replace(' ', '').replace('-', '')


def normalize_station_name(raw_name):
    """괄호 안의 호선 정보 제거"""
    return re.sub(r'\(.*?\)', '', raw_name).strip()

# ----------------------------------------

class Command(BaseCommand):
    help = '서울시 승하차 인원 데이터를 API에서 직접 조회하여 적재합니다. (최근 7일 자동 검색)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None, 
            help='조회 날짜 (YYYYMMDD 형식, 지정하지 않으면 최근 7일간 자동 검색)'
        )

    def handle(self, *args, **options):
        days_to_check = 7 
        target_date_found = False

        # 지정된 날짜가 있으면 그 날짜만 시도하고, 없으면 역순으로 검색
        dates_to_check = [options['date']] if options['date'] else [
            (datetime.today() - timedelta(days=i)).strftime('%Y%m%d') 
            for i in range(1, days_to_check + 1)
        ]

        for target_date in dates_to_check:
            # API는 한 번에 1000개의 레코드만 조회 가능합니다.
            API_URL = f'{API_BASE_URL}1/1000/{target_date}' 
            self.stdout.write(self.style.NOTICE(f'API 데이터 다운로드 시도: {target_date}'))

            try:
                response = requests.get(API_URL)
                response.raise_for_status() 
                data = response.json()
                
                # API 성공 응답 확인 및 데이터 추출
                if 'CardSubwayStatsNew' in data:
                    rows = data['CardSubwayStatsNew']['row']
                    if rows:
                        self.stdout.write(self.style.SUCCESS(f'✅ 데이터 찾기 성공! 날짜: {target_date}'))
                        
                        # 2. StationDict 적재 및 3. RidershipDaily 적재
                        self._sync_station_dict(rows)
                        self._sync_ridership_data(rows)
                        
                        target_date_found = True
                        break # 데이터 적재 성공 후 반복문 종료

                # 데이터 없음 (INFO-200/INFO-300) 또는 기타 오류 메시지 출력 후 다음 날짜 시도
                else:
                    error_msg = data.get('RESULT', {}).get('MESSAGE', '알 수 없는 API 오류')
                    self.stdout.write(self.style.WARNING(f'API 오류 응답: {error_msg}. 이전 날짜 시도.'))
                    if options['date']: # 지정된 날짜인데 실패하면 루프 종료
                        raise CommandError(f'지정된 날짜 데이터 동기화 실패: {target_date}')
                    continue

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f'API 호출 실패 ({target_date}): {e}. 네트워크 문제 확인.'))
                continue
            except json.JSONDecodeError:
                raise CommandError('API 응답이 유효한 JSON 형식이 아닙니다. (API 키/URL 오류)')
            except Exception as e:
                raise CommandError(f'데이터 처리 중 치명적인 오류 발생: {e}')
        
        if not target_date_found:
            raise CommandError(f'🚨 지난 {days_to_check}일간 데이터 동기화에 실패했습니다. API 상태를 확인하세요.')

        self.stdout.write(self.style.SUCCESS('데이터 적재 및 정제가 완료되었습니다.'))


    # NOTE: 이하 _sync_station_dict와 _sync_ridership_data 함수는 JSON 리스트 'rows'를 처리하도록 
    # 구현되어야 합니다. 이 단계에서는 로직 구현 없이 성공 가정하고 진행합니다.

    def _sync_station_dict(self, rows):
        """StationDict를 먼저 채워서 역 표준화 정보를 확보합니다. (JSON rows 처리)"""
        # 실제 로직: rows를 순회하며 station_name_raw, line_code를 추출하고 StationDict를 업데이트/생성해야 합니다.
        self.stdout.write(self.style.MIGRATE_HEADING('1/2단계: StationDict 적재 (로직 생략)'))
        pass

    @transaction.atomic
    def _sync_ridership_data(self, rows):
        """RidershipDaily 테이블에 일별 승하차 인원 데이터를 적재합니다. (JSON rows 처리)"""
        # 실제 로직: rows를 순회하며 date, line_code, station_name_std, total 등을 추출하고 RidershipDaily를 업데이트/생성해야 합니다.
        self.stdout.write(self.style.MIGRATE_HEADING('2/2단계: RidershipDaily 적재 (로직 생략)'))
        pass