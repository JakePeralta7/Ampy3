/**
 * API client for scheduled playlist sync endpoints
 */

import { apiDelete, apiGet, apiPost, apiPut } from "../client";

export interface ScheduledSync {
  id: number;
  source: string;
  target_ids: string[];
  source_url: string;
  target_playlist_name: string;
  schedule_interval: string;
  is_active: boolean;
  last_synced_at: string | null;
  next_sync_at: string;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface CreateScheduledSyncInput {
  source: string;
  target_ids: string[];
  source_url: string;
  target_playlist_name: string;
  schedule_interval: string;
}

export interface UpdateScheduledSyncInput {
  target_ids?: string[];
  target_playlist_name?: string;
  schedule_interval?: string;
  is_active?: boolean;
}

export interface BulkResponse {
  processed: number;
  task_ids?: string[];
}

export const scheduledSyncsAPI = {
  listScheduledSyncs: (activeOnly: boolean = false): Promise<ScheduledSync[]> =>
    apiGet<ScheduledSync[]>(`/v1/schedules/${activeOnly ? "?active_only=true" : ""}`),

  getScheduledSync: (syncId: number): Promise<ScheduledSync> =>
    apiGet<ScheduledSync>(`/v1/schedules/${syncId}`),

  createScheduledSync: (input: CreateScheduledSyncInput): Promise<ScheduledSync> =>
    apiPost<ScheduledSync>("/v1/schedules/", input),

  updateScheduledSync: (syncId: number, input: UpdateScheduledSyncInput): Promise<ScheduledSync> =>
    apiPut<ScheduledSync>(`/v1/schedules/${syncId}`, input),

  deleteScheduledSync: (syncId: number): Promise<{ id: number; success: boolean }> =>
    apiDelete<{ id: number; success: boolean }>(`/v1/schedules/${syncId}`),

  triggerSyncNow: (syncId: number): Promise<{ task_id: string; message: string }> =>
    apiPost<{ task_id: string; message: string }>(`/v1/schedules/${syncId}/sync-now`, {}),

  bulkSyncNow: (ids: number[]): Promise<BulkResponse> =>
    apiPost<BulkResponse>("/v1/schedules/bulk/sync-now", { ids }),

  bulkToggleActive: (ids: number[], isActive: boolean): Promise<BulkResponse> =>
    apiPost<BulkResponse>("/v1/schedules/bulk/toggle-active", { ids, is_active: isActive }),

  bulkDelete: (ids: number[]): Promise<BulkResponse> =>
    apiPost<BulkResponse>("/v1/schedules/bulk/delete", { ids }),
};
