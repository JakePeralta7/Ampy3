/**
 * Shared base component for Modal and Slideover.
 * Handles keyboard management, body scroll lock, backdrop, and focus.
 */
import { X } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";

export interface OverlayProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  /** Class names applied to the panel container (positioning + sizing). */
  panelClassName: string;
  /** z-index for backdrop; panel uses one step higher. */
  zIndex?: number;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Overlay({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  panelClassName,
  zIndex = 50,
}: OverlayProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
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
      panelRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)?.focus();
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
      <div className="fixed inset-0 bg-black/50" style={{ zIndex }} onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={panelClassName}
        style={{ zIndex: zIndex + 1 }}
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
