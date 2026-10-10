import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { settingsAPI } from "../api/settings";
import { SOURCE_YOUTUBE_MUSIC } from "../lib/constants";
import { POLLING_CONFIG } from "../lib/pollingConfig";
import { getErrorMessage } from "../lib/utils";

export interface UseSourcesReturn {
  values: Record<string, string>;
  original: Record<string, string>;
  authSet: boolean;
  loading: boolean;
  saving: boolean;
  testing: boolean;
  testResult: "pass" | "fail" | null;
  hasChanges: boolean;
  setField: (key: string, val: string) => void;
  testAuth: () => Promise<void>;
  save: () => Promise<void>;
  lastUpdated: Date | null;
}

export function useSources(): UseSourcesReturn {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [authSet, setAuthSet] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"pass" | "fail" | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchSettings = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      const data = await settingsAPI.getSettings();
      if (isMountedRef.current) {
        const flat: Record<string, string> = {
          ytmusic_auth: "",
          yt_dlp_timeout: String(data.yt_dlp_timeout),
        };
        setOriginal(flat);
        setAuthSet(data.ytmusic_auth_set);
        setLastUpdated(new Date());
        // Only update values if no unsaved changes
        if (!values.ytmusic_auth && (values.yt_dlp_timeout ?? "") === (original.yt_dlp_timeout ?? "")) {
          setValues(flat);
        }
      }
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load source settings"));
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [values, original]);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchSettings();

    // Set up polling
    pollIntervalRef.current = setInterval(() => {
      fetchSettings();
    }, POLLING_CONFIG.DEFAULT_INTERVAL);

    return () => {
      isMountedRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
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
      setLastUpdated(new Date());
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
    lastUpdated,
  };
}
