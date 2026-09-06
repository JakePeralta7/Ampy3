import { CheckCircle, Info, Plug, Save, XCircle } from "lucide-react";
import deezerSvg from "../assets/deezer.svg";
import ytmusicSvg from "../assets/ytmusic.svg";
import { PageLayout } from "../components/layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Skeleton } from "../components/ui/Skeleton";
import { useSources } from "../hooks/useSources";
import { SOURCE_YOUTUBE_MUSIC } from "../lib/constants";

function YouTubeMusicIcon({ size = 20 }: { size?: number }) {
  return (
    <img src={ytmusicSvg} alt="YouTube Music" width={size} height={size} className="shrink-0" />
  );
}

function DeezerIcon({ size = 20 }: { size?: number }) {
  return <img src={deezerSvg} alt="Deezer" width={size} height={size} className="shrink-0" />;
}

function StatusBadge({ authenticated }: { authenticated: boolean }) {
  return authenticated ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success-500 bg-success-50 rounded-full px-2 py-0.5">
      <CheckCircle size={12} />
      Authenticated
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-fg-subtle bg-bg-muted rounded-full px-2 py-0.5">
      Not configured
    </span>
  );
}

function YouTubeMusicSection({
  authSet,
  values,
  onFieldChange,
  onTest,
  onSubmit,
  testing,
  testResult,
  saving,
  hasChanges,
}: {
  authSet: boolean;
  values: Record<string, string>;
  onFieldChange: (key: string, val: string) => void;
  onTest: () => void;
  onSubmit: () => void;
  testing: boolean;
  testResult: "pass" | "fail" | null;
  saving: boolean;
  hasChanges: boolean;
}) {
  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-lg font-semibold text-fg">
          <YouTubeMusicIcon />
          YouTube Music
        </div>
        <StatusBadge authenticated={authSet} />
      </div>

      <FormField
        id={`${SOURCE_YOUTUBE_MUSIC}-auth`}
        label="Authentication (ytmusicapi browser headers JSON)"
        type="textarea"
        rows={6}
        secretSet={authSet}
        value={values.ytmusic_auth ?? ""}
        onChange={(v) => onFieldChange("ytmusic_auth", v)}
        placeholder={
          '{\n  "Authorization": "SAPISIDHASH ...",\n  "Cookie": "...",\n  "X-Goog-AuthUser": "0"\n}'
        }
      />
      <p className="text-xs text-fg-subtle">
        Paste the browser headers JSON exported by the{" "}
        <a
          href="https://ytmusicapi.readthedocs.io/en/latest/setup/browser.html"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          ytmusicapi setup
        </a>{" "}
        flow (a flat JSON object with "Authorization" and "Cookie"). Used to fetch authenticated
        playlists and personalized Explore content.
      </p>
      <FormField
        id={`${SOURCE_YOUTUBE_MUSIC}-timeout`}
        label="Fetch timeout (seconds)"
        type="number"
        value={values.yt_dlp_timeout ?? ""}
        onChange={(v) => onFieldChange("yt_dlp_timeout", v)}
      />

      <div className="flex items-center gap-3 pt-2">
        <Button variant="secondary" onClick={onTest} disabled={testing} icon={<Plug size={14} />}>
          {testing ? "Testing..." : "Test"}
        </Button>

        {testResult === "pass" && (
          <span className="text-sm text-success-500 flex items-center gap-1">
            <CheckCircle size={14} /> Authentication successful
          </span>
        )}
        {testResult === "fail" && (
          <span className="text-sm text-danger-500 flex items-center gap-1">
            <XCircle size={14} /> Authentication failed
          </span>
        )}

        <div className="flex-1" />

        <Button onClick={onSubmit} disabled={!hasChanges || saving} icon={<Save size={14} />}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </Card>
  );
}

function DeezerSection() {
  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-lg font-semibold text-fg">
          <DeezerIcon />
          Deezer
        </div>
        <span className="inline-flex items-center gap-1 text-xs font-medium text-fg-subtle bg-bg-muted rounded-full px-2 py-0.5">
          <Info size={12} />
          No auth needed
        </span>
      </div>
      <p className="text-sm text-fg-muted">
        Deezer playlists are fetched through the public Deezer API — no authentication or
        configuration is required.
      </p>
    </Card>
  );
}

export function SourcesPage() {
  const {
    values,
    authSet,
    loading,
    saving,
    testing,
    testResult,
    hasChanges,
    setField,
    testAuth,
    save,
  } = useSources();

  if (loading) {
    return (
      <div className="max-w-3xl p-8">
        <Skeleton />
      </div>
    );
  }

  return (
    <PageLayout title="" maxWidth="md">
      <div className="space-y-8">
        <YouTubeMusicSection
          authSet={authSet}
          values={values}
          onFieldChange={setField}
          onTest={testAuth}
          onSubmit={save}
          testing={testing}
          testResult={testResult}
          saving={saving}
          hasChanges={hasChanges}
        />
        <DeezerSection />
      </div>
    </PageLayout>
  );
}
