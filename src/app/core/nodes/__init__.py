"""Node-graph node handler abstractions.

Importing this package auto-imports all handler submodules so that
every ``@register_node`` decorator runs and populates the registry.
"""

# Ensure all handler modules are imported so decorators register.
import src.app.core.nodes.io  # noqa: F401
import src.app.core.nodes.logic  # noqa: F401
import src.app.core.nodes.matching  # noqa: F401
import src.app.core.nodes.musicbrainz  # noqa: F401
import src.app.core.nodes.search  # noqa: F401
import src.app.core.nodes.similarity  # noqa: F401
import src.app.core.nodes.transform  # noqa: F401
from src.app.core.nodes.base import (  # noqa: F401
    NodeConfig,
    NodeHandlerBase,
    NodeInputs,
    NodeOutputs,
)
from src.app.core.nodes.registry import NodeRegistry  # noqa: F401
