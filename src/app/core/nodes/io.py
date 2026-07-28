"""Input/output node handlers."""

from __future__ import annotations

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


@register_node("track_source")
class TrackSourceNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        return {
            "out": {
                "title": track.title or "",
                "artist_name": track.artist_name or "",
                "album_name": track.album_name or "",
                "duration_ms": track.duration_ms,
                "source_id": track.source_id,
                "track_number": track.track_number,
                "disc_number": track.disc_number,
                "mbid": track.mbid,
                "artist_mbid": track.artist_mbid,
                "album_mbid": track.album_mbid,
            }
        }


@register_node("constant")
class ConstantNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        return {"out": self._config.get("value", "")}


@register_node("match_output")
class MatchOutputNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        return {"out": inputs.get("in")}
