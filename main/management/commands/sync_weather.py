import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
from main.models import WeatherDaily
import xml.etree.ElementTree as ET
from urllib.parse import quote

class Command(BaseCommand):
    help = "기상청 ASOS XML 데이터(서울 108번)를 불러와 WeatherDaily에 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--start',
            type=str,
            help="시작일 (YYYYMMDD) — 기본: 최근 3개월 전"
        )
        parser.add_argument(
            '--end',
            type=str,
            help="종료일 (YYYYMMDD) — 기본: 어제"
        )

    def handle(self, *args, **options):
        today = datetime.today().date()
        default_end = today - timedelta(days=1)
        default_start = today - timedelta(days=90)

        start_date = options["start"] or default_start.strftime("%Y%m%d")
        end_date = options["end"] or default_end.strftime("%Y%m%d")

        self.stdout.write(self.style.NOTICE(
            f"[기상청 ASOS] {start_date} ~ {end_date} 데이터 수집 시작..."
        ))

        # 서비스키 안전 인코딩
        service_key = "ea75cf77fdfafd681baef485ee16d1438074896ad9380e8160ed5dfe87a4eb80"
        encoded_key = quote(service_key, safe='')  # URL 안전 인코딩

        url = (
            f"http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
            f"?serviceKey={encoded_key}"
            f"&dataType=XML"
            f"&numOfRows=500"
            f"&pageNo=1"
            f"&dataCd=ASOS"
            f"&dateCd=DAY"
            f"&startDt={start_date}"
            f"&endDt={end_date}"
            f"&stnIds=108"
        )

        response = requests.get(url)

        if response.status_code != 200:
            self.stderr.write(f"HTTP 오류: {response.status_code}")
            self.stderr.write(response.text[:500])
            return

        # XML 파싱
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            self.stderr.write("⚠ XML 파싱 실패")
            self.stderr.write(response.text[:500])
            return

        header = root.find("header")
        result_code = header.findtext("resultCode")
        result_msg = header.findtext("resultMsg")
        if result_code != "00":
            self.stderr.write(f"API 오류: {result_msg}")
            return

        items = root.find("body/items")
        if items is None:
            self.stderr.write("데이터가 없습니다.")
            return

        saved_count = 0
        for item in items.findall("item"):
            date_str = item.findtext("tm")
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

            avg_temp = item.findtext("avgTa")
            avg_temp = float(avg_temp) if avg_temp not in [None, ""] else None

            rain_mm = item.findtext("sumRn")
            rain_mm = float(rain_mm) if rain_mm not in [None, ""] else 0.0
            is_rainy = rain_mm > 0

            WeatherDaily.objects.update_or_create(
                date=date_obj,
                city_code="SEOUL",
                defaults={
                    "avg_temp": avg_temp,
                    "rain_mm": rain_mm,
                    "is_rainy": is_rainy,
                }
            )
            saved_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"✔ 수집 완료 — 총 {saved_count}건 저장됨."
        ))
