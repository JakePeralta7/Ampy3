import { Overlay, type OverlayProps } from "./Overlay";

interface SlideoverProps extends Omit<OverlayProps, "panelClassName"> {
  size?: "sm" | "md" | "lg" | "xl";
}

const sizeStyles: Record<string, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
};

export function Slideover({ size = "md", ...props }: SlideoverProps) {
  return (
    <Overlay
      {...props}
      panelClassName={`fixed inset-y-0 right-0 w-full ${sizeStyles[size]} bg-bg-surface shadow-lg flex flex-col`}
    />
  );
}
