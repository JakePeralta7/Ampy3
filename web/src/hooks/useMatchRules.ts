import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { type MatchRule, matchRulesAPI } from "../api/rules";
import { POLLING_CONFIG } from "../lib/pollingConfig";
import { getErrorMessage } from "../lib/utils";

export interface UseMatchRulesReturn {
  rules: MatchRule[];
  loading: boolean;
  fetchRules: () => Promise<void>;
  createRule: (name: string, yaml_content: string) => Promise<MatchRule | null>;
  cloneRule: (id: number, name?: string) => Promise<MatchRule | null>;
  updateRule: (
    id: number,
    data: { name?: string; is_active?: boolean; yaml_content?: string },
  ) => Promise<MatchRule | null>;
  deleteRule: (id: number) => Promise<void>;
  reorderRules: (order: { id: number; priority: number }[]) => Promise<void>;
  lastUpdated: Date | null;
}

export function useMatchRules(): UseMatchRulesReturn {
  const [rules, setRules] = useState<MatchRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchRules = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      const data = await matchRulesAPI.list();
      if (isMountedRef.current) {
        setRules(data);
        setLastUpdated(new Date());
      }
    } catch (e: unknown) {
      const msg = getErrorMessage(e, "Failed to load rules");
      toast.error(msg);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchRules();

    // Set up polling
    pollIntervalRef.current = setInterval(() => {
      fetchRules();
    }, POLLING_CONFIG.DEFAULT_INTERVAL);

    return () => {
      isMountedRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [fetchRules]);

  const createRule = useCallback(async (name: string, yaml_content: string) => {
    try {
      const rule = await matchRulesAPI.create({ name, yaml_content });
      setRules((prev) => [...prev, rule]);
      setLastUpdated(new Date());
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
      setLastUpdated(new Date());
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
        setLastUpdated(new Date());
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
      setLastUpdated(new Date());
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
        setLastUpdated(new Date());
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
    lastUpdated,
  };
}
