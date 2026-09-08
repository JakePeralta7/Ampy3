"""Explore provider discovery endpoints."""

from src.app.api import explore as explore_api


async def test_list_providers_returns_auth_required(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.app.api.explore.ExploreRegistry.list_providers",
        staticmethod(
            lambda: [
                {
                    "provider_id": "youtube_music",
                    "display_name": "YouTube Music",
                    "anonymous": True,
                    "auth_required": True,
                },
                {
                    "provider_id": "deezer",
                    "display_name": "Deezer",
                    "anonymous": True,
                    "auth_required": False,
                },
            ]
        ),
    )

    providers = await explore_api.list_providers(_user={"id": "user"})

    by_id = {p.provider_id: p for p in providers}
    assert by_id["youtube_music"].anonymous is True
    assert by_id["youtube_music"].auth_required is True
    assert by_id["deezer"].auth_required is False
