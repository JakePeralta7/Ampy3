# Ampy3

[![CI](https://github.com/JakePeralta7/Ampy3/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JakePeralta7/Ampy3/actions/workflows/ci.yml)

Syncs YouTube Music playlists to Plex or Jellyfin using MusicBrainz IDs for metadata matching.

## Quick Start

```bash
git clone https://github.com/JakePeralta7/Ampy3 && cd Ampy3
docker compose up --build -d
```

Open `http://localhost:8000` and complete setup/configuration to connect your target server.

## Stack

- **Backend:** Python / FastAPI + Celery workers
- **Frontend:** React / TypeScript / Tailwind
- **Infra:** Docker Compose, PostgreSQL, Valkey (Redis)
