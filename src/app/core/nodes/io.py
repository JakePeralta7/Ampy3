"""Input/output node handlers."""

from __future__ import annotations

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeConfig, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


@register_node("track_source")
async def _handle_track_source(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
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
async def _handle_constant(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
    return {"out": config.get("value", "")}


@register_node("match_output")
async def _handle_match_output(
    config: NodeConfig,
    track: TrackMetadata,
    inputs: NodeInputs,
) -> NodeOutputs:
    return {"out": inputs.get("in")}
