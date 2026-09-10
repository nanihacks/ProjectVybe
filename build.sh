#!/usr/bin/env bash
set -euo pipefail

python manage.py collectstatic --noinput

# Run database migrations as a controlled deployment step after the build.
