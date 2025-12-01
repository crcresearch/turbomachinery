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

#LOGIN_URL = 'login/'
#LOGOUT_URL = 'logout/'

#CAS_REDIRECT_URL = '/reports/home/'
#CAS_IGNORE_REFERER = True
#CAS_SERVER_URL = 'https://login.nd.edu/cas/login'
#CAS_AUTO_CREATE_USERS = False

LOGIN_URL = '/reports/oidc/authenticate/'
LOGIN_REDIRECT_URL = '/reports/'
LOGOUT_REDIRECT_URL = '/reports/'

# OIDC (Okta) authentication
_OIDC_BASE_URL = 'https://okta.nd.edu/oauth2/ausxosq06SDdaFNMB356/v1'
OIDC_RP_CLIENT_ID = '0oa2z5it0yam6HvF7357'
OIDC_RP_CLIENT_SECRET = 'l99xNmmM75TPdzaBidTIZkU1DSdB4SDchRvcWIwA'

OIDC_OP_AUTHORIZATION_ENDPOINT = "{}/authorize".format(_OIDC_BASE_URL)
OIDC_OP_TOKEN_ENDPOINT = "{}/token".format(_OIDC_BASE_URL)
OIDC_OP_USER_ENDPOINT = "{}/userinfo".format(_OIDC_BASE_URL)

OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = "{}/keys".format(_OIDC_BASE_URL)

OIDC_OP_LOGOUT_URL_METHOD = "users.provider_logout"
OIDC_OP_LOGOUT_ENDPOINT = "{}/logout".format(_OIDC_BASE_URL)

# This setting restricts Django from creating new users upon first login to okta
OIDC_CREATE_USER = False #ENV.bool('DJANGO_OIDC_CREATE_USER', default=False)  # Default is True in OIDC library

# This is the middleware setting to say how often to check for valid okta session.
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 900 #ENV.int('DJANGO_OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS', default=900)

# We have to store the ID token (not the access token) to do a provider logout.
OIDC_STORE_ID_TOKEN = True

AUTHENTICATION_BACKENDS = (
    #'django.contrib.auth.backends.ModelBackend',
    #'cas.middleware.CASMiddleware',
    #'cas.backends.CASBackend'
    'mozilla_django_oidc.auth.OIDCAuthenticationBackend',
)

#CAS_REDIRECT_URL = '/reports/'
#CAS_IGNORE_REFERER = True
#CAS_SERVER_URL = 'https://login.nd.edu/cas/login'
#CAS_AUTO_CREATE_USERS = True

