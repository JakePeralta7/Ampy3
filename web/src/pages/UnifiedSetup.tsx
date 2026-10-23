import { AlertCircle, CheckCircle, Loader2, Server, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Card } from "../components/ui/Card";
import { usePlexSetup } from "../hooks/useTargets";
import { getErrorMessage } from "../lib/utils";
import { settingsAPI } from "../api/settings";

type SetupStep = "system" | "target" | "complete";

interface SystemConfig {
  secret_key: string;
  require_auth: boolean;
}

export function UnifiedSetupPage() {
  const navigate = useNavigate();
  const { resources, loading: discoveringServers, error: discoveryError } = usePlexSetup();

  const [step, setStep] = useState<SetupStep>("system");
  const [setupComplete, setSetupComplete] = useState(false);
  const [submittingSystem, setSubmittingSystem] = useState(false);
  const [savingTarget, setSavingTarget] = useState(false);

  // System config form state
  const [systemConfig, setSystemConfig] = useState<SystemConfig>({
    secret_key: "",
    require_auth: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Target selection state
  const [selectedTarget, setSelectedTarget] = useState<{
    serverIdx: number;
    connIdx: number;
  } | null>(null);
  const [manualMode, setManualMode] = useState(false);
  const [manualConfig, setManualConfig] = useState({
    plex_host: "",
    plex_token: "",
  });

  // Check if setup is already complete
  useEffect(() => {
    const checkSetupStatus = async () => {
      try {
        const response = await fetch("/api/v1/settings/");
        if (response.status === 200) {
          const data = await response.json();
          if (data.secret_key_set) {
            setSetupComplete(true);
            // Redirect to plex setup or dashboard
            navigate("/", { replace: true });
          }
        }
      } catch {
        // Not set up yet
      }
    };
    checkSetupStatus();
  }, [navigate]);

  if (setupComplete) {
    return <Navigate to="/" replace />;
  }

  const validateSystemConfig = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!systemConfig.secret_key.trim()) {
      newErrors.secret_key = "Secret key is required";
    } else if (systemConfig.secret_key.length < 32) {
      newErrors.secret_key = "Secret key must be at least 32 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSystemConfigSubmit = async () => {
    if (!validateSystemConfig()) {
      return;
    }

    setSubmittingSystem(true);
    try {
      await settingsAPI.setup(systemConfig);
      setStep("target");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save system configuration"));
    } finally {
      setSubmittingSystem(false);
    }
  };

  const handleTargetSetup = async () => {
    if (manualMode) {
      if (!manualConfig.plex_host.trim() || !manualConfig.plex_token.trim()) {
        toast.error("Please enter both Plex host and token");
        return;
      }

      setSavingTarget(true);
      try {
        await settingsAPI.updateSettings({
          plex_host: manualConfig.plex_host,
          plex_token: manualConfig.plex_token,
        });

        toast.success("Plex server configured successfully!");
        setStep("complete");
        setTimeout(() => {
          navigate("/", { replace: true });
        }, 1500);
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to configure Plex server"));
      } finally {
        setSavingTarget(false);
      }
    } else if (selectedTarget !== null) {
      const server = resources[selectedTarget.serverIdx];
      const conn = server.connections[selectedTarget.connIdx];

      setSavingTarget(true);
      try {
        await settingsAPI.setupPlexTarget(conn.uri, server.client_identifier);

        toast.success("Plex server configured successfully!");
        setStep("complete");
        setTimeout(() => {
          navigate("/", { replace: true });
        }, 1500);
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to setup Plex server"));
      } finally {
        setSavingTarget(false);
      }
    } else {
      toast.error("Please select a Plex server");
    }
  };

  const handleSkipTarget = () => {
    // Allow skipping for now, can configure later in Settings
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-app p-4">
      <div className="w-full max-w-lg mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="h-14 w-14 rounded-xl bg-accent-500 text-accent-fg flex items-center justify-center font-bold text-xl mx-auto mb-4">
            A
          </div>
          <h1 className="text-2xl font-semibold text-fg mb-2">Welcome to Ampy3</h1>
          <p className="text-sm text-fg-muted">
            {step === "system" && "Configure your system settings"}
            {step === "target" && "Set up your sync target"}
            {step === "complete" && "Setup complete!"}
          </p>
        </div>

        {/* Progress indicator */}
        <div className="flex gap-2 mb-8 justify-center">
          <div
            className={`h-2 w-8 rounded-full transition-colors ${
              step !== "system" ? "bg-accent-500" : "bg-accent-500"
            }`}
          />
          <div
            className={`h-2 w-8 rounded-full transition-colors ${
              step === "target" || step === "complete" ? "bg-accent-500" : "bg-border"
            }`}
          />
          <div
            className={`h-2 w-8 rounded-full transition-colors ${
              step === "complete" ? "bg-accent-500" : "bg-border"
            }`}
          />
        </div>

        {/* Step 1: System Configuration */}
        {step === "system" && (
          <Card className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-fg mb-2">
                Secret Key <span className="text-error-500">*</span>
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="Min 32 characters (for encryption)"
                  value={systemConfig.secret_key}
                  onChange={(e) => {
                    setSystemConfig({ ...systemConfig, secret_key: e.target.value });
                    if (errors.secret_key) {
                      setErrors({ ...errors, secret_key: "" });
                    }
                  }}
                  className={`flex-1 px-3 py-2 border rounded-lg bg-bg-subtle text-fg placeholder-fg-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent-500 ${
                    errors.secret_key ? "border-error-500" : "border-border"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => {
                    // Generate a 64-character hex string (32 random bytes = 64 hex chars)
                    const randomBytes = new Uint8Array(32);
                    crypto.getRandomValues(randomBytes);
                    const secretKey = Array.from(randomBytes)
                      .map((b) => b.toString(16).padStart(2, "0"))
                      .join("");
                    setSystemConfig({ ...systemConfig, secret_key: secretKey });
                    if (errors.secret_key) {
                      setErrors({ ...errors, secret_key: "" });
                    }
                  }}
                  className="px-3 py-2 rounded-lg bg-bg-muted hover:bg-bg-subtle border border-border font-medium text-sm transition-colors whitespace-nowrap"
                >
                  Generate
                </button>
              </div>
              {errors.secret_key && (
                <p className="text-xs text-error-500 mt-1">{errors.secret_key}</p>
              )}
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="require_auth"
                checked={systemConfig.require_auth}
                onChange={(e) =>
                  setSystemConfig({ ...systemConfig, require_auth: e.target.checked })
                }
                className="rounded border-border cursor-pointer"
              />
              <label htmlFor="require_auth" className="text-sm text-fg cursor-pointer">
                Require authentication (Plex SSO login)
              </label>
            </div>

            <button
              onClick={handleSystemConfigSubmit}
              disabled={submittingSystem}
              className="w-full px-4 py-2 rounded-lg bg-accent-500 text-accent-fg hover:bg-accent-600 disabled:opacity-50 font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {submittingSystem ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Configuring...
                </>
              ) : (
                "Continue to Target Setup"
              )}
            </button>
          </Card>
        )}

        {/* Step 2: Target Configuration */}
        {step === "target" && (
          <div className="space-y-4">
            {!manualMode && (
              <>
                {discoveringServers && (
                  <Card className="p-6 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
                      <p className="text-sm text-fg-muted">Discovering Plex servers...</p>
                    </div>
                  </Card>
                )}

                {discoveryError && !discoveringServers && (
                  <Card className="p-6 text-center space-y-4">
                    <AlertCircle className="h-10 w-10 mx-auto text-warning-500" />
                    <p className="text-sm text-fg-muted">{discoveryError}</p>
                    <p className="text-xs text-fg-subtle">
                      No servers found via auto-discovery. You can configure manually below.
                    </p>
                  </Card>
                )}

                {!discoveringServers && !discoveryError && resources.length > 0 && (
                  <div className="space-y-3">
                    {resources.map((server, si) => (
                      <Card
                        key={server.client_identifier}
                        variant="bordered"
                        className="divide-y divide-border"
                      >
                        <div className="px-5 py-3">
                          <h3 className="font-semibold text-fg text-sm">{server.name}</h3>
                          {!server.owned && (
                            <span className="text-xs text-fg-subtle">Shared server</span>
                          )}
                        </div>
                        {server.connections.map((conn, ci) => {
                          const isSelected =
                            selectedTarget?.serverIdx === si && selectedTarget?.connIdx === ci;
                          return (
                            <button
                              type="button"
                              key={conn.uri}
                              onClick={() => setSelectedTarget({ serverIdx: si, connIdx: ci })}
                              className={`w-full flex items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-bg-muted ${
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
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => setManualMode(true)}
                  className="w-full text-sm text-accent-500 hover:text-accent-600 font-medium underline underline-offset-2"
                >
                  Configure manually instead
                </button>
              </>
            )}

            {manualMode && (
              <Card className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-fg mb-2">
                    Plex Host <span className="text-error-500">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="192.168.1.100:32400"
                    value={manualConfig.plex_host}
                    onChange={(e) =>
                      setManualConfig({ ...manualConfig, plex_host: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-border rounded-lg bg-bg-subtle text-fg placeholder-fg-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-fg mb-2">
                    Plex API Token <span className="text-error-500">*</span>
                  </label>
                  <input
                    type="password"
                    placeholder="Your Plex API token"
                    value={manualConfig.plex_token}
                    onChange={(e) =>
                      setManualConfig({ ...manualConfig, plex_token: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-border rounded-lg bg-bg-subtle text-fg placeholder-fg-muted text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                  />
                  <p className="text-xs text-fg-muted mt-1">
                    Find your token at{" "}
                    <a
                      href="https://www.plex.tv/api/v2/user"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent-500 hover:underline"
                    >
                      plex.tv/api/v2/user
                    </a>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setManualMode(false)}
                  className="text-sm text-fg-muted hover:text-fg underline underline-offset-2"
                >
                  ← Back to auto-discovery
                </button>
              </Card>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleSkipTarget}
                disabled={savingTarget}
                className="flex-1 px-4 py-2 rounded-lg border border-border text-fg hover:bg-bg-muted disabled:opacity-50 font-medium text-sm transition-colors"
              >
                Skip for now
              </button>
              <button
                onClick={handleTargetSetup}
                disabled={savingTarget || (!manualMode && selectedTarget === null)}
                className="flex-1 px-4 py-2 rounded-lg bg-accent-500 text-accent-fg hover:bg-accent-600 disabled:opacity-50 font-medium text-sm transition-colors flex items-center justify-center gap-2"
              >
                {savingTarget ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Configuring...
                  </>
                ) : (
                  "Continue"
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Complete */}
        {step === "complete" && (
          <Card className="p-6 text-center space-y-4">
            <CheckCircle className="h-12 w-12 mx-auto text-success-500" />
            <div>
              <h2 className="text-lg font-semibold text-fg mb-1">Setup Complete!</h2>
              <p className="text-sm text-fg-muted">
                Ampy3 is ready to use. Redirecting to dashboard...
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
