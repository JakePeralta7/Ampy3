# First sync

This walkthrough takes you from a fresh Ampy3 install to a completed playlist sync on Plex (the flow for Jellyfin is identical — pick Jellyfin during step 1).

## 1. Connect your media server

Open `http://localhost:8000`. The first page is the **Setup wizard**.

- **Plex:** click *Connect Plex*. Ampy3 uses Plex's server discovery — pick your server from the list. A long-lived token is stored in the database (`src/app/api/targets.py`).
- **Jellyfin:** enter your base URL and an API key.

The Dashboard, Syncs, Explore, Audit Log, and Settings pages unlock once a target server is configured.

![Plex server setup](../assets/screenshots/plex-setup.png)

## 2. (Optional) Tune match rules

Open **Settings → Match rules** to adjust the search/compare thresholds and which target-library fields to weight (`title`, `artist_name`, `album_name`). The defaults work for most users; see [Metadata matching](../guides/metadata-matching.md) for the full rule-graph walkthrough.

![Settings — Match rules](../assets/screenshots/settings-matching.png)

## 3. Add a source playlist

Open **Syncs → + New sync**.

- Pick a **Source** (currently YouTube Music; Deezer is wired in via `core/sources/deezer.py`).
- Paste the playlist URL or ID.
- Pick a **Target library** on your Plex/Jellyfin server.
- Choose a **Schedule**: `manual` (no auto-run), `every_6h`, `every_12h`, `every_24h`, `daily`, or `weekly`. See [`INTERVAL_DELTAS` in `src/app/constants.py`](https://github.com/JakePeralta7/Ampy3/blob/main/src/app/constants.py) for the canonical list.

![Adding a sync schedule](../assets/screenshots/sync-create.png)

Save — the schedule is now active.

## 4. Run the first sync manually

You don't need to wait for the scheduler. Click **Run now** on the sync row. A Celery task is enqueued (`src/app/worker/tasks.py`).

Watch progress in the **Syncs** page. Each track gets a status: `matched`, `unmatched`, `error`, `skipped`.

![Syncs](../assets/screenshots/syncs.png)

## 5. Inspect the audit log

The **Audit log** page shows per-track outcomes across every run. Use it to identify tracks Ampy3 couldn't confidently match — usually titles where YouTube Music's casing differs from your library, remixes with no clean release in the library, or tracks that simply aren't in your Plex/Jellyfin library yet.

![Audit log](../assets/screenshots/audit.png)

## 6. Iterate on match rules

If the audit log shows too many `unmatched` rows:

1. Open **Settings → Match rules** and lower the confidence threshold, or enable broader fuzzy matching.
2. Re-run the affected sync.
3. The audit log is additive — old runs stay so you can compare.

## What's next

- [Sync pipeline](../guides/sync-pipeline.md) — what actually happens between *Run now* and `matched`.
- [Explore](../guides/explore.md) — discover charts, moods, and playlists across your sources.
- [Auth](../guides/auth.md) — enable Plex SSO before exposing Ampy3 beyond localhost.