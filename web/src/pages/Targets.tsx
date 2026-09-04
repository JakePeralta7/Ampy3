import { CheckCircle, Plug, Save, XCircle } from "lucide-react";
import jellyfinSvg from "../assets/jellyfin.svg";
import plexSvg from "../assets/plex.svg";
import { PageLayout } from "../components/layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Skeleton } from "../components/ui/Skeleton";
import { useTargets } from "../hooks/useTargets";
import { TARGET_JELLYFIN, TARGET_PLEX } from "../lib/constants";

function PlexIcon({ size = 20 }: { size?: number }) {
  return <img src={plexSvg} alt="Plex" width={size} height={size} className="shrink-0" />;
}

function JellyfinIcon({ size = 20 }: { size?: number }) {
  return <img src={jellyfinSvg} alt="Jellyfin" width={size} height={size} className="shrink-0" />;
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
        <FormField
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
  const {
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
  } = useTargets();

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
          onTest={() => testConnection(TARGET_PLEX)}
          onSubmit={() => save(TARGET_PLEX)}
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
          onTest={() => testConnection(TARGET_JELLYFIN)}
          onSubmit={() => save(TARGET_JELLYFIN)}
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
