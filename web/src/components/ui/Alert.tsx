interface AlertProps {
  variant?: "error" | "success" | "warning";
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<string, string> = {
  error: "bg-danger-500/10 text-danger-500 border-danger-500/20",
  success: "bg-success-500/10 text-success-500 border-success-500/20",
  warning: "bg-warning-500/10 text-warning-700 border-warning-500/20",
};

export function Alert({ variant = "error", children, className = "" }: AlertProps) {
  return (
    <div className={`p-3 border rounded-md text-sm ${variantStyles[variant]} ${className}`}>
      {children}
    </div>
  );
}
