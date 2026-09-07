import { Beaker, Plus, SlidersHorizontal } from "lucide-react";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { MatchRule } from "../api/rules";
import { PageLayout } from "../components/layout/PageLayout";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { RuleList } from "../features/rules/RuleList";
import { TestPanel } from "../features/rules/TestPanel";
import { useMatchRules } from "../hooks/useMatchRules";

/** Minimal starter YAML for a brand-new rule. */
const STARTER_YAML = `name: "New Rule"
description: "Basic search and compare matching"
nodes:
  source:
    type: track_source

  search:
    type: search
    config:
      fields_to_search:
        - search_title
        - search_artist
        - search_album
      max_results: 50

  compare:
    type: compare
    config:
      fields_to_match:
        - title
        - artist_name
        - album_name
      threshold: 0.75
      weights:
        title: 50
        artist_name: 25
        album_name: 25

  output:
    type: match_output

edges:
  - from: source
    to: search

  - from: search
    to: compare
    source_handle: out
    target_handle: candidates

  - from: compare
    to: output
`;

export function MatchRulesPage() {
  const navigate = useNavigate();
  const { rules, loading, createRule, cloneRule, updateRule, deleteRule, reorderRules } =
    useMatchRules();
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
    const rule = await createRule(name, STARTER_YAML);
    if (rule) {
      navigate(`/settings/matching/${rule.id}`);
    }
  }, [rules.length, createRule, navigate]);

  const handleCloneRule = useCallback(
    async (ruleId: number) => {
      const rule = await cloneRule(ruleId);
      if (rule) {
        navigate(`/settings/matching/${rule.id}`);
      }
    },
    [cloneRule, navigate],
  );

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
    <PageLayout
      title="Match Rules"
      icon={<SlidersHorizontal size={28} className="text-fg-muted" />}
      subtitle={`Configure matching rules • ${rules.length} rule${rules.length !== 1 ? "s" : ""}`}
      actions={
        <>
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
        </>
      }
    >
      <RuleList
        rules={rules}
        onRuleClick={handleRuleClick}
        onRulesReorder={handleReorder}
        onDeleteRule={handleDeleteRule}
        onToggleActive={handleToggleActive}
        onCloneRule={handleCloneRule}
        loading={loading}
      />

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
    </PageLayout>
  );
}
