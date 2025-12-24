from django.urls import path
from main import views

urlpatterns = [
    path('', views.analysis_view, {'section': 'visualization'}, name='analysis_visualization'),

    #LostItem 아카이브
    path('archive/lostitem/', views.lostitem_list, name='lostitem_list'), 
    path('archive/lostitem/create/', views.lostitem_create, name='lostitem_create'), 
    path('archive/lostitem/update/<int:pk>/', views.lostitem_update, name='lostitem_update'),
    path('archive/lostitem/upload/csv/', views.lostitem_upload_csv, name='lostitem_upload_csv'), 

    #추가 분석 페이지
    path('analysis/table/', views.analysis_view, {'section': 'table'}, name='analysis_table'),
    path('analysis/stats/', views.analysis_view, {'section': 'stats'}, name='analysis_stats'),
    path('analysis/boxPlot/', views.analysis_view, {'section': 'boxPlot'}, name='analysis_boxPlot'),
    path('analysis/regression/', views.analysis_view, {'section': 'regression'}, name='analysis_regression'),
    path('analysis/dumbbell/', views.analysis_view, {'section': 'dumbbellPlot'}, name='analysis_dumbbell'),
]
