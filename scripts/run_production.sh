#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-sop-portal-change-this-secret-key}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-False}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export SERVE_MEDIA_IN_PRODUCTION="${SERVE_MEDIA_IN_PRODUCTION:-True}"

python manage.py migrate
python manage.py collectstatic --noinput

PORT="${PORT:-8000}"
exec waitress-serve --listen=0.0.0.0:${PORT} sop_portal.wsgi:application
