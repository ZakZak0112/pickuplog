# pickuplog/main/urls.py (최종 수정)

from django.urls import path, include
# 💡 필수: views 모듈을 임포트하여 아래 path() 함수에서 사용할 수 있게 합니다.
from . import views 

urlpatterns = [
    # 1. Home 및 분석 페이지 연결
    path('', views.analysis_view, {'section': 'visualization'}, name='analysis_visualization'),

    # 2. LostItem CRUD 및 아카이브 연결
    path('archive/lostitem/create/', views.lostitem_create, name='lostitem_create'), 
    path('archive/lostitem/update/<int:pk>/', views.lostitem_update, name='lostitem_update'),
    path('archive/lostitem/upload/csv/', views.lostitem_upload_csv, name='lostitem_upload_csv'), 

    #추가 분석 페이지
    path('analysis/table/', views.analysis_view, {'section': 'table'}, name='analysis_table'),
    path('analysis/stats/', views.analysis_view, {'section': 'stats'}, name='analysis_stats'),
    path('analysis/boxPlot/', views.analysis_view, {'section': 'boxPlot'}, name='analysis_boxPlot'),
    path('analysis/regression/', views.analysis_view, {'section': 'regression'}, name='analysis_regression'),
]
