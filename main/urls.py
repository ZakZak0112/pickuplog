# pickuplog/main/urls.py (최종 수정)

from django.urls import path, include
from . import views 

urlpatterns = [
    # 1. Home 및 분석 페이지 연결
    path('', views.home, name='home'),
    path('trend/', views.trend_analysis, name='trend'), 
    path('correlation/', views.correlation_analysis, name='correlation'),
    path('insight/', views.insight_report, name='insight'),

    # 2. LostItem CRUD 및 아카이브 연결
    path('archive/lostitem/create/', views.lostitem_create, name='lostitem_create'), 
    path('archive/lostitem/update/<int:pk>/', views.lostitem_update, name='lostitem_update'),
    path('archive/lostitem/upload/csv/', views.lostitem_upload_csv, name='lostitem_upload_csv'), 

    #추가 분석 페이지
    path('analysis/table/', views.analysis_view, {'section': 'table'}, name='analysis_table'),
    path('analysis/regression/', views.analysis_view, {'section': 'regression'}, name='analysis_regression'),
]
