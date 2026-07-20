"""pytest configuration: set required env vars before any imports."""
import os

os.environ.setdefault("PLEX_HOST", "http://localhost:32400")
os.environ.setdefault("PLEX_TOKEN", "test-token")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "gemma4-e4b-128:latest")
