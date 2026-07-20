import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  GitCompare,
  ListTree,
  Play,
  Search,
  XCircle,
} from "lucide-react";
import { useCallback, useState } from "react";
import { matchRulesAPI, type TestResponse, type TrackTestInput } from "../../api/rules";
import { Button } from "../ui/Button";

interface TestPanelProps {
  ruleId: number | null;
  onTestResult?: (result: TestResponse) => void;
}

export function TestPanel({ ruleId, onTestResult }: TestPanelProps) {
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [album, setAlbum] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Set<number>>(new Set());
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  const toggleStep = useCallback((stepKey: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepKey)) next.delete(stepKey);
      else next.add(stepKey);
      return next;
    });
  }, []);

  const toggleTrace = useCallback((ruleId: number) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
  }, []);

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const track: TrackTestInput = { title, artist_name: artist, album_name: album || undefined };
      const ruleIds = ruleId ? [ruleId] : undefined;
      const res = await matchRulesAPI.test(track, ruleIds);
      setResult(res);
      setExpandedTraces(new Set(res.matches?.length ? res.matches.map((m) => m.rule_id) : []));
      onTestResult?.(res);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Test request failed";
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [title, artist, album, ruleId, onTestResult]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && title && !loading) {
        handleRun();
      }
    },
    [title, loading, handleRun],
  );

  const handleClear = useCallback(() => {
    setResult(null);
    setError(null);
    setExpandedTraces(new Set());
  }, []);

  const matchedCount = result?.matches?.filter((m) => m.matched).length ?? 0;
  const totalRules = result?.matches?.length ?? 0;
  const hasResults = result !== null;

  return (
    <div className="border-t border-border bg-bg-muted">
      <div className="p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ListTree size={14} className="text-fg-subtle" />
            <span className="text-xs font-semibold text-fg-muted uppercase tracking-wider">
              Test Track Matching
            </span>
            {hasResults && (
              <span
                className={`text-xs font-medium px-1.5 py-0.5 rounded-sm ${
                  matchedCount > 0
                    ? "bg-success-500/10 text-success-500 border border-success-500/20"
                    : "bg-danger-500/10 text-danger-500 border border-danger-500/20"
                }`}
              >
                {matchedCount}/{totalRules} matched
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {hasResults && (
              <Button variant="ghost" size="xs" onClick={handleClear}>
                Clear
              </Button>
            )}
          </div>
        </div>

        {/* Input form */}
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label className="block text-xs text-fg-subtle mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-2.5 py-1.5 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus placeholder-fg-subtle"
              placeholder="Song title"
              disabled={loading}
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-fg-subtle mb-1">Artist</label>
            <input
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-2.5 py-1.5 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus placeholder-fg-subtle"
              placeholder="Artist name"
              disabled={loading}
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-fg-subtle mb-1">Album</label>
            <input
              type="text"
              value={album}
              onChange={(e) => setAlbum(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-2.5 py-1.5 text-xs bg-bg-surface border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-border-focus placeholder-fg-subtle"
              placeholder="Album (optional)"
              disabled={loading}
            />
          </div>
          <Button
            onClick={handleRun}
            disabled={loading || !title}
            loading={loading}
            size="sm"
            icon={<Play size={12} />}
          >
            {loading ? "Testing..." : "Run Test"}
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-3 flex items-start gap-2 p-2.5 rounded-sm bg-danger-500/10 border border-danger-500/30">
            <AlertCircle size={14} className="text-danger-500 mt-0.5 shrink-0" />
            <div className="text-xs text-danger-500">{error}</div>
          </div>
        )}

        {/* Results */}
        {hasResults && !error && (
          <div className="mt-3 space-y-2">
            {/* Summary */}
            <div className="flex items-center gap-3 text-xs text-fg-muted px-1">
              <span className="flex items-center gap-1">
                <CheckCircle2 size={12} className="text-success-500" />
                {matchedCount} matched
              </span>
              <span className="flex items-center gap-1">
                <XCircle size={12} className="text-danger-500" />
                {totalRules - matchedCount} unmatched
              </span>
              <span className="text-border-strong">|</span>
              <span>
                {totalRules} rule{totalRules !== 1 ? "s" : ""} tested
              </span>
            </div>

            {/* Match cards */}
            {result.matches && result.matches.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {result.matches.map((m) => (
                  <div
                    key={m.rule_id}
                    className={`rounded-lg p-3 border ${
                      m.matched
                        ? "bg-success-500/5 border-success-500/30"
                        : "bg-danger-500/5 border-danger-500/30"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold text-fg truncate">{m.rule_name}</span>
                      {m.matched ? (
                        <span className="text-xs font-medium text-success-500 bg-success-500/10 px-1.5 py-0.5 rounded-sm flex items-center gap-1 shrink-0">
                          <CheckCircle2 size={10} /> Matched
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-danger-500 bg-danger-500/10 px-1.5 py-0.5 rounded-sm flex items-center gap-1 shrink-0">
                          <XCircle size={10} /> No match
                        </span>
                      )}
                    </div>
                    {m.error && (
                      <div className="text-xs text-danger-500 mb-1.5 flex items-start gap-1">
                        <AlertCircle size={10} className="mt-0.5 shrink-0" />
                        <span>{m.error}</span>
                      </div>
                    )}
                    {m.matched && m.result && (
                      <div className="text-xs text-fg-muted space-y-0.5 bg-bg-surface/60 rounded-sm px-2 py-1.5">
                        {m.result.title != null && (
                          <div className="flex gap-2">
                            <span className="font-medium text-fg-subtle w-10 shrink-0">Title</span>
                            <span className="text-fg truncate">{String(m.result.title)}</span>
                          </div>
                        )}
                        {m.result.artist_name != null && (
                          <div className="flex gap-2">
                            <span className="font-medium text-fg-subtle w-10 shrink-0">Artist</span>
                            <span className="text-fg truncate">{String(m.result.artist_name)}</span>
                          </div>
                        )}
                        {m.result.album_name != null && (
                          <div className="flex gap-2">
                            <span className="font-medium text-fg-subtle w-10 shrink-0">Album</span>
                            <span className="text-fg truncate">{String(m.result.album_name)}</span>
                          </div>
                        )}
                        {m.result.plex_id != null && (
                          <div className="flex gap-2">
                            <span className="font-medium text-fg-subtle w-10 shrink-0">Plex</span>
                            <span className="font-mono text-fg truncate text-xs">
                              {String(m.result.plex_id)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Traces section */}
            {result.traces.length > 0 && (
              <div className="space-y-1">
                <div className="text-xs font-medium text-fg-subtle uppercase tracking-wider px-1">
                  Execution Traces
                </div>
                {result.traces.map((trace) => {
                  const isExpanded = expandedTraces.has(trace.rule_id);
                  const hasMatch = trace.steps.some(
                    (s) => s.node_type === "compare" && s.outputs?.out != null,
                  );
                  return (
                    <div
                      key={trace.rule_id}
                      className="bg-bg-surface rounded-lg border border-border overflow-hidden"
                    >
                      <button
                        onClick={() => toggleTrace(trace.rule_id)}
                        className="w-full flex items-center justify-between px-3 py-2 text-xs hover:bg-bg-muted transition-colors duration-fast"
                        aria-expanded={isExpanded}
                      >
                        <div className="flex items-center gap-2">
                          {isExpanded ? (
                            <ChevronDown size={12} className="text-fg-subtle" />
                          ) : (
                            <ChevronRight size={12} className="text-fg-subtle" />
                          )}
                          <span className="font-medium text-fg-muted">{trace.rule_name}</span>
                          <span
                            className={`text-xs font-medium px-1.5 py-0.5 rounded-sm ${
                              hasMatch
                                ? "bg-success-500/10 text-success-500 border border-success-500/20"
                                : "bg-danger-500/10 text-danger-500 border border-danger-500/20"
                            }`}
                          >
                            {hasMatch ? "Matched" : "No match"}
                          </span>
                          <span className="text-fg-subtle">{trace.steps.length} steps</span>
                        </div>
                        {trace.error && (
                          <AlertCircle size={12} className="text-danger-500 shrink-0" />
                        )}
                      </button>
                      {isExpanded && trace.steps.length > 0 && (
                        <div className="border-t border-border divide-y divide-border">
                          {trace.steps.map((step, i) => {
                            const stepKey = `${trace.rule_id}-${step.node_id}`;
                            const isStepExpanded = expandedSteps.has(stepKey);
                            const stepOut = step.outputs?.out;
                            const hasStepData =
                              stepOut != null && !(Array.isArray(stepOut) && stepOut.length === 0);
                            const isCompare = step.node_type === "compare";
                            return (
                              <div key={step.node_id}>
                                <button
                                  onClick={() => toggleStep(stepKey)}
                                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-bg-muted/50 transition-colors duration-fast"
                                >
                                  <span className="text-fg-subtle w-4 text-right shrink-0">
                                    {i + 1}.
                                  </span>
                                  {isCompare ? (
                                    <GitCompare size={11} className="text-accent-500 shrink-0" />
                                  ) : step.node_type === "search" ? (
                                    <Search size={11} className="text-accent-500 shrink-0" />
                                  ) : null}
                                  <span
                                    className={`font-medium shrink-0 ${
                                      isCompare ? "text-accent-500" : "text-fg-muted"
                                    }`}
                                  >
                                    {step.node_type}
                                  </span>
                                  {isCompare && hasStepData && (
                                    <span className="text-success-500 flex items-center gap-1">
                                      <CheckCircle2 size={10} /> Matched
                                    </span>
                                  )}
                                  {isCompare && !hasStepData && (
                                    <span className="text-danger-500">No data</span>
                                  )}
                                  {!isCompare && step.node_type === "search" && (
                                    <span className="text-fg-subtle">
                                      {Array.isArray(stepOut) ? stepOut.length : 0} results
                                    </span>
                                  )}
                                  <span className="ml-auto text-fg-subtle">
                                    {isStepExpanded ? <EyeOff size={11} /> : <Eye size={11} />}
                                  </span>
                                </button>
                                {isStepExpanded && (
                                  <div className="px-6 pb-2 space-y-1.5">
                                    {Object.keys(step.inputs || {}).length > 0 && (
                                      <div>
                                        <div className="text-xs font-medium text-fg-subtle uppercase tracking-wider">
                                          Inputs
                                        </div>
                                        <pre className="text-xs text-fg-muted bg-bg-muted p-1.5 rounded-sm overflow-x-auto max-h-32 overflow-y-auto">
                                          {formatStepValue(step.inputs)}
                                        </pre>
                                      </div>
                                    )}
                                    {step.outputs != null &&
                                      Object.keys(step.outputs).length > 0 && (
                                        <div>
                                          <div className="text-xs font-medium text-fg-subtle uppercase tracking-wider">
                                            Outputs
                                          </div>
                                          <pre className="text-xs text-fg-muted bg-bg-muted p-1.5 rounded-sm overflow-x-auto max-h-32 overflow-y-auto">
                                            {formatStepValue(step.outputs)}
                                          </pre>
                                        </div>
                                      )}
                                    {step.config != null && Object.keys(step.config).length > 0 && (
                                      <div>
                                        <div className="text-xs font-medium text-fg-subtle uppercase tracking-wider">
                                          Config
                                        </div>
                                        <pre className="text-xs text-fg-muted bg-bg-muted p-1.5 rounded-sm overflow-x-auto max-h-32 overflow-y-auto">
                                          {formatStepValue(step.config)}
                                        </pre>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!hasResults && !error && (
          <div className="mt-2 text-center py-4">
            <p className="text-xs text-fg-subtle">
              Enter a track title{ruleId ? "" : " to test all active rules"} and press{" "}
              <kbd className="px-1 py-0.5 bg-bg-muted rounded-sm text-fg-muted font-mono">
                Enter
              </kbd>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function formatStepValue(val: unknown): string {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val.length > 200 ? `${val.slice(0, 200)}...` : val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (Array.isArray(val)) {
    if (val.length === 0) return "[]";
    if (val.length > 3) {
      return `${JSON.stringify(val.slice(0, 3), null, 2)}\n… and ${val.length - 3} more`;
    }
    return JSON.stringify(val, null, 2);
  }
  const str = JSON.stringify(val, null, 2);
  return str.length > 500 ? `${str.slice(0, 500)}\n… (truncated)` : str;
}
