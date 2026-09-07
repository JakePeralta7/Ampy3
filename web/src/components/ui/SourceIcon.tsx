import deezerSvg from "../../assets/deezer.svg";
import ytmusicSvg from "../../assets/ytmusic.svg";

interface SourceIconProps {
  size?: number;
}

export function YouTubeMusicIcon({ size = 28 }: SourceIconProps) {
  return (
    <img src={ytmusicSvg} alt="YouTube Music" width={size} height={size} className="shrink-0" />
  );
}

export function DeezerIcon({ size = 28 }: SourceIconProps) {
  return <img src={deezerSvg} alt="Deezer" width={size} height={size} className="shrink-0" />;
}
