import { ChevronRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Toaster } from "sonner";

import { AppRoutes } from "../../router";
import { CommandPalette, type PaletteItem } from "../ui/CommandPalette";
import { ErrorBoundary } from "../ui/ErrorBoundary";
import { links, Nav } from "./Nav";

function linksToPaletteItems(navLinks: typeof links): PaletteItem[] {
  const items: PaletteItem[] = [];
  const subIcon = ChevronRight; // default icon for sub-items

  for (const link of navLinks) {
    if (link.sub) {
      // Sub-menu items (e.g., Settings > Sources/Targets/Match Rules)
      for (const sub of link.sub) {
        items.push({
          to: sub.path,
          label: sub.label,
          icon: subIcon,
          parentLabel: link.label,
        });
      }
    } else {
      // Top-level item (no sub-menu)
      items.push({
        to: link.path,
        label: link.label,
        icon: link.icon,
      });
    }
  }
  return items;
}

const PALETTE_ITEMS = linksToPaletteItems(links);

export function AppLayout() {
  const location = useLocation();
  const hideNav = ["/login"].includes(location.pathname);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      )
        return;
      e.preventDefault();
      setPaletteOpen((prev) => !prev);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="h-screen flex bg-bg-app">
      {!hideNav && <Nav />}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </main>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} items={PALETTE_ITEMS} />
      <Toaster
        theme={theme}
        position="bottom-right"
        richColors
        closeButton
        toastOptions={{
          duration: 4000,
        }}
      />
    </div>
  );
}
