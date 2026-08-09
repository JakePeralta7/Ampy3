import { Download, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { type AppSettings, getSettings, updateSettings } from "../api/settings";
import { PageLayout } from "../components/Layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { INPUT_STYLES } from "../lib/styles";
import { getErrorMessage } from "../lib/utils";

function SettingField({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "password" | "number";
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-fg-muted">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={type === "password" ? "password" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={INPUT_STYLES}
        />
      </div>
    </div>
  );
}

function SectionCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2 text-lg font-semibold text-fg">
        {icon}
        {title}
      </div>
      {children}
    </Card>
  );
}

export function ConfigPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const setField = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSettings()
      .then((data: AppSettings) => {
        if (cancelled) return;
        const flat: Record<string, string> = {
          yt_dlp_cookies: data.yt_dlp_cookies,
          yt_dlp_timeout: String(data.yt_dlp_timeout),
        };
        setValues(flat);
        setOriginal(flat);
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

  const hasChanges = Object.keys(values).some((k) => values[k] !== original[k]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      for (const key of Object.keys(values)) {
        if (values[key] !== original[key]) {
          if (key === "yt_dlp_timeout") {
            payload[key] = Number(values[key]);
          } else {
            payload[key] = values[key];
          }
        }
      }
      const result = await updateSettings(payload);
      const flat: Record<string, string> = {
        yt_dlp_cookies: result.yt_dlp_cookies,
        yt_dlp_timeout: String(result.yt_dlp_timeout),
      };
      setValues(flat);
      setOriginal(flat);
      toast.success("Settings saved");
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
    <PageLayout
      title=""
      maxWidth="md"
      actions={
        <Button onClick={handleSave} disabled={!hasChanges || saving} icon={<Save size={16} />}>
          {saving ? "Saving..." : "Save"}
        </Button>
      }
    >
      <div className="space-y-8">
        <SectionCard icon={<Download size={20} className="text-accent-500" />} title="yt-dlp">
          <SettingField
            id="yt_dlp_cookies"
            label="Cookies file path (optional)"
            value={values.yt_dlp_cookies ?? ""}
            onChange={(v) => setField("yt_dlp_cookies", v)}
            placeholder="/cookies/cookies.txt"
          />
          <p className="text-xs text-fg-subtle -mt-2">
            Optional — only needed for age- or region-restricted content. Everything works without
            it.
          </p>
          <SettingField
            id="yt_dlp_timeout"
            label="Timeout (seconds)"
            type="number"
            value={values.yt_dlp_timeout ?? ""}
            onChange={(v) => setField("yt_dlp_timeout", v)}
          />
        </SectionCard>

        {hasChanges && (
          <p className="text-sm text-warning-700 text-center">Changes apply immediately.</p>
        )}
      </div>
    </PageLayout>
  );
}
