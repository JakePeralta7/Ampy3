#!/bin/bash
set -e

echo "Waiting for web service to be configured..."

# Wait for web to be reachable and configured
until curl -sf http://web:8000/api/v1/system/health | grep -q '"configured":true'; do
  echo "  App not configured yet, waiting..."
  sleep 3
done

echo "App is configured. Starting Celery worker..."
exec celery -A app.worker.app:celery_app worker --loglevel=INFO