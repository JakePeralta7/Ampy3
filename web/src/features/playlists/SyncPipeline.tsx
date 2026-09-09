import type { PipelineStatusResponse } from "../../api/syncs";
import deezerSvg from "../../assets/deezer.svg";
import jellyfinSvg from "../../assets/jellyfin.svg";
import plexSvg from "../../assets/plex.svg";
import ytmusicSvg from "../../assets/ytmusic.svg";
import { getSourceLabel, TARGET_JELLYFIN, TARGET_PLEX } from "../../lib/constants";
import { PipelineNode, type PipelineStatus } from "./PipelineNode";

const SOURCE_ICONS: Record<string, string> = {
  deezer: deezerSvg,
  youtube_music: ytmusicSvg,
};

const TARGET_ICONS: Record<string, string> = {
  [TARGET_PLEX]: plexSvg,
  [TARGET_JELLYFIN]: jellyfinSvg,
};

function toPipelineStatus(status: string): PipelineStatus {
  switch (status) {
    case "running":
    case "started":
      return "running";
    case "completed":
    case "success":
      return "success";
    case "failed":
    case "failure":
      return "failed";
    default:
      return "pending";
  }
}

function targetSubtitle(matched: number, failed: number, running: boolean): string | undefined {
  if (running && matched === 0 && failed === 0) return "Matching tracks…";
  return `${matched} matched${failed > 0 ? `, ${failed} failed` : ""}`;
}

interface SyncPipelineProps {
  pipeline: PipelineStatusResponse;
}

export function SyncPipeline({ pipeline }: SyncPipelineProps) {
  const sourceIcon = SOURCE_ICONS[pipeline.source] ?? ytmusicSvg;

  return (
    <div className="space-y-2 py-1">
      <PipelineNode
        title={pipeline.orchestrator.label || `Fetch ${getSourceLabel(pipeline.source)}`}
        subtitle={pipeline.orchestrator.detail ?? undefined}
        status={toPipelineStatus(pipeline.orchestrator.status)}
        icon={
          <img
            src={sourceIcon}
            alt={getSourceLabel(pipeline.source)}
            width={16}
            height={16}
            className="shrink-0"
          />
        }
      />

      <div className="ml-3 pl-3 border-l border-border space-y-1.5">
        {pipeline.targets.length === 0 ? (
          <p className="text-xs text-fg-muted">Waiting for target tasks to start…</p>
        ) : (
          pipeline.targets.map((target) => (
            <PipelineNode
              key={target.run_id}
              title={target.target_id}
              subtitle={targetSubtitle(
                target.matched_count,
                target.failed_count,
                target.status === "running",
              )}
              status={toPipelineStatus(target.status)}
              icon={
                <img
                  src={TARGET_ICONS[target.target_id] ?? plexSvg}
                  alt={target.target_id}
                  width={16}
                  height={16}
                  className="shrink-0"
                />
              }
            />
          ))
        )}
      </div>
    </div>
  );
}
