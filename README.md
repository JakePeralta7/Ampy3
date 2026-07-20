# Ampy3 - YouTube Music Sync & Plex Bridge

Ampy3 syncs music playlists from services like YouTube Music to Plex, utilizing unique identifiers from MusicBrainz to ensure correct metadata matching and persistent cross-platform linkage.

## 🚀 Getting Started

### Prerequisites
*   Docker & Docker Compose
*   FFmpeg (required for `yt-dlp` video/audio stripping)
*   Plex Media Server instance running locally with user access credentials.

### Setup and Build

1.  **Clone the repository:**
    ```bash
    git clone <repo-url> adupy3
    cd adupy3
    ```

2.  **Environment Variables:** Create a `.env` file in the root directory:
    ```ini
    # Required for database operation/caching
    REDIS_HOST=redis
    REDIS_PORT=6379
    CELERY_BROKER_URL=redis://redis:6379/0
    CELERY_RESULT_BACKEND=redis://redis:6379/1

    # Plex credentials (Token should have write access)
    PLEX_HOST=http://plex.lan:3240
    PLEX_TOKEN=<YOUR_PLEX_API_TOKEN> 
    
    # Application environment flag
    APP_ENV=development
    DEBUG=True
    ```

3.  **Build and Run:** Use Docker Compose to build all services (Web app, Backend API, Celery Workers, Redis/Valkey).

    ```bash
    docker compose up --build
    ```

## 🔗 Architecture Overview

- **Frontend:** React SPA served by the `web` container. Used for UI configuration and triggering sync jobs.
- **Backend API (FastAPI):** Served by the `api` container. Handles web requests, mediates state changes, and triggers background tasks via Celery.
- **Celery Workers:** Dedicated workers that execute the resource-intensive synchronization logic (`SyncOrchestrator`).
- **Data Stores:** Valkey/Redis handles message queuing (Celery Broker) and storing task status results (Celery Backend).

## 📋 Usage Flow

1.  **Configuration:** Configure API tokens in `.env`.
2.  **Manual Test Sync:** Use the frontend UI to select a source playlist and trigger sync. This sends an HTTP POST request to `/v1/playlists/sync`.
3.  **Background Processing:** The API returns immediately with a `task_id`, while the actual work happens in Celery Workers.
4.  **Status Monitoring:** Poll the `/v1/status/{task_id}` endpoint periodically until `finished: true` is returned, or an error occurs.

## 🏗️ Code Organization & Architecture

### Backend (Python/FastAPI)

**Configuration**
- `src/app/settings.py`: Canonical Pydantic `BaseSettings` config. All settings load from environment variables.
- `.env` file: Local overrides for development
- No wrapper or template files needed

**API Organization**
- `src/main.py`: Application entry point and FastAPI setup
- `src/app/api/__init__.py`: Centralized router registration via `register_routers(app)`
- `src/app/api/`: All API route handlers
  - `chat_history.py`: Chat history endpoints (`/v1/chat/history`)
  - `langgraph_handler.py`: LangGraph agent endpoint (`/api/chat`)
  - `playlists.py`: Playlist management (`/api/v1/playlists`)

**Service Layer (Dependency Injection)**
- `src/app/services/__init__.py`: `ServiceContainer` with lazy singleton factories
  - `get_plex_client()`: Plex Media Server client
  - `get_ollama_client()`: Ollama/LLM client
  - `get_celery_app()`: Celery task queue app
- Usage: Import and call `get_plex_client()` instead of global instances for better testability

**Business Logic**
- `src/app/amp/`: Music synchronization domain
  - `plex/`: Plex Media Server integration
  - `services/orchestrator.py`: Main sync orchestration logic
  - `sources/ytmusic.py`: YouTube Music source parser
- `src/app/llm/`: LLM/Agent integration
  - `agents/sync_agent.py`: LangGraph agent for sync operations
  - `tools/`: Tool definitions for the agent
  - `history.py`: Chat message persistence (Valkey)
- `src/app/tasks.py`: Celery task definitions

### Frontend (React/TypeScript)

**Pages & Routing**
- `web/src/pages/`: Page-level components
  - `Home.tsx`: Playlists page
  - `Chat.tsx`: Chat interface page
- `web/src/router.tsx`: Centralized route definitions (React Router v6+)
- `web/src/main.tsx`: App entry point with navigation

**API Clients**
- `web/src/api/client.ts`: Unified HTTP client with error handling and helpers
  - `apiRequest()`: Base fetch wrapper
  - `apiGet()`, `apiPost()`, `apiDelete()`: Convenience helpers
- `web/src/api/chat.ts`: Chat-specific client using unified HTTP client
- `web/src/api/index.ts`: Centralized API exports

**Components & Hooks**
- `web/src/components/Chat/`: Chat feature components
- `web/src/hooks/useAgentChat.ts`: Chat state management hook
- `web/src/components/README.md`: Component organization guide

### Testing
- `tests/`: Python unit and integration tests
  - `conftest.py`: Pytest configuration with env var setup
  - `test_chat_api.py`: API endpoint tests
  - `test_chat_history.py`: Message history tests
  - `test_ollama_client.py`: LLM client tests

## 🧑‍💻 Running Tests (Development)

To ensure data integrity across the sync logic, run the unit and integration tests:
```bash
# Requires a minimal test/docker setup if running against containerized services
pytest --rootdir=./tests
```