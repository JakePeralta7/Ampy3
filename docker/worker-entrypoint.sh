#!/bin/bash
# Worker entrypoint - waits for app:configured signal before starting Celery

set -euo pipefail

echo "=== Ampy3 Worker Entrypoint ==="

# Valkey connection details from environment
VALKEY_HOST="${VALKEY_HOST:-valkey}"
VALKEY_PORT="${VALKEY_PORT:-6379}"

# Function to check if instance is already configured (secret_key in DB)
check_db_configured() {
    PGPASSWORD="${DATABASE_PASSWORD}" psql \
        -h "${DATABASE_HOST:-postgres}" \
        -U "${DATABASE_USERNAME:-ampy3}" \
        -d "${DATABASE_NAME:-ampy3}" \
        -t -c "SELECT EXISTS(SELECT 1 FROM config WHERE key='secret_key')" 2>/dev/null | grep -q "t"
}

# First, check if already configured in DB (e.g., restart after setup)
if check_db_configured; then
    echo "Instance already configured in database. Starting Celery immediately..."
    exec celery -A app.worker.app worker "$@"
fi

echo "Instance not configured. Waiting for 'app:configured' signal on Valkey..."

# Use Python with valkey library (already installed) to subscribe to the channel
python3 << 'EOF'
import sys
import time
import os

import valkey

valkey_host = os.getenv("VALKEY_HOST", "valkey")
valkey_port = int(os.getenv("VALKEY_PORT", "6379"))

def wait_for_signal():
    while True:
        print("Subscribing to app:configured channel...")
        try:
            # Create valkey client
            client = valkey.Redis(
                host=valkey_host,
                port=valkey_port,
                decode_responses=True,
                socket_timeout=None,
                socket_connect_timeout=5
            )
            
            pubsub = client.pubsub()
            pubsub.subscribe("app:configured")
            print("Subscribed to app:configured channel")
            
            for message in pubsub.listen():
                print(f"Valkey message: {message}")
                if message["type"] == "message" and message["data"] == "1":
                    print("Received app:configured signal. Starting Celery worker...")
                    pubsub.unsubscribe("app:configured")
                    pubsub.close()
                    client.close()
                    return True
                    
        except Exception as e:
            print(f"Valkey error: {e}")
            time.sleep(5)
            continue
        
        print("Valkey subscription ended, retrying in 5s...")
        time.sleep(5)

if __name__ == "__main__":
    wait_for_signal()
    sys.exit(0)
EOF

# If Python script returns, start Celery
echo "Received app:configured signal. Starting Celery worker..."
exec celery -A app.worker.app worker "$@"