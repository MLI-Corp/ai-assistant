#!/bin/bash
set -e

# Wait for the database to be ready
echo "Waiting for database to be ready..."
until nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

# Run migrations if needed
echo "Running migrations..."
alembic upgrade head

# Start the application
echo "Starting application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
