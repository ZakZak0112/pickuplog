from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from main.models import LostItem, WeatherDaily, RainImpactReport

def calculate_comprehensive_loss_analysis():
    """
    LostItem, WeatherDaily 데이터를 기반으로
    노선별 비 영향 지수(RII)를 계산하고 저장합니다.
    """

    # 분석 기간 설정 (최근 90일)
    recent_date_limit = timezone.now().date() - timedelta(days=90)

    # 기존 보고서 삭제
    RainImpactReport.objects.all().delete()
    reports_to_create = []

    # 1️⃣ 노선별 분실 건수 집계
    line_loss = (
        LostItem.objects
        .filter(registered_at__date__gte=recent_date_limit)
        .values('line')
        .annotate(lost_count=Count('id'))
    )

    # 2️⃣ 날씨 데이터 가져오기
    weather_days = WeatherDaily.objects.filter(date__gte=recent_date_limit)
    rainy_days_count = weather_days.filter(is_rainy=True).count()
    total_days_count = weather_days.count()

    # 3️⃣ 노선별 RII 계산
    for row in line_loss:
        line_code = row['line'] or '기타'
        lost_count = row['lost_count']

        # 단순 RII 예시: (비 오는 날 대비 분실 건수 비율) * 100
        rii = round((lost_count / (rainy_days_count or 1)) * 100, 2)

        report = RainImpactReport(
            line_code=line_code,
            station_name_std='전체',  # 노선 전체 기준
            rain_impact_index=rii
        )
        reports_to_create.append(report)

    # 4️⃣ DB 저장
    RainImpactReport.objects.bulk_create(reports_to_create)

    return len(reports_to_create)
