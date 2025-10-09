from django.contrib import admin
from django.urls import path, include
from main.views import lostitem_list

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lostitem_list, name='home'), 
    path('', include('main.urls')),   # ← main 앱 URL 연결
    path('lost/', include('main.urls')), 
]
