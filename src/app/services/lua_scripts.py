"""Valkey/Redis Lua scripts.

Centralizes all Lua scripts used by the application for atomic operations.
Scripts are loaded once and executed via EVALSHA for performance.

Each script is documented with its KEYS and ARGV schema.
Note: Valkey uses the same Redis API, so `redis.call` is correct for Valkey.
"""

from __future__ import annotations

# ─── Config Fingerprint ────────────────────────────────────────────

# Atomic config fingerprint check-and-set.
# KEYS:  [0] config:fingerprint key
# ARGV:  [0] new_fingerprint (string)
# Returns: [changed_int, status_str]
#   changed_int: 1 if fingerprint was updated, 0 if unchanged
#   status_str: 'set' (first write), 'unchanged', 'changed'
FINGERPRINT_SCRIPT = """
local key = KEYS[1]
local new_fp = ARGV[1]
local current = redis.call('GET', key)
if not current then
    redis.call('SET', key, new_fp)
    return {1, 'set'}
end
if current == new_fp then
    return {0, 'unchanged'}
end
redis.call('SET', key, new_fp)
return {1, 'changed'}
"""

# ─── Rate Limiting ─────────────────────────────────────────────────

# Atomic fixed-window rate limit (INCR + EXPIRE in single round-trip).
# KEYS:  [0] rate_limit_key
# ARGV:  [0] window_seconds (int)
# Returns: count (int) — incremented counter value
RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""

# ─── Dispatch Lock Management ──────────────────────────────────────

# Compare-and-delete dispatch lock + counter key.
# KEYS:  [0] lock_key, [1] counter_key
# ARGV:  [0] expected_token (string)
# Returns: 1 if lock was deleted (we owned it), 0 if token mismatch/expired
RELEASE_LOCK_SCRIPT = """\
local current = redis.call('get', KEYS[1])
if not current or tostring(current) ~= ARGV[1] then
  return 0
end
redis.call('del', KEYS[1], KEYS[2])
return 1
"""

# Decrement pending-child counter; last child deletes lock + counter.
# KEYS:  [0] lock_key, [1] counter_key
# ARGV:  [0] owner_token (string), [1] ttl_seconds (string/int)
# Counter value format: "token:count" (e.g., "abc123:3")
# Returns: 1 if lock was deleted (last child), 0 otherwise
CHILD_FINISHED_SCRIPT = """\
local val = redis.call('get', KEYS[2])
if not val then
  return 0
end
-- Expected format: "token:count"
local tok, n = string.match(val, '^(.-):(%d+)$')
if not tok or tok ~= ARGV[1] then
  return 0
end
n = tonumber(n) - 1
if n <= 0 then
  redis.call('del', KEYS[2])
  redis.call('del', KEYS[1])
  return 1
end
redis.call('set', KEYS[2], tok .. ':' .. n, 'EX', ARGV[2])
return 0
"""

# ─── Script Registry ───────────────────────────────────────────────

# Map of script name -> script source.
# Used for automatic loading/registration.
SCRIPTS: dict[str, str] = {
    "fingerprint": FINGERPRINT_SCRIPT,
    "rate_limit": RATE_LIMIT_SCRIPT,
    "release_lock": RELEASE_LOCK_SCRIPT,
    "child_finished": CHILD_FINISHED_SCRIPT,
}

# ─── Helper Functions ──────────────────────────────────────────────


async def load_all_scripts(client) -> dict[str, str]:
    """Load all scripts into Valkey and return SHA cache.

    Args:
        client: Async Valkey client

    Returns:
        Dict mapping script name -> SHA
    """
    shas = {}
    for name, script in SCRIPTS.items():
        shas[name] = await client.script_load(script)
    return shas


async def ensure_scripts_loaded(client, shas: dict[str, str] | None = None) -> dict[str, str]:
    """Ensure all scripts are loaded, handling NoScriptError.

    Args:
        client: Async Valkey client
        shas: Optional existing SHA cache to update

    Returns:
        Updated SHA cache
    """
    if shas is None:
        shas = {}

    for name, script in SCRIPTS.items():
        if name not in shas:
            shas[name] = await client.script_load(script)
    return shas
