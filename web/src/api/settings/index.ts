/**
 * API client for runtime application settings.
 */

import { apiGet, apiPost, apiPut } from "../client";

export interface AppSettings {
  // Credentials (Sources & Targets)
  plex_host: string;
  plex_token_set: boolean;
  jellyfin_server_url: string;
  jellyfin_api_key_set: boolean;
  jellyfin_user_id: string;
  ytmusic_auth_set: boolean;

  // Infrastructure
  yt_dlp_timeout: number;
  celery_broker_url: string;
  celery_worker_concurrency: number;
  celery_log_level: string;
  log_format: string;
  source_playlist_cache_ttl_seconds: number;
  explore_cache_ttl_seconds: number;
  session_ttl_hours: number;

  // Network
  behind_proxy: boolean;
  trusted_proxies: string[];

  // Security & Server
  require_auth: boolean;
  app_url: string;
  plex_client_id: string;
  secret_key_set: boolean;
}

export type SettingsUpdate = Partial<AppSettings> & {
  plex_token?: string;
  jellyfin_api_key?: string;
  ytmusic_auth?: string;
  trusted_proxies?: string[];
};

export interface SetupRequest {
  secret_key: string;
  require_auth: boolean;
}

export interface SetupResponse {
  success: boolean;
  message: string;
}

export interface SourceInfo {
  id: string;
  name: string;
  auth_required: boolean;
  auth_set: boolean | null;
}

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

  setup: (input: SetupRequest) => apiPost<SetupResponse>("/v1/settings/setup", input),

  getConfiguredTargets: () => apiGet<string[]>("/v1/targets/configured"),

  testTarget: (targetId: string, config: Record<string, string>) =>
    apiPost<TargetTestResult>("/v1/targets/test", { target_id: targetId, config }),

  getPlexResources: () => apiGet<PlexResourcesResponse>("/auth/plex/resources"),

  setupPlexTarget: (serverUrl: string, clientIdentifier: string) =>
    apiPost("/auth/plex/setup", { server_url: serverUrl, client_identifier: clientIdentifier }),

  listSources: () => apiGet<SourceInfo[]>("/v1/sources/"),

  testSource: (sourceId: string, auth: string) =>
    apiPost<TargetTestResult>("/v1/sources/test", { source_id: sourceId, auth }),
};

// Legacy named exports for backward compatibility during migration
export const getSettings = settingsAPI.getSettings;
export const updateSettings = settingsAPI.updateSettings;
export const getConfiguredTargets = settingsAPI.getConfiguredTargets;
export const testTarget = settingsAPI.testTarget;
export const getPlexResources = settingsAPI.getPlexResources;
export const setupPlexTarget = settingsAPI.setupPlexTarget;
export const listSources = settingsAPI.listSources;
export const testSource = settingsAPI.testSource;
