import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { type MatchRule, type MatchRuleCanvas, matchRulesAPI } from "../api/rules";

export function useMatchRules() {
  const [rules, setRules] = useState<MatchRule[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRules = useCallback(async () => {
    try {
      const data = await matchRulesAPI.list();
      setRules(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load rules";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const createRule = useCallback(async (name: string) => {
    try {
      const rule = await matchRulesAPI.create({ name });
      setRules((prev) => [...prev, rule]);
      toast.success(`Rule "${name}" created`);
      return rule;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to create rule";
      toast.error(msg);
      return null;
    }
  }, []);

  const updateRule = useCallback(
    async (id: number, data: { name?: string; is_active?: boolean; canvas?: MatchRuleCanvas }) => {
      try {
        const rule = await matchRulesAPI.update(id, data);
        setRules((prev) => prev.map((r) => (r.id === id ? rule : r)));
        return rule;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to update rule";
        toast.error(msg);
        return null;
      }
    },
    [],
  );

  const deleteRule = useCallback(async (id: number) => {
    try {
      await matchRulesAPI.delete(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
      toast.success("Rule deleted");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to delete rule";
      toast.error(msg);
    }
  }, []);

  const reorderRules = useCallback(
    async (order: { id: number; priority: number }[]) => {
      try {
        const updated = await matchRulesAPI.reorder(order);
        setRules(updated);
        toast.success("Rules reordered");
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to reorder rules";
        toast.error(msg);
        await fetchRules();
      }
    },
    [fetchRules],
  );

  const saveCanvas = useCallback(
    async (ruleId: number, canvas: MatchRuleCanvas) => {
      return updateRule(ruleId, { canvas });
    },
    [updateRule],
  );

  return {
    rules,
    loading,
    fetchRules,
    createRule,
    updateRule,
    deleteRule,
    reorderRules,
    saveCanvas,
  };
}
