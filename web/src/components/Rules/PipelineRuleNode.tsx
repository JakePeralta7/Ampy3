import { Handle, type NodeProps, Position } from "@xyflow/react";
import { memo, useCallback } from "react";

interface PipelineRuleData {
  name: string;
  priority: number;
  isActive: boolean;
  nodeCount: number;
  hasOutput: boolean;
}

export const PipelineRuleNode = memo(({ data }: NodeProps) => {
  const d = data as unknown as PipelineRuleData;

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      e.dataTransfer.setData("application/rule-id", String(d.priority));
      e.dataTransfer.effectAllowed = "move";
    },
    [d.priority],
  );

  return (
    <div draggable onDragStart={handleDragStart} className="group cursor-pointer">
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Top}
        id="in"
        className="!w-3 !h-3 !border-2 !border-white !bg-accent-500"
      />

      <div
        className={`w-72 rounded-lg border-2 bg-bg-surface shadow-sm transition-all hover:shadow-md active:shadow-sm ${
          d.isActive ? "border-accent-500" : "border-border opacity-60"
        }`}
      >
        {/* Header */}
        <div
          className={`px-3 py-2 flex items-center justify-between rounded-t-md ${
            d.isActive ? "bg-accent-500 text-accent-fg" : "bg-fg-subtle text-accent-fg"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold opacity-70">#{d.priority + 1}</span>
            <span className="text-sm font-semibold truncate">{d.name}</span>
          </div>
          <div className="flex items-center gap-1">
            {d.isActive ? (
              <span className="w-2 h-2 rounded-full bg-success-500" title="Active" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-fg-on-accent/50" title="Inactive" />
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="px-3 py-2 flex items-center gap-3 text-xs text-fg-muted">
          <span>
            {d.nodeCount} node{d.nodeCount !== 1 ? "s" : ""}
          </span>
          {d.hasOutput && <span className="text-success-500">✓ Has output</span>}
        </div>
      </div>

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="out"
        className="!w-3 !h-3 !border-2 !border-white !bg-accent-500"
      />
    </div>
  );
});
