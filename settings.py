from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'dev-only-secret-key'
DEBUG = True
ALLOWED_HOSTS = []
STATIC_URL = '/static/'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',  
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',   # admin 필수
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # admin 필수
    'django.contrib.messages.middleware.MessageMiddleware',      # admin 필수
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'pickuplog.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',  # admin 필수
        'DIRS': [BASE_DIR / 'main' / 'templates', BASE_DIR / 'main' / 'templates'],
        'APP_DIRS': True,                                              # admin 필수
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',          # admin 필수
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pickuplog.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',   # ← 이게 없으면 방금 같은 에러
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATICFILES_DIRS = [
    # 이 경로는 pickuplog 프로젝트 폴더 바로 아래의 static 폴더를 명확히 지정합니다.
    # BASE_DIR이 프로젝트 루트를 가리킨다고 가정합니다.
    BASE_DIR / "pickuplog" / "pickuplog" / "static", 
    
    # 만약 main 앱 내부에 static 폴더를 만들어 pico.min.css를 넣었다면, 이 경로도 추가해야 합니다.
    # BASE_DIR / 'main' / 'static',
]

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static', 
]

LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
