from django.urls import path
from . import views
from .views import lostitem_list, lostitem_create, lostitem_update

urlpatterns = [
        # http://127.0.0.1:8000/ 로 접속하면 lostitem_list 뷰를 실행
    path('', views.lostitem_list, name='lostitem_list'), 
    
    # CSV 업로드 기능 URL 추가
    path('upload/csv/', views.lostitem_upload_csv, name='lostitem_upload_csv'), 

    path("lost/", lostitem_list, name="lostitem_list"),
    path("lost/new/", lostitem_create, name="lostitem_create"),
    path("lost/<str:pk>/edit/", lostitem_update, name="lostitem_update"),
]