import { Beaker, Plus } from "lucide-react";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { type MatchRule } from "../api/rules";
import { RuleList } from "../components/Rules/RuleList";
import { TestPanel } from "../components/Rules/TestPanel";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { useMatchRules } from "../hooks/useMatchRules";

export function MatchRulesPage() {
  const navigate = useNavigate();
  const { rules, loading, createRule, updateRule, deleteRule, reorderRules } = useMatchRules();
  const [showTest, setShowTest] = useState(false);
  const [deleteConfirmRuleId, setDeleteConfirmRuleId] = useState<number | null>(null);

  const handleRuleClick = useCallback(
    (ruleId: number) => {
      navigate(`/settings/matching/${ruleId}`);
    },
    [navigate],
  );

  const handleAddRule = useCallback(async () => {
    const name = `Rule ${rules.length + 1}`;
    const rule = await createRule(name);
    if (rule) {
      navigate(`/settings/matching/${rule.id}`);
    }
  }, [rules.length, createRule, navigate]);

  const handleDeleteRule = useCallback((ruleId: number) => {
    setDeleteConfirmRuleId(ruleId);
  }, []);

  const confirmDeleteRule = useCallback(async () => {
    if (deleteConfirmRuleId === null) return;
    await deleteRule(deleteConfirmRuleId);
    setDeleteConfirmRuleId(null);
  }, [deleteConfirmRuleId, deleteRule]);

  const handleReorder = useCallback(
    async (order: { id: number; priority: number }[]) => {
      await reorderRules(order);
    },
    [reorderRules],
  );

  const handleToggleActive = useCallback(
    async (rule: MatchRule) => {
      await updateRule(rule.id, { is_active: !rule.is_active });
    },
    [updateRule],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-bg-surface">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-fg">Match Rules</h1>
          <span className="text-xs text-fg-subtle">
            {rules.length} rule{rules.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="xs"
            icon={<Beaker size={12} />}
            onClick={() => setShowTest(!showTest)}
          >
            {showTest ? "Hide Test" : "Test Matching"}
          </Button>
          <Button variant="primary" size="xs" icon={<Plus size={12} />} onClick={handleAddRule}>
            Add Rule
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <RuleList
          rules={rules}
          onRuleClick={handleRuleClick}
          onRulesReorder={handleReorder}
          onDeleteRule={handleDeleteRule}
          onToggleActive={handleToggleActive}
          loading={loading}
        />
      </div>

      {showTest && <TestPanel ruleId={null} />}

      <ConfirmDialog
        open={deleteConfirmRuleId !== null}
        title="Delete rule"
        message="Delete this rule?"
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDeleteRule}
        onCancel={() => setDeleteConfirmRuleId(null)}
      />
    </div>
  );
}
