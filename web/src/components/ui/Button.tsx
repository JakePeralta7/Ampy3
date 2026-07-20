import { Loader2 } from "lucide-react";
import type React from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "xs" | "sm" | "md";
  loading?: boolean;
  icon?: React.ReactNode;
}

const variantStyles: Record<string, string> = {
  primary:
    "bg-accent-500 text-accent-fg hover:bg-accent-600 border border-transparent shadow-sm hover:shadow-md disabled:opacity-50",
  secondary:
    "bg-bg-surface text-fg border border-border hover:bg-bg-muted shadow-sm hover:shadow-md disabled:opacity-50",
  danger:
    "bg-danger-500 text-danger-fg hover:bg-danger-500/90 border border-transparent shadow-sm hover:shadow-md disabled:opacity-50",
  ghost: "bg-transparent text-fg-muted hover:bg-bg-muted hover:text-fg disabled:opacity-50",
};

const sizeStyles: Record<string, string> = {
  xs: "px-2 py-1 text-xs rounded-sm",
  sm: "px-3 py-1.5 text-sm rounded-md",
  md: "px-4 py-2 text-sm rounded-md",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-medium transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg-app ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 size={size === "xs" ? 12 : 16} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}
