import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { settingsAPI } from "../api/settings";
import { getErrorMessage } from "../lib/utils";

export type UseNetworkSettingsReturn = {
  values: {
    behind_proxy: boolean;
    trusted_proxies: string[];
  };
  original: {
    behind_proxy: boolean;
    trusted_proxies: string[];
  };
  loading: boolean;
  saving: boolean;
  hasChanges: boolean;
  setField: {
    (key: "behind_proxy", val: boolean): void;
    (key: "trusted_proxies", val: string[]): void;
  };
  save: () => Promise<void>;
  lastUpdated: Date | null;
};

export function useNetworkSettings(): UseNetworkSettingsReturn {
  const [values, setValues] = useState<{ behind_proxy: boolean; trusted_proxies: string[] }>({
    behind_proxy: false,
    trusted_proxies: [],
  });
  const [original, setOriginal] = useState<{ behind_proxy: boolean; trusted_proxies: string[] }>({
    behind_proxy: false,
    trusted_proxies: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const settings = await settingsAPI.getSettings();
        const data = {
          behind_proxy: settings.behind_proxy ?? false,
          trusted_proxies: settings.trusted_proxies ?? [],
        };
        setValues(data);
        setOriginal(data);
        setLastUpdated(new Date());
      } catch (error) {
        toast.error(`Failed to load network settings: ${getErrorMessage(error)}`);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  const setField = useCallback(
    (key: "behind_proxy" | "trusted_proxies", val: boolean | string[]) => {
      setValues((prev) => ({ ...prev, [key]: val }));
    },
    [],
  );

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const settings = await settingsAPI.updateSettings(values);
      setOriginal({
        behind_proxy: settings.behind_proxy ?? false,
        trusted_proxies: settings.trusted_proxies ?? [],
      });
      setValues({
        behind_proxy: settings.behind_proxy ?? false,
        trusted_proxies: settings.trusted_proxies ?? [],
      });
      toast.success("Network settings saved. Restart required for changes to take effect.");
      setLastUpdated(new Date());
    } catch (error) {
      toast.error(`Failed to save network settings: ${getErrorMessage(error)}`);
    } finally {
      setSaving(false);
    }
  }, [values]);

  const hasChanges =
    values.behind_proxy !== original.behind_proxy ||
    JSON.stringify(values.trusted_proxies) !== JSON.stringify(original.trusted_proxies);

  return {
    values,
    original,
    loading,
    saving,
    hasChanges,
    setField,
    save,
    lastUpdated,
  };
}
