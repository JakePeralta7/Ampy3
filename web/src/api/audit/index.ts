/**
 * API client for audit log endpoints
 */

import { apiGet } from "../client";

export interface AuditLogEntry {
  id: number;
  event_type: string;
  resource_type: string | null;
  resource_id: string | null;
  summary: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogResponse {
  logs: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export const auditLogsAPI = {
  list: (
    params: { limit?: number; offset?: number; event_type?: string } = {},
  ): Promise<AuditLogResponse> => {
    const query = new URLSearchParams();
    if (params.limit) query.set("limit", String(params.limit));
    if (params.offset) query.set("offset", String(params.offset));
    if (params.event_type) query.set("event_type", params.event_type);
    const qs = query.toString();
    return apiGet<AuditLogResponse>(`/v1/audit/logs${qs ? `?${qs}` : ""}`);
  },
};
