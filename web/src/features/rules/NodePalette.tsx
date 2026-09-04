import { useCallback } from "react";
import { NODE_TYPE_DEFS } from "./nodeTypes";

interface NodePaletteProps {
  onAddNode: (type: string) => void;
}

const ESSENTIAL_NODES = new Set(["transform", "search", "compare"]);

export function NodePalette({ onAddNode }: NodePaletteProps) {
  const handleDragStart = useCallback((e: React.DragEvent, type: string) => {
    e.dataTransfer.setData("application/reactflow", type);
    e.dataTransfer.effectAllowed = "move";
  }, []);

  return (
    <div className="w-56 bg-bg-muted border-r border-border overflow-y-auto flex-shrink-0">
      <div className="p-3 text-xs font-semibold text-fg-muted uppercase tracking-wider">Nodes</div>

      {/* Essential Nodes Only */}
      <div className="mb-3">
        <div className="space-y-0.5 px-2">
          {Object.values(NODE_TYPE_DEFS)
            .filter((n) => ESSENTIAL_NODES.has(n.type))
            .map((node) => (
              <button
                key={node.type}
                draggable
                onDragStart={(e) => handleDragStart(e, node.type)}
                onClick={() => onAddNode(node.type)}
                className="w-full text-left px-2 py-1.5 rounded-sm text-xs flex items-center gap-2 hover:bg-accent-50 dark:hover:bg-accent-100 transition-colors duration-fast cursor-grab active:cursor-grabbing"
              >
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: node.color }}
                />
                <span className="text-fg-muted truncate font-medium">{node.label}</span>
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}
