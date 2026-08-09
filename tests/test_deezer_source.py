from src.app.core.models import TrackMetadata
from src.app.core.sources.deezer import DeezerSource


def test_deezer_parser_keeps_source_metadata_mapping():
    playlist = DeezerSource._parse_playlist_data(
        "12345",
        {
            "title": "My Mix",
            "description": "A playlist",
            "tracks": {
                "data": [
                    {
                        "id": 999,
                        "title": "Song",
                        "artist": {"name": "Artist"},
                        "album": {"title": "Album"},
                        "duration": 180,
                    }
                ]
            },
        },
    )

    assert playlist.source_id == "12345"
    assert playlist.description == "A playlist"
    assert playlist.tracks == [
        TrackMetadata(
            title="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
            source_id="999",
        )
    ]


def test_deezer_parser_skips_tracks_without_title():
    playlist = DeezerSource._parse_playlist_data(
        "12345",
        {
            "title": "My Mix",
            "tracks": {"data": [{"id": 1}, {"id": 2, "title": "Kept"}]},
        },
    )

    assert playlist.tracks == [TrackMetadata(title="Kept", source_id="2")]


def test_deezer_supports_playlist_and_link_urls():
    assert DeezerSource.supports_url("https://www.deezer.com/playlist/12345")
    assert DeezerSource.supports_url("http://deezer.com/playlist/12345")
    assert not DeezerSource.supports_url("https://www.deezer.com/album/12345")


def test_deezer_parses_playlist_id():
    assert DeezerSource._parse_playlist_id("https://www.deezer.com/playlist/12345") == "12345"
