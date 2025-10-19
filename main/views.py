from django.db.models import Q, Count, Sum, Avg # Avg 추가
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone 
from django.conf import settings 
from django.contrib import messages 
from django.db import IntegrityError 
from django.http import HttpResponse

# 프로젝트 모델 임포트
from .models import LostItem, RidershipDaily, RainImpactReport, WeatherDaily 
from .forms import LostItemSearchForm, LostItemForm, LostItemCsvUploadForm 

# API/CSV 처리는 뷰에서 제거 (별도 커맨드 파일로 분리해야 함)
import csv
from io import TextIOWrapper 

# ----------------------------------------------------------------------
# Helper Functions (도우미 함수)
# ----------------------------------------------------------------------

# 날짜/시간 형식 변환 및 Timezone 적용 (기존 코드 유지)
def parse_date_and_make_aware(date_str):
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


# ----------------------------------------------------------------------
# 1. PickUpLog 핵심 뷰: 오늘의 분실 예보
# ----------------------------------------------------------------------

def home(request):
    """
    PickUpLog 홈 화면 뷰: 사용자가 입력한 노선에 대한 오늘의 분실 예보를 제공합니다.
    """
    # 1. 사용자 입력 받기 (오늘 날씨와 기본 노선을 가정)
    line_input = request.GET.get('line', 'LINE2') # 기본값: 2호선
    date_condition = request.GET.get('condition', '평소') 
    is_rainy_today = (date_condition == '비오는 날')
    
    # 분석 기준 날짜 (가장 최근 동기화된 날짜를 사용)
    latest_date = RidershipDaily.objects.order_by('-date').values_list('date', flat=True).first()
    
    # 2. 정규화 분실률 계산을 위한 데이터 조회
    # 해당 노선의 평균 이용자 수 (최근 90일 평균 사용 가정)
    avg_ridership = RidershipDaily.objects.filter(
        line_code=line_input,
        date__gte=timezone.now().date() - timezone.timedelta(days=90)
    ).aggregate(avg_total=Avg('total'))['avg_total'] or 1.0 # 0으로 나누는 것 방지
    
    # 3. 노선별 기본 카테고리 비율 계산
    top_categories_qs = LostItem.objects.filter(
        line=line_input,
        registered_at__isnull=False,
        registered_at__date__gte=timezone.now().date() - timezone.timedelta(days=90) # 최근 90일 데이터 사용
    ).values('category').annotate(
        raw_count=Count('category')
    ).order_by('-raw_count')[:5] # 상위 5개 카테고리
    
    report_items = []
    special_warning = "분실물 발생 위험은 평소 수준입니다."
    
    # 4. 오늘의 분실 예보 계산 및 가중치 적용
    
    for item in top_categories_qs:
        category = item['category']
        raw_count = item['raw_count']
        
        # 정규화된 분실률 (Loss Rate per 10k)
        normalized_loss_rate = (raw_count / avg_ridership) * 10000 
        
        weather_weight = 1.0 # 기본 가중치
        umbrella_impact_ratio = 1.0
        
        # 💡 날씨 조건 반영 (가설 G2: 비 오는 날 우산 급증)
        if is_rainy_today:
            
            # RainImpactReport에서 해당 노선의 비 영향 지수를 가져옵니다.
            # 이 지수를 사용하여 혼잡도 변화를 반영할 수 있습니다.
            rain_report = RainImpactReport.objects.filter(
                line_code=line_input
            ).order_by('-created_at').first()
            
            if category == '우산' and rain_report:
                # 우산 가중치: 임시로 RII 지수를 사용 (RII=100을 기준으로 가중치 부여)
                # 비오는 날 승하차량이 20% 증가하면 (RII=120), 우산 분실률도 2.0배 증가한다고 가정
                weather_weight = max(1.0, rain_report.rain_impact_index / 60) # RII 120이면 2.0으로 가중치
                umbrella_impact_ratio = weather_weight
                special_warning = f"비 오는 날 혼잡도가 높습니다. 우산 분실률이 약 {umbrella_impact_ratio:.1f}배 높습니다. 주의하세요."
            elif category == '가방':
                # 가방은 혼잡도(RII)에 비례하여 약간 증가한다고 가정
                if rain_report and rain_report.rain_impact_index > 100:
                     weather_weight = 1.0 + (rain_report.rain_impact_index - 100) / 500 # RII 120이면 1.04배
                     
        
        # 최종 예측 비율 (정규화된 비율 * 가중치)
        final_prediction = normalized_loss_rate * weather_weight
        report_items.append({
            'category': category,
            'prediction': final_prediction,
        })
        
    # 최종 예측 비율을 기준으로 상위 3개만 선택하고 비율로 변환
    sorted_items = sorted(report_items, key=lambda x: x['prediction'], reverse=True)[:3]
    total_prediction_sum = sum(item['prediction'] for item in sorted_items)
    
    if total_prediction_sum > 0:
        for item in sorted_items:
            item['rate'] = round((item['prediction'] / total_prediction_sum) * 100, 1) # 백분율로 변환
    else:
        # 데이터가 없는 경우를 대비
        sorted_items = [{'category': 'N/A', 'rate': 0.0}]

    # 5. 리포트 출력 데이터
    report = {
        'line': line_input,
        'date_condition': date_condition,
        'latest_date': latest_date,
        'items': sorted_items,
        'warning': special_warning
    }
    
    return render(request, 'main/home.html', {'report': report})

def trend_analysis(request):
    """
    Trend 페이지: 노선/월별/요일별 분실 패턴 시각화 (기획서 항목)
    """
    # NOTE: 분석이 완료되면 실제 데이터와 템플릿을 연결해야 합니다.
    return HttpResponse("<h2>Trend Analysis Page</h2><p>노선별, 요일별 분실 패턴 분석 결과가 표시될 예정입니다.</p>")

def correlation_analysis(request):
    """
    Correlation 페이지: 날씨·혼잡도 상관 분석 결과 (기획서 항목)
    """
    # NOTE: 분석이 완료되면 실제 데이터와 템플릿을 연결해야 합니다.
    return HttpResponse("<h2>Correlation Analysis Page</h2><p>날씨·혼잡도 지수와 분실률 간의 상관관계 분석 결과가 표시될 예정입니다.</p>")

def insight_report(request):
    """
    Insight 페이지: 결론 및 가설 검증 리포트 (기획서 항목)
    """
    # NOTE: 분석이 완료되면 실제 데이터와 템플릿을 연결해야 합니다.
    # 이 페이지에서 가설 G1~G5의 검증 결과를 최종적으로 요약합니다.
    return HttpResponse("<h2>Insight Report Page</h2><p>분석 가설(혼잡도, 비 등)에 대한 최종 검증 결과와 결론이 표시될 예정입니다.</p>")
