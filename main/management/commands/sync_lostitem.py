import requests
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
import os
from dotenv import load_dotenv

from main.models import LostItem, StationDict

# --- Helper Functions ---
def parse_date_and_make_aware(date_str):
    """
    문자열 날짜를 받아 timezone aware datetime으로 변환.
    API에서 날짜가 없거나 형식이 잘못되면 None 반환.
    """
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
    help = '서울시 공공 API를 통해 분실물 데이터를 가져와 LostItem 모델에 적재합니다. (transport 분류 개선)'

    def handle(self, *args, **options):
        load_dotenv()
        API_KEY = os.getenv("SEOUL_API_KEY", "6671454b426c6f763833785471726d") 
        BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/lostArticleInfo/1/1000/" 
        
        self.stdout.write(self.style.MIGRATE_HEADING('LostItem 데이터 동기화 시작...'))
        
        # 서울 지하철역 목록 로드 (StationDict 활용)
        subway_stations = set()
        for sd in StationDict.objects.all():
            subway_stations.add(sd.station_name_raw)
            # "강남역" 형태로도 추가
            if not sd.station_name_raw.endswith('역'):
                subway_stations.add(sd.station_name_raw + '역')
            # 표준명으로도 추가
            subway_stations.add(sd.station_name_std)
            if not sd.station_name_std.endswith('역'):
                subway_stations.add(sd.station_name_std + '역')
        
        self.stdout.write(f'[INFO] 서울 지하철역 {len(subway_stations)}개 로드 완료')
        
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
             
        busList = ["중부운수", "대진여객", "원버스", "상진운수", "성원여객", "보성운수",
                   "동성교통", "도선여객", "선진운수", "남성교통", "삼양교통"]
        taxiList = ["삼이택시", "동화통운", "고려운수", "경일운수", "동도자동차", "안전한택시",
                    "양평운수", "대진흥업", "승진통상", "백제운수", "삼익택시", "새한택시",
                    "경서운수", "대하운수", "동성상운",]

        success_count = 0
        subway_count = 0
        train_count = 0
        
        with transaction.atomic():
            for data in rows:
                CSTD_PLC = data.get("CSTD_PLC", "")
                RCPL = data.get("RCPL", "")
                
                # 교통수단 및 역명 판별 (개선됨!)
                transport = "etc"
                station_name = ""
                
                if CSTD_PLC.endswith("역"):
                    # "역"으로 끝나는 경우
                    # 1. StationDict에 있으면 지하철역
                    if CSTD_PLC in subway_stations:
                        transport = "subway"
                        station_name = CSTD_PLC
                        subway_count += 1
                    else:
                        # 2. StationDict에 없으면 기차역 등 기타
                        transport = "etc"
                        station_name = CSTD_PLC
                        train_count += 1
                        
                elif RCPL in busList:
                    transport = "bus"
                    station_name = ""
                    
                elif RCPL in taxiList:
                    transport = "taxi"
                    station_name = ""
                    
                else: 
                    transport = "etc"
                    station_name = ""
                
                # 날짜 필드 처리
                registered_at = parse_date_and_make_aware(data.get("REG_YMD"))
                received_at = parse_date_and_make_aware(data.get("RCV_YMD"))
                
                try:
                    # DB 적재
                    obj, created = LostItem.objects.update_or_create(
                        item_id=data.get("LOST_MNG_NO"),
                        defaults={
                            "transport": transport,
                            "station": station_name,
                            "category": data.get("LOST_KND"),
                            "item_name": data.get("LOST_NM"),
                            "status": data.get("LOST_STTS"),
                            "is_received": data.get("RCPT_YN") == "Y",
                            "registered_at": registered_at,
                            "received_at": received_at,
                            "description": data.get("LGS_DTL_CN"),
                            "storage_location": CSTD_PLC,
                            "registrar_id": data.get("LOST_RGTR_ID"),
                            "pickup_company_location": RCPL,
                            "views": int(data.get("INQ_CNT") or 0),
                        }
                    )
                    success_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"[{data.get('LOST_MNG_NO')}] 데이터 처리 오류: {e}"))
                    continue

        self.stdout.write(self.style.SUCCESS(
            f'[SUCCESS] LostItem 데이터 동기화 완료! 총 {len(rows)}건 중 {success_count}건 적재/업데이트되었습니다.'
        ))
        self.stdout.write(f'   - 지하철역: {subway_count}건')
        self.stdout.write(f'   - 기차역/기타: {train_count}건')