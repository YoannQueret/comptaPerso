#!/bin/sh
set -e

echo "Applying database migrations..."
flask db upgrade

echo "Starting server..."
exec gunicorn -b "0.0.0.0:${PORT:-5000}" -w 2 --timeout 60 run:app
