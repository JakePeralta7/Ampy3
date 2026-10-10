import { SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { type MatchRule, type MatchRuleCanvas, matchRulesAPI } from "../api/rules";
import { PageLayout } from "../components/layout/PageLayout";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { UpdateTimestamp } from "../components/ui/UpdateTimestamp";
import { ProgramCanvas } from "../features/rules/ProgramCanvas";
import { POLLING_CONFIG } from "../lib/pollingConfig";
import { getErrorMessage } from "../lib/utils";

export function RuleProgramPage() {
  const { ruleId } = useParams<{ ruleId: string }>();
  const navigate = useNavigate();

  const [rule, setRule] = useState<MatchRule | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const numericId = ruleId ? parseInt(ruleId, 10) : null;
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchRule = useCallback(async () => {
    if (!numericId || !isMountedRef.current) return;
    try {
      const r = await matchRulesAPI.get(numericId);
      if (isMountedRef.current) {
        setRule(r);
        setLastUpdated(new Date());
      }
    } catch (err) {
      if (isMountedRef.current) {
        toast.error(getErrorMessage(err, "Failed to reload rule"));
        navigate("/settings/matching");
      }
    }
  }, [numericId, navigate]);

  useEffect(() => {
    isMountedRef.current = true;

    if (!numericId) return;

    setLoading(true);
    matchRulesAPI
      .get(numericId)
      .then((r) => {
        if (isMountedRef.current) {
          setRule(r);
          setLastUpdated(new Date());
        }
      })
      .catch(() => navigate("/settings/matching"))
      .finally(() => {
        if (isMountedRef.current) {
          setLoading(false);
        }
      });

    // Set up polling
    pollIntervalRef.current = setInterval(() => {
      fetchRule();
    }, POLLING_CONFIG.DEFAULT_INTERVAL);

    return () => {
      isMountedRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [numericId, navigate, fetchRule]);

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
        const yamlContent = canvasToYaml(rule.name, canvas, rule.description ?? null);
        const updated = await matchRulesAPI.update(numericId, {
          name: rule.name,
          yaml_content: yamlContent,
        });
        setRule(updated);
        setLastUpdated(new Date());
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
    <PageLayout
      title={rule.name}
      icon={<SlidersHorizontal size={28} className="text-fg-muted" />}
      subtitle="Rule program canvas"
    >
      <div className="h-[calc(100dvh-16rem)] flex flex-col">
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
        <div className="border-t border-border bg-bg-subtle p-3 text-xs text-gray-500">
          <UpdateTimestamp lastUpdated={lastUpdated} />
        </div>
      </div>
    </PageLayout>
  );
}

/**
 * Minimal client-side canvas → YAML serialiser.
 * Mirrors the Python backend's canvas_to_yaml().
 */
function canvasToYaml(
  ruleName: string,
  canvas: MatchRuleCanvas,
  description?: string | null,
): string {
  const lines: string[] = [];
  lines.push(`name: ${JSON.stringify(ruleName)}`);
  if (description) {
    lines.push(`description: ${JSON.stringify(description)}`);
  }
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
