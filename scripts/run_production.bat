@echo off
setlocal
cd /d "%~dp0\.."

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if "%DJANGO_SECRET_KEY%"=="" set DJANGO_SECRET_KEY=sop-portal-change-this-secret-key
if "%DJANGO_DEBUG%"=="" set DJANGO_DEBUG=False
if "%DJANGO_ALLOWED_HOSTS%"=="" set DJANGO_ALLOWED_HOSTS=*
if "%SERVE_MEDIA_IN_PRODUCTION%"=="" set SERVE_MEDIA_IN_PRODUCTION=True

python manage.py migrate
python manage.py collectstatic --noinput

if "%PORT%"=="" set PORT=8000
waitress-serve --listen=0.0.0.0:%PORT% sop_portal.wsgi:application
