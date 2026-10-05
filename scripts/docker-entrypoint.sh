#!/bin/sh
set -e

echo "waiting for db..."
until python -c "import socket; s=socket.socket(); s.connect(('db',5432)); s.close()" 2>/dev/null; do
  echo "waiting for db..."
  sleep 2
done

echo "running migrations..."
alembic upgrade head

exec "$@"
