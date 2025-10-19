from django.contrib import admin
from .models import LostItem, StationDict, RidershipDaily, WeatherDaily

# ----------------------------------------------------------------------
# 1. LostItem (기존 코드 유지 및 확장)
# ----------------------------------------------------------------------
@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    """분실물 정보 모델 관리"""
    list_display = ("item_id", "category", "item_name", "transport", "line", "station", "status", "is_received", "registered_at", "views")
    list_filter = ("transport", "status", "is_received", "category", "line") # station 필터는 너무 많아 제외
    search_fields = ("item_id", "item_name", "description", "storage_location", "station")
    date_hierarchy = "registered_at"
    ordering = ('-registered_at',) # 최신 등록 순 정렬



# ----------------------------------------------------------------------
# 2. StationDict (역 표준화 딕셔너리 - A 담당)
# ----------------------------------------------------------------------
@admin.register(StationDict)
class StationDictAdmin(admin.ModelAdmin):
    """역 표준화 및 환승 정보 관리"""
    list_display = ("station_name_std", "line_code", "station_name_raw", "is_transfer")
    list_filter = ("line_code", "is_transfer")
    search_fields = ("station_name_std", "station_name_raw")
    # 표준 역명(station_name_std) 기준으로 정렬하여 환승역 그룹화 확인 용이
    ordering = ('station_name_std', 'line_code')



# ----------------------------------------------------------------------
# 3. RidershipDaily (일별 승하차 인원 - A 담당)
# ----------------------------------------------------------------------
@admin.register(RidershipDaily)
class RidershipDailyAdmin(admin.ModelAdmin):
    """일별 승하차 인원 데이터 관리"""
    list_display = ("date", "line_code", "station_name_std", "total", "boardings", "alightings")
    list_filter = ("line_code", "date") # 날짜별로 필터링 용이하게
    search_fields = ("station_name_std", "line_code")
    date_hierarchy = "date"
    # 최신 날짜 순, 총 인원 순으로 정렬
    ordering = ('-date', '-total') 



# ----------------------------------------------------------------------
# 4. WeatherDaily (일별 날씨 정보 - B 담당)
# ----------------------------------------------------------------------
@admin.register(WeatherDaily)
class WeatherDailyAdmin(admin.ModelAdmin):
    """일별 날씨 데이터 관리"""
    list_display = ("date", "is_rainy", "rain_mm", "avg_temp", "city_code")
    list_filter = ("is_rainy", "city_code")
    search_fields = ("city_code",)
    date_hierarchy = "date"
    ordering = ('-date',) # 최신 날짜 순 정렬