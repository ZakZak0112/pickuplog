# pickuplog/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # 1. 관리자 페이지 연결
    path('admin/', admin.site.urls),
    
    # 2. 루트 경로('/')로 들어오는 모든 요청을 'main.urls'로 연결 (핵심)
    path('', include('main.urls')),
]