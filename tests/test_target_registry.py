"""Regression tests for sync target registration.

Targets self-register when ``src.app.core.targets`` is imported. That package
auto-imports its children, so a target implemented as a *subpackage* (``plex/``,
``jellyfin/``) must be imported too — skipping packages leaves the registry
empty and every lookup fails with ``Unknown target 'X'. Available: (none)``.

The check runs in a subprocess so the registry starts empty and cannot be
populated by another test module's imports.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_CHECK = """
import src.app.services  # noqa: F401  (service layer must be enough)
from src.app.core.targets.registry import TargetRegistry

print(",".join(sorted(TargetRegistry._targets)))
print(",".join(sorted(TargetRegistry._factories)))
"""


def test_importing_services_registers_all_targets():
    result = subprocess.run(
        [sys.executable, "-c", _CHECK],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    targets, factories = result.stdout.strip().splitlines()

    assert targets == "Jellyfin,Plex"
    assert factories == "Jellyfin,Plex"
