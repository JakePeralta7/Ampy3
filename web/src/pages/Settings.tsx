import { Download, Save } from "lucide-react";
import { PageLayout } from "../components/layout/PageLayout";
import { Button } from "../components/ui/Button";
import { FormField } from "../components/ui/FormField";
import { SectionCard } from "../components/ui/SectionCard";
import { Skeleton } from "../components/ui/Skeleton";
import { useSettings } from "../hooks/useSettings";

export function ConfigPage() {
  const { values, loading, saving, hasChanges, setField, save } = useSettings();

  if (loading) {
    return (
      <div className="max-w-3xl p-8">
        <Skeleton />
      </div>
    );
  }

  return (
    <PageLayout
      title=""
      maxWidth="md"
      actions={
        <Button onClick={save} disabled={!hasChanges || saving} icon={<Save size={16} />}>
          {saving ? "Saving..." : "Save"}
        </Button>
      }
    >
      <div className="space-y-8">
        <SectionCard icon={<Download size={20} className="text-accent-500" />} title="yt-dlp">
          <FormField
            id="yt_dlp_cookies"
            label="Cookies file path (optional)"
            value={values.yt_dlp_cookies ?? ""}
            onChange={(v) => setField("yt_dlp_cookies", v)}
            placeholder="/cookies/cookies.txt"
          />
          <FormField
            id="yt_dlp_timeout"
            label="Timeout (seconds)"
            type="number"
            value={values.yt_dlp_timeout ?? ""}
            onChange={(v) => setField("yt_dlp_timeout", v)}
          />
        </SectionCard>
      </div>
    </PageLayout>
  );
}
