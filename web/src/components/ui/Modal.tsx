import { Overlay, type OverlayProps } from "./Overlay";

interface ModalProps extends Omit<OverlayProps, "panelClassName"> {
  size?: "sm" | "md" | "lg" | "xl";
}

const sizeStyles: Record<string, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
};

export function Modal({ size = "sm", ...props }: ModalProps) {
  return (
    <Overlay
      {...props}
      panelClassName={`fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full ${sizeStyles[size]} bg-bg-surface rounded-lg shadow-lg overflow-y-auto max-h-[90vh] flex flex-col`}
    />
  );
}
