"""MusicBrainz search node handler."""

from __future__ import annotations

from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


@register_node("search_musicbrainz")
class SearchMusicBrainzNode(NodeHandlerBase):
    """Search MusicBrainz for recording info."""

    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        from src.app.core.musicbrainz import MusicBrainzResolver

        data = inputs.get("in", {})
        title = data.get("title", track.title or "")
        artist = data.get("artist_name", track.artist_name or "")

        if not title:
            return {"out": None}

        resolver = MusicBrainzResolver()
        recordings = await resolver.search_recording(title, artist)
        if recordings:
            return {"out": recordings[0]}
        return {"out": None}
