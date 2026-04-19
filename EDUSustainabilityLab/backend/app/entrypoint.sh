#!/bin/sh

echo "Waiting for MySQL to start..."

while ! nc -z db 3306; do
  sleep 1
done

echo "MySQL started successfully. Running migrations..."
exec "$@"
