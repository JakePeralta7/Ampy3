import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { settingsAPI } from "../api/settings";
import { getErrorMessage } from "../lib/utils";

export function useSettings() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await settingsAPI.getSettings();
      const flat: Record<string, string> = {
        yt_dlp_cookies: data.yt_dlp_cookies,
        yt_dlp_timeout: String(data.yt_dlp_timeout),
      };
      setValues(flat);
      setOriginal(flat);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load settings"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const hasChanges = Object.keys(values).some((k) => values[k] !== original[k]);

  const save = useCallback(async () => {
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
      const result = await settingsAPI.updateSettings(payload);
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
  }, [values, original]);

  const setField = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  }, []);

  return { values, loading, saving, hasChanges, setField, save };
}
