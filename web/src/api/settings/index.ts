/**
 * API client for runtime application settings.
 */

import { apiGet, apiPost, apiPut } from "../client";

export interface AppSettings {
  plex_host: string;
  plex_token_set: boolean;
  jellyfin_server_url: string;
  jellyfin_api_key_set: boolean;
  jellyfin_user_id: string;
  ollama_host: string;
  ollama_model: string;
  ollama_timeout: number;
  yt_dlp_cookies: string;
  yt_dlp_timeout: number;
}

export type SettingsUpdate = Partial<AppSettings> & {
  plex_token?: string;
  jellyfin_api_key?: string;
};

export async function getSettings(): Promise<AppSettings> {
  return apiGet<AppSettings>("/v1/settings/");
}

export async function updateSettings(input: SettingsUpdate): Promise<AppSettings> {
  return apiPut<AppSettings>("/v1/settings/", input);
}

export async function getConfiguredTargets(): Promise<string[]> {
  return apiGet<string[]>("/v1/targets/configured");
}

export interface TargetTestResult {
  ok: boolean;
  error?: string;
}

export async function testTarget(
  targetId: string,
  config: Record<string, string>,
): Promise<TargetTestResult> {
  return apiPost<TargetTestResult>("/v1/targets/test", {
    target_id: targetId,
    config,
  });
}

// ── Plex SSO server discovery ─────────────────────────────────────

export interface PlexResourceConnection {
  uri: string;
  local: boolean;
  relay: boolean;
  status: number;
}

export interface PlexResource {
  name: string;
  client_identifier: string;
  connections: PlexResourceConnection[];
  access_token: string;
  owned: boolean;
  product: string;
  product_version: string;
}

export interface PlexResourcesResponse {
  servers: PlexResource[];
}

export async function getPlexResources(): Promise<PlexResourcesResponse> {
  return apiGet<PlexResourcesResponse>("/auth/plex/resources");
}

export async function setupPlexTarget(serverUrl: string, token: string): Promise<void> {
  return apiPost("/auth/plex/setup", { server_url: serverUrl, token });
}
