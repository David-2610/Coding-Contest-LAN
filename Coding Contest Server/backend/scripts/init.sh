#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")/.."
: "${CONTEST_DATA:=$PWD/var}"
export CONTEST_DATA
export LD_LIBRARY_PATH="$PWD/var/maria-runtime/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$CONTEST_DATA"
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets,os
p=Path(os.environ["CONTEST_DATA"])/"django.key"
if not p.exists():
    with p.open("x") as f: f.write(secrets.token_urlsafe(48))
PY
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput --verbosity 0
# Set up the organizer with manage.py createsuperuser --username organizer.
