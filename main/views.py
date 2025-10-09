from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone 
from django.conf import settings 
from django.contrib import messages 
from django.db import IntegrityError 

import csv
import requests
from datetime import datetime
from io import TextIOWrapper 

from .models import LostItem
from .forms import LostItemSearchForm, LostItemForm, LostItemCsvUploadForm 


# ----------------------------------------------------------------------
# Helper Functions (도우미 함수)
# ----------------------------------------------------------------------

# 날짜/시간 형식 변환 및 Timezone 적용
def parse_date_and_make_aware(date_str):
    if not date_str or date_str.strip() in ['00:00.0', '']:
        return None
    
    # 공백 제거 후 첫 번째 부분(날짜)만 파싱 시도
    date_part = date_str.strip().split(' ')[0]
    #/ 파싱
    date_part = date_part.replace('/', '-')
    
    try:
        # 'YYYY-MM-DD' 형식으로 파싱 시도
        naive_datetime = datetime.strptime(date_part, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        
        # Timezone 정보 강제 부여
        return timezone.make_aware(
            naive_datetime, 
            timezone=timezone.get_current_timezone() 
        )
    except ValueError:
        return None # 파싱 실패


# ----------------------------------------------------------------------
# Views (뷰 함수 정의)
# ----------------------------------------------------------------------

# 분실물 목록 조회 및 검색
def lostitem_list(request):
    form = LostItemSearchForm(request.GET or None)
    qs = LostItem.objects.all()

    if form.is_valid():
        cd = form.cleaned_data
        
        # 1. 검색어 (q)
        if cd.get("q"):
            q = cd["q"]
            qs = qs.filter(
                Q(item_name__icontains=q) |
                Q(description__icontains=q) |
                Q(storage_location__icontains=q) |
                Q(station__icontains=q)
            )
            
        # 2. 기타 필터링 조건들
        if cd.get("transport"):
            qs = qs.filter(transport=cd["transport"])
        if cd.get("status"):
            qs = qs.filter(status=cd["status"])
        if cd.get("category"):
            if cd["category"]: 
                qs = qs.filter(category__in=cd["category"]) # __in을 사용하여 리스트의 모든 값과 비교
        if cd.get("only_unreceived"):
            qs = qs.filter(is_received=False)
            
        # 3. 날짜 범위 필터링
        if cd.get("date_from"):
            qs = qs.filter(registered_at__date__gte=cd["date_from"])
        if cd.get("date_to"):
            qs = qs.filter(registered_at__date__lte=cd["date_to"])

        # 4. 정렬
        sort = cd.get("sort") or "registered_at_desc"
        if sort == "registered_at_desc": qs = qs.order_by("-registered_at")
        elif sort == "registered_at_asc": qs = qs.order_by("registered_at")
        elif sort == "views_desc": qs = qs.order_by("-views")
        
        # 5. 페이지 크기
        page_size = cd.get("page_size") or 30
    else:
        # 기본 정렬 및 페이지 크기
        qs = qs.order_by("-registered_at")
        page_size = 30
    
    # 카테고리 집계 (검색 조건 적용 후)
    categories = (
        qs.values("category").annotate(cnt=Count("id")).order_by("-cnt","category")[:50]
    )

    # 페이징 처리
    paginator = Paginator(qs, page_size)
    
    # 요청 페이지 번호 검증 및 예외 처리
    try:
        page_obj = paginator.get_page(request.GET.get("page"))
    except EmptyPage:
        # 페이지 번호가 범위를 벗어날 경우 (1보다 작거나 너무 클 경우), 마지막 페이지를 보여줍니다.
        page_obj = paginator.page(paginator.num_pages) 
    
    # 템플릿의 페이징 링크 생성을 위한 쿼리스트링 헬퍼 준비
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    
    # 쿼리스트링이 있으면 앞에 '&'를 붙여서 URL에 쉽게 추가할 수 있도록 준비
    url_query_string = '&' + query_params.urlencode() if query_params else ''


    ctx = {
        "form": form,
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "categories": categories,
        "total_count": paginator.count,
        "url_query_string": url_query_string, # 템플릿으로 전달
    }
    return render(request, "main/lostitem_list.html", ctx)


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
                    
                    # CSV 순서: 0:분실물SEQ, 1:분실물상태, 2:등록일자, 3:수령일자, 4:유실물상세내용, 5:보관장소, 
                    # 6:분실물등록자ID, 7:분실물명, 8:분실물종류, 9:수령위치(회사), 10:조회수
                    
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
                # 파일 인코딩 오류 등
                messages.error(request, f'파일 처리 중 치명적인 오류 발생: {e}')
                return redirect('lostitem_upload_csv')

            
            messages.success(request, f'CSV 업로드 완료! 성공 {success_count}건, 실패/중복 {fail_count}건.')
            return redirect('lostitem_list') 
            
        else:
            messages.error(request, '유효하지 않은 파일입니다. CSV 파일을 선택해주세요.')
            
    else:
        form = LostItemCsvUploadForm()
        
    return render(request, 'main/lostitem_csv_upload.html', {'form': form})

#API 연결
response = requests.get("http://openapi.seoul.go.kr:8088/6671454b426c6f763833785471726d/json/lostArticleInfo/1/1000/") #1번부터 1000번까지 불러옴
api_data = response.json() 
LostItem.objects.all().delete()

#수동 리스트
busList = ["중부운수", "대진여객", "원버스", 
           "상진운수", "성원여객", "보성운수",
           "동성교통", "도선여객", "선진운수",
           "남성교통", "삼양교통"]
taxiList = ["삼이택시", "동화통운", "고려운수", 
            "경일운수", "동도자동차", "안전한택시", 
            "양평운수", "대진흥업", "승진통상",
            "백제운수", "삼익택시", "새한택시",
            "경서운수", "대하운수", "동성상운",]

for data in api_data["lostArticleInfo"]["row"]:
    obj, created = LostItem.objects.update_or_create(
        item_id=data.get("LOST_MNG_NO"),
        defaults = {
        "item_id": data.get("LOST_MNG_NO"),
        "transport": lambda x=data.get("CSTD_PLC"), y=data.get("RCPL"): "subway" if x[-1]=="역" else ("bus" if y in busList else ("taxi" if y in taxiList else "etc")),
        #(위) 보관장소가 역일 경우 지하철, 수령위치가 버스회사일 경우 버스, 택시회사일 경우 택시, 다 아닐 경우 기타 반환
        "station": lambda x=data.get("CSTD_PLC"): x if x[-1]=="역" else "",
        "category": data.get("LOST_KND"),
        "item_name": data.get("LOST_NM"),
        "status": data.get("LOST_STTS"),
        "is_received" : lambda x=data.get("LOST_STTS"): True if x=="수령" else False , 
        #(위) LOST_STTS가 "수령"일 걍우 True를, 아닐 경우 False를 반환한다
        "registered_at": parse_date_and_make_aware(data.get("REG_YMD")),
        "received_at": parse_date_and_make_aware(data.get("RCV_YMD")),
        "description": data.get("LGS_DTL_CN"),
        "registrar_id": data.get("LOST_RGTR_ID"),
        "storage_location": lambda x=data.get("RCPL"), y=data.get("CSTD_PLC"): y if y[-1]=="역" else x,
        #(위) 역일 경우 보관장소 표시, 아닐 경우 수령위치 표시
        "pickup_company_location": data.get("RCPL"),
        "views": int(data.get("INQ_CNT") or 0),
        }
    )
    