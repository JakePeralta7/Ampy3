import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { type MatchRule, type MatchRuleCanvas, matchRulesAPI } from "../api/rules";
import { ProgramCanvas } from "../components/Rules/ProgramCanvas";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";

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

  /**
   * Serialise the React Flow canvas back to YAML via the backend API.
   * The backend computes canonical positions; we only need to send nodes/edges.
   *
   * For now we send the canvas dict directly and let the backend's
   * canvas_to_yaml convert it. The update endpoint accepts yaml_content,
   * so we first retrieve the current yaml_content from the rule and patch
   * the node configs in it — or simply save as canvas (which the backend
   * will reject if there's no yaml_content).
   *
   * Since the backend no longer accepts canvas directly, we call the
   * update endpoint with yaml_content built from the canvas by serialising
   * the node/edge data. The backend's canvas_to_yaml helper does this job.
   *
   * Until a proper client-side YAML serialiser is wired, we round-trip
   * through the backend: POST the canvas as JSON and let it build YAML.
   *
   * Simple approach: keep using yaml_content from the rule for non-structural
   * edits; for structural (node/edge) changes, send canvas and let the backend
   * rebuild yaml. The backend PUT now accepts yaml_content only — so we need
   * a dedicated endpoint or we build YAML on the client.
   *
   * For now: on save, fetch the updated rule with new canvas, and persist
   * yaml_content from the latest server state (which was computed on-load).
   * We do this by calling update with the node configs merged from the canvas.
   *
   * TODO: implement client-side canvas→YAML serialiser to avoid the round-trip.
   */
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
        toast.error(err instanceof Error ? err.message : "Failed to save rule");
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
      toast.error(err instanceof Error ? err.message : "Failed to clone rule");
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
