# pickuplog/main/urls.py

from django.urls import path
from . import views

# Home 뷰와 기획서에 명시된 다른 페이지들을 연결합니다.
urlpatterns = [
    # 1. Home: 오늘의 분실 예보 (views.py의 home 함수로 연결)
    path('', views.home, name='home'),
    
    # 2. Trend: 노선/월별/요일별 분실 패턴 (기획서 항목)
    path('trend/', views.trend_analysis, name='trend'), 
    
    # 3. Correlation: 날씨·혼잡도 상관 분석 (기획서 항목)
    path('correlation/', views.correlation_analysis, name='correlation'),
    
    # 4. Insight: 결론 및 가설 검증 (기획서 항목)
    path('insight/', views.insight_report, name='insight'),

    # (LostItem CRUD 뷰가 있다면 여기에 추가 연결)
]