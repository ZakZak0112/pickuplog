# pickuplog/main/management/commands/sync_lostitem.py (API 기반 로직)

import requests
import json
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
import os
from dotenv import load_dotenv

from main.models import LostItem

# --- Helper Functions 및 Mapping (views.py에서 가져온 것) ---
def parse_date_and_make_aware(date_str):
    # ... (생략: views.py에서 정의된 parse_date_and_make_aware 로직)
    if not date_str or date_str.strip() in ['00:00.0', '']:
        return None
    date_part = date_str.strip().split(' ')[0]
    date_part = date_part.replace('/', '-')
    try:
        naive_datetime = datetime.strptime(date_part, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        return timezone.make_aware(
            naive_datetime, 
            timezone=timezone.get_current_timezone() 
        )
    except ValueError:
        return None 
# --- Helper Functions 끝 ---


class Command(BaseCommand):
    help = '서울시 공공 API를 통해 분실물 데이터를 가져와 LostItem 모델에 적재합니다. (API 기반)'

    # 💡 add_arguments 메서드가 없으므로, 인수를 요구하지 않습니다.
    
    def handle(self, *args, **options):
        load_dotenv()
        API_KEY = os.getenv("SEOUL_API_KEY", "6671454b426c6f763833785471726d") 
        BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/lostArticleInfo/1/1000/" 
        
        self.stdout.write(self.style.MIGRATE_HEADING('LostItem 데이터 동기화 시작...'))
        
        try:
            response = requests.get(BASE_URL, timeout=10)
            response.raise_for_status() 
            api_data = response.json()
            rows = api_data.get("lostArticleInfo", {}).get("row", [])
        except Exception as e:
            raise CommandError(f'API 호출 또는 JSON 디코딩 오류: {e}')
        
        if not rows:
             self.stdout.write(self.style.WARNING("API로부터 받은 데이터가 없습니다."))
             return
             
        # --- 기존 views.py에 있던 수동 리스트 및 처리 로직 재현 ---
        busList = ["중부운수", "대진여객", "원버스", "상진운수", "성원여객", "보성운수", "동성교통", "도선여객", "선진운수", "남성교통", "삼양교통"]
        taxiList = ["삼이택시", "동화통운", "고려운수", "경일운수", "동도자동차", "안전한택시", "양평운수", "대진흥업", "승진통상", "백제운수", "삼익택시", "새한택시", "경서운수", "대하운수", "동성상운",]

        success_count = 0
        
        with transaction.atomic():
            for data in rows:
                CSTD_PLC = data.get("CSTD_PLC", "")
                RCPL = data.get("RCPL", "")
                LOST_STTS = data.get("LOST_STTS", "")
                
                if CSTD_PLC.endswith("역"):
                    transport = "subway"
                    station_name = CSTD_PLC
                elif RCPL in busList:
                    transport = "bus"
                    station_name = ""
                elif RCPL in taxiList:
                    transport = "taxi"
                    station_name = ""
                # 💡 추가: 위에 해당하지 않는 모든 경우를 'etc'로 처리
                else: 
                    transport = "etc" # 기본값을 할당
                    station_name = ""
                try:
                    # DB 적재 (LostItem.objects.update_or_create)
                    # ... (코드가 길어 생략하지만, 실제 파일에는 모든 DB 필드 매핑 로직이 들어갑니다)
                    
                    obj, created = LostItem.objects.update_or_create(
                        item_id=data.get("LOST_MNG_NO"), # PK로 사용
                        # ... defaults dict 내용 ...
                        defaults={
                            # (모든 필드 매핑)
                            "transport": transport,
                            "station": station_name,
                            "category": data.get("LOST_KND"),
                            # ... (나머지 필드)
                        }
                    )
                    success_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"[{data.get('LOST_MNG_NO')}] 데이터 처리 오류: {e}"))
                    continue

        self.stdout.write(self.style.SUCCESS(f'✅ LostItem 데이터 동기화 완료! 총 {len(rows)}건 중 {success_count}건 적재/업데이트되었습니다.'))