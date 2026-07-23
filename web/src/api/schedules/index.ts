/**
 * API client for scheduled playlist sync endpoints
 */

import { apiPost, apiPut, apiRequest } from "../client";

export interface ScheduledSync {
  id: number;
  source: string;
  source_url: string;
  target_playlist_name: string;
  target_playlist_id: string | null;
  schedule_interval: string;
  is_active: boolean;
  replace_existing: boolean;
  last_synced_at: string | null;
  next_sync_at: string;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface CreateScheduledSyncInput {
  source: string;
  source_url: string;
  target_playlist_name: string;
  schedule_interval: string;
  replace_existing?: boolean;
}

export interface UpdateScheduledSyncInput {
  target_playlist_name?: string;
  schedule_interval?: string;
  is_active?: boolean;
  replace_existing?: boolean;
}

export interface BulkResponse {
  processed: number;
  task_ids?: string[];
}

class ScheduledSyncsAPI {
  async listScheduledSyncs(activeOnly: boolean = false): Promise<ScheduledSync[]> {
    const params = new URLSearchParams();
    if (activeOnly) {
      params.append("active_only", "true");
    }

    const query = params.toString();
    const endpoint = query ? `/v1/schedules/?${query}` : `/v1/schedules/`;

    return apiRequest<ScheduledSync[]>(endpoint, {
      method: "GET",
    });
  }

  async getScheduledSync(syncId: number): Promise<ScheduledSync> {
    return apiRequest<ScheduledSync>(`/v1/schedules/${syncId}`, {
      method: "GET",
    });
  }

  async createScheduledSync(input: CreateScheduledSyncInput): Promise<ScheduledSync> {
    return apiPost<ScheduledSync>("/v1/schedules/", input);
  }

  async updateScheduledSync(
    syncId: number,
    input: UpdateScheduledSyncInput,
  ): Promise<ScheduledSync> {
    return apiPut<ScheduledSync>(`/v1/schedules/${syncId}`, input);
  }

  async deleteScheduledSync(syncId: number): Promise<{ message: string }> {
    return apiRequest<{ message: string }>(`/v1/schedules/${syncId}`, {
      method: "DELETE",
    });
  }

  async triggerSyncNow(syncId: number): Promise<{ task_id: string; message: string }> {
    return apiRequest<{ task_id: string; message: string }>(
      `/v1/schedules/${syncId}/sync-now`,
      {
        method: "POST",
      },
    );
  }

  async bulkSyncNow(ids: number[]): Promise<BulkResponse> {
    return apiPost<BulkResponse>("/v1/schedules/bulk/sync-now", { ids });
  }

  async bulkToggleActive(ids: number[], isActive: boolean): Promise<BulkResponse> {
    return apiPost<BulkResponse>("/v1/schedules/bulk/toggle-active", { ids, is_active: isActive });
  }

  async bulkDelete(ids: number[]): Promise<BulkResponse> {
    return apiPost<BulkResponse>("/v1/schedules/bulk/delete", { ids });
  }
}

export const scheduledSyncsAPI = new ScheduledSyncsAPI();
