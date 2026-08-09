/**
 * Platform identifiers — single source of truth for target and source IDs.
 * Must stay in sync with src/app/constants.py
 */

// Target platform IDs
export const TARGET_PLEX = "Plex";
export const TARGET_JELLYFIN = "Jellyfin";

// Source platform IDs
export const SOURCE_YOUTUBE_MUSIC = "youtube_music";
export const SOURCE_YOUTUBE_MUSIC_DISPLAY = "YouTube Music";
export const SOURCE_DEEZER = "deezer";
export const SOURCE_DEEZER_DISPLAY = "Deezer";

// Display label maps
export const TARGET_LABELS: Record<string, string> = {
  [TARGET_PLEX]: "Plex",
  [TARGET_JELLYFIN]: "Jellyfin",
};

export const SOURCE_LABELS: Record<string, string> = {
  [SOURCE_YOUTUBE_MUSIC]: SOURCE_YOUTUBE_MUSIC_DISPLAY,
  [SOURCE_DEEZER]: SOURCE_DEEZER_DISPLAY,
};

export function getSourceLabel(source: string): string {
  return SOURCE_LABELS[source] || source;
}
