import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { type MatchRule, matchRulesAPI } from "../api/rules";
import { getErrorMessage } from "../lib/utils";

export function useMatchRules() {
  const [rules, setRules] = useState<MatchRule[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRules = useCallback(async () => {
    try {
      const data = await matchRulesAPI.list();
      setRules(data);
    } catch (e: unknown) {
      const msg = getErrorMessage(e, "Failed to load rules");
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const createRule = useCallback(async (name: string, yaml_content: string) => {
    try {
      const rule = await matchRulesAPI.create({ name, yaml_content });
      setRules((prev) => [...prev, rule]);
      toast.success(`Rule "${name}" created`);
      return rule;
    } catch (e: unknown) {
      const msg = getErrorMessage(e, "Failed to create rule");
      toast.error(msg);
      return null;
    }
  }, []);

  const cloneRule = useCallback(async (id: number, name?: string) => {
    try {
      const rule = await matchRulesAPI.clone(id, name ? { name } : undefined);
      setRules((prev) => [...prev, rule]);
      toast.success(`Rule cloned as "${rule.name}"`);
      return rule;
    } catch (e: unknown) {
      const msg = getErrorMessage(e, "Failed to clone rule");
      toast.error(msg);
      return null;
    }
  }, []);

  const updateRule = useCallback(
    async (id: number, data: { name?: string; is_active?: boolean; yaml_content?: string }) => {
      try {
        const rule = await matchRulesAPI.update(id, data);
        setRules((prev) => prev.map((r) => (r.id === id ? rule : r)));
        return rule;
      } catch (e: unknown) {
        const msg = getErrorMessage(e, "Failed to update rule");
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
      const msg = getErrorMessage(e, "Failed to delete rule");
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
        const msg = getErrorMessage(e, "Failed to reorder rules");
        toast.error(msg);
        await fetchRules();
      }
    },
    [fetchRules],
  );

  return {
    rules,
    loading,
    fetchRules,
    createRule,
    cloneRule,
    updateRule,
    deleteRule,
    reorderRules,
  };
}
