from django.db import models

# ----------------------------------------------------------------------
# 1. 분실물 원천 데이터 모델 (기존 코드 유지)
# OA-15490 서울시 지하철 분실물 정보
# ----------------------------------------------------------------------
class LostItem(models.Model):
    """
    서울시 분실물 원천 데이터를 저장하는 모델.
    item_id는 원본 데이터의 Unique ID를 사용.
    """
    item_id = models.CharField(max_length=50, unique=True, verbose_name="분실물 ID")
    transport = models.CharField(max_length=20, null=True, blank=True, verbose_name="교통수단")
    line = models.CharField(max_length=50, null=True, blank=True, verbose_name="노선명")
    station = models.CharField(max_length=100, null=True, blank=True, verbose_name="발견역")
    category = models.CharField(max_length=50, null=True, blank=True, verbose_name="분실물 카테고리")
    item_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="물품 상세명")
    status = models.CharField(max_length=50, null=True, blank=True, verbose_name="처리 상태")
    is_received = models.BooleanField(default=False, verbose_name="반환 여부")
    registered_at = models.DateTimeField(null=True, blank=True, verbose_name="등록일시")
    received_at = models.DateTimeField(null=True, blank=True, verbose_name="수령일시")
    description = models.TextField(null=True, blank=True, verbose_name="상세 설명")
    storage_location = models.CharField(max_length=200, null=True, blank=True, verbose_name="보관 위치")
    registrar_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="등록자 ID")
    pickup_company_location = models.CharField(max_length=200, null=True, blank=True, verbose_name="수령 회사/위치")
    views = models.IntegerField(default=0, verbose_name="조회수")

    def __str__(self):
        return f"[{self.category}] {self.item_name} @{self.station}"

    class Meta:
        verbose_name = "1. 분실물 정보 (LostItem)"
        verbose_name_plural = "1. 분실물 정보 (LostItems)"

# ----------------------------------------------------------------------
# 2. 메타 정보 및 승하차 인원 모델 (A 담당)
# ----------------------------------------------------------------------
class StationDict(models.Model):
    """
    지하철 역명 및 노선 정보의 표준화를 위한 딕셔너리 모델.
    정제 규칙: (1) 괄호 제거 통일, (3) 2개 이상 노선 환승역 처리
    """
    station_name_raw = models.CharField(max_length=100, verbose_name="원천 역명 (OA-12251)", help_text="데이터 원본에 기록된 역 이름")
    station_name_std = models.CharField(max_length=100, db_index=True, verbose_name="표준 역명", help_text="괄호 제거 후 통일된 분석용 역 이름")
    line_code = models.CharField(max_length=20, db_index=True, verbose_name="표준 노선 코드", help_text="LINE1, LINE2 등")
    is_transfer = models.BooleanField(default=False, verbose_name="환승역 여부", help_text="2개 이상의 노선이 교차하는 역")

    class Meta:
        unique_together = ('station_name_raw', 'line_code')
        verbose_name = "2-1. 역 표준화 딕셔너리 (StationDict)"
        verbose_name_plural = "2-1. 역 표준화 딕셔너리 (StationDicts)"

    def __str__(self):
        return f"[{self.line_code}] {self.station_name_std} (Raw: {self.station_name_raw})"


class RidershipDaily(models.Model):
    """
    일별, 노선별, 표준역별 승하차 인원 정보 모델.
    OA-12251 서울시 도시철도 승하차 인원정보를 정제하여 저장.
    """
    date = models.DateField(db_index=True, verbose_name="날짜")
    line_code = models.CharField(max_length=20, verbose_name="표준 노선 코드")
    station_name_std = models.CharField(max_length=100, verbose_name="표준 역명")
    boardings = models.IntegerField(verbose_name="승차 인원 합계")
    alightings = models.IntegerField(verbose_name="하차 인원 합계")
    total = models.IntegerField(verbose_name="총 이용자 수 (승차+하차)")

    class Meta:
        unique_together = ('date', 'line_code', 'station_name_std')
        verbose_name = "2-2. 일별 승하차 인원 (RidershipDaily)"
        verbose_name_plural = "2-2. 일별 승하차 인원 (RidershipDailies)"

    def __str__(self):
        return f"{self.date} / {self.line_code} @{self.station_name_std}: {self.total}명"

# ----------------------------------------------------------------------
# 3. 날씨 정보 모델 (B 담당)
# ----------------------------------------------------------------------
class WeatherDaily(models.Model):
    """
    일별 날씨 정보 모델.
    OpenWeatherMap 또는 기상청 API 데이터를 저장. (B 담당)
    """
    date = models.DateField(db_index=True, verbose_name="날짜")
    city_code = models.CharField(max_length=50, default='SEOUL', verbose_name="도시 코드")
    is_rainy = models.BooleanField(default=False, verbose_name="강수 여부", help_text="강수량이 0 이상이면 True")
    rain_mm = models.FloatField(default=0.0, verbose_name="일 강수량 (mm)")
    avg_temp = models.FloatField(null=True, blank=True, verbose_name="평균 기온 (C)")

    class Meta:
        unique_together = ('date', 'city_code')
        verbose_name = "3. 일별 날씨 정보 (WeatherDaily)"
        verbose_name_plural = "3. 일별 날씨 정보 (WeatherDailies)"

    def __str__(self):
        rain_status = "비 옴" if self.is_rainy else "맑음/흐림"
        return f"{self.date} ({self.city_code}): {rain_status}, {self.rain_mm}mm"


class RainImpactReport(models.Model):
    """
    비가 승하차 인원에 미치는 영향 지수(RII)를 저장하는 모델.
    """
    line_code = models.CharField(max_length=10, verbose_name='노선 코드') 
    station_name_std = models.CharField(max_length=50, verbose_name='표준 역명', db_index=True)
    
    # 비 효과 지수 (Rain Impact Index): 100을 기준으로 영향도를 판단
    rain_impact_index = models.FloatField(verbose_name='비 효과 지수')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성 시각')

    class Meta:
        verbose_name = '비 영향 보고서'
        verbose_name_plural = '비 영향 보고서'
        unique_together = ('line_code', 'station_name_std') 

    def __str__(self):
        return f"[{self.line_code}] {self.station_name_std}: RII {self.rain_impact_index:.2f}"