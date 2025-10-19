from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # 1. 관리자 페이지 연결
    path('admin/', admin.site.urls),
    
    # 2. 루트 경로('/')를 'main' 앱의 URL 설정으로 연결 (프로젝트 홈 포함)
    path('', include('main.urls')),
    
    # 'lost/' 경로는 main.urls에 필요한 내용이 포함되어 있다면 제거하는 것이 좋습니다.
    # main.urls 내에서 /trends, /correlation 등을 처리하게 됩니다.
]