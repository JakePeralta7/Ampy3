import { X } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";

interface ModalProps {
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

export function Modal({ isOpen, onClose, title, subtitle, size = "sm", children }: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
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
      const firstFocusable = modalRef.current?.querySelector<HTMLElement>(
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
      <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose} />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full ${sizeStyles[size]} bg-bg-surface rounded-lg shadow-lg z-50 overflow-y-auto max-h-[90vh] flex flex-col`}
      >
        <div className="flex items-center justify-between border-b border-border p-6 shrink-0">
          <div>
            <h2 className="text-2xl font-bold text-fg">{title}</h2>
            {subtitle && <p className="text-sm text-fg-muted mt-1">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="text-fg-muted hover:text-fg transition-colors duration-fast"
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
