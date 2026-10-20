#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python manage.py collectstatic --noinput

# Run database migrations as a controlled deployment step after the build.
