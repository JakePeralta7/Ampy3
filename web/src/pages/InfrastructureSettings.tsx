import { AlertCircle, CheckCircle2, Loader } from "lucide-react";
import { useEffect, useState } from "react";
import { type AppSettings, type SettingsUpdate, settingsAPI } from "../api/settings";
import { Button } from "../components/ui/Button";
import { getErrorMessage } from "../lib/utils";

export function InfrastructureSettingsPage() {
  const [_settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    celery_broker_url: "",
    celery_worker_concurrency: 1,
    celery_log_level: "info",
    log_format: "json",
    source_playlist_cache_ttl_seconds: 300,
    explore_cache_ttl_seconds: 900,
    yt_dlp_timeout: 60,
    session_ttl_hours: 24,
  });

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await settingsAPI.getSettings();
        setSettings(data);
        setFormData({
          celery_broker_url: data.celery_broker_url,
          celery_worker_concurrency: data.celery_worker_concurrency,
          celery_log_level: data.celery_log_level,
          log_format: data.log_format,
          source_playlist_cache_ttl_seconds: data.source_playlist_cache_ttl_seconds,
          explore_cache_ttl_seconds: data.explore_cache_ttl_seconds,
          yt_dlp_timeout: data.yt_dlp_timeout,
          session_ttl_hours: data.session_ttl_hours,
        });
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, []);

  const handleInputChange = (field: keyof typeof formData, value: string | number) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setSaving(true);

    try {
      const updateData: SettingsUpdate = {
        celery_broker_url: formData.celery_broker_url,
        celery_worker_concurrency: formData.celery_worker_concurrency,
        celery_log_level: formData.celery_log_level,
        log_format: formData.log_format,
        source_playlist_cache_ttl_seconds: formData.source_playlist_cache_ttl_seconds,
        explore_cache_ttl_seconds: formData.explore_cache_ttl_seconds,
        yt_dlp_timeout: formData.yt_dlp_timeout,
        session_ttl_hours: formData.session_ttl_hours,
      };

      await settingsAPI.updateSettings(updateData);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader className="h-6 w-6 animate-spin text-fg-muted" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-3xl mx-auto px-8 py-6">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-fg">Infrastructure</h2>
          <p className="text-fg-muted mt-1">Configure Celery workers, caching, and logging</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex gap-3">
            <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
            <p className="text-sm text-green-700">Settings saved successfully</p>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="bg-bg-surface rounded-lg border border-border p-6 space-y-6"
        >
          {/* Celery Broker URL */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Celery Broker URL</label>
            <input
              type="text"
              value={formData.celery_broker_url}
              onChange={(e) => handleInputChange("celery_broker_url", e.target.value)}
              placeholder="redis://valkey:6379/0"
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">
              Redis/Valkey connection string for Celery tasks
            </p>
          </div>

          {/* Worker Concurrency */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Worker Concurrency</label>
            <input
              type="number"
              min="1"
              max="100"
              value={formData.celery_worker_concurrency}
              onChange={(e) =>
                handleInputChange("celery_worker_concurrency", parseInt(e.target.value, 10))
              }
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">Number of concurrent workers</p>
          </div>

          {/* Log Level */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Celery Log Level</label>
            <select
              value={formData.celery_log_level}
              onChange={(e) => handleInputChange("celery_log_level", e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            >
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>
            <p className="text-xs text-fg-muted mt-1">Minimum log level for Celery workers</p>
          </div>

          {/* Log Format */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Log Format</label>
            <select
              value={formData.log_format}
              onChange={(e) => handleInputChange("log_format", e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            >
              <option value="json">JSON (structured)</option>
              <option value="console">Console (human-readable)</option>
            </select>
            <p className="text-xs text-fg-muted mt-1">Output format for application logs</p>
          </div>

          {/* Source Playlist Cache TTL */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">
              Source Playlist Cache TTL
            </label>
            <input
              type="number"
              min="1"
              value={formData.source_playlist_cache_ttl_seconds}
              onChange={(e) =>
                handleInputChange("source_playlist_cache_ttl_seconds", parseInt(e.target.value, 10))
              }
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">
              Cache duration for source playlists in seconds
            </p>
          </div>

          {/* Explore Cache TTL */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Explore Cache TTL</label>
            <input
              type="number"
              min="1"
              value={formData.explore_cache_ttl_seconds}
              onChange={(e) =>
                handleInputChange("explore_cache_ttl_seconds", parseInt(e.target.value, 10))
              }
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">
              Cache duration for Explore content in seconds
            </p>
          </div>

          {/* YT-DLP Timeout */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">YT-DLP Timeout</label>
            <input
              type="number"
              min="1"
              value={formData.yt_dlp_timeout}
              onChange={(e) => handleInputChange("yt_dlp_timeout", parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">
              Maximum time (in seconds) for YouTube metadata operations
            </p>
          </div>

          {/* Session TTL */}
          <div>
            <label className="block text-sm font-medium text-fg mb-2">Session TTL</label>
            <input
              type="number"
              min="1"
              value={formData.session_ttl_hours}
              onChange={(e) => handleInputChange("session_ttl_hours", parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-1">User session timeout in hours</p>
          </div>

          <div className="flex gap-3 pt-4 border-t border-border">
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
