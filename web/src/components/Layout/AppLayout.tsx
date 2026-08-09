import {
  Cog,
  Compass,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Music2,
  ScrollText,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AppRoutes } from "../../router";
import { CommandPalette } from "../ui/CommandPalette";
import { ErrorBoundary } from "../ui/ErrorBoundary";
import { Nav } from "./Nav";

const paletteItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/syncs", label: "Syncs", icon: Music2 },
  { to: "/explore", label: "Explore", icon: Compass },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/audit", label: "Audit Log", icon: ScrollText },
  { to: "/settings/config", label: "Settings", icon: Cog },
  { to: "/settings/config", label: "Config", icon: Cog, parentLabel: "Settings" },
  { to: "/settings/matching", label: "Match Rules", icon: GitBranch, parentLabel: "Settings" },
];

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
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} items={paletteItems} />
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
