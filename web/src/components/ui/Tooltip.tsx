import { type ReactNode, useRef, useState, useMemo } from "react";
import { createPortal } from "react-dom";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  position?: "top" | "bottom" | "left" | "right";
  delay?: number;
}

export function Tooltip({ content, children, position = "top", delay = 200 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useRef<number | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  const show = () => {
    timeoutRef.current = window.setTimeout(() => setVisible(true), delay);
  };

  const hide = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setVisible(false);
  };

  const positionStyles: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  const arrowStyles: Record<string, string> = {
    top: "top-full left-1/2 -translate-x-1/2 border-t-accent-500",
    bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-accent-500",
    left: "left-full top-1/2 -translate-y-1/2 border-l-accent-500",
    right: "right-full top-1/2 -translate-y-1/2 border-r-accent-500",
  };

  const tooltip = useMemo(() => (
    <div
      ref={tooltipRef}
      className={`fixed z-50 px-2 py-1 text-xs text-accent-fg bg-accent-500 rounded shadow-lg whitespace-nowrap ${positionStyles[position]}`}
      role="tooltip"
    >
      {content}
      <div className={`absolute w-0 h-0 border-4 border-transparent ${arrowStyles[position]}`} />
    </div>
  ), [content, position, positionStyles, arrowStyles, tooltipRef]);

  if (!visible) {
    return (
      <div
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="inline-block"
      >
        {children}
      </div>
    );
  }

  return (
    <>
      <div
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="inline-block"
      >
        {children}
      </div>
      {createPortal(tooltip, document.body)}
    </>
  );
}
