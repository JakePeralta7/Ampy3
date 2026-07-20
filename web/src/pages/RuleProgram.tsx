import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { type MatchRule, matchRulesAPI } from "../api/rules";
import { type MatchRuleCanvas, ProgramCanvas } from "../components/Rules/ProgramCanvas";

export function RuleProgramPage() {
  const { ruleId } = useParams<{ ruleId: string }>();
  const navigate = useNavigate();

  const [rule, setRule] = useState<MatchRule | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const numericId = ruleId ? parseInt(ruleId, 10) : null;

  useEffect(() => {
    if (!numericId) return;
    setLoading(true);
    matchRulesAPI
      .get(numericId)
      .then((rule) => {
        setRule(rule);
      })
      .catch(() => {
        navigate("/settings/matching");
      })
      .finally(() => setLoading(false));
  }, [numericId, navigate]);

  const handleCanvasChange = useCallback((canvas: MatchRuleCanvas) => {
    setRule((prev) => (prev ? { ...prev, canvas } : prev));
  }, []);

  const handleNameChange = useCallback((name: string) => {
    setRule((prev) => (prev ? { ...prev, name } : prev));
  }, []);

  const handleSave = useCallback(
    async (canvas: MatchRuleCanvas) => {
      if (!rule || !numericId) return;
      setSaving(true);
      try {
        await matchRulesAPI.update(numericId, {
          name: rule.name,
          canvas,
        });
        toast.success("Rule saved");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to save rule");
      } finally {
        setSaving(false);
      }
    },
    [rule, numericId],
  );

  const handleBack = useCallback(() => {
    navigate("/settings/matching");
  }, [navigate]);

  if (loading || !rule) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-fg-subtle">
        Loading rule...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <ProgramCanvas
        ruleId={numericId}
        ruleName={rule.name}
        canvas={rule.canvas || { nodes: [], edges: [] }}
        onCanvasChange={handleCanvasChange}
        onNameChange={handleNameChange}
        onBack={handleBack}
        onSave={handleSave}
        saving={saving}
      />
    </div>
  );
}
