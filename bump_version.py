#!/usr/bin/env python
"""Bump the app version in every location where it is defined.

The ``version`` under ``[project]`` in pyproject.toml is the source of truth;
a bump rewrites every location to match it:

    pyproject.toml            [project] version
    src/app/__init__.py       __version__
    web/package.json          version

Usage:
    python bump_version.py 0.2.0     # Set an explicit version (X.Y.Z)
    python bump_version.py minor     # Increment major | minor | patch
    python bump_version.py check     # Verify all locations agree; edit nothing

No git commit or tag is created.
"""

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

VERSION_PATHS = {
    "pyproject.toml": REPO_ROOT / "pyproject.toml",
    "__init__.py": REPO_ROOT / "src" / "app" / "__init__.py",
    "package.json": REPO_ROOT / "web" / "package.json",
}

VERSION_PATTERNS = {
    "pyproject.toml": r'^version\s*=\s*"(?P<version>[^"]+)"',
    "__init__.py": r'^__version__\s*=\s*"(?P<version>[^"]+)"',
    "package.json": r'^\s*"version"\s*:\s*"(?P<version>[^"]+)"',
}

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

USAGE = f"Usage: python {Path(__file__).name} 0.2.0 | major | minor | patch | check"


def read_current(name: str) -> str | None:
    path = VERSION_PATHS[name]
    text = path.read_text(encoding="utf-8")
    match = re.search(VERSION_PATTERNS[name], text, re.MULTILINE)
    return match.group("version") if match else None


def write_version(name: str, version: str) -> None:
    path = VERSION_PATHS[name]
    text = path.read_text(encoding="utf-8")
    match = re.search(VERSION_PATTERNS[name], text, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Could not locate the version field in {path}")
    start, end = match.span("version")
    path.write_text(f"{text[:start]}{version}{text[end:]}", encoding="utf-8")


def increment(current: str, part: str) -> str:
    major, minor, patch = (int(piece) for piece in current.split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    return f"{major}.{minor}.{patch}"


def verify(version: str) -> bool:
    ok = True
    for name in VERSION_PATHS:
        value = read_current(name)
        matches = value == version
        ok = ok and matches
        marker = "OK" if matches else "MISMATCH"
        print(f"  {name:<18} {value or 'MISSING':<12} {marker}")
    return ok


def check() -> None:
    current = read_current("pyproject.toml")
    if current is None:
        print("Could not determine the current version from pyproject.toml.")
        sys.exit(1)
    print(f"Canonical version: {current}")
    if not verify(current):
        sys.exit(1)


def bump(raw: str) -> None:
    current = read_current("pyproject.toml")
    if current is None:
        print("Could not determine the current version from pyproject.toml.")
        sys.exit(1)

    if raw in ("major", "minor", "patch"):
        new = increment(current, raw)
    elif VERSION_RE.match(raw):
        new = raw
    else:
        print(f"Invalid version {raw!r}: expected X.Y.Z or major|minor|patch.")
        sys.exit(1)

    if new == current:
        print(f"Version is already {current}; nothing to change.")
        return

    print(f"Bumping version {current} -> {new}")
    for name in VERSION_PATHS:
        previous = read_current(name)
        write_version(name, new)
        print(f"  {name:<18} {previous} -> {new}")

    print("Verifying...")
    if not verify(new):
        print(f"ERROR: not all locations were updated to {new}")
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)
    try:
        check() if sys.argv[1] == "check" else bump(sys.argv[1])
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
