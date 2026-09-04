import { CheckCircle, Loader2, Server, Wifi, WifiOff } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Card } from "../components/ui/Card";
import { usePlexSetup } from "../hooks/useTargets";
import { getErrorMessage } from "../lib/utils";

export function PlexSetupPage() {
  const navigate = useNavigate();
  const { resources, loading, error, configured, setupPlex } = usePlexSetup();
  const [selectedIdx, setSelectedIdx] = useState<{
    serverIdx: number;
    connIdx: number;
  } | null>(null);
  const [saving, setSaving] = useState(false);

  if (configured) {
    return <Navigate to="/" replace />;
  }

  const handleSelect = async () => {
    if (selectedIdx === null) return;
    const server = resources[selectedIdx.serverIdx];
    const conn = server.connections[selectedIdx.connIdx];
    setSaving(true);
    try {
      await setupPlex(conn.uri, server.access_token);
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to configure Plex server"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-app p-4">
      <div className="w-full max-w-lg mx-auto">
        <div className="text-center mb-8">
          <div className="h-14 w-14 rounded-xl bg-accent-500 text-accent-fg flex items-center justify-center font-bold text-xl mx-auto mb-4">
            A
          </div>
          <h1 className="text-xl font-semibold text-fg mb-1">Select Your Plex Server</h1>
        </div>

        {loading && (
          <div className="flex flex-col items-center gap-3 py-12">
            <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
            <p className="text-sm text-fg-muted">Discovering Plex servers...</p>
          </div>
        )}

        {error && !loading && (
          <Card className="p-6 text-center space-y-4">
            <Server className="h-10 w-10 mx-auto text-fg-subtle" />
            <p className="text-sm text-fg-muted">{error}</p>
            <a
              href="/settings/targets"
              className="inline-block text-sm font-medium text-accent-500 hover:text-accent-600 underline underline-offset-2"
            >
              Configure manually in Settings
            </a>
          </Card>
        )}

        {!loading && !error && resources.length > 0 && (
          <div className="space-y-3">
            {resources.map((server, si) => (
              <Card
                key={server.client_identifier}
                variant="bordered"
                className="divide-y divide-border"
              >
                <div className="px-5 py-3">
                  <h3 className="font-semibold text-fg text-sm">{server.name}</h3>
                  {!server.owned && <span className="text-xs text-fg-subtle">Shared server</span>}
                </div>
                {server.connections.map((conn, ci) => {
                  const isSelected = selectedIdx?.serverIdx === si && selectedIdx?.connIdx === ci;
                  return (
                    <button
                      type="button"
                      key={conn.uri}
                      onClick={() => setSelectedIdx({ serverIdx: si, connIdx: ci })}
                      className={`w-full flex items-center gap-3 px-5 py-3 text-left transition-colors duration-fast hover:bg-bg-muted ${
                        isSelected ? "bg-accent-50" : ""
                      }`}
                    >
                      <div
                        className={`shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          isSelected ? "border-accent-500" : "border-border"
                        }`}
                      >
                        {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-accent-500" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-fg truncate">{conn.uri}</p>
                      </div>
                      {conn.local ? (
                        <span className="shrink-0 inline-flex items-center gap-1 text-xs font-medium text-success-500 bg-success-50 rounded-full px-2 py-0.5">
                          <Wifi size={10} />
                          Local
                        </span>
                      ) : (
                        <span className="shrink-0 inline-flex items-center gap-1 text-xs font-medium text-fg-subtle bg-bg-muted rounded-full px-2 py-0.5">
                          <WifiOff size={10} />
                          Remote
                        </span>
                      )}
                    </button>
                  );
                })}
              </Card>
            ))}

            <button
              type="button"
              disabled={selectedIdx === null || saving}
              onClick={handleSelect}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-accent-500 text-accent-fg hover:bg-accent-600 disabled:opacity-50 font-medium text-sm transition-colors duration-fast cursor-pointer disabled:cursor-not-allowed"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="h-4 w-4" />
              )}
              {saving ? "Configuring..." : "Use This Server"}
            </button>

            <p className="text-center">
              <a
                href="/settings/targets"
                className="text-xs text-fg-subtle hover:text-fg underline underline-offset-2"
              >
                Configure manually instead
              </a>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
