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
  yt_dlp_cookies: string;
  yt_dlp_timeout: number;
}

export type SettingsUpdate = Partial<AppSettings> & {
  plex_token?: string;
  jellyfin_api_key?: string;
};

export interface TargetTestResult {
  ok: boolean;
  error?: string;
}

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

export const settingsAPI = {
  getSettings: () => apiGet<AppSettings>("/v1/settings/"),

  updateSettings: (input: SettingsUpdate) => apiPut<AppSettings>("/v1/settings/", input),

  getConfiguredTargets: () => apiGet<string[]>("/v1/targets/configured"),

  testTarget: (targetId: string, config: Record<string, string>) =>
    apiPost<TargetTestResult>("/v1/targets/test", { target_id: targetId, config }),

  getPlexResources: () => apiGet<PlexResourcesResponse>("/auth/plex/resources"),

  setupPlexTarget: (serverUrl: string, token: string) =>
    apiPost("/auth/plex/setup", { server_url: serverUrl, token }),
};

// Legacy named exports for backward compatibility during migration
export const getSettings = settingsAPI.getSettings;
export const updateSettings = settingsAPI.updateSettings;
export const getConfiguredTargets = settingsAPI.getConfiguredTargets;
export const testTarget = settingsAPI.testTarget;
export const getPlexResources = settingsAPI.getPlexResources;
export const setupPlexTarget = settingsAPI.setupPlexTarget;
