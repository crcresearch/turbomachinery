from pr.settings.base import *

DEBUG = True
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
