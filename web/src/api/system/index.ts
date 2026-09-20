/**
 * API client for system metadata (version, etc.).
 */

import { apiGet } from "../client";

export interface SystemInfo {
  version: string;
  repository_url: string;
}

export const systemInfoAPI = {
  getVersion: (): Promise<SystemInfo> => apiGet<SystemInfo>("/v1/system/version"),
};
