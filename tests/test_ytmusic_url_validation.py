from src.app.core.sources.ytmusic import YouTubeMusicSource


def test_validates_wellformed_playlist_urls():
    assert YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com/playlist?list=PL1234567890abcdefg"
    )
    assert YouTubeMusicSource.is_valid_url(
        "http://music.youtube.com/playlist?list=PL1234567890abcdefg"
    )
    assert YouTubeMusicSource.is_valid_url(
        "https://www.music.youtube.com/playlist?list=PL1234567890abcdefg"
    )


def test_accepts_share_urls_with_extra_query_params():
    assert YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com/playlist?list=PL1234567890abcdefg&si=abc123"
    )
    assert YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com/playlist?list=PL1234567890abcdefg&feature=share"
    )
    assert (
        YouTubeMusicSource._parse_playlist_id(
            "https://music.youtube.com/playlist?list=PL1234567890abcdefg&si=abc123"
        )
        == "PL1234567890abcdefg"
    )


def test_rejects_urls_without_valid_scheme_or_host():
    assert not YouTubeMusicSource.is_valid_url("ftp://music.youtube.com/playlist?list=PLx")
    assert not YouTubeMusicSource.is_valid_url("https://evil.example.com/playlist?list=PLx")
    assert not YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com.evil.com/playlist?list=PLx"
    )


def test_rejects_substring_host_bypasses():
    assert not YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com@169.254.169.254/latest/meta-data/"
    )
    assert not YouTubeMusicSource.is_valid_url(
        "https://music.youtube.com@localhost:8000/playlist?list=PLx"
    )


def test_rejects_wrong_path_and_missing_playlist():
    assert not YouTubeMusicSource.is_valid_url("https://music.youtube.com/")
    assert not YouTubeMusicSource.is_valid_url("https://music.youtube.com/watch?v=abc")
    assert not YouTubeMusicSource.is_valid_url("https://music.youtube.com/playlist")


def test_rejects_non_string_and_empty():
    assert not YouTubeMusicSource.is_valid_url("")
    assert not YouTubeMusicSource.is_valid_url(None)
    assert not YouTubeMusicSource.is_valid_url(12345)


def test_supports_url_matches_valid():
    assert YouTubeMusicSource.supports_url(
        "https://music.youtube.com/playlist?list=PL1234567890abcdefg"
    )
    assert not YouTubeMusicSource.supports_url(
        "https://music.youtube.com.evil.com/playlist?list=PLx"
    )
