from django.db.models import Q, Count, Sum, Avg
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone 
from datetime import datetime, timedelta
from django.conf import settings 
from django.contrib import messages 
from django.db import IntegrityError 
from django.http import HttpResponse
from django.db.models.functions import ExtractWeekDay # Trend 분석용

# 프로젝트 모델 및 폼 임포트
from .models import LostItem, RidershipDaily, RainImpactReport, WeatherDaily 
from .forms import LostItemSearchForm, LostItemForm, LostItemCsvUploadForm 

import csv
from io import TextIOWrapper 


# ----------------------------------------------------------------------
# Helper Functions (도우미 함수)
# ----------------------------------------------------------------------
def parse_date_and_make_aware(date_str):
    # ... (날짜 파싱 로직 유지)
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
# 1. LostItem CRUD Views (순환 참조 방지를 위해 최상단으로 이동)
# ----------------------------------------------------------------------

def lostitem_create(request):
    """분실물 생성"""
    if request.method == "POST":
        form = LostItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "새로운 분실물이 등록되었습니다.")
            return redirect("lostitem_list")
    else:
        form = LostItemForm()
    return render(request, "main/lostitem_form.html", {"form": form})

def lostitem_update(request, pk):
    """분실물 수정"""
    obj = get_object_or_404(LostItem, pk=pk)
    if request.method == "POST":
        form = LostItemForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{obj.item_name}' 정보가 수정되었습니다.")
            return redirect("lostitem_list")
    else:
        form = LostItemForm(instance=obj)
    return render(request, "main/lostitem_form.html", {"form": form, "object": obj})

def lostitem_upload_csv(request):
    """CSV 파일 업로드 및 처리"""
    if request.method == 'POST':
        form = LostItemCsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'CSV 파일만 업로드할 수 있습니다.')
                return redirect('lostitem_list')
            
            success_count = 0
            fail_count = 0
            
            try:
                # 파일 스트림 처리 로직 (기존 로직 유지)
                try:
                    csv_file_wrapper = TextIOWrapper(csv_file, encoding='utf-8', newline='', errors='replace') 
                except Exception:
                    csv_file_wrapper = TextIOWrapper(csv_file, encoding='cp949', newline='', errors='replace')
                
                reader = csv.reader(csv_file_wrapper)
                next(reader) 
                
                for row in reader:
                    if not row or len(row) < 11: 
                        fail_count += 1
                        continue 
                    
                    try:
                        registered_dt = parse_date_and_make_aware(row[2])
                        received_dt = parse_date_and_make_aware(row[3])
                        
                        LostItem.objects.create(
                            # ... (DB 필드 매핑 로직 유지)
                            item_id=row[0], 
                            status=row[1], 
                            registered_at=registered_dt, 
                            received_at=received_dt, 
                            description=row[4], 
                            storage_location=row[5], 
                            registrar_id=row[6], 
                            item_name=row[7], 
                            category=row[8], 
                            pickup_company_location=row[9], 
                            views=int(row[10] or 0), 
                            is_received=(row[1].strip() == '수령')
                        )
                        success_count += 1
                    except IntegrityError:
                        fail_count += 1
                    except Exception:
                        fail_count += 1

            except Exception as e:
                messages.error(request, f'파일 처리 중 치명적인 오류 발생: {e}')
                return redirect('lostitem_upload_csv')
            
            messages.success(request, f'CSV 업로드 완료! 성공 {success_count}건, 실패/중복 {fail_count}건.')
            return redirect('lostitem_list') 
            
        else:
            messages.error(request, '유효하지 않은 파일입니다. CSV 파일을 선택해주세요.')
            
    else:
        form = LostItemCsvUploadForm()
        
    return render(request, 'main/lostitem_csv_upload.html', {'form': form})

# ----------------------------------------------------------------------
# 2. PickUpLog 핵심 뷰: 오늘의 분실 예보 (home)
# ----------------------------------------------------------------------
def home(request):
    """
    PickUpLog 홈 화면 뷰: 오늘의 분실 예보 및 RII 기반 인사이트를 제공합니다.
    """
    # ... (home 함수 로직 유지)
    line_input = request.GET.get('line', 'LINE2') 
    is_rainy_today = (request.GET.get('condition', '평소') == '비오는 날')
    
    latest_date = RidershipDaily.objects.order_by('-date').values_list('date', flat=True).first()
    
    avg_ridership = RidershipDaily.objects.filter(
        line_code=line_input,
        date__gte=timezone.now().date() - timezone.timedelta(days=90)
    ).aggregate(avg_total=Avg('total'))['avg_total'] or 1.0
    
    top_categories_qs = LostItem.objects.filter(
        line=line_input,
        registered_at__isnull=False,
        registered_at__date__gte=timezone.now().date() - timezone.timedelta(days=90)
    ).values('category').annotate(
        raw_count=Count('category')
    ).order_by('-raw_count')[:5]
    
    report_items = []
    special_warning = "분실물 발생 위험은 평소 수준입니다."
    
    for item in top_categories_qs:
        category = item['category']
        raw_count = item['raw_count']
        
        normalized_loss_rate = (raw_count / avg_ridership) * 10000 
        
        weather_weight = 1.0 
        umbrella_impact_ratio = 1.0
        
        if is_rainy_today:
            
            rain_report = RainImpactReport.objects.filter(
                line_code=line_input
            ).order_by('-created_at').first()
            
            if category == '우산' and rain_report:
                weather_weight = max(1.0, rain_report.rain_impact_index / 60)
                umbrella_impact_ratio = weather_weight
                special_warning = f"비 오는 날 혼잡도가 높습니다. 우산 분실률이 약 {umbrella_impact_ratio:.1f}배 높습니다. 주의하세요."
            elif category == '가방':
                if rain_report and rain_report.rain_impact_index > 100:
                     weather_weight = 1.0 + (rain_report.rain_impact_index - 100) / 500
                     
        
        final_prediction = normalized_loss_rate * weather_weight
        report_items.append({
            'category': category,
            'prediction': final_prediction,
        })
        
    sorted_items = sorted(report_items, key=lambda x: x['prediction'], reverse=True)[:3]
    total_prediction_sum = sum(item['prediction'] for item in sorted_items)
    
    if total_prediction_sum > 0:
        for item in sorted_items:
            item['rate'] = round((item['prediction'] / total_prediction_sum) * 100, 1)
    else:
        sorted_items = [{'category': 'N/A', 'rate': 0.0}]

    report = {
        'line': line_input,
        'date_condition': request.GET.get('condition', '평소'),
        'latest_date': latest_date,
        'items': sorted_items,
        'warning': special_warning
    }
    
    return render(request, 'main/home.html', {'report': report})


# ----------------------------------------------------------------------
# 3. Archive View (분실물 데이터 아카이빙)
# ----------------------------------------------------------------------

def lostitem_list(request):
    """
    LostItem 데이터를 조회하고 검색/필터링을 적용하는 뷰.
    """
    form = LostItemSearchForm(request.GET)
    queryset = LostItem.objects.all().order_by('-registered_at') # 기본은 최신 등록 순

    page_size = 30 

    # 1. 필터링 로직
    if form.is_valid():
        data = form.cleaned_data
        
        # ... (필터링 로직 유지)
        if data['q']:
            queryset = queryset.filter(
                Q(item_name__icontains=data['q']) |
                Q(description__icontains=data['q']) |
                Q(station__icontains=data['q'])
            )

        if data['transport']:
            queryset = queryset.filter(transport=data['transport'])

        if data['status']:
            queryset = queryset.filter(status=data['status'])
            
        if data['only_unreceived']: 
            queryset = queryset.filter(is_received=False)
            
        if data['category']:
             queryset = queryset.filter(category__in=data['category'])

        if data['date_from']:
            queryset = queryset.filter(registered_at__gte=data['date_from'])
        if data['date_to']:
            end_date = data['date_to'] + timedelta(days=1)
            queryset = queryset.filter(registered_at__lt=end_date)
            
        if data['sort']:
            if data['sort'] == 'registered_at_asc':
                queryset = queryset.order_by('registered_at')
            elif data['sort'] == 'views_desc':
                 queryset = queryset.order_by('-views')

        raw_page_size = data.get('page_size', 30)
        
        try:
            page_size = int(raw_page_size) if raw_page_size is not None else 30
        except ValueError:
            page_size = 30

    # 2. 페이지네이션
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    except:
        page_obj = paginator.page(1)

    # 3. 쿼리 스트링 생성
    url_query_string = request.GET.copy()
    if 'page' in url_query_string:
        del url_query_string['page']
    
    url_query_string = f"&{url_query_string.urlencode()}" if url_query_string else ""

    context = {
        'form': form,
        'page_obj': page_obj,
        'url_query_string': url_query_string,
        'total_count': queryset.count(),
        'items': page_obj.object_list, # 템플릿에 전달할 항목
    }
    
    return render(request, 'main/lostitem_list.html', context)


# ----------------------------------------------------------------------
# 4. 분석 결과 뷰 (trend, correlation, insight)
# ----------------------------------------------------------------------
def trend_analysis(request):
    """
    Trend 페이지: 노선/월별/요일별 분실 패턴 시각화 (기획서 항목)
    """
    # ... (분석 로직 필요)
    return HttpResponse("<h2>Trend Analysis Page</h2><p>노선별, 요일별 분실 패턴 분석 결과가 표시될 예정입니다.</p>")

def correlation_analysis(request):
    """
    Correlation 페이지: 날씨·혼잡도 상관 분석 결과 (기획서 항목)
    """
    # ... (분석 로직 필요)
    return HttpResponse("<h2>Correlation Analysis Page</h2><p>날씨·혼잡도 지수와 분실률 간의 상관관계 분석 결과가 표시될 예정입니다.</p>")

def insight_report(request):
    """
    Insight 페이지: 결론 및 가설 검증 리포트 (기획서 항목)
    """
    # ... (분석 로직 필요)
    return HttpResponse("<h2>Insight Report Page</h2><p>분석 가설(혼잡도, 비 등)에 대한 최종 검증 결과와 결론이 표시될 예정입니다.</p>")