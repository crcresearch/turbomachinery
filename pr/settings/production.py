from pr.settings.base import *

SECRET_KEY = ENV('SECRET_KEY')
DEBUG = False


ALLOWED_HOSTS = ['turbo.crc.nd.edu']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': ENV('POSTGRES_DB'),
        'USER': ENV('POSTGRES_USER'),
        'PASSWORD': ENV('POSTGRES_PASSWORD'),
        'HOST': ENV('POSTGRES_HOST'),
        'PORT': ENV('POSTGRES_PORT', default='5432')
    }
}

LOGIN_URL = '/reports/login/'
LOGOUT_URL = '/reports/logout/'

CAS_REDIRECT_URL = '/reports/home/'
CAS_IGNORE_REFERER = True
CAS_SERVER_URL = 'https://login.nd.edu/cas/login'
CAS_AUTO_CREATE_USERS = False


#AUTHENTICATION_BACKENDS = (
#    'django.contrib.auth.backends.ModelBackend',
#    'cas.middleware.CASMiddleware',
#)

CAS_REDIRECT_URL = '/reports/'
CAS_IGNORE_REFERER = True
CAS_SERVER_URL = 'https://login.nd.edu/cas/login'
CAS_AUTO_CREATE_USERS = False

