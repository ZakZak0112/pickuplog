# main/management/commands/sync_ridership.py (기간 옵션 처리 로직 완성)

import re
import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from main.models import StationDict, RidershipDaily, LostItem # LostItem 임포트 추가 (옵션이지만 안전을 위해)
from django.utils import timezone # Timezone 사용을 위해 추가

# 환경 변수 로드 및 API 키 설정 (기존 코드 유지)
load_dotenv() 
API_KEY = os.getenv("SEOUL_API_KEY", "sample") 
API_BASE_URL = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/CardSubwayStatsNew/' 

# --- 데이터 정제 함수 (노선명, 역명 표준화)는 그대로 유지 ---
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
    help = '서울시 승하차 인원 데이터를 API에서 직접 조회하여 적재합니다. (기간 지정 또는 최근 7일 자동 검색)'

    def add_arguments(self, parser):
        # 💡 수정: --from과 --to는 Django가 내부적으로 'from', 'to'로 인식하므로, 변수명에 주의합니다.
        parser.add_argument(
            '--date', type=str, default=None, 
            help='특정 날짜 조회 (YYYYMMDD 형식)'
        )
        parser.add_argument(
            '--from', dest='start_date', type=str, default=None,
            help='조회 시작 날짜 (YYYYMMDD 형식)'
        )
        parser.add_argument(
            '--to', dest='end_date', type=str, default=None,
            help='조회 종료 날짜 (YYYYMMDD 형식)'
        )
    
    # [handle 메서드 로직 전면 수정]
    def handle(self, *args, **options):
        # 1. 옵션 값 가져오기 (dest 이름을 사용)
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        target_date_str = options['date']
        days_to_check = 7
        
        dates_to_check = []
        
        try:
            if start_date_str and end_date_str:
                # 기간이 지정된 경우: 모든 날짜를 역순으로 생성하여 API 서버 부담을 줄입니다.
                start_date = datetime.strptime(start_date_str, '%Y%m%d').date()
                end_date = datetime.strptime(end_date_str, '%Y%m%d').date()
                
                # 날짜 리스트 생성 (종료일 -> 시작일 순서)
                current_date = end_date
                while current_date >= start_date:
                    dates_to_check.append(current_date.strftime('%Y%m%d'))
                    current_date -= timedelta(days=1)

            elif target_date_str:
                # 특정 날짜가 지정된 경우
                dates_to_check.append(target_date_str)
            
            else:
                # 옵션이 없을 경우: 최근 7일간 역순 검색 로직 (기존 로직 유지)
                dates_to_check = [
                    (timezone.now().date() - timedelta(days=i)).strftime('%Y%m%d') 
                    for i in range(1, days_to_check + 1)
                ]
        except ValueError:
            raise CommandError("날짜 형식이 잘못되었습니다. YYYYMMDD 형식으로 입력하세요.")


        # 2. 데이터 동기화 루프 시작
        target_date_found = False
        
        for target_date in dates_to_check:
            API_URL = f'{API_BASE_URL}1/1000/{target_date}' 
            self.stdout.write(self.style.NOTICE(f'API 데이터 다운로드 시도: {target_date}'))

            try:
                response = requests.get(API_URL)
                response.raise_for_status() 
                data = response.json()
                
                if 'CardSubwayStatsNew' in data:
                    rows = data['CardSubwayStatsNew']['row']
                    if rows:
                        self.stdout.write(self.style.SUCCESS(f'✅ 데이터 찾기 성공! 날짜: {target_date}'))
                        
                        # 적재 및 정제 실행
                        self._sync_station_dict(rows)
                        self._sync_ridership_data(rows)
                        
                        target_date_found = True
                        
                        # 기간 지정이 없거나 (자동 검색) 특정 날짜 지정만 했을 경우, 
                        # 성공 시 반복을 멈춥니다. 기간 지정 시에는 끝까지 실행합니다.
                        if not (start_date_str and end_date_str):
                            break 
                            
                    else:
                        self.stdout.write(self.style.WARNING(f'데이터 없음. 다음 날짜 시도.'))

                else:
                    error_msg = data.get('RESULT', {}).get('MESSAGE', '알 수 없는 API 오류')
                    self.stdout.write(self.style.WARNING(f'API 오류 응답: {error_msg}. 다음 날짜 시도.'))

            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f'API 호출 실패 ({target_date}): {e}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('API 응답이 유효한 JSON 형식이 아닙니다.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'치명적 오류 발생: {e}'))

        if not target_date_found and not (start_date_str and end_date_str):
            raise CommandError(f'🚨 지난 {days_to_check}일간 데이터 동기화에 실패했습니다. API 상태를 확인하세요.')
        elif not target_date_found and (start_date_str and end_date_str):
             self.stdout.write(self.style.WARNING(f'경고: 지정된 기간 ({start_date_str}~{end_date_str}) 내에 적재된 데이터가 없습니다.'))

        self.stdout.write(self.style.SUCCESS('데이터 적재 및 정제가 완료되었습니다.'))


    # 3. 데이터 적재 함수 (로직 구현 필요)
    # NOTE: 이 함수들은 이전과 동일하게 rows 리스트를 받아 처리해야 합니다.
    # 이 단계에서는 로직 구현 없이 성공 가정하고 진행합니다.

    @transaction.atomic
    def _sync_station_dict(self, rows):
        """StationDict를 먼저 채워서 역 표준화 정보를 확보합니다. (JSON rows 처리)"""
        # 실제 로직 구현 필요
        self.stdout.write(self.style.MIGRATE_HEADING('1/2단계: StationDict 적재 (로직 구현 필요)'))
        pass

    @transaction.atomic
    def _sync_ridership_data(self, rows):
        """RidershipDaily 테이블에 일별 승하차 인원 데이터를 적재합니다. (JSON rows 처리)"""
        # 실제 로직 구현 필요
        self.stdout.write(self.style.MIGRATE_HEADING('2/2단계: RidershipDaily 적재 (로직 구현 필요)'))
        pass