interface CardProps {
  variant?: "default" | "bordered";
  padding?: "none" | "sm" | "md" | "lg";
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

const paddingStyles: Record<string, string> = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

const variantStyles: Record<string, string> = {
  default: "bg-bg-surface rounded-lg shadow-sm",
  bordered: "bg-bg-surface rounded-lg border border-border",
};

export function Card({
  variant = "default",
  padding = "md",
  children,
  className = "",
  onClick,
}: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`${variantStyles[variant]} ${paddingStyles[padding]} ${className} ${
        onClick ? "cursor-pointer" : ""
      }`}
    >
      {children}
    </div>
  );
}
