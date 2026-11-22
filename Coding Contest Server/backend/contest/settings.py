import os
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CONTEST_DATA", BASE / "var"))
SECRET_KEY = (DATA / "django.key").read_text().strip()
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver","codeclash.test","contest.test","10.50.0.1"]
ROOT_URLCONF = "contest.urls"
WSGI_APPLICATION = "contest.wsgi.application"
INSTALLED_APPS = ["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","arena"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware","whitenoise.middleware.WhiteNoiseMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","arena.access.RosterAccess","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE.parent/"frontend/templates"],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
DATABASES = {"default":{"ENGINE":"django.db.backends.sqlite3","NAME":DATA/"contest.sqlite3","OPTIONS":{"timeout":15,"transaction_mode":"IMMEDIATE"}}}
if (DATA / "db-key").exists() and os.environ.get("CONTEST_TEST_SQLITE")!="1":
    DATABASES = {"default":{"ENGINE":"django.db.backends.mysql","NAME":"contest_pilot","HOST":str(DATA/"mysql.sock"),"USER":"contest_app","PASSWORD":(DATA/"db-key").read_text().strip(),"OPTIONS":{"charset":"utf8mb4"}}}
elif os.environ.get("CONTEST_DB_NAME"):
    DATABASES = {"default":{"ENGINE":"django.db.backends.mysql","NAME":os.environ["CONTEST_DB_NAME"],"HOST":"localhost","USER":os.environ["CONTEST_DB_USER"],"PASSWORD":os.environ["CONTEST_DB_PASSWORD"],"OPTIONS":{"charset":"utf8mb4"}}}
STATIC_URL = "/static/"
STATIC_ROOT = DATA / "static"
STATICFILES_DIRS = [BASE.parent/"frontend/dist"]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_AGE=4*60*60
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
USE_TZ = True
TIME_ZONE = "UTC"
DATA_UPLOAD_MAX_MEMORY_SIZE = 200000
AUTH_PASSWORD_VALIDATORS = [{"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},{"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"}]
