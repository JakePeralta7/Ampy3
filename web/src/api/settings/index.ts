/**
 * API client for runtime application settings.
 */

import { apiGet, apiPut } from "../client";

export interface AppSettings {
  plex_host: string;
  plex_token: string;
  ollama_host: string;
  ollama_model: string;
  ollama_timeout: number;
  yt_dlp_cookies: string;
  yt_dlp_timeout: number;
}

export type SettingsUpdate = Partial<AppSettings>;

export async function getSettings(): Promise<AppSettings> {
  return apiGet<AppSettings>("/v1/settings/");
}

export async function updateSettings(input: SettingsUpdate): Promise<AppSettings> {
  return apiPut<AppSettings>("/v1/settings/", input);
}
