interface BadgeProps {
  variant: "success" | "danger" | "warning" | "neutral";
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<string, string> = {
  success: "bg-success-500/10 text-success-500 border border-success-500/20",
  danger: "bg-danger-500/10 text-danger-500 border border-danger-500/20",
  warning: "bg-warn-500/10 text-warn-500 border border-warn-500/20",
  neutral: "bg-bg-muted text-fg-muted border border-border",
};

export function Badge({ variant, children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-block px-2 py-1 rounded-sm text-xs font-medium ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
