import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { type MatchRule, type MatchRuleCanvas, matchRulesAPI } from "../api/rules";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { ProgramCanvas } from "../features/rules/ProgramCanvas";
import { getErrorMessage } from "../lib/utils";

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
      .then((r) => setRule(r))
      .catch(() => navigate("/settings/matching"))
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
        // Build a minimal YAML from the canvas node/edge structure.
        // The backend's yaml_content field is required, so we construct
        // a YAML string client-side from the canvas and send it.
        const yamlContent = canvasToYaml(rule.name, canvas);
        const updated = await matchRulesAPI.update(numericId, {
          name: rule.name,
          yaml_content: yamlContent,
        });
        setRule(updated);
        toast.success("Rule saved");
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to save rule"));
      } finally {
        setSaving(false);
      }
    },
    [rule, numericId],
  );

  const handleClone = useCallback(async () => {
    if (!numericId) return;
    try {
      const cloned = await matchRulesAPI.clone(numericId);
      toast.success(`Cloned as "${cloned.name}"`);
      navigate(`/settings/matching/${cloned.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to clone rule"));
    }
  }, [numericId, navigate]);

  const handleBack = useCallback(() => {
    navigate("/settings/matching");
  }, [navigate]);

  if (loading || !rule) {
    return <LoadingSpinner text="Loading rule..." />;
  }

  return (
    <div className="flex flex-col h-full">
      <ProgramCanvas
        ruleId={numericId}
        ruleName={rule.name}
        isDefault={rule.is_default}
        canvas={rule.canvas || { nodes: [], edges: [] }}
        onCanvasChange={handleCanvasChange}
        onNameChange={handleNameChange}
        onBack={handleBack}
        onSave={handleSave}
        onClone={handleClone}
        saving={saving}
      />
    </div>
  );
}

/**
 * Minimal client-side canvas → YAML serialiser.
 * Mirrors the Python backend's canvas_to_yaml().
 */
function canvasToYaml(ruleName: string, canvas: MatchRuleCanvas): string {
  const lines: string[] = [];
  lines.push(`name: ${JSON.stringify(ruleName)}`);
  lines.push("nodes:");

  for (const node of canvas.nodes) {
    lines.push(`  ${node.id}:`);
    lines.push(`    type: ${node.type}`);
    const config = node.config;
    if (config && Object.keys(config).length > 0) {
      lines.push("    config:");
      for (const [k, v] of Object.entries(config)) {
        lines.push(`      ${k}: ${JSON.stringify(v)}`);
      }
    }
  }

  lines.push("edges:");
  for (const edge of canvas.edges) {
    const src = edge.source;
    const tgt = edge.target;
    const sh = edge.sourceHandle ?? "out";
    const th = edge.targetHandle ?? "in";
    lines.push(`  - from: ${src}`);
    lines.push(`    to: ${tgt}`);
    if (sh !== "out") lines.push(`    source_handle: ${sh}`);
    if (th !== "in") lines.push(`    target_handle: ${th}`);
  }

  return `${lines.join("\n")}\n`;
}
