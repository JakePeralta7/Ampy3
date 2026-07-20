import { Button } from "./Button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-50" onClick={onCancel} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full max-w-md bg-bg-surface rounded-lg shadow-lg z-50 p-6"
      >
        <h2 className="text-lg font-bold text-fg">{title}</h2>
        <p className="text-sm text-fg-muted mt-2">{message}</p>
        <div className="flex justify-end gap-3 mt-6">
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={variant} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </>
  );
}
