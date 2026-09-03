import {
  addEdge,
  Background,
  BackgroundVariant,
  type Connection,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  type NodeTypes,
  ReactFlow,
  type ReactFlowInstance,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import { AlignLeft, Copy, LayoutGrid } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "@xyflow/react/dist/style.css";

import type { MatchRuleCanvas, MatchRuleEdge, MatchRuleNode } from "../../api/rules";
import { Button } from "../ui/Button";
import { NODE_COMPONENTS } from "./NodeComponents";
import { NodeInspector } from "./NodeInspector";
import { NodePalette } from "./NodePalette";
import { getNodeDef } from "./nodeTypes";
import { TestPanel } from "./TestPanel";

export type { MatchRuleCanvas, MatchRuleEdge, MatchRuleNode };

// Layout constants — must match backend layout.py
const H_SPACING = 220;
const V_SPACING = 120;
const MARGIN_X = 80;
const MARGIN_Y = 80;

interface ProgramCanvasProps {
  ruleId: number | null;
  ruleName: string;
  isDefault: boolean;
  canvas: MatchRuleCanvas;
  onCanvasChange: (canvas: MatchRuleCanvas) => void;
  onNameChange: (name: string) => void;
  onBack: () => void;
  onSave: (canvas: MatchRuleCanvas) => void;
  onClone: () => void;
  saving?: boolean;
}

/**
 * Compute auto-layout positions for nodes using a hierarchical left-to-right
 * algorithm that mirrors the Python backend's layout.py.
 */
function computeAutoLayout(nodes: Node[], edges: Edge[]): Map<string, { x: number; y: number }> {
  const nodeIds = nodes.map((n) => n.id);
  const children: Map<string, string[]> = new Map(nodeIds.map((id) => [id, []]));
  const inDegree: Map<string, number> = new Map(nodeIds.map((id) => [id, 0]));

  for (const edge of edges) {
    children.get(edge.source)?.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  // BFS layer assignment
  const layer: Map<string, number> = new Map();
  const queue: string[] = [];

  for (const id of nodeIds) {
    if ((inDegree.get(id) ?? 0) === 0) {
      layer.set(id, 0);
      queue.push(id);
    }
  }
  if (queue.length === 0) {
    for (const id of nodeIds) {
      layer.set(id, 0);
      queue.push(id);
    }
  }

  let qi = 0;
  while (qi < queue.length) {
    const cur = queue[qi++];
    const curLayer = layer.get(cur) ?? 0;
    for (const child of children.get(cur) ?? []) {
      const newLayer = curLayer + 1;
      if (!layer.has(child) || (layer.get(child) ?? 0) < newLayer) {
        layer.set(child, newLayer);
        queue.push(child);
      }
    }
  }
  for (const id of nodeIds) {
    if (!layer.has(id)) layer.set(id, 0);
  }

  // Group by layer (in original node order)
  const layers: Map<number, string[]> = new Map();
  for (const id of nodeIds) {
    const l = layer.get(id) ?? 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)?.push(id);
  }

  // Assign pixel positions
  const positions: Map<string, { x: number; y: number }> = new Map();
  for (const [layerIdx, layerNodes] of layers) {
    for (let ni = 0; ni < layerNodes.length; ni++) {
      positions.set(layerNodes[ni], {
        x: MARGIN_X + layerIdx * H_SPACING,
        y: MARGIN_Y + ni * V_SPACING,
      });
    }
  }
  return positions;
}

function generateNodeId(existingIds: Set<string> = new Set()): string {
  let counter = 0;
  let id: string;
  do {
    counter++;
    id = `n_${counter}`;
  } while (existingIds.has(id));
  return id;
}

function reactFlowNodeFromRule(n: MatchRuleNode): Node {
  return {
    id: n.id,
    type: n.type,
    position: n.position,
    data: {
      label: n.label || (n.config?.label as string) || getNodeDef(n.type)?.label || n.type,
      nodeType: n.type,
      config: n.config || {},
    },
  };
}

function ruleNodeFromReactFlow(n: Node): MatchRuleNode {
  return {
    id: n.id,
    type: n.type || "",
    position: { x: n.position.x, y: n.position.y },
    label: (n.data?.label as string) || undefined,
    config: (n.data?.config as Record<string, unknown>) || {},
  };
}

function reactFlowEdgeFromRule(e: MatchRuleEdge): Edge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
    animated: true,
    style: { strokeWidth: 1.5, stroke: "#60a5fa" },
  };
}

function ruleEdgeFromReactFlow(e: Edge): MatchRuleEdge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    targetHandle: e.targetHandle ?? undefined,
  };
}

export function ProgramCanvasInner({
  ruleId,
  canvas,
  onCanvasChange,
  onNameChange,
  onBack,
  onSave,
  onClone,
  saving,
  ruleName,
  isDefault,
}: ProgramCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const { fitView } = useReactFlow();

  const initialNodes = useMemo(() => canvas.nodes.map(reactFlowNodeFromRule), [canvas.nodes]);
  const initialEdges = useMemo(() => canvas.edges.map(reactFlowEdgeFromRule), [canvas.edges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [nodeName, setNodeName] = useState("");
  const [hasBreakpoint, setHasBreakpoint] = useState(false);

  const nodeTypes = useMemo(() => NODE_COMPONENTS as unknown as NodeTypes, []);

  // Apply dark mode to minimap SVG
  useEffect(() => {
    const applyMinimapStyling = () => {
      const minimap = document.querySelector(".react-flow__minimap");
      if (minimap) {
        (minimap as HTMLElement).style.backgroundColor = "#1f2937";
        const svg = minimap.querySelector("svg");
        if (svg) {
          svg.setAttribute(
            "style",
            "background-color: #1f2937 !important; background: #1f2937 !important;",
          );
        }
        const rects = minimap.querySelectorAll("rect");
        rects.forEach((rect) => {
          const fill = rect.getAttribute("fill");
          if (!fill || fill === "white" || fill === "#fff" || fill === "rgb(255, 255, 255)") {
            rect.setAttribute("fill", "#1f2937");
          }
        });
      }
    };
    const timer1 = setTimeout(applyMinimapStyling, 100);
    const timer2 = setTimeout(applyMinimapStyling, 300);
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, []);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      setEdges((eds) => {
        const newEdge: Edge = {
          id: `e_${connection.source}_${connection.sourceHandle || "out"}_${connection.target}_${connection.targetHandle || "in"}`,
          source: connection.source,
          target: connection.target,
          sourceHandle: connection.sourceHandle || "out",
          targetHandle: connection.targetHandle || "in",
          animated: true,
          style: { strokeWidth: 1.5, stroke: "#60a5fa" },
        };
        return addEdge(newEdge, eds);
      });
    },
    [setEdges],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (isDefault) return; // read-only
      const type = event.dataTransfer.getData("application/reactflow");
      if (!type || !getNodeDef(type)) return;

      const screenPos = rfInstance?.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      if (!screenPos) return;

      const def = getNodeDef(type);
      setNodes((nds) => {
        const existingIds = new Set(nds.map((n) => n.id));
        let position = screenPos;
        const nodeWidth = 160;
        const nodeHeight = 100;
        let offset = 0;
        while (offset < 10) {
          const testPos = { x: position.x + offset * 20, y: position.y + offset * 20 };
          const overlaps = nds.some(
            (n) =>
              Math.abs(n.position.x - testPos.x) < nodeWidth + 40 &&
              Math.abs(n.position.y - testPos.y) < nodeHeight + 40,
          );
          if (!overlaps) {
            position = testPos;
            break;
          }
          offset++;
        }

        const newNode: Node = {
          id: generateNodeId(existingIds),
          type,
          position,
          data: {
            label: def?.label || type,
            nodeType: type,
            config: def ? { ...def.defaultConfig } : {},
          },
        };
        return nds.concat(newNode);
      });
    },
    [rfInstance, setNodes, isDefault],
  );

  /** Apply automatic tidy-up layout to current nodes/edges. */
  const handleTidyUp = useCallback(() => {
    const positions = computeAutoLayout(nodes, edges);
    setNodes((nds) =>
      nds.map((n) => {
        const pos = positions.get(n.id);
        return pos ? { ...n, position: pos } : n;
      }),
    );
    // Fit view after layout settles
    setTimeout(() => fitView({ padding: 0.15, duration: 300 }), 50);
  }, [nodes, edges, setNodes, fitView]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id);
    setSelectedEdge(null);
    setNodeName((node.data?.label as string) || "");
    setHasBreakpoint(!!(node.data?.config as Record<string, unknown>)?.breakpoint);
  }, []);

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge);
    setSelectedNode(null);
  }, []);

  const handleDeleteEdge = useCallback(() => {
    if (!selectedEdge) return;
    setEdges((eds) => eds.filter((e) => e.id !== selectedEdge.id));
    setSelectedEdge(null);
  }, [selectedEdge, setEdges]);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, []);

  const handleNodeNameChange = useCallback(
    (name: string) => {
      setNodeName(name);
      setNodes((nds) =>
        nds.map((n) => (n.id === selectedNode ? { ...n, data: { ...n.data, label: name } } : n)),
      );
    },
    [selectedNode, setNodes],
  );

  const handleConfigChange = useCallback(
    (newConfig: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedNode ? { ...n, data: { ...n.data, config: newConfig } } : n,
        ),
      );
    },
    [selectedNode, setNodes],
  );

  const handleBreakpointToggle = useCallback(() => {
    const next = !hasBreakpoint;
    setHasBreakpoint(next);
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode
          ? {
              ...n,
              data: {
                ...n.data,
                config: {
                  ...((n.data?.config as Record<string, unknown>) || {}),
                  breakpoint: next,
                },
              },
            }
          : n,
      ),
    );
  }, [selectedNode, hasBreakpoint, setNodes]);

  const handleDeleteNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode && e.target !== selectedNode));
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  const handleAddNode = useCallback(
    (type: string) => {
      if (!rfInstance) return;
      const def = getNodeDef(type);
      const center = rfInstance.screenToFlowPosition({
        x: document.documentElement.clientWidth / 2,
        y: document.documentElement.clientHeight / 3,
      });
      setNodes((nds) => {
        const existingIds = new Set(nds.map((n) => n.id));
        const newNode: Node = {
          id: generateNodeId(existingIds),
          type,
          position: center,
          data: {
            label: def?.label || type,
            nodeType: type,
            config: def ? { ...def.defaultConfig } : {},
          },
        };
        return nds.concat(newNode);
      });
    },
    [rfInstance, setNodes],
  );

  const persistCanvas = useCallback(() => {
    const rfNodes = nodes.map(ruleNodeFromReactFlow);
    const rfEdges = edges.map(ruleEdgeFromReactFlow);
    const canvasData = { nodes: rfNodes, edges: rfEdges };
    onCanvasChange(canvasData);
    onSave(canvasData);
  }, [nodes, edges, onCanvasChange, onSave]);

  const selectedNodeType = selectedNode
    ? (nodes.find((n) => n.id === selectedNode)?.type ?? null)
    : null;
  const selectedNodeConfig = selectedNode
    ? (nodes.find((n) => n.id === selectedNode)?.data?.config as Record<string, unknown>) || {}
    : {};

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-bg-surface">
        <Button variant="ghost" size="xs" onClick={onBack}>
          ← Back
        </Button>
        <input
          type="text"
          value={ruleName}
          onChange={(e) => onNameChange(e.target.value)}
          readOnly={isDefault}
          className="flex-1 px-2 py-1 text-sm font-medium bg-transparent border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus text-fg disabled:opacity-50"
          placeholder="Rule name"
        />
        {/* Tidy Up — applies auto-layout */}
        <Button
          variant="secondary"
          size="xs"
          icon={<LayoutGrid size={12} />}
          onClick={handleTidyUp}
          title="Automatically tidy up node positions"
        >
          Tidy Up
        </Button>
        {isDefault ? (
          <Button variant="secondary" size="sm" icon={<Copy size={14} />} onClick={onClone}>
            Clone to Edit
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            onClick={persistCanvas}
            disabled={saving}
            loading={saving}
          >
            {saving ? "Saving..." : "Save"}
          </Button>
        )}
      </div>

      {/* Default rule read-only banner */}
      {isDefault && (
        <div className="flex items-center gap-2 px-4 py-2 bg-accent-500/10 border-b border-accent-500/20 text-xs text-accent-500">
          <AlignLeft size={12} />
          This is a built-in default rule and cannot be edited.
        </div>
      )}

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Node Palette */}
        <NodePalette onAddNode={isDefault ? () => {} : handleAddNode} />

        {/* Center: Canvas */}
        <div
          ref={reactFlowWrapper}
          className="flex-1 relative"
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={isDefault ? undefined : onNodesChange}
            onEdgesChange={isDefault ? undefined : onEdgesChange}
            onConnect={isDefault ? undefined : onConnect}
            onInit={setRfInstance}
            onNodeClick={onNodeClick}
            onEdgeClick={isDefault ? undefined : onEdgeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode={isDefault ? null : ["Backspace", "Delete"]}
            nodesDraggable={!isDefault}
            nodesConnectable={!isDefault}
            connectionLineStyle={{ stroke: "#60a5fa", strokeWidth: 2 }}
            defaultEdgeOptions={{
              animated: true,
              style: { strokeWidth: 1.5, stroke: "#94a3b8" },
            }}
          >
            <Controls />
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
            <MiniMap
              nodeStrokeColor="#1f2937"
              nodeColor="#374151"
              maskColor="rgba(0,0,0,0.3)"
              style={{
                width: 150,
                height: 100,
                backgroundColor: "#1f2937",
                borderRadius: "var(--radius-lg)",
              }}
            />
          </ReactFlow>
        </div>

        {/* Right: Inspector */}
        {selectedEdge && !isDefault ? (
          <div className="w-72 bg-bg-muted border-l border-border p-4 flex-shrink-0">
            <div className="text-xs text-fg-subtle uppercase tracking-wider mb-3">Connection</div>
            <div className="text-xs text-fg-muted mb-4 space-y-1">
              <p>
                <span className="text-fg-subtle">From:</span> {selectedEdge.source}
              </p>
              <p>
                <span className="text-fg-subtle">To:</span> {selectedEdge.target}
              </p>
            </div>
            <Button variant="danger" size="sm" onClick={handleDeleteEdge}>
              Disconnect
            </Button>
          </div>
        ) : (
          <NodeInspector
            nodeId={selectedNode}
            nodeType={selectedNodeType}
            nodeName={nodeName}
            config={selectedNodeConfig}
            onNameChange={isDefault ? () => {} : handleNodeNameChange}
            onConfigChange={isDefault ? () => {} : handleConfigChange}
            onDelete={isDefault ? () => {} : handleDeleteNode}
            onBreakpointToggle={isDefault ? () => {} : handleBreakpointToggle}
            hasBreakpoint={hasBreakpoint}
            readOnly={isDefault}
          />
        )}
      </div>

      {/* Bottom: Test Panel */}
      <TestPanel ruleId={ruleId} />
    </div>
  );
}

export function ProgramCanvas(props: ProgramCanvasProps) {
  return (
    <ReactFlowProvider>
      <ProgramCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
