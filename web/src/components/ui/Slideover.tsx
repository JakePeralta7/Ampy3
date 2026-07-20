import { X } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";

interface SlideoverProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  children: React.ReactNode;
}

const sizeStyles: Record<string, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
};

export function Slideover({
  isOpen,
  onClose,
  title,
  subtitle,
  size = "md",
  children,
}: SlideoverProps) {
  const slideoverRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && slideoverRef.current) {
        const focusableElements = slideoverRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusableElements.length === 0) return;
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    previousActiveElement.current = document.activeElement;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    const timer = setTimeout(() => {
      const firstFocusable = slideoverRef.current?.querySelector<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      firstFocusable?.focus();
    }, 50);
    return () => {
      clearTimeout(timer);
      document.body.style.overflow = "";
      document.removeEventListener("keydown", handleKeyDown);
      if (previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-30" onClick={onClose} />
      <div
        ref={slideoverRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`fixed inset-y-0 right-0 w-full ${sizeStyles[size]} bg-bg-surface shadow-lg z-40 flex flex-col`}
      >
        <div className="flex items-center justify-between border-b border-border p-6 shrink-0">
          <div className="min-w-0 flex-1">
            <h2 className="text-2xl font-bold text-fg truncate">{title}</h2>
            {subtitle && <p className="text-sm text-fg-muted mt-1 truncate">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="ml-4 text-fg-muted hover:text-fg shrink-0 transition-colors duration-fast"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </div>
    </>
  );
}
