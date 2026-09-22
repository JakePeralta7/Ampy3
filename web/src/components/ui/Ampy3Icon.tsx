import ampy3Svg from "../../assets/ampy3.svg";

interface Ampy3IconProps {
  size?: number;
  className?: string;
}

export function Ampy3Icon({ size = 56, className = "" }: Ampy3IconProps) {
  return (
    <img
      src={ampy3Svg}
      alt="Ampy3"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
    />
  );
}
