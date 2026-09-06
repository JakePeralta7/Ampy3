import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { settingsAPI } from "../api/settings";
import { SOURCE_YOUTUBE_MUSIC } from "../lib/constants";
import { getErrorMessage } from "../lib/utils";

export function useSources() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [authSet, setAuthSet] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"pass" | "fail" | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await settingsAPI.getSettings();
      const flat: Record<string, string> = {
        ytmusic_auth: "",
        yt_dlp_timeout: String(data.yt_dlp_timeout),
      };
      setValues(flat);
      setOriginal(flat);
      setAuthSet(data.ytmusic_auth_set);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load source settings"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const hasChanges =
    (values.yt_dlp_timeout ?? "") !== (original.yt_dlp_timeout ?? "") ||
    Boolean(values.ytmusic_auth?.trim());

  const setField = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
    if (key === "ytmusic_auth") setTestResult(null);
  }, []);

  const testAuth = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await settingsAPI.testSource(SOURCE_YOUTUBE_MUSIC, values.ytmusic_auth ?? "");
      setTestResult(result.ok ? "pass" : "fail");
      if (!result.ok) toast.error(result.error ?? "Connection failed");
    } catch (err) {
      setTestResult("fail");
      toast.error(getErrorMessage(err, "Test failed"));
    } finally {
      setTesting(false);
    }
  }, [values.ytmusic_auth]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      if ((values.ytmusic_auth ?? "").trim()) payload.ytmusic_auth = values.ytmusic_auth;
      if ((values.yt_dlp_timeout ?? "") !== (original.yt_dlp_timeout ?? "")) {
        payload.yt_dlp_timeout = Number(values.yt_dlp_timeout);
      }
      const result = await settingsAPI.updateSettings(payload);
      const flat: Record<string, string> = {
        ytmusic_auth: "",
        yt_dlp_timeout: String(result.yt_dlp_timeout),
      };
      setValues(flat);
      setOriginal(flat);
      setAuthSet(result.ytmusic_auth_set);
      setTestResult(null);
      toast.success("YouTube Music settings saved");
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to save source settings"));
    } finally {
      setSaving(false);
    }
  }, [values, original]);

  return {
    values,
    original,
    authSet,
    loading,
    saving,
    testing,
    testResult,
    hasChanges,
    setField,
    testAuth,
    save,
  };
}
