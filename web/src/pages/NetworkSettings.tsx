import { AlertCircle, Save } from "lucide-react";
import { PageLayout } from "../components/layout/PageLayout";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { useNetworkSettings } from "../hooks/useNetworkSettings";

export function NetworkSettingsPage() {
  const { values, loading, saving, hasChanges, setField, save } = useNetworkSettings();

  if (loading) {
    return (
      <PageLayout title="Network" subtitle="Reverse proxy configuration">
        <div className="space-y-4 max-w-2xl">
          <Skeleton className="h-12 w-64" />
          <Skeleton className="h-32" />
          <Skeleton className="h-24" />
          <Skeleton className="h-10 w-24" />
        </div>
      </PageLayout>
    );
  }

  const trustedProxiesText = values.trusted_proxies.join("\n");

  return (
    <PageLayout title="Network" subtitle="Reverse proxy configuration">
      <div className="max-w-2xl space-y-6">
        <Card className="p-6 space-y-4">
          <h2 className="text-xl font-semibold text-fg">Reverse Proxy Configuration</h2>

          <Alert variant="warning">
            <div className="flex gap-3">
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
              <div>
                <div className="font-medium">Restart required</div>
                <p className="text-sm">
                  Changes to proxy settings require restarting the container to take effect.
                </p>
              </div>
            </div>
          </Alert>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={values.behind_proxy}
                  onChange={(e) => setField("behind_proxy", e.target.checked)}
                  className="w-4 h-4 rounded border-input border bg-bg-base cursor-pointer"
                />
                <span className="text-sm font-medium text-fg">
                  Behind a reverse proxy (nginx, Traefik, Cloudflare, etc.)
                </span>
              </label>
              <p className="text-xs text-fg-muted ml-7">
                Enable when Ampy3 runs behind a reverse proxy. Allows the app to read
                X-Forwarded-For headers to identify the real client IP for rate limiting. Only trust
                this header when the request originates from a trusted proxy IP.
              </p>
            </div>

            {values.behind_proxy && (
              <div className="space-y-2 p-4 bg-bg-muted rounded border border-border">
                <label htmlFor="trusted-proxies" className="block text-sm font-medium text-fg">
                  Trusted proxy IP ranges (CIDR)
                </label>
                <textarea
                  id="trusted-proxies"
                  value={trustedProxiesText}
                  onChange={(e) =>
                    setField(
                      "trusted_proxies",
                      e.target.value
                        .split("\n")
                        .map((line) => line.trim())
                        .filter((line) => line.length > 0),
                    )
                  }
                  placeholder="10.0.0.0/8&#10;192.168.0.0/16&#10;172.17.0.1/32"
                  rows={6}
                  className="w-full px-3 py-2 text-sm bg-bg-base border border-input rounded font-mono"
                />
                <p className="text-xs text-fg-muted">
                  Enter one CIDR range per line. Only requests from these IP ranges will have their
                  X-Forwarded-For headers trusted. Examples: 10.0.0.0/8, 192.168.1.0/24,
                  172.17.0.1/32
                </p>

                {values.behind_proxy && values.trusted_proxies.length === 0 && (
                  <Alert variant="error">
                    <div className="flex gap-3">
                      <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                      <div>
                        <div className="font-medium">Warning: No trusted proxies configured</div>
                        <p className="text-sm">
                          Enabling 'Behind reverse proxy' without configuring trusted IP ranges
                          means the proxy headers will not be trusted, and rate limiting will not
                          work properly for proxied clients.
                        </p>
                      </div>
                    </div>
                  </Alert>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 pt-4">
            <Button
              onClick={save}
              disabled={!hasChanges || saving}
              icon={<Save size={14} />}
              variant={hasChanges ? "primary" : "secondary"}
            >
              {saving ? "Saving..." : "Save settings"}
            </Button>
            {!hasChanges && <span className="text-xs text-fg-muted">No changes to save</span>}
          </div>
        </Card>

        <Card className="p-6 space-y-3">
          <h3 className="text-sm font-semibold text-fg">About reverse proxies</h3>
          <div className="text-xs text-fg-muted space-y-2">
            <p>
              A reverse proxy (nginx, Traefik, Cloudflare) sits in front of Ampy3 and forwards
              requests to it. When properly configured, the proxy adds X-Forwarded-For headers to
              indicate the real client IP.
            </p>
            <p>
              Without proper configuration, all clients appear to come from the proxy's IP, causing
              rate-limit buckets to become useless (one bucket per proxy, not per client).
            </p>
            <p>
              <strong>Security:</strong> Only enable proxy headers if your app is NOT directly
              reachable from the internet. Otherwise, attackers can spoof X-Forwarded-For headers to
              bypass rate limits and security checks.
            </p>
            <p>
              See{" "}
              <a
                href="https://docs.ampy3.dev/getting-started/configuration#reverse-proxy"
                target="_blank"
                rel="noreferrer"
                className="underline text-link-default hover:text-link-hover"
              >
                Reverse proxy documentation
              </a>{" "}
              for setup examples (nginx, Traefik, Cloudflare IPs).
            </p>
          </div>
        </Card>
      </div>
    </PageLayout>
  );
}
