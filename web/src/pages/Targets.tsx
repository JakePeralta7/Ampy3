import { CheckCircle, Plug, Save, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { type AppSettings, getSettings, testTarget, updateSettings } from "../api/settings";
import jellyfinSvg from "../assets/jellyfin.svg";
import plexSvg from "../assets/plex.svg";
import { PageLayout } from "../components/Layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TARGET_JELLYFIN, TARGET_PLEX } from "../lib/constants";
import { INPUT_STYLES } from "../lib/styles";
import { getErrorMessage } from "../lib/utils";

function PlexIcon({ size = 20 }: { size?: number }) {
  return <img src={plexSvg} alt="Plex" width={size} height={size} className="shrink-0" />;
}

function JellyfinIcon({ size = 20 }: { size?: number }) {
  return <img src={jellyfinSvg} alt="Jellyfin" width={size} height={size} className="shrink-0" />;
}

function SettingField({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  secretSet,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "password";
  placeholder?: string;
  secretSet?: boolean;
}) {
  const [focused, setFocused] = useState(false);
  const masked = secretSet && !value && !focused;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-fg-muted">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={masked ? "••••••••••••••••••••" : value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className={`${INPUT_STYLES} ${masked ? "text-fg-subtle" : ""}`}
      />
    </div>
  );
}

function StatusBadge({ configured }: { configured: boolean }) {
  return configured ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success-500 bg-success-50 rounded-full px-2 py-0.5">
      <CheckCircle size={12} />
      Configured
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-fg-subtle bg-bg-muted rounded-full px-2 py-0.5">
      Not configured
    </span>
  );
}

function TargetSection({
  title,
  icon,
  targetId,
  configured,
  fields,
  values,
  onFieldChange,
  onTest,
  onSubmit,
  testing,
  testingResult,
  saving,
  hasChanges,
}: {
  title: string;
  icon: React.ReactNode;
  targetId: string;
  configured: boolean;
  fields: {
    key: string;
    label: string;
    type?: "text" | "password";
    placeholder?: string;
    secretSet?: boolean;
  }[];
  values: Record<string, string>;
  onFieldChange: (key: string, val: string) => void;
  onTest: () => void;
  onSubmit: () => void;
  testing: boolean;
  testingResult: "pass" | "fail" | null;
  saving: boolean;
  hasChanges: boolean;
}) {
  const submitDisabled = testingResult !== "pass" || saving || !hasChanges;

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-lg font-semibold text-fg">
          {icon}
          {title}
        </div>
        <StatusBadge configured={configured} />
      </div>

      {fields.map((field) => (
        <SettingField
          key={field.key}
          id={`${targetId}-${field.key}`}
          label={field.label}
          type={field.type}
          value={values[field.key] ?? ""}
          onChange={(v) => onFieldChange(field.key, v)}
          placeholder={field.placeholder}
          secretSet={field.secretSet}
        />
      ))}

      <div className="flex items-center gap-3 pt-2">
        <Button variant="secondary" onClick={onTest} disabled={testing} icon={<Plug size={14} />}>
          {testing ? "Testing..." : "Test"}
        </Button>

        {testingResult === "pass" && (
          <span className="text-sm text-success-500 flex items-center gap-1">
            <CheckCircle size={14} /> Connection successful
          </span>
        )}
        {testingResult === "fail" && (
          <span className="text-sm text-danger-500 flex items-center gap-1">
            <XCircle size={14} /> Connection failed
          </span>
        )}

        <div className="flex-1" />

        <Button onClick={onSubmit} disabled={submitDisabled} icon={<Save size={14} />}>
          {saving ? "Saving..." : "Submit"}
        </Button>
      </div>
    </Card>
  );
}

export function TargetsPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Per-target test state
  const [plexTesting, setPlexTesting] = useState(false);
  const [plexTestResult, setPlexTestResult] = useState<"pass" | "fail" | null>(null);
  const [jellyfinTesting, setJellyfinTesting] = useState(false);
  const [jellyfinTestResult, setJellyfinTestResult] = useState<"pass" | "fail" | null>(null);

  // Configured status from API
  const [plexConfigured, setPlexConfigured] = useState(false);
  const [jellyfinConfigured, setJellyfinConfigured] = useState(false);

  const setField = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
    // Reset test result when fields change
    if (key.startsWith("plex_")) setPlexTestResult(null);
    if (key.startsWith("jellyfin_")) setJellyfinTestResult(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSettings()
      .then((data: AppSettings) => {
        if (cancelled) return;
        const flat: Record<string, string> = {
          plex_host: data.plex_host,
          plex_token: "",
          jellyfin_server_url: data.jellyfin_server_url,
          jellyfin_api_key: "",
          jellyfin_user_id: data.jellyfin_user_id,
        };
        setValues(flat);
        setOriginal(flat);
        setPlexConfigured(data.plex_token_set);
        setJellyfinConfigured(data.jellyfin_api_key_set);
      })
      .catch((err) => {
        if (!cancelled) toast.error(getErrorMessage(err, "Failed to load settings"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTest = async (targetId: string) => {
    const setTesting = targetId === TARGET_PLEX ? setPlexTesting : setJellyfinTesting;
    const setResult = targetId === TARGET_PLEX ? setPlexTestResult : setJellyfinTestResult;

    setTesting(true);
    setResult(null);
    try {
      const config: Record<string, string> = {};
      if (targetId === TARGET_PLEX) {
        config.plex_host = values.plex_host ?? "";
        config.plex_token = values.plex_token ?? "";
      } else {
        config.jellyfin_server_url = values.jellyfin_server_url ?? "";
        config.jellyfin_api_key = values.jellyfin_api_key ?? "";
        config.jellyfin_user_id = values.jellyfin_user_id ?? "";
      }
      const result = await testTarget(targetId, config);
      setResult(result.ok ? "pass" : "fail");
      if (!result.ok) {
        toast.error(result.error ?? "Connection failed");
      }
    } catch (err) {
      setResult("fail");
      toast.error(getErrorMessage(err, "Test failed"));
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async (targetId: string) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      if (targetId === TARGET_PLEX) {
        if (values.plex_host !== original.plex_host) payload.plex_host = values.plex_host;
        if (values.plex_token) payload.plex_token = values.plex_token;
      } else {
        if (values.jellyfin_server_url !== original.jellyfin_server_url)
          payload.jellyfin_server_url = values.jellyfin_server_url;
        if (values.jellyfin_api_key) payload.jellyfin_api_key = values.jellyfin_api_key;
        if (values.jellyfin_user_id !== original.jellyfin_user_id)
          payload.jellyfin_user_id = values.jellyfin_user_id;
      }
      const result = await updateSettings(payload);

      // Update state with new values
      setValues((prev) => {
        const next = { ...prev };
        if (targetId === TARGET_PLEX) {
          next.plex_host = result.plex_host;
          next.plex_token = "";
          setPlexConfigured(result.plex_token_set);
        } else {
          next.jellyfin_server_url = result.jellyfin_server_url;
          next.jellyfin_api_key = "";
          next.jellyfin_user_id = result.jellyfin_user_id;
          setJellyfinConfigured(result.jellyfin_api_key_set);
        }
        return next;
      });
      setOriginal((prev) => {
        const next = { ...prev };
        if (targetId === TARGET_PLEX) {
          next.plex_host = result.plex_host;
          next.plex_token = "";
        } else {
          next.jellyfin_server_url = result.jellyfin_server_url;
          next.jellyfin_api_key = "";
          next.jellyfin_user_id = result.jellyfin_user_id;
        }
        return next;
      });

      // Reset test state after successful save
      if (targetId === TARGET_PLEX) {
        setPlexTestResult(null);
      } else {
        setJellyfinTestResult(null);
      }

      toast.success(`${targetId} settings saved`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save settings"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-bg-muted rounded" />
          <div className="h-64 bg-bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <PageLayout title="" maxWidth="md">
      <div className="space-y-8">
        <TargetSection
          title="Plex Media Server"
          icon={<PlexIcon />}
          targetId={TARGET_PLEX}
          configured={plexConfigured}
          fields={[
            { key: "plex_host", label: "Host URL", placeholder: "http://plex.lan:32400" },
            {
              key: "plex_token",
              label: "Token",
              type: "password",
              placeholder: "Plex API token",
              secretSet: plexConfigured,
            },
          ]}
          values={values}
          onFieldChange={setField}
          onTest={() => handleTest(TARGET_PLEX)}
          onSubmit={() => handleSubmit(TARGET_PLEX)}
          testing={plexTesting}
          testingResult={plexTestResult}
          saving={saving}
          hasChanges={!!(values.plex_host !== original.plex_host || values.plex_token)}
        />

        <TargetSection
          title="Jellyfin"
          icon={<JellyfinIcon />}
          targetId={TARGET_JELLYFIN}
          configured={jellyfinConfigured}
          fields={[
            {
              key: "jellyfin_server_url",
              label: "Server URL",
              placeholder: "http://jellyfin.lan:8096",
            },
            {
              key: "jellyfin_api_key",
              label: "API Key",
              type: "password",
              placeholder: "Jellyfin API key",
              secretSet: jellyfinConfigured,
            },
            {
              key: "jellyfin_user_id",
              label: "User ID",
              placeholder: "Jellyfin user ID",
            },
          ]}
          values={values}
          onFieldChange={setField}
          onTest={() => handleTest(TARGET_JELLYFIN)}
          onSubmit={() => handleSubmit(TARGET_JELLYFIN)}
          testing={jellyfinTesting}
          testingResult={jellyfinTestResult}
          saving={saving}
          hasChanges={
            !!(
              values.jellyfin_server_url !== original.jellyfin_server_url ||
              values.jellyfin_api_key ||
              values.jellyfin_user_id !== original.jellyfin_user_id
            )
          }
        />
      </div>
    </PageLayout>
  );
}
