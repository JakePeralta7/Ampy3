/** Node type registry - defines all available nodes and their config forms. */

export type PortType = "any" | "string" | "number" | "boolean" | "dict" | "list" | "track";

export interface PortDef {
  id: string;
  label: string;
  type: PortType;
}

export interface NodeTypeDef {
  type: string;
  label: string;
  color: string;
  icon: string;
  category: "input-output" | "string" | "logic" | "plex" | "external" | "compare";
  inputs: PortDef[];
  outputs: PortDef[];
  defaultConfig: Record<string, unknown>;
  configFields?: ConfigFieldDef[];
}

export interface ConfigFieldDef {
  key: string;
  label: string;
  type: "text" | "number" | "boolean" | "select" | "slider" | "checkbox_list";
  default: unknown;
  options?: { label: string; value: string | number }[];
  min?: number;
  max?: number;
  step?: number;
  visibleWhen?: { key: string; value: string };
}

export const TRACK_FIELD_OPTIONS = [
  { label: "Raw value", value: "value" },
  { label: "Title", value: "title" },
  { label: "Artist", value: "artist_name" },
  { label: "Album", value: "album_name" },
];

export const STRING_OP_OPTIONS = [
  { label: "Lowercase", value: "lowercase" },
  { label: "Uppercase", value: "uppercase" },
  { label: "Trim", value: "trim" },
  { label: "Replace", value: "replace" },
  { label: "Regex replace", value: "regex_replace" },
  { label: "Regex match", value: "regex_match" },
  { label: "Regex extract", value: "regex_extract" },
  { label: "Contains", value: "contains" },
  { label: "Split", value: "split" },
  { label: "Join", value: "join" },
  { label: "Substring", value: "substring" },
];

export const NODE_TYPE_DEFS: Record<string, NodeTypeDef> = {
  // ────────────────────────────────────────────────────────
  // ESSENTIAL NODES ONLY (v2)
  // ────────────────────────────────────────────────────────

  // ── Transform (prepare/normalize data) ──
  transform: {
    type: "transform",
    label: "Transform",
    color: "#06b6d4",
    icon: "✏️",
    category: "string",
    inputs: [{ id: "in", label: "Input", type: "any" }],
    outputs: [{ id: "out", label: "Output", type: "any" }],
    defaultConfig: { field: "value", target_field: "value", operation: "lowercase" },
    configFields: [
      {
        key: "field",
        label: "Source field",
        type: "select",
        default: "value",
        options: TRACK_FIELD_OPTIONS,
      },
      {
        key: "target_field",
        label: "Target field",
        type: "select",
        default: "value",
        options: TRACK_FIELD_OPTIONS,
      },
      {
        key: "operation",
        label: "Operation",
        type: "select",
        default: "lowercase",
        options: STRING_OP_OPTIONS,
      },
      // Replace-specific
      {
        key: "find",
        label: "Find",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "replace" },
      },
      {
        key: "replacement",
        label: "Replacement",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "replace" },
      },
      {
        key: "case_sensitive",
        label: "Case sensitive",
        type: "boolean",
        default: false,
        visibleWhen: { key: "operation", value: "replace" },
      },
      // Regex-specific
      {
        key: "pattern",
        label: "Pattern",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "regex_replace" },
      },
      {
        key: "replacement",
        label: "Replacement",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "regex_replace" },
      },
      {
        key: "pattern",
        label: "Pattern",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "regex_match" },
      },
      {
        key: "case_sensitive",
        label: "Case sensitive",
        type: "boolean",
        default: false,
        visibleWhen: { key: "operation", value: "regex_match" },
      },
      {
        key: "pattern",
        label: "Pattern",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "regex_extract" },
      },
      {
        key: "group",
        label: "Group",
        type: "number",
        default: 0,
        visibleWhen: { key: "operation", value: "regex_extract" },
      },
      // Contains-specific
      {
        key: "substring",
        label: "Substring",
        type: "text",
        default: "",
        visibleWhen: { key: "operation", value: "contains" },
      },
      {
        key: "case_sensitive",
        label: "Case sensitive",
        type: "boolean",
        default: false,
        visibleWhen: { key: "operation", value: "contains" },
      },
      // Split/Join-specific
      {
        key: "delimiter",
        label: "Delimiter",
        type: "text",
        default: ",",
        visibleWhen: { key: "operation", value: "split" },
      },
      {
        key: "delimiter",
        label: "Delimiter",
        type: "text",
        default: ", ",
        visibleWhen: { key: "operation", value: "join" },
      },
      // Substring-specific
      {
        key: "start",
        label: "Start",
        type: "number",
        default: 0,
        visibleWhen: { key: "operation", value: "substring" },
      },
      {
        key: "end",
        label: "End",
        type: "number",
        default: 0,
        visibleWhen: { key: "operation", value: "substring" },
      },
    ],
  },

  // ── Search (query Plex library) ──
  search: {
    type: "search",
    label: "Search",
    color: "#e11d48",
    icon: "🔍",
    category: "plex",
    inputs: [{ id: "in", label: "Track", type: "track" }],
    outputs: [{ id: "out", label: "Results", type: "list" }],
    defaultConfig: {
      fields_to_search: ["search_title", "search_artist", "search_album"],
      max_results: 50,
    },
    configFields: [
      {
        key: "fields_to_search",
        label: "Fields to search",
        type: "checkbox_list",
        default: ["search_title", "search_artist", "search_album"],
        options: [
          { label: "Title", value: "search_title" },
          { label: "Artist", value: "search_artist" },
          { label: "Album", value: "search_album" },
        ],
      },
      { key: "max_results", label: "Max results", type: "number", default: 50, min: 1, max: 100 },
    ],
  },

  // ── Compare (find best match & threshold) ──
  compare: {
    type: "compare",
    label: "Compare",
    color: "#10b981",
    icon: "📊",
    category: "compare",
    inputs: [
      { id: "candidates", label: "Candidates", type: "list" },
      { id: "reference", label: "Reference Track", type: "track" },
    ],
    outputs: [{ id: "out", label: "Best Match", type: "dict" }],
    defaultConfig: {
      fields_to_match: ["title", "artist_name", "album_name"],
      threshold: 0.75,
    },
    configFields: [
      {
        key: "fields_to_match",
        label: "Fields to compare",
        type: "checkbox_list",
        default: ["title", "artist_name", "album_name"],
        options: [
          { label: "Title", value: "title" },
          { label: "Artist", value: "artist_name" },
          { label: "Album", value: "album_name" },
        ],
      },
      {
        key: "threshold",
        label: "Confidence threshold",
        type: "slider",
        default: 0.75,
        min: 0,
        max: 1,
        step: 0.05,
      },
    ],
  },
};

export function getNodeDef(type: string): NodeTypeDef | undefined {
  return NODE_TYPE_DEFS[type];
}

export function getVisibleConfigFields(
  def: NodeTypeDef,
  config: Record<string, unknown>,
): ConfigFieldDef[] {
  if (!def.configFields) return [];
  return def.configFields.filter((f) => {
    if (!f.visibleWhen) return true;
    return config[f.visibleWhen.key] === f.visibleWhen.value;
  });
}
