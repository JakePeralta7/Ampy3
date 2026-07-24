import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { apiGet, apiPost } from "../api/client";
import { Button } from "../components/ui/Button";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { INPUT_STYLES } from "../lib/styles";

interface PlexServer {
  name: string;
  host: string;
  port: number;
  protocol: string;
  machine_identifier: string;
  local: boolean;
}

export function SetupPage() {
  const navigate = useNavigate();
  const [servers, setServers] = useState<PlexServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [needsToken, setNeedsToken] = useState(false);
  const [customUrl, setCustomUrl] = useState("");
  const [plexToken, setPlexToken] = useState("");
  const [saving, setSaving] = useState(false);

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<PlexServer | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiGet<{ servers: PlexServer[] }>("/plex/servers")
      .then((data) => {
        setServers(data.servers);
        if (data.servers.length === 0) setNeedsToken(true);
      })
      .catch(() => setNeedsToken(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    if (!query) return servers;
    const q = query.toLowerCase();
    return servers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.host.toLowerCase().includes(q) ||
        `${s.protocol}://${s.host}:${s.port}`.toLowerCase().includes(q),
    );
  }, [servers, query]);

  const handleSelectServer = async (server: PlexServer) => {
    setSelected(server);
    setQuery(server.name);
    setOpen(false);
    const url = `${server.protocol}://${server.host}:${server.port}`;
    setSaving(true);
    try {
      await apiPost("/plex/server", { server_url: url });
      toast.success(`Connected to "${server.name}"`);
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setSaving(false);
    }
  };

  const handleCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customUrl.trim()) return;
    setSaving(true);
    try {
      const body: { server_url: string; plex_token?: string } = {
        server_url: customUrl.trim(),
      };
      if (plexToken.trim()) body.plex_token = plexToken.trim();
      await apiPost("/plex/server", body);
      toast.success("Plex server connected");
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingSpinner fullPage />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-app">
      <div className="w-full max-w-lg mx-auto px-4">
        <div className="bg-bg-surface rounded-xl border border-border shadow-sm p-8">
          <div className="mb-6">
            <div className="h-14 w-14 rounded-xl bg-accent-500 text-accent-fg flex items-center justify-center font-bold text-xl mx-auto">
              A
            </div>
          </div>

          <h1 className="text-xl font-semibold text-fg mb-1 text-center">Connect to Plex</h1>
          <p className="text-sm text-fg-muted mb-8 text-center">
            {needsToken
              ? "Enter your Plex token and server URL to get started."
              : "Select your Plex Media Server to get started."}
          </p>

          {needsToken ? (
            <form onSubmit={handleCustomSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-fg-muted mb-1.5">Server URL</label>
                <input
                  type="url"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="http://192.168.1.100:32400"
                  className={INPUT_STYLES}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-fg-muted mb-1.5">Plex Token</label>
                <input
                  type="text"
                  value={plexToken}
                  onChange={(e) => setPlexToken(e.target.value)}
                  placeholder="Find it at plex.tv → Account → Authorized Devices"
                  className={INPUT_STYLES}
                  required
                />
                <p className="mt-1.5 text-xs text-fg-subtle">
                  Settings → Authorized Devices → copy the token string
                </p>
              </div>
              <Button type="submit" loading={saving} className="w-full">
                Connect
              </Button>
            </form>
          ) : (
            <>
              {servers.length > 0 && (
                <div className="mb-6" ref={dropdownRef}>
                  <label className="block text-xs font-medium text-fg-muted mb-1.5">
                    Plex Server
                  </label>
                  <div className="relative">
                    <input
                      ref={inputRef}
                      type="text"
                      value={query}
                      onChange={(e) => {
                        setQuery(e.target.value);
                        setSelected(null);
                        setOpen(true);
                      }}
                      onFocus={() => setOpen(true)}
                      placeholder="Search servers..."
                      disabled={saving}
                      className={INPUT_STYLES}
                    />
                    {open && filtered.length > 0 && (
                      <div className="absolute z-10 mt-1 w-full max-h-60 overflow-auto rounded-md border border-border bg-bg-surface shadow-lg">
                        {filtered.map((server) => (
                          <button
                            key={server.machine_identifier}
                            type="button"
                            disabled={saving}
                            onClick={() => handleSelectServer(server)}
                            className={`w-full flex items-center justify-between px-3 py-2 text-left text-sm hover:bg-bg-muted transition-colors disabled:opacity-50 cursor-pointer ${
                              selected?.machine_identifier === server.machine_identifier
                                ? "bg-accent-500/10"
                                : ""
                            }`}
                          >
                            <span className="font-medium text-fg">{server.name}</span>
                            <span className="text-xs text-fg-muted">
                              {server.protocol}://{server.host}:{server.port}
                              {server.local && <span className="ml-1 text-accent-500">local</span>}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                    {open && query && filtered.length === 0 && (
                      <div className="absolute z-10 mt-1 w-full rounded-md border border-border bg-bg-surface shadow-lg px-3 py-2 text-sm text-fg-muted">
                        No servers match &quot;{query}&quot;
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="border-t border-border pt-6">
                <p className="text-xs text-fg-muted mb-3 text-center">
                  Or enter your server URL manually
                </p>
                <form onSubmit={handleCustomSubmit} className="flex gap-2">
                  <input
                    type="url"
                    value={customUrl}
                    onChange={(e) => setCustomUrl(e.target.value)}
                    placeholder="http://192.168.1.100:32400"
                    className={`flex-1 ${INPUT_STYLES}`}
                    required
                  />
                  <Button type="submit" loading={saving} size="sm">
                    Connect
                  </Button>
                </form>
              </div>
            </>
          )}
        </div>

        <p className="text-center text-xs text-fg-subtle mt-4">
          Only the server owner can access this application.
        </p>
      </div>
    </div>
  );
}
