# pickuplog/main/reports.py

from django.db.models import Avg
import random
from main.models import RidershipDaily, RainImpactReport

# NOTE: 이 분석 로직은 비 오는 날과 비 안 오는 날을 구분해야 하므로,
# 실제로는 'WeatherDaily' 모델(날짜, 강우 여부 필드 포함)이 반드시 필요합니다.
# 현재 모델 부재로 인해 계산은 임시 더미(Random) 로직을 사용합니다.

def calculate_rain_impact_index():
    """
    RidershipDaily 데이터를 기반으로 역별/노선별 비 영향 지수(RII)를 계산합니다.
    (WeatherDaily 모델 부재로 임시 RII를 사용하며, 계산 후 RainImpactReport에 적재합니다.)
    """
    
    # RidershipDaily에 있는 모든 고유 역/노선 조합을 가져옵니다.
    unique_stations = RidershipDaily.objects.values(
        'line_code', 'station_name_std'
    ).distinct()
    
    reports_count = 0
    
    for station in unique_stations:
        line_code = station['line_code']
        station_name_std = station['station_name_std']
        
        try:
            # -------------------------------------------------------------
            # [실제 로직 대체 부분]
            # 실제 RII = (비 오는 날 평균) / (비 안 오는 날 평균) * 100 
            # 이 코드가 완성되려면 WeatherDaily 모델이 먼저 필요합니다.
            
            # 임시 로직: 95.0 ~ 110.0 사이의 랜덤 값 생성 (더미 데이터)
            rain_impact_index = round(random.uniform(95.0, 110.0), 2)
            # -------------------------------------------------------------
            
            # RainImpactReport 모델에 결과 저장 또는 업데이트
            RainImpactReport.objects.update_or_create(
                line_code=line_code,
                station_name_std=station_name_std,
                defaults={
                    'rain_impact_index': rain_impact_index
                }
            )
            reports_count += 1
            
        except Exception as e:
            print(f"[{line_code}] {station_name_std} 보고서 생성 오류: {e}")
            continue

    return reports_count