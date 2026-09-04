import { Handle, type NodeProps, Position } from "@xyflow/react";
import { memo } from "react";
import { getNodeDef, type PortType } from "./nodeTypes";

const PORT_COLORS: Record<PortType, string> = {
  any: "#94a3b8",
  string: "#22c55e",
  number: "#3b82f6",
  boolean: "#f97316",
  dict: "#a855f7",
  list: "#ec4899",
  track: "#6366f1",
};

const CATEGORY_COLORS: Record<string, string> = {
  "input-output": "#6366f1",
  string: "#06b6d4",
  logic: "#f97316",
  plex: "#e11d48",
  compare: "#10b981",
};

interface NodeData {
  label: string;
  nodeType: string;
  config: Record<string, unknown>;
  onConfigChange?: (config: Record<string, unknown>) => void;
  isSelected?: boolean;
}

function BaseNode({ data, selected }: { data: NodeData; selected: boolean }) {
  const def = getNodeDef(data.nodeType);
  const accentColor = def ? CATEGORY_COLORS[def.category] || "#64748b" : "#64748b";
  const showConfig = data.config && Object.keys(data.config).length > 0;

  return (
    <div
      className={`rounded-lg border-2 bg-bg-surface shadow-sm min-w-[160px] ${
        selected ? "ring-2 ring-accent-500 border-accent-500" : "border-border"
      }`}
      style={{ borderTopColor: accentColor, borderTopWidth: 3 }}
    >
      {/* Header */}
      <div
        className="px-3 py-1.5 text-xs font-semibold text-white rounded-t-md flex items-center gap-1.5"
        style={{ backgroundColor: accentColor }}
      >
        <span>{def?.icon || "◆"}</span>
        <span>{data.label || def?.label || data.nodeType}</span>
      </div>

      {/* Config summary */}
      {showConfig && (
        <div className="px-3 py-1.5 text-xs text-fg-muted space-y-0.5">
          {Object.entries(data.config).map(([key, value]) => {
            if (key === "breakpoint") return null;

            if (Array.isArray(value)) {
              if (value.length === 0) return null;
              const items = value
                .map((v) => {
                  if (typeof v === "string") {
                    return v
                      .replace(/^search_/, "")
                      .replace(/_/g, " ")
                      .split(" ")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" ");
                  }
                  return String(v);
                })
                .join(", ");
              return (
                <div key={key} className="text-fg font-medium">
                  ✓ {items}
                </div>
              );
            }

            if (typeof value === "boolean") {
              if (!value) return null;
              return <div key={key}>{key.replace(/_/g, " ")}: ✓</div>;
            }

            if (typeof value === "number") {
              return (
                <div key={key}>
                  {key.replace(/_/g, " ")}: {value}
                </div>
              );
            }

            if (typeof value === "string" && value) {
              const display = value.length > 20 ? `${value.slice(0, 20)}...` : value;
              return (
                <div key={key}>
                  {key.replace(/_/g, " ")}: "{display}"
                </div>
              );
            }

            if (typeof value === "object" && value !== null) {
              return null;
            }

            return null;
          })}
        </div>
      )}
    </div>
  );
}

const nodeStyle = "px-3 py-2 text-xs";

// Input handles
function InputHandle({ id, label, type }: { id: string; label: string; type: PortType }) {
  return (
    <Handle
      type="target"
      position={Position.Left}
      id={id}
      title={`${label} (${type})`}
      className="!w-2.5 !h-2.5 !border-2 !border-white"
      style={{ backgroundColor: PORT_COLORS[type] || PORT_COLORS.any }}
    />
  );
}

// Output handles
function OutputHandle({ id, label, type }: { id: string; label: string; type: PortType }) {
  return (
    <Handle
      type="source"
      position={Position.Right}
      id={id}
      title={`${label} (${type})`}
      className="!w-2.5 !h-2.5 !border-2 !border-white"
      style={{ backgroundColor: PORT_COLORS[type] || PORT_COLORS.any }}
    />
  );
}

// ─── Track Source ────────────────────────
export const TrackSourceNode = memo(({ data, selected }: NodeProps) => {
  const _d = data as unknown as NodeData;
  return (
    <div
      className={`rounded-lg border-2 bg-bg-surface shadow-sm min-w-[140px] ${selected ? "ring-2 ring-accent-500 border-accent-500" : "border-border"}`}
    >
      <div className="px-3 py-2 text-xs font-semibold text-white rounded-t-md bg-indigo-500 flex items-center gap-1.5">
        <span>♫</span>
        <span>Track Source</span>
      </div>
      <OutputHandle id="out" label="Track" type="track" />
    </div>
  );
});

// ─── Constant ────────────────────────────
export const ConstantNode = memo(({ data, selected }: NodeProps) => {
  const d = data as unknown as NodeData;
  const value = (d.config?.value as string) || "";
  return (
    <div
      className={`rounded-lg border-2 bg-bg-surface shadow-sm min-w-[140px] ${selected ? "ring-2 ring-accent-500 border-accent-500" : "border-border"}`}
    >
      <div className="px-3 py-1.5 text-xs font-semibold text-white rounded-t-md bg-purple-500">
        Constant
      </div>
      <div className="px-3 py-1.5 text-xs text-fg-muted font-mono">
        &quot;{value || "..."}&quot;
      </div>
      <OutputHandle id="out" label="Value" type="any" />
    </div>
  );
});

// ─── Match Output ─────────────────────────
export const MatchOutputNode = memo(({ data: _data, selected }: NodeProps) => {
  return (
    <div
      className={`rounded-lg border-2 bg-bg-surface shadow-sm min-w-[140px] ${selected ? "ring-2 ring-accent-500 border-success-500" : "border-border"}`}
    >
      <div className="px-3 py-2 text-xs font-semibold text-white rounded-t-md bg-success-500 flex items-center gap-1.5">
        <span>✓</span>
        <span>Match Output</span>
      </div>
      <InputHandle id="in" label="Match Data" type="any" />
    </div>
  );
});

// ─── Generic Node ────────────────────────
function GenericNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as NodeData;
  const def = getNodeDef(d.nodeType);
  if (!def) return <div className={nodeStyle}>Unknown: {d.nodeType}</div>;

  return (
    <div>
      <BaseNode data={d} selected={selected} />
      <div className="flex flex-col gap-1 mt-1">
        {def.inputs.map((port) => (
          <div key={port.id} className={nodeStyle}>
            <InputHandle id={port.id} label={port.label} type={port.type} />
          </div>
        ))}
        {def.outputs.map((port) => (
          <div key={port.id} className={nodeStyle}>
            <OutputHandle id={port.id} label={port.label} type={port.type} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Node Types Map ──────────────────────
export const NODE_COMPONENTS = {
  track_source: TrackSourceNode,
  constant: ConstantNode,
  match_output: MatchOutputNode,
  transform: GenericNodeComponent,
  string_op: GenericNodeComponent,
  logic_op: GenericNodeComponent,
  compare: GenericNodeComponent,
  search: GenericNodeComponent,
  similarity: GenericNodeComponent,
  threshold: GenericNodeComponent,
  plex_search: GenericNodeComponent,
  filter: GenericNodeComponent,
  pick_best: GenericNodeComponent,
  sort_by_score: GenericNodeComponent,
  search_musicbrainz: GenericNodeComponent,
} as const;
