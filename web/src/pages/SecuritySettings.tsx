import { AlertCircle, CheckCircle2, Loader, Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { settingsAPI, type AppSettings, type SettingsUpdate } from "../api/settings";
import { Button } from "../components/ui/Button";
import { getErrorMessage } from "../lib/utils";

export function SecuritySettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    require_auth: true,
    app_url: "",
    plex_client_id: "",
  });

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const data = await settingsAPI.getSettings();
        setSettings(data);
        setFormData({
          require_auth: data.require_auth,
          app_url: data.app_url,
          plex_client_id: data.plex_client_id,
        });
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, []);

  const handleInputChange = (
    field: keyof typeof formData,
    value: string | boolean
  ) => {
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
        require_auth: formData.require_auth,
        app_url: formData.app_url,
        plex_client_id: formData.plex_client_id,
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
          <div className="flex items-center gap-3">
            <Lock className="h-8 w-8 text-accent-600" />
            <div>
              <h2 className="text-2xl font-bold text-fg">Security</h2>
              <p className="text-fg-muted mt-1">Authentication and encryption settings</p>
            </div>
          </div>
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

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Secret Key Status */}
          <div className="bg-bg-surface rounded-lg border border-border p-6">
            <h3 className="font-semibold text-fg mb-4">Secret Key</h3>
            <div className="flex items-center gap-3">
              {settings?.secret_key_set ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <span className="text-sm text-fg-muted">
                    Secret key is configured and encrypted at rest
                  </span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-5 w-5 text-yellow-600" />
                  <span className="text-sm text-fg-muted">
                    Secret key is not configured
                  </span>
                </>
              )}
            </div>
            <p className="text-xs text-fg-muted mt-3">
              The secret key is used to encrypt sensitive credentials at rest and sign session cookies.
              It cannot be viewed or changed via this interface.
            </p>
          </div>

          {/* Require Auth */}
          <div className="bg-bg-surface rounded-lg border border-border p-6">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-fg">
                Require Authentication
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.require_auth}
                  onChange={(e) => handleInputChange("require_auth", e.target.checked)}
                  className="rounded border-border cursor-pointer w-4 h-4"
                  disabled={saving}
                />
                <span className={formData.require_auth ? "text-green-600 text-sm font-medium" : "text-fg-muted text-sm"}>
                  {formData.require_auth ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>
            <p className="text-xs text-fg-muted">
              When enabled, users must authenticate via Plex SSO to access the application
            </p>
            {!formData.require_auth && (
              <p className="text-xs text-yellow-600 mt-3 font-medium">
                ⚠️ Authentication is disabled. The application is publicly accessible without login.
              </p>
            )}
          </div>

          {/* App URL */}
          <div className="bg-bg-surface rounded-lg border border-border p-6">
            <label className="block text-sm font-medium text-fg mb-2">
              App URL
            </label>
            <input
              type="url"
              value={formData.app_url}
              onChange={(e) => handleInputChange("app_url", e.target.value)}
              placeholder="https://ampy3.example.com"
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-2">
              Public URL where this application is accessible
            </p>
          </div>

          {/* Plex Client ID */}
          <div className="bg-bg-surface rounded-lg border border-border p-6">
            <label className="block text-sm font-medium text-fg mb-2">
              Plex Client ID
            </label>
            <input
              type="text"
              value={formData.plex_client_id}
              onChange={(e) => handleInputChange("plex_client_id", e.target.value)}
              placeholder="ampy3-client"
              className="w-full px-3 py-2 border border-border rounded-md bg-bg text-fg text-sm"
              disabled={saving}
            />
            <p className="text-xs text-fg-muted mt-2">
              Unique identifier for this Plex application
            </p>
          </div>

          <div className="flex gap-3 pt-4">
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
