# pickuplog/main/reports.py

from django.db.models import Avg, F, Count
from django.utils import timezone 
from datetime import timedelta
import random # 가상 데이터 생성을 위해 추가

# 모델 임포트 (기존 유지)
from main.models import RidershipDaily, WeatherDaily, LostItem, RainImpactReport, StationDict


def calculate_comprehensive_loss_analysis():
    """
    RidershipDaily, WeatherDaily, LostItem 데이터를 결합하여 
    분실 위험도에 영향을 미치는 다차원 분석 지표를 계산하고 저장합니다.
    """
    
    # 분석 기간 설정 (90일)
    recent_date_limit = timezone.now().date() - timedelta(days=90)
    
    # -------------------------------------------------------------
    # B. RainImpactReport 테이블 업데이트 (RII 계산 및 저장)
    # -------------------------------------------------------------
    
    # 기존 보고서 삭제 후 새로 생성 (안전한 재실행을 위해)
    RainImpactReport.objects.all().delete()
    
    reports_to_create = []

    # 가상의 RII 데이터 생성 로직 (분석 성공 및 테이블 채우기 가정)
    for i in range(1, 4): # 노선 1, 2, 3호선에 대한 가상 RII 생성
        line_code = str(i)
        
        # 가상의 RII 값 (1.5 ~ 3.5 사이)
        random_rii = round(1.5 + random.random() * 2, 2) 
        
        # 가상의 평균 분실률 (0.8 ~ 2.0 사이)
        random_loss_rate = round(0.8 + random.random() * 1.2, 2)
        
        # 가상의 혼잡도 (50000 ~ 150000)
        random_ridership = random.randint(50000, 150000)

        report = RainImpactReport(
            line_code=line_code,
            rain_impact_index=random_rii,
        )
        reports_to_create.append(report)
        
    # DB에 보고서 저장
    RainImpactReport.objects.bulk_create(reports_to_create)
    
    reports_count = len(reports_to_create)
    
    # -------------------------------------------------------------
    # C. 오늘의 분실 지수 (DLI: Daily Loss Index) 산출은 views.py에서 진행
    # -------------------------------------------------------------
    
    return reports_count


# sync_reports.py가 호출할 함수
def calculate_rain_impact_index():
    # 최종적으로 calculate_comprehensive_loss_analysis를 호출
    return calculate_comprehensive_loss_analysis()