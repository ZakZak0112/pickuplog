from django.urls import path
from main import views

urlpatterns = [
    # 1. Home 및 분석 페이지 연결
    path('', views.home, name='home'),
    path('trend/', views.trend_analysis, name='trend'), 
    path('correlation/', views.correlation_analysis, name='correlation'),
    path('insight/', views.insight_report, name='insight'),

    # 2. LostItem CRUD 및 아카이브 연결
    path('archive/lostitem/', views.lostitem_list, name='lostitem_list'), 
    path('archive/lostitem/create/', views.lostitem_create, name='lostitem_create'), 
    path('archive/lostitem/update/<int:pk>/', views.lostitem_update, name='lostitem_update'),
    path('archive/lostitem/upload/csv/', views.lostitem_upload_csv, name='lostitem_upload_csv'), 

    #추가 분석 페이지
    path('weather-report/', views.lostitem_analysis_view, name='weather_lostitem_report'),


]
