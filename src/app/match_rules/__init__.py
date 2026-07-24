"""YAML-based match rule system.

Rules are defined as YAML files (defaults shipped with the codebase)
and stored as raw YAML text in the database. Canvas positions are
computed on-load using a hierarchical left-to-right auto-layout.
"""

from src.app.match_rules.layout import auto_layout
from src.app.match_rules.parser import canvas_to_yaml, yaml_to_canvas
from src.app.match_rules.validator import ValidationError, validate_rule_yaml

__all__ = [
    "auto_layout",
    "canvas_to_yaml",
    "yaml_to_canvas",
    "validate_rule_yaml",
    "ValidationError",
]
