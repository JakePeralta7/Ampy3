import { apiDelete, apiGet, apiPost, apiPut } from "../client";

export interface MatchRuleNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  label?: string;
  config: Record<string, unknown>;
}

export interface MatchRuleEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface MatchRuleCanvas {
  nodes: MatchRuleNode[];
  edges: MatchRuleEdge[];
}

export interface MatchRule {
  id: number;
  name: string;
  priority: number;
  is_active: boolean;
  is_default: boolean;
  canvas: MatchRuleCanvas;
  created_at: string;
  updated_at: string;
}

export interface TestStep {
  node_id: string;
  node_type: string;
  config: Record<string, unknown>;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
}

export interface TestRuleTrace {
  rule_id: number;
  rule_name: string;
  rule_priority: number;
  steps: TestStep[];
  error?: string;
}

export interface TestMatchResult {
  rule_id: number;
  rule_name: string;
  rule_priority: number;
  matched: boolean;
  result: Record<string, unknown> | null;
  error?: string;
}

export interface TestResponse {
  traces: TestRuleTrace[];
  matches: TestMatchResult[];
  match_results: Record<string, unknown>[];
}

export interface TrackTestInput {
  title?: string;
  artist_name?: string;
  album_name?: string;
  duration_ms?: number;
  source_id?: string;
}

export const matchRulesAPI = {
  list: () => apiGet<MatchRule[]>("/v1/match-rules"),

  get: (id: number) => apiGet<MatchRule>(`/v1/match-rules/${id}`),

  create: (data: { name: string }) => apiPost<MatchRule>("/v1/match-rules", data),

  update: (
    id: number,
    data: {
      name?: string;
      is_active?: boolean;
      canvas?: MatchRuleCanvas;
    },
  ) => apiPut<MatchRule>(`/v1/match-rules/${id}`, data),

  delete: (id: number) => apiDelete(`/v1/match-rules/${id}`),

  reorder: (order: { id: number; priority: number }[]) =>
    apiPut<MatchRule[]>("/v1/match-rules/reorder", order),

  test: (track: TrackTestInput, ruleIds?: number[]) =>
    apiPost<TestResponse>("/v1/match-rules/test", { track, rule_ids: ruleIds }),
};
