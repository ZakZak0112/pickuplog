from pathlib import Path

# 💡 수정 1: BASE_DIR이 settings.py 파일이 있는 'pickuplog' 폴더 자체를 가리키도록 수정
# (parent.parent -> parent)
BASE_DIR = Path(__file__).resolve().parent 

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'pickuplog.urls' 

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# 💡 수정 2: 파일 구조에 맞게 WSGI_APPLICATION 경로 수정 (config.wsgi -> pickuplog.wsgi)
WSGI_APPLICATION = 'pickuplog.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 정적 파일 설정 (Static Files Configuration)

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static', 
]


LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'