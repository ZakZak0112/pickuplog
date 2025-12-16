from django.db.models import Q, Count, Sum, Avg
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone 
from django.conf import settings 
from django.contrib import messages 
from django.db import IntegrityError 
from django.http import HttpResponse
from datetime import datetime, timedelta, date
from django.shortcuts import render
import math
import copy

from django.shortcuts import render
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from main.models import LostItem, WeatherDaily, RidershipDaily, BusDaily

import json

# 프로젝트 모델 임포트
from .models import LostItem, RidershipDaily, RainImpactReport, WeatherDaily 
# .forms 임포트는 제거 (최종 코드 제공을 위해)
from .forms import LostItemSearchForm, LostItemForm, LostItemCsvUploadForm 

import csv
from i
o import TextIOWrapper 

# ----------------------------------------------------------------------
# Helper Functions (도우미 함수) - (유지)
# ----------------------------------------------------------------------
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
# 1. LostItem CRUD Views (순환 참조 방지를 위해 상단으로 이동)
# ----------------------------------------------------------------------

# 분실물 생성 (LostItemForm 사용)
def lostitem_create(request):
    if request.method == "POST":
        form = LostItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "새로운 분실물이 등록되었습니다.")
            return redirect("lostitem_list")
    else:
        form = LostItemForm()
    return render(request, "main/lostitem_form.html", {"form": form})

# 분실물 수정 (LostItemForm 사용)
def lostitem_update(request, pk):
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


# CSV 파일 업로드 및 처리 (스트림 방식)
def lostitem_upload_csv(request):
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
                # 1. 파일 스트림 열기 (인코딩 우선순위)
                try:
                    csv_file_wrapper = TextIOWrapper(csv_file, encoding='utf-8', newline='', errors='replace') 
                except Exception:
                    csv_file_wrapper = TextIOWrapper(csv_file, encoding='cp949', newline='', errors='replace')
                
                reader = csv.reader(csv_file_wrapper)
                next(reader) # 헤더(첫 번째 줄) 건너뛰기
                
                # 2. 데이터 처리 루프
                for row in reader:
                    
                    if not row or len(row) < 11: 
                        fail_count += 1
                        continue # 빈 줄 또는 부족한 열 건너뛰기
                    
                    try:
                        registered_dt = parse_date_and_make_aware(row[2])
                        received_dt = parse_date_and_make_aware(row[3])
                        
                        LostItem.objects.create(
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
# 2. PickUpLog 핵심 뷰: 오늘의 분실 예보 (home) - ★ 최종 수정된 뷰
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 3. Archive View (분실물 데이터 아카이빙)
# ----------------------------------------------------------------------
def lostitem_list(request):
    """
    LostItem 데이터를 조회하고 검색/필터링을 적용하는 뷰.
    """
    form = LostItemSearchForm(request.GET)
    queryset = LostItem.objects.all().order_by('-registered_at')  # select_related 제거
    page_size = 30

    # 1. 필터링
    if form.is_valid():
        data = form.cleaned_data
        
        if data.get('q'):
            queryset = queryset.filter(
                Q(item_name__icontains=data['q']) |
                Q(description__icontains=data['q']) |
                Q(station__icontains=data['q'])
            )

        if data.get('transport'):
            queryset = queryset.filter(transport=data['transport'])

        if data.get('status'):
            queryset = queryset.filter(status=data['status'])

        if data.get('only_unreceived'):
            queryset = queryset.filter(is_received=False)

        if data.get('category'):
            queryset = queryset.filter(category__in=data['category'])

        if data.get('date_from'):
            queryset = queryset.filter(registered_at__gte=data['date_from'])

        if data.get('date_to'):
            end_date = data['date_to'] + timedelta(days=1)
            queryset = queryset.filter(registered_at__lt=end_date)

        if data.get('sort') == 'registered_at_asc':
            queryset = queryset.order_by('registered_at')
        elif data.get('sort') == 'views_desc':
            queryset = queryset.order_by('-views')

        # page_size 안전 처리
        try:
            page_size = int(data.get('page_size') or 30)
        except (ValueError, TypeError):
            page_size = 30

    # 2. 페이지네이션
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    # 3. 쿼리 스트링 생성
    url_query_string = request.GET.copy()
    url_query_string.pop('page', None)
    url_query_string = f"&{url_query_string.urlencode()}" if url_query_string else ""

    context = {
        'form': form,
        'page_obj': page_obj,
        'url_query_string': url_query_string,
        'total_count': queryset.count(),
        'items': page_obj.object_list,  # 전체 쿼리셋 대신 현재 페이지 아이템만 전달
    }

    return render(request, 'main/lostitem_list.html', context)
# ----------------------------------------------------------------------
# 4. 분석 결과 뷰 (trend, correlation, insight)
# ----------------------------------------------------------------------
from django.db.models.functions import ExtractWeekDay

def trend_analysis(request):
    """
    노선별 · 역별 · 요일별 분실 패턴 분석
    """
    # --------------------------------------------------
    # 1️⃣ Trend 데이터 (LostItem 집계)
    # 최근 90일 데이터만 사용
    
    reports = RainImpactReport.objects.all()
    line_stats = (
        reports.values('line_code')
        .annotate(avg_rii=Avg('rain_impact_index'))
        .order_by('line_code')
    )

    context = {
        'reports': reports,
        'chart_labels': [stat['line_code'] for stat in line_stats],
        'chart_values': [round(stat['avg_rii'], 2) for stat in line_stats],
        'total_stations': reports.count(),
        'avg_rii': reports.aggregate(Avg('rain_impact_index'))['rain_impact_index__avg'] or 0,
    }

    return render(request, 'main/trend_analysis.html', context)
def correlation_analysis(request):    
    # 최근 30일 기온, 강수, 분실물 개수 집계
    weather_data = WeatherDaily.objects.filter()
    lost_data = (
        LostItem.objects
        .filter()
        .extra(select={'date': "date(registered_at)"})
        .values('date')
        .annotate(lost_count=Count('id'))
    )

    # 날짜별 매칭
    merged = []
    for w in weather_data:
        lost_count = next((x['lost_count'] for x in lost_data if str(x['date']) == str(w.date)), 0)
        merged.append({
            'date': w.date.strftime("%Y-%m-%d"),  # JS에서 문자열로 사용
            'temp': w.avg_temp,
            'rain': w.rain_mm,
            'lost': lost_count,
        })

    # 상관계수 계산
    def correlation(xs, ys):
        if not xs or not ys or len(xs) != len(ys):
            return 0
        mean_x = sum(xs)/len(xs)
        mean_y = sum(ys)/len(ys)
        num = sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))
        den = (sum((x-mean_x)**2 for x in xs) * sum((y-mean_y)**2 for y in ys)) ** 0.5
        return round(num/den, 3) if den else 0

    temp_corr = correlation([m['temp'] for m in merged if m['temp'] is not None], [m['lost'] for m in merged])
    rain_corr = correlation([m['rain'] for m in merged if m['rain'] is not None], [m['lost'] for m in merged])

    context = {
        'merged': merged,
        'temp_corr': temp_corr,
        'rain_corr': rain_corr,
        'has_data': bool(merged),
    }

    return render(request, 'main/correlation_analysis.html', context)

def insight_report(request):
    # 노선별 평균 RII
    avg_rii = (
        RainImpactReport.objects
        .values('line_code')
        .annotate(avg_index=Avg('rain_impact_index'))
        .order_by('-avg_index')
    )

    # 분실물 상위 노선 TOP 5
    lost_top = (
        LostItem.objects
        .values('line')
        .annotate(total_lost=Count('id'))
        .order_by('-total_lost')[:5]
    )

    # 간단한 요약 문 생성
    summary = ""
    if avg_rii:
        top_line = avg_rii[0]['line_code']
        top_value = round(avg_rii[0]['avg_index'], 2)
        summary += f"비의 영향을 가장 많이 받은 노선은 {top_line}이며, 평균 RII는 {top_value}입니다. "
    if lost_top:
        summary += f"가장 분실물이 많은 노선은 {lost_top[0]['line']}입니다. "
    if not summary:
        summary = "데이터가 부족하여 인사이트를 생성할 수 없습니다."

    context = {
        'avg_rii': avg_rii,
        'lost_top': lost_top,
        'summary': summary,
    }

    return render(request, 'main/insight_report.html', context)


#날씨별, 노선별, 역별 분실물 + 승하차 인원 집계 뷰
def analysis_view(request, section):
    #LostItem 불러오기
    lostitems = LostItem.objects.all().values(
        'registered_at', 'category'
    )
    lost_df = pd.DataFrame(lostitems)

    if lost_df.empty:
        return render(request, 'main/analysis.html', {'reports': []})

    lost_df['date'] = pd.to_datetime(lost_df['registered_at']).dt.date
    lost_df['category'] = lost_df['category'].fillna('기타')

    # 날짜별 + 카테고리별 pivot
    pivot_df = lost_df.pivot_table(
        index='date',
        columns='category',
        values='registered_at',
        aggfunc='count',
        fill_value=0
    ).reset_index()

    pivot_df.columns.name = None

    #WeatherDaily 불러오기
    weather = WeatherDaily.objects.all().values(
        'date', 'is_rainy', 'rain_mm', 'avg_temp'
    )
    weather_df = pd.DataFrame(weather)
    weather_df['date'] = pd.to_datetime(weather_df['date']).dt.date

    #RidershipDaily 불러오기
    ridership = RidershipDaily.objects.values('date', 'boardings', 'alightings', 'total')
    ridership_df = pd.DataFrame(ridership)
    ridership_df['date'] = pd.to_datetime(ridership_df['date']).dt.date
    
    ridership_qs = (RidershipDaily.objects
                    .values('date')
                    .annotate(
                        subway_boardings=Sum('boardings'),
                        subway_alightings=Sum('alightings')
                    )
                    .order_by('date')
    )
    ridership_df=pd.DataFrame(list(ridership_qs))

    #BusDaily 불러오기
    bus = BusDaily.objects.values('date', 'ride_on', 'ride_off')
    bus_df = pd.DataFrame(bus)
    bus_df['date'] = pd.to_datetime(bus_df['date']).dt.date

    bus_qs = (BusDaily.objects
              .values('date')
              .annotate(
                  bus_boardings = Sum('ride_on'),
                  bus_alightings = Sum('ride_off')
              )
              .order_by('date')
            )

    bus_df = pd.DataFrame(list(bus_qs))


    #버스+지하철 통합 승하차 인원
    boardings_df = pd.merge(bus_df, ridership_df, on='date', how='outer').fillna(0)
    boardings_df['total_boardings'] = boardings_df['bus_boardings'] + boardings_df['subway_boardings']
    boardings_df['date_str'] = boardings_df['date'].astype(str)
    total_boardings_dict = {row['date_str']: row['total_boardings'] for _, row in boardings_df.iterrows()}
    
    alightings_df = pd.merge(bus_df, ridership_df, on='date', how='outer').fillna(0)
    alightings_df['total_alightings'] = alightings_df['bus_alightings'] + alightings_df['subway_alightings']
    alightings_df['date_str'] = alightings_df['date'].astype(str)
    total_alightings_dict = {row['date_str']: row['total_alightings'] for _, row in alightings_df.iterrows()}

    #날씨 + 분실물 + 지하철 승하차 인원
    final_df = pd.merge(
        weather_df,
        pivot_df,
        on='date',
        how='left'
    ).fillna(0)

    final_df = pd.merge(
        final_df, 
        ridership_df, 
        on='date', 
        how='left'
    )

    final_df = pd.merge(
        final_df,
        bus_df,
        on='date',
        how='left'
    ).fillna(0)

    # 총 분실물 계산
    category_cols = [
        c for c in pivot_df.columns
        if c not in ['date', 'registered_at']
    ]

    final_df['total_lost'] = final_df[category_cols].sum(axis=1)

    # 최신순 정렬
    final_df = final_df.sort_values('date', ascending=False)

    ##회귀 분석 (강수량 → 분실물 총합)
    rain_list = final_df['rain_mm'].astype(float).tolist()
    lost_list = final_df['total_lost'].astype(int).tolist()

    X = np.array(rain_list).reshape(-1, 1)
    y = np.array(lost_list)

    # 선형 회귀 모델
    model = LinearRegression()
    model.fit(X, y)

    # 회귀선용 Y 계산
    x_line = np.linspace(min(rain_list), max(rain_list), 50).reshape(-1, 1)
    y_line = model.predict(x_line)

    regression_line = [
        {'x': float(x_line[i][0]), 'y': float(y_line[i])}
        for i in range(len(x_line))
    ]

    ##집단별 통계 계산
    stats = {
        'rain_mm': {
            'mean': round(final_df['rain_mm'].mean(), 2),
            'std': round(final_df['rain_mm'].std(), 2),
            'median': round(final_df['rain_mm'].median(), 2),
            'count': int(final_df['rain_mm'].count()),
        },
        'avg_temp': {
            'mean': round(final_df['avg_temp'].mean(), 2),
            'std': round(final_df['avg_temp'].std(), 2),
            'median': round(final_df['avg_temp'].median(), 2),
            'count': int(final_df['avg_temp'].count()),
        },
        'total_lost': {
            'mean': round(final_df['total_lost'].mean(), 2),
            'std': round(final_df['total_lost'].std(), 2),
            'median': round(final_df['total_lost'].median(), 2),
            'count': int(final_df['total_lost'].count()),
        },
    }

    #=====템플릿 전달=====
    reports = final_df.to_dict(orient='records')

    recent_rainy = 0
    recent_sunny = 0
    i = 0
    while recent_rainy == 0 or recent_sunny == 0:
        if reports[i]['total_lost'] > 0 and reports[i]['subway_boardings'] > 0 and reports[i]['bus_boardings'] > 0:
            if reports[i]['is_rainy']:
                recent_rainy = reports[i]['date']
                recent_rainy_lostitem = reports[i]['total_lost']
                recent_rain_mm = reports[i]['rain_mm']
            elif not reports[i]['is_rainy']:
                recent_sunny = reports[i]['date']
                recent_sunny_lostitem = reports[i]['total_lost']
            
        i += 1

    #분모 집계
    rainy_people = (
        boardings_df.loc[final_df['is_rainy'] == True, 'total_boardings'].sum() +
        alightings_df.loc[final_df['is_rainy'] == True, 'total_alightings'].sum()
    )
    sunny_people = (
        boardings_df.loc[final_df['is_rainy'] == False, 'total_boardings'].sum() +
        alightings_df.loc[final_df['is_rainy'] == False, 'total_alightings'].sum()
    )
    rainy_days = final_df['is_rainy'].sum()
    sunny_days = final_df['is_rainy'].sum()

    conut_df = pd.merge(final_df, lost_df, on='date', how='left')
    # 카테고리별 분실물 집계
    rainy_category_counts = (
        conut_df[conut_df['is_rainy'] == True]
        .groupby('category')['total_lost']
        .sum()
    )
    sunny_category_counts = (
        conut_df[conut_df['is_rainy'] == False]
        .groupby('category')['total_lost']
        .sum()
    )

    #분실률 계산
    rainy_lostitem_perDay = (rainy_category_counts / rainy_days).tolist()
    sunny_lostitem_perDay = (sunny_category_counts / sunny_days).tolist()
    rainy_lostitem_perPerson = (rainy_category_counts / rainy_people).tolist()
    sunny_lostitem_perPerson = (sunny_category_counts / sunny_people).tolist()
    categories = rainy_category_counts.index.tolist()

    #분실량 차이
    lostitem_percent_increse = sum(sunny_lostitem_perDay) / sum(rainy_lostitem_perDay)
    p = (sum(rainy_lostitem_perPerson) + sum(sunny_lostitem_perPerson)) / (rainy_people + sunny_people)
    z_test = (sum(rainy_lostitem_perPerson) - sum(sunny_lostitem_perPerson)) / math.sqrt(p * (1-p) * (1/sum(rainy_lostitem_perPerson) + 1/sum(sunny_lostitem_perPerson)))

    #-----꺾은선그래프-----
    lineGraph = conut_df
    lineGraph['date'] = [d.strftime('%Y-%m-%d') for d in lineGraph['date']]
    lineGraph = lineGraph.to_dict(orient='records')
    lineGraph_weather = copy.deepcopy(lineGraph) #날씨 정보 lineGraph 복제

    #lineGraph
    for item in lineGraph: #키 이름 맞추기
        if 'total_lost' in item:
            item['value'] = item.pop('total_lost')

    keys_to_keep = ['date', 'value'] 
    for item in lineGraph:  #사용되는 키 제외하고 전부 삭제
        for key in list(item.keys()): 
            if key not in keys_to_keep:
                item.pop(key)

    #lineGraph_weater
    for item in lineGraph_weather: #키 이름 맞추기
        if 'rain_mm' in item:
            item['value'] = item.pop('rain_mm')
    
    #(리스트는 같은 것 사용)
    for item in lineGraph_weather:  #사용되는 키 제외하고 전부 삭제
        for key in list(item.keys()): 
            if key not in keys_to_keep:
                item.pop(key)

    #-----상자수염그래프-----
    box_rainy_date = conut_df[conut_df['is_rainy'] == True]['total_lost'].tolist()
    box_sunny_date = conut_df[conut_df['is_rainy'] == False]['total_lost'].tolist()


    #-----회귀 그래프 값 전달-----
    cols = ['subway_boardings', 'subway_alightings', 'bus_boardings', 'bus_alightings']

    # 네 개 중 하나라도 0이면 제외
    filtered_df = final_df[final_df[cols].min(axis=1) > 0]

    # total_people 계산
    filtered_df['total_people'] = (
        filtered_df['subway_boardings'] +
        filtered_df['subway_alightings'] +
        filtered_df['bus_boardings'] +
        filtered_df['bus_alightings']
    )

    # 그래프 전달용 데이터
    regression_data = filtered_df[['date', 'total_people', 'total_lost', 'is_rainy']] \
                        .to_dict(orient='records')

    #-----덤벨 차트-----
    dumbbell_rainy = (rainy_category_counts / rainy_days).to_dict()
    dumbbell_sunny = (sunny_category_counts / sunny_days).to_dict()
    print(dumbbell_rainy)
    print(dumbbell_sunny)

    #-----전달-----
    context ={
        'reports': reports,
        'rain_list': rain_list,
        'lost_list': lost_list,
        'regression_line': regression_line,
        'stats': stats,

        'total_boardings': json.dumps(total_boardings_dict),
        'total_alightings': json.dumps(total_alightings_dict),
        'recent_rainy': recent_rainy,
        'recent_sunny': recent_sunny,
        'recent_rainy_lostitem': recent_rainy_lostitem,
        'recent_sunny_lostitem': recent_sunny_lostitem,
        'recent_rain_mm': recent_rain_mm,

        'sunny_lostitem_perDay': sunny_lostitem_perDay,
        'rainy_lostitem_perDay': rainy_lostitem_perDay,
        'lostitem_percent_increse':lostitem_percent_increse,
        'categories': categories,
        'rainy_lostitem_perPerson': rainy_lostitem_perPerson,
        'sunny_lostitem_perPerson': sunny_lostitem_perPerson,
        'z_test': z_test,

        'lineGraph': lineGraph,
        'lineGraph_weather': lineGraph_weather,
        'box_rainy_date': box_rainy_date,
        'box_sunny_date': box_sunny_date,

        'regression_data': regression_data,

        'dumbbell_rainy': dumbbell_rainy,
        'dumbbell_sunny': dumbbell_sunny
    }

    if section == 'table':
        context['show_table'] = True
    elif section == 'regression':
        context['show_regression'] = True
    elif section == 'stats':
        context['show_stats'] = True
    elif section == 'visualization':
        context['show_visualization'] = True
    elif section == 'boxPlot':
        context['show_boxPlot'] = True
    elif section == 'dumbbellPlot':
        context['show_dumbbellPlot'] = True

    return render(request, 'main/analysis.html', context)