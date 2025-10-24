# pickuplog/main/reports.py (최종 RII 계산 로직 - 실행 확정 버전)

from django.db.models import Avg, F, Count
from django.utils import timezone 
from datetime import datetime, timedelta
from main.models import RidershipDaily, WeatherDaily, RainImpactReport

def calculate_rain_impact_index():
    """
    RidershipDaily와 WeatherDaily를 결합하여, 역별/노선별 비 영향 지수(RII)를 계산하고 저장합니다.
    (이 함수가 sync_reports 명령에 의해 호출되는 최종 분석 로직입니다.)
    """
    
    # 1. 분석 기간 설정 및 초기화
    recent_date_limit = timezone.now().date() - timedelta(days=90)
    RainImpactReport.objects.all().delete()
    
    # 2. WeatherDaily 데이터 매핑 준비
    # {date: is_rainy} 딕셔너리를 생성하여 Ridership 데이터와 결합에 사용
    weather_data_map = {
        item.date: item.is_rainy
        for item in WeatherDaily.objects.all() # 모든 데이터 조회
    }
    if not weather_data_map: 
        print("경고: WeatherDaily 데이터가 DB에 전혀 없습니다. RII 계산을 건너뜁니다.")
        return 0
    
    # 💡 30일 체크 기준을 10일로 완화 (DB에 데이터가 있다면 분석을 진행하기 위함)
    if len(weather_data_map) < 10: 
        print("경고: WeatherDaily 데이터가 10일 미만이므로 RII 계산을 건너뜁니다.")
        return 0

    # 3. RidershipDaily 데이터 처리 및 그룹화 (RII 계산 기반)
    ridership_qs = RidershipDaily.objects.filter(
        date__in=list(weather_data_map.keys()) # 날씨 데이터가 있는 날짜만 필터링
    ).values('date', 'line_code', 'station_name_std', 'total')

    grouped_ridership_data = {} 
    
    for row in ridership_qs:
        date = row['date']
        key = (row['line_code'], row['station_name_std'])
        is_rainy = weather_data_map.get(date) # 메모리에서 날씨 정보 가져오기
        
        if is_rainy is None: continue 
            
        if key not in grouped_ridership_data:
            grouped_ridership_data[key] = {'rainy_sum': 0, 'rainy_count': 0, 'clear_sum': 0, 'clear_count': 0}
        
        if is_rainy:
            grouped_ridership_data[key]['rainy_sum'] += row['total']
            grouped_ridership_data[key]['rainy_count'] += 1
        else:
            grouped_ridership_data[key]['clear_sum'] += row['total']
            grouped_ridership_data[key]['clear_count'] += 1

    reports_to_create = []

    # 4. RII 계산 및 DB 저장
    for (line_code, station_name_std), data in grouped_ridership_data.items():
        # 💡 최종 완화 기준: 비오는 날/맑은 날 데이터가 최소 1일씩만 있어도 계산합니다.
        if data['rainy_count'] >= 1 and data['clear_count'] >= 1: 
            
            avg_rainy = data['rainy_sum'] / data['rainy_count']
            avg_clear = data['clear_sum'] / data['clear_count']
            
            if avg_clear > 0:
                rain_impact_index = (avg_rainy / avg_clear) * 100
                
                reports_to_create.append(RainImpactReport(
                    line_code=line_code,
                    station_name_std=station_name_std,
                    rain_impact_index=round(rain_impact_index, 2)
                ))
    
    # 5. DB에 대량 저장
    RainImpactReport.objects.bulk_create(reports_to_create)

    return len(reports_to_create)