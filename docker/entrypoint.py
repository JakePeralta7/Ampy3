#!/usr/bin/env python
"""Entrypoint script for Ampy3 web service.

Reads proxy configuration from the database and starts uvicorn with appropriate
--proxy-headers and --forwarded-allow-ips settings.
"""

import os
import sys
import time

try:
    import psycopg
except ImportError:
    psycopg = None


def build_database_url() -> str:
    """Construct DATABASE_URL from environment variables.
    
    DATABASE_USERNAME and DATABASE_PASSWORD are required.
    Database host and port are hardcoded.
    """
    username = os.environ.get("DATABASE_USERNAME")
    password = os.environ.get("DATABASE_PASSWORD")
    
    if not username or not password:
        raise ValueError("DATABASE_USERNAME and DATABASE_PASSWORD env vars are required")
    
    host = "postgres"
    port = "5432"
    db = "ampy3"
    
    return f"postgresql://{username}:{password}@{host}:{port}/{db}"


def wait_for_database(max_retries: int = 30, retry_delay: int = 1) -> bool:
    """Wait for PostgreSQL to be ready.

    Returns True if database is ready, False if max retries exceeded.
    """
    try:
        database_url = build_database_url()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False

    # Parse connection string: postgresql://user:password@host:port/database
    parts = database_url.replace("postgresql://", "").split("@")
    if len(parts) != 2:
        print(f"ERROR: Invalid DATABASE_URL format: {database_url}", file=sys.stderr)
        return False

    user_pass, host_db = parts
    user, password = user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
    host, port, db = (host_db + ":5432").split(":")[0], "5432", host_db.split("/")[-1]

    if ":" in host_db.split("/")[0]:
        host, port = host_db.split("/")[0].rsplit(":", 1)

    print(f"Waiting for PostgreSQL at {host}:{port}...", file=sys.stderr)

    for attempt in range(max_retries):
        try:
            if psycopg:
                conn = psycopg.connect(
                    user=user, password=password, host=host, port=port, dbname=db
                )
                conn.close()
            else:
                import subprocess

                subprocess.run(
                    ["pg_isready", "-h", host, "-p", port, "-U", user],
                    check=True,
                    capture_output=True,
                )
            print("PostgreSQL is ready", file=sys.stderr)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(
                    f"  Attempt {attempt + 1}/{max_retries}: {e}. Retrying in {retry_delay}s...",
                    file=sys.stderr,
                )
                time.sleep(retry_delay)
            else:
                print(f"  Failed after {max_retries} attempts: {e}", file=sys.stderr)

    return False


def get_proxy_config() -> tuple[bool, list[str]]:
    """Read proxy configuration from database.

    Returns (behind_proxy, trusted_proxies_list)
    """
    try:
        database_url = build_database_url()
        
        if not psycopg:
            print("WARNING: psycopg not available, skipping proxy config", file=sys.stderr)
            return False, []

        # Parse connection string
        parts = database_url.replace("postgresql://", "").split("@")
        user_pass, host_db = parts
        user, password = user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
        host = host_db.split(":")[0]
        port = host_db.split(":")[1].split("/")[0] if ":" in host_db.split("/")[0] else "5432"
        db = host_db.split("/")[-1]

        conn = psycopg.connect(user=user, password=password, host=host, port=port, dbname=db)
        cursor = conn.cursor()

        # Query config table for proxy settings
        cursor.execute(
            "SELECT value FROM config WHERE key = %s",
            ("behind_proxy",),
        )
        behind_proxy_row = cursor.fetchone()
        behind_proxy = (
            behind_proxy_row[0].lower() in ("true", "1", "yes") if behind_proxy_row else False
        )

        cursor.execute(
            "SELECT value FROM config WHERE key = %s",
            ("trusted_proxies",),
        )
        trusted_proxies_row = cursor.fetchone()
        trusted_proxies_str = trusted_proxies_row[0] if trusted_proxies_row else ""
        trusted_proxies = (
            [ip.strip() for ip in trusted_proxies_str.split(",") if ip.strip()]
            if trusted_proxies_str
            else []
        )

        cursor.close()
        conn.close()

        return behind_proxy, trusted_proxies

    except Exception as e:
        print(f"WARNING: Failed to read proxy config from database: {e}", file=sys.stderr)
        return False, []


def build_uvicorn_cmd() -> list[str]:
    """Build uvicorn command with proxy configuration."""
    cmd = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

    behind_proxy, trusted_proxies = get_proxy_config()

    if behind_proxy and trusted_proxies:
        cmd.append("--proxy-headers")
        cmd.append(f"--forwarded-allow-ips={','.join(trusted_proxies)}")
        print(
            f"Proxy config: behind_proxy=true, trusted_ips={','.join(trusted_proxies)}",
            file=sys.stderr,
        )
    elif behind_proxy:
        print(
            "WARNING: behind_proxy=true but trusted_proxies is empty"
            " — proxy headers will NOT be trusted",
            file=sys.stderr,
        )

    # Check if initial setup is required
    setup_needed = check_setup_required()
    if setup_needed:
        print("Setup required: navigate to http://localhost:8000 to configure", file=sys.stderr)
    else:
        print("Setup completed, starting normally", file=sys.stderr)

    return cmd


def check_setup_required() -> bool:
    """Check if initial setup is needed (secret_key not in config table)."""
    try:
        database_url = build_database_url()
        
        if not psycopg:
            return True

        # Parse connection string
        parts = database_url.replace("postgresql://", "").split("@")
        user_pass, host_db = parts
        user, password = user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
        host = host_db.split(":")[0]
        port = host_db.split(":")[1].split("/")[0] if ":" in host_db.split("/")[0] else "5432"
        db = host_db.split("/")[-1]

        conn = psycopg.connect(user=user, password=password, host=host, port=port, dbname=db)
        cursor = conn.cursor()

        # Query config table for secret_key
        cursor.execute("SELECT value FROM config WHERE key = %s", ("secret_key",))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return not result  # Setup needed if secret_key not found

    except Exception as e:
        print(f"WARNING: Could not check setup status: {e}", file=sys.stderr)
        return True  # Assume setup needed on error


if __name__ == "__main__":
    # Wait for database
    if not wait_for_database():
        print("ERROR: Could not connect to database", file=sys.stderr)
        sys.exit(1)

    # Build and exec uvicorn command
    cmd = build_uvicorn_cmd()
    print(f"Executing: {' '.join(cmd)}", file=sys.stderr)

    # Use os.execvp to replace the current process with uvicorn
    os.execvp(cmd[0], cmd)
