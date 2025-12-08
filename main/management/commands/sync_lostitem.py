from main.models import LostItem, StationDict
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import requests
from django.db import transaction
from django.core.management.base import BaseCommand
from datetime import datetime
import os

def parse_date_and_make_aware(date_str): 
    if not date_str or date_str.strip() in ['00:00.0', '']: 
        return None 
    date_part = date_str.strip().split(' ')[0].replace('/', '-') 
    try: 
        naive_datetime = datetime.strptime(date_part, '%Y-%m-%d').replace(hour=0, minute=0, second=0) 
        return timezone.make_aware(naive_datetime, timezone.get_current_timezone()) 
    except ValueError: 
        return None

class Command(BaseCommand):
    help = "기상청 ASOS XML 데이터(서울 108번)를 불러와 WeatherDaily에 저장합니다."


    def handle(self, *args, **options):
        three_months_ago = timezone.now() - relativedelta(months=3)
        start_index = 1
        page_size = 1000
        total_success = 0
        total_subway = 0
        total_bus = 0
        total_taxi = 0
        total_etc = 0
        API_KEY = "6671454b426c6f763833785471726d"

        while True:
            end_index = start_index + page_size - 1
            BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/lostArticleInfo/{start_index}/{end_index}/"

            try:
                response = requests.get(BASE_URL, timeout=10)
                response.raise_for_status()
                rows = response.json().get("lostArticleInfo", {}).get("row", [])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{start_index}-{end_index}] API 호출 오류: {e}"))
                break

            if not rows:
                break  # 더 이상 데이터 없음
            
            subway_stations = {sd.station_name_raw for sd in StationDict.objects.all()}
            busList = ["중부운수", "대진여객", "원버스", "상진운수", "성원여객", "보성운수", "동성교통", "도선여객", "선진운수", "남성교통", "삼양교통", "한성운수", "아진교통", "진화운수", "서울버스", "제일교통"] 
            taxiList = ["삼이택시", "동화통운", "고려운수", "경일운수", "동도자동차", "안전한택시", "양평운수", "대진흥업", "승진통상", "백제운수", "삼익택시", "새한택시", "경서운수", "대하운수", "동성상운"]

            with transaction.atomic():
                for data in rows:
                    registered_at = parse_date_and_make_aware(data.get("REG_YMD"))
                    if not registered_at or registered_at < three_months_ago:
                        continue  # 최근 3개월 이전 데이터는 건너뜀

                    CSTD_PLC = data.get("CSTD_PLC", "")
                    RCPL = data.get("RCPL", "")

                    station_name = ""
                    if CSTD_PLC in subway_stations:
                        transport = "subway"
                        station_name = CSTD_PLC
                        total_subway += 1
                    elif RCPL in busList:
                        transport = "bus"
                        total_bus += 1
                    elif RCPL in taxiList:
                        transport = "taxi"
                        total_taxi += 1
                    else:
                        transport = "etc"
                        self.stdout.write(CSTD_PLC)
                        self.stdout.write(RCPL)
                        total_etc += 1

                    received_at = parse_date_and_make_aware(data.get("RCV_YMD"))

                    LostItem.objects.update_or_create(
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
                    total_success += 1

            start_index += page_size

        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] 최근 3개월 데이터 동기화 완료! 총 {total_success}건 적재/업데이트됨."))
        self.stdout.write(f"   - 지하철: {total_subway}건")
        self.stdout.write(f"   - 버스: {total_bus}건")
        self.stdout.write(f"   - 택시: {total_taxi}건")
        self.stdout.write(f"   - 기타: {total_etc}건")
