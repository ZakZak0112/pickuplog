import os
import sys
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware
from django.conf import settings
from main.models import LostItem  # 앱 이름 맞게 변경

# ---------------------------------------------------------------------
API_KEY = "724b6a686a7268643431725653704f"
if not API_KEY:
    raise ValueError("환경변수 'SEOUL_API_KEY'가 설정되어 있지 않습니다!")

BASE_URL = "http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START_INDEX}/{END_INDEX}/"
SERVICE = "lostArticleInfo"
BATCH_SIZE = 1000  # 한 번에 가져오는 데이터 수
# ---------------------------------------------------------------------

def parse_date(date_str):
    """날짜 문자열 안전 파싱 + timezone aware"""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.0"):
        try:
            dt = datetime.strptime(date_str, fmt)
            # timezone 적용
            if settings.USE_TZ:
                dt = make_aware(dt)
            return dt
        except ValueError:
            continue
    print(f"날짜 형식 오류: {date_str}", file=sys.stderr)
    return None

class Command(BaseCommand):
    help = "서울시 분실물 데이터를 batch 단위로 안전하게 수집/DB 저장"

    def fetch_lost_items_batch(self, start_index, end_index):
        """API 요청 후 데이터 반환"""
        url = BASE_URL.format(KEY=API_KEY, SERVICE=SERVICE, START_INDEX=start_index, END_INDEX=end_index)
        response = requests.get(url)
        if response.status_code != 200:
            print(f"API 요청 실패: {response.status_code}", file=sys.stderr)
            return []

        try:
            data = response.json()
        except ValueError:
            print("JSON 디코딩 실패", file=sys.stderr)
            print(response.text[:500], file=sys.stderr)
            return []

        rows = data.get("lostArticleInfo", {}).get("row", [])
        return rows

    def save_lost_items_bulk(self, rows):
        """데이터를 bulk_create로 DB 저장"""
        objs_to_create = []

        for row in rows:
            item_id = row.get("LOST_MNG_NO")
            if not item_id:
                continue  # 필수 key 없으면 건너뜀

            try:
                registered_at = parse_date(row.get("REG_YMD"))
                received_at = parse_date(row.get("RCV_YMD"))

                objs_to_create.append(
                    LostItem(
                        item_id=item_id,
                        transport=row.get("TRSPT"),
                        line=row.get("LINE"),
                        station=row.get("STATION"),
                        category=row.get("LOST_KND"),
                        item_name=row.get("LOST_NM"),
                        status=row.get("LOST_STTS"),
                        is_received=row.get("IS_RECEIVED") == "Y",
                        registered_at=registered_at,
                        received_at=received_at,
                        description=row.get("LGS_DTL_CN"),
                        storage_location=row.get("CSTD_PLC"),
                        registrar_id=row.get("LOST_RGTR_ID"),
                        pickup_company_location=row.get("RCPL"),
                        views=int(row.get("INQ_CNT") or 0)
                    )
                )
            except Exception as e:
                print(f"저장 실패: {item_id} 에러: {e}", file=sys.stderr)

        if objs_to_create:
            LostItem.objects.bulk_create(objs_to_create, ignore_conflicts=True)

    def handle(self, *args, **options):
        """메인 실행 함수"""
        start_index = 1

        while True:
            end_index = start_index + BATCH_SIZE - 1
            rows = self.fetch_lost_items_batch(start_index, end_index)
            if not rows:
                break

            self.save_lost_items_bulk(rows)
            # 진행 로그
            total_saved = len(rows)
            print(f"{start_index}~{end_index}: {total_saved}건 저장 완료", file=sys.stdout)

            start_index += BATCH_SIZE

        print("분실물 데이터 전체 수집 완료!", file=sys.stdout)
