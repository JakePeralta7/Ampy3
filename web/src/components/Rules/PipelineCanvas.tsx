import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  MarkerType,
  type Node,
  ReactFlow,
  type ReactFlowInstance,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useCallback, useEffect, useRef, useState } from "react";
import "@xyflow/react/dist/style.css";

import type { MatchRule } from "../../api/rules";
import { PipelineRuleNode } from "./PipelineRuleNode";

interface PipelineCanvasProps {
  rules: MatchRule[];
  onRuleClick: (ruleId: number) => void;
  onRulesReorder: (order: { id: number; priority: number }[]) => void;
  onAddRule: () => void;
  loading: boolean;
}

function pipelineNodesFromRules(rules: MatchRule[]): Node[] {
  return rules.map((rule, i) => ({
    id: String(rule.id),
    type: "pipelineRule",
    position: { x: 0, y: i * 160 },
    data: {
      name: rule.name,
      priority: rule.priority,
      isActive: rule.is_active,
      nodeCount: rule.canvas?.nodes?.length || 0,
      hasOutput: (rule.canvas?.nodes || []).some((n) => n.type === "match_output"),
    },
  }));
}

function pipelineEdgesFromRules(rules: MatchRule[]): Edge[] {
  const edges: Edge[] = [];
  for (let i = 0; i < rules.length - 1; i++) {
    edges.push({
      id: `e_${rules[i].id}_${rules[i + 1].id}`,
      source: String(rules[i].id),
      target: String(rules[i + 1].id),
      animated: true,
      style: { stroke: "#94a3b8", strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
    });
  }
  return edges;
}

const NODE_TYPES = { pipelineRule: PipelineRuleNode };

function PipelineCanvasInner({
  rules,
  onRuleClick,
  onRulesReorder,
  onAddRule: _onAddRule,
  loading,
}: PipelineCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState(pipelineNodesFromRules(rules));
  const [edges, setEdges, onEdgesChange] = useEdgesState(pipelineEdgesFromRules(rules));

  useEffect(() => {
    setNodes(pipelineNodesFromRules(rules));
    setEdges(pipelineEdgesFromRules(rules));
  }, [rules, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onRuleClick(parseInt(node.id, 10));
    },
    [onRuleClick],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setDragOver(false);
      const ruleIdStr = event.dataTransfer.getData("application/rule-id");
      if (!ruleIdStr) return;

      const draggedId = parseInt(ruleIdStr, 10);
      const position = rfInstance?.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      if (!position) return;

      const targetY = position.y;
      const currentRules = [...rules];
      const draggedIndex = currentRules.findIndex((r) => r.id === draggedId);

      if (draggedIndex === -1) return;
      const [removed] = currentRules.splice(draggedIndex, 1);

      let insertIndex = currentRules.length;
      for (let i = 0; i < currentRules.length; i++) {
        const nodeY = i * 160;
        if (targetY < nodeY + 80) {
          insertIndex = i;
          break;
        }
      }
      currentRules.splice(insertIndex, 0, removed);

      const reorder = currentRules.map((r, i) => ({ id: r.id, priority: i }));
      onRulesReorder(reorder);
    },
    [rfInstance, rules, onRulesReorder],
  );

  return (
    <div className="flex flex-col h-full">
      <div
        ref={reactFlowWrapper}
        className={`flex-1 transition-colors duration-fast ${dragOver ? "bg-accent-50/50" : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        {loading ? (
          <div className="flex items-center justify-center h-full text-sm text-fg-subtle">
            Loading rules...
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={setRfInstance}
            onNodeClick={onNodeClick}
            nodeTypes={NODE_TYPES}
            fitView
            panOnDrag={false}
            zoomOnScroll={false}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
          >
            <Controls showInteractive={false} />
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="var(--border-default)"
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

export function PipelineCanvas(props: PipelineCanvasProps) {
  return (
    <ReactFlowProvider>
      <PipelineCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
