import { Pause, Pencil, Play, Trash2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import type { MatchRule } from "../../api/rules";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface RuleListProps {
  rules: MatchRule[];
  onRuleClick: (ruleId: number) => void;
  onRulesReorder: (order: { id: number; priority: number }[]) => void;
  onDeleteRule: (ruleId: number) => void;
  onToggleActive: (rule: MatchRule) => void;
  loading: boolean;
}

export function RuleList({
  rules,
  onRuleClick,
  onRulesReorder,
  onDeleteRule,
  onToggleActive,
  loading,
}: RuleListProps) {
  const [localRules, setLocalRules] = useState<MatchRule[] | null>(null);
  const draggedId = useRef<number | null>(null);

  const displayRules = localRules ?? rules;

  const handleDragStart = useCallback((e: React.DragEvent, ruleId: number) => {
    draggedId.current = ruleId;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(ruleId));
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent, targetIdx: number) => {
      e.preventDefault();
      if (draggedId.current === null) return;

      const firstNonDefaultIdx = displayRules.findIndex((r) => !r.is_default);
      if (targetIdx < firstNonDefaultIdx) return;

      const currentIdx = displayRules.findIndex((r) => r.id === draggedId.current);
      if (currentIdx === -1 || currentIdx === targetIdx) return;

      const reordered = [...displayRules];
      const [removed] = reordered.splice(currentIdx, 1);
      reordered.splice(targetIdx, 0, removed);
      setLocalRules(reordered);
    },
    [displayRules],
  );

  const handleDragEnd = useCallback(() => {
    draggedId.current = null;
    if (localRules) {
      const order = localRules.map((r, i) => ({ id: r.id, priority: i }));
      const currentOrder = rules.map((r) => r.id).join(",");
      const proposedOrder = localRules.map((r) => r.id).join(",");
      if (currentOrder !== proposedOrder) {
        onRulesReorder(order);
      }
      setLocalRules(null);
    }
  }, [localRules, rules, onRulesReorder]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-fg-subtle">
        Loading rules...
      </div>
    );
  }

  if (displayRules.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-fg-subtle">
        No rules yet. Click "+ Add Rule" to create one.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-2 overflow-auto">
      {displayRules.map((rule, index) => (
        <div
          key={rule.id}
          draggable={!rule.is_default}
          onDragStart={(e) => handleDragStart(e, rule.id)}
          onDragOver={(e) => handleDragOver(e, index)}
          onDragEnd={handleDragEnd}
          onClick={() => onRuleClick(rule.id)}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg border bg-bg-surface cursor-pointer transition-all hover:shadow-md active:shadow-sm ${
            draggedId.current === rule.id ? "opacity-50 border-accent-500" : "border-border"
          } ${rule.is_active ? "" : "opacity-60"}`}
        >
          {!rule.is_default && (
            <span className="text-fg-subtle cursor-grab active:cursor-grabbing text-lg leading-none select-none">
              ⠿
            </span>
          )}

          <span className="w-6 h-6 rounded-full bg-accent-500 text-accent-fg text-xs font-bold flex items-center justify-center shrink-0">
            {index + 1}
          </span>

          <span className="flex-1 text-sm font-semibold text-fg truncate">{rule.name}</span>

          <Badge variant={rule.is_active ? "success" : "neutral"}>
            {rule.is_active ? "Active" : "Paused"}
          </Badge>

          <span className="text-xs text-fg-subtle shrink-0">
            {rule.canvas?.nodes?.length || 0} node
            {(rule.canvas?.nodes?.length || 0) !== 1 ? "s" : ""}
          </span>

          {rule.is_default && (
            <span className="text-[10px] uppercase tracking-wider text-fg-subtle font-semibold shrink-0 px-1">
              Default
            </span>
          )}

          <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="xs"
              icon={rule.is_active ? <Pause size={14} /> : <Play size={14} />}
              onClick={() => onToggleActive(rule)}
              title={rule.is_active ? "Pause" : "Resume"}
            />
            {!rule.is_default && (
              <>
                <Button
                  variant="ghost"
                  size="xs"
                  icon={<Pencil size={14} />}
                  onClick={() => onRuleClick(rule.id)}
                  title="Edit"
                />
                <Button
                  variant="ghost"
                  size="xs"
                  icon={<Trash2 size={14} />}
                  onClick={() => onDeleteRule(rule.id)}
                  title="Delete"
                  className="text-danger-500 hover:bg-danger-500/10"
                />
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
