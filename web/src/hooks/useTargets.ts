import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { type PlexResource, settingsAPI } from "../api/settings";
import { getErrorMessage } from "../lib/utils";

export function useTargets() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [original, setOriginal] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [plexConfigured, setPlexConfigured] = useState(false);
  const [jellyfinConfigured, setJellyfinConfigured] = useState(false);
  const [plexTesting, setPlexTesting] = useState(false);
  const [plexTestResult, setPlexTestResult] = useState<"pass" | "fail" | null>(null);
  const [jellyfinTesting, setJellyfinTesting] = useState(false);
  const [jellyfinTestResult, setJellyfinTestResult] = useState<"pass" | "fail" | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await settingsAPI.getSettings();
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
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to load settings"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const setField = useCallback((key: string, val: string) => {
    setValues((prev) => ({ ...prev, [key]: val }));
    if (key.startsWith("plex_")) setPlexTestResult(null);
    if (key.startsWith("jellyfin_")) setJellyfinTestResult(null);
  }, []);

  const testConnection = useCallback(
    async (targetId: string) => {
      const setTesting = targetId === "Plex" ? setPlexTesting : setJellyfinTesting;
      const setResult = targetId === "Plex" ? setPlexTestResult : setJellyfinTestResult;
      setTesting(true);
      setResult(null);
      try {
        const config: Record<string, string> = {};
        if (targetId === "Plex") {
          config.plex_host = values.plex_host ?? "";
          config.plex_token = values.plex_token ?? "";
        } else {
          config.jellyfin_server_url = values.jellyfin_server_url ?? "";
          config.jellyfin_api_key = values.jellyfin_api_key ?? "";
          config.jellyfin_user_id = values.jellyfin_user_id ?? "";
        }
        const result = await settingsAPI.testTarget(targetId, config);
        setResult(result.ok ? "pass" : "fail");
        if (!result.ok) toast.error(result.error ?? "Connection failed");
      } catch (err) {
        setResult("fail");
        toast.error(getErrorMessage(err, "Test failed"));
      } finally {
        setTesting(false);
      }
    },
    [values],
  );

  const save = useCallback(
    async (targetId: string) => {
      setSaving(true);
      try {
        const payload: Record<string, unknown> = {};
        if (targetId === "Plex") {
          if (values.plex_host !== original.plex_host) payload.plex_host = values.plex_host;
          if (values.plex_token) payload.plex_token = values.plex_token;
        } else {
          if (values.jellyfin_server_url !== original.jellyfin_server_url)
            payload.jellyfin_server_url = values.jellyfin_server_url;
          if (values.jellyfin_api_key) payload.jellyfin_api_key = values.jellyfin_api_key;
          if (values.jellyfin_user_id !== original.jellyfin_user_id)
            payload.jellyfin_user_id = values.jellyfin_user_id;
        }
        const result = await settingsAPI.updateSettings(payload);
        setValues((prev) => {
          const next = { ...prev };
          if (targetId === "Plex") {
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
          if (targetId === "Plex") {
            next.plex_host = result.plex_host;
            next.plex_token = "";
          } else {
            next.jellyfin_server_url = result.jellyfin_server_url;
            next.jellyfin_api_key = "";
            next.jellyfin_user_id = result.jellyfin_user_id;
          }
          return next;
        });
        if (targetId === "Plex") setPlexTestResult(null);
        else setJellyfinTestResult(null);
        toast.success(`${targetId} settings saved`);
      } catch (err) {
        toast.error(getErrorMessage(err, "Failed to save settings"));
      } finally {
        setSaving(false);
      }
    },
    [values, original],
  );

  return {
    values,
    original,
    loading,
    saving,
    plexConfigured,
    jellyfinConfigured,
    plexTesting,
    plexTestResult,
    jellyfinTesting,
    jellyfinTestResult,
    setField,
    testConnection,
    save,
  };
}

export function useConfiguredTargets() {
  const [targets, setTargets] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    settingsAPI
      .getConfiguredTargets()
      .then(setTargets)
      .catch(() => setTargets([]))
      .finally(() => setLoading(false));
  }, []);

  return { targets, loading };
}

export function usePlexSetup() {
  const [resources, setResources] = useState<PlexResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([settingsAPI.getConfiguredTargets(), settingsAPI.getPlexResources()])
      .then(([targets, data]) => {
        if (cancelled) return;
        if (targets.includes("Plex")) {
          setConfigured(true);
          return;
        }
        setConfigured(false);
        setResources(data.servers);
        if (data.servers.length === 0) setError("No Plex Media Servers found on your account.");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(getErrorMessage(err, "Failed to discover Plex servers"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setupPlex = useCallback(async (serverUrl: string, token: string) => {
    await settingsAPI.setupPlexTarget(serverUrl, token);
    toast.success("Plex server configured");
  }, []);

  return { resources, loading, error, configured, setupPlex };
}
