import {
  Cog,
  Compass,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  Menu,
  Music2,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  ScrollText,
  Server,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import githubSvg from "../../assets/github.svg";
import { useAuth } from "../../contexts/AuthContext";
import { useVersion } from "../../hooks/useVersion";
import { DeezerIcon, YouTubeMusicIcon } from "../ui/SourceIcon";

const COLLAPSE_KEY = "ampy3:sidebar-collapsed";

type SubLink = {
  path: string;
  label: string;
  icon?: LucideIcon | ((props: { size?: number }) => ReturnType<typeof YouTubeMusicIcon>);
};

type NavLink = {
  path: string;
  label: string;
  icon: typeof LayoutDashboard;
  sub?: SubLink[];
};

export const links: NavLink[] = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/syncs", label: "Syncs", icon: Music2 },
  {
    path: "/explore",
    label: "Explore",
    icon: Compass,
    sub: [
      { path: "/explore/ytmusic", label: "YouTube Music", icon: YouTubeMusicIcon },
      { path: "/explore/deezer", label: "Deezer", icon: DeezerIcon },
    ],
  },
  { path: "/audit", label: "Audit Log", icon: ScrollText },
  {
    path: "/settings",
    label: "Settings",
    icon: Cog,
    sub: [
      { path: "/settings/sources", label: "Sources", icon: Radio },
      { path: "/settings/targets", label: "Targets", icon: Server },
      { path: "/settings/matching", label: "Match Rules", icon: SlidersHorizontal },
    ],
  },
];

export function Nav() {
  const location = useLocation();
  const { user, logout, requireAuth } = useAuth();
  const { version, repositoryUrl } = useVersion();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  const isActive = (path: string) =>
    (path === "/settings" && location.pathname.startsWith("/settings")) ||
    (path === "/explore" && location.pathname.startsWith("/explore"))
      ? true
      : location.pathname === path;

  const linkClass = (path: string) => {
    const active = isActive(path);
    return [
      "flex items-center gap-3 rounded-md px-3 py-2 transition-colors duration-fast",
      "text-fg-muted hover:bg-bg-muted hover:text-fg",
      active && "bg-accent-50 text-accent-700",
      "focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:outline-none",
    ]
      .filter(Boolean)
      .join(" ");
  };

  const sidebarContent = (
    <>
      <div
        className="flex items-center gap-2 p-4"
        title={collapsed ? `Ampy3 v${version ?? ""}` : undefined}
      >
        <img src="/ampy3.svg" alt="" className="h-8 w-8 shrink-0" />
        {!collapsed && (
          <div className="flex flex-col leading-tight">
            <span className="font-bold text-accent-700">Ampy3</span>
            {version && <span className="text-xs text-fg-subtle">v{version}</span>}
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-1 px-2" aria-label="Main navigation">
        {links.map((link) => {
          const Icon = link.icon;
          const active = isActive(link.path);
          return (
            <div key={link.path}>
              <Link
                to={link.path}
                className={linkClass(link.path)}
                title={collapsed ? link.label : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {!collapsed && <span>{link.label}</span>}
                {collapsed && <span className="sr-only">{link.label}</span>}
              </Link>
              {!collapsed && active && link.sub && (
                <div className="ml-2 mt-1 flex flex-col gap-0.5 border-l border-border pl-3">
                  {link.sub.map((sub) => {
                    const subActive =
                      location.pathname === sub.path ||
                      location.pathname.startsWith(`${sub.path}/`);
                    return (
                      <Link
                        key={sub.path}
                        to={sub.path}
                        className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors duration-fast ${
                          subActive
                            ? "bg-accent-50 text-accent-700 font-medium"
                            : "text-fg-subtle hover:bg-bg-muted hover:text-fg"
                        }`}
                      >
                        {sub.icon && <sub.icon size={16} />}
                        {sub.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="flex-1" />

      {/* User info + logout */}
      {user && requireAuth && (
        <div className="px-2 mb-2">
          {collapsed ? (
            <button
              onClick={logout}
              className="w-full flex items-center justify-center p-2 rounded-md hover:bg-bg-muted text-fg-subtle transition-colors duration-fast"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          ) : (
            <div className="flex items-center gap-2 rounded-md px-3 py-2 bg-bg-muted">
              {user.thumb ? (
                <img
                  src={user.thumb}
                  alt=""
                  className="h-6 w-6 rounded-full object-cover shrink-0"
                />
              ) : (
                <div className="h-6 w-6 rounded-full bg-accent-100 text-accent-700 flex items-center justify-center text-xs font-medium shrink-0">
                  {user.username.charAt(0).toUpperCase()}
                </div>
              )}
              <span className="text-sm text-fg-muted truncate flex-1">{user.username}</span>
              <button
                onClick={logout}
                className="p-1 rounded hover:bg-bg-surface text-fg-subtle hover:text-fg transition-colors duration-fast"
                title="Sign out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* GitHub link */}
      {repositoryUrl && (
        <div className="px-2 mb-2">
          <a
            href={repositoryUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-fg-subtle hover:bg-bg-muted hover:text-fg transition-colors duration-fast"
            title="View on GitHub"
          >
            <img src={githubSvg} alt="GitHub" width={16} height={16} className="shrink-0" />
            {!collapsed && <span className="text-sm font-medium">GitHub</span>}
            {collapsed && <span className="sr-only">View on GitHub</span>}
          </a>
        </div>
      )}

      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="m-2 p-2 rounded-md hover:bg-bg-muted text-fg-subtle self-start transition-colors duration-fast"
      >
        {collapsed ? (
          <PanelLeftOpen className="h-4 w-4" aria-hidden />
        ) : (
          <PanelLeftClose className="h-4 w-4" aria-hidden />
        )}
      </button>
    </>
  );

  return (
    <>
      {/* Mobile hamburger */}
      <button
        className="fixed top-3 left-3 z-50 sm:hidden p-2 text-fg-muted rounded-lg focus:outline-none focus:ring-2 focus:ring-border-focus bg-bg-surface shadow-sm"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={mobileOpen ? "Close menu" : "Open menu"}
        aria-expanded={mobileOpen}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 sm:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <nav
            className="relative w-60 h-full bg-bg-surface border-r border-border flex flex-col"
            aria-label="Mobile navigation"
          >
            <div className="pt-14 flex flex-col flex-1">{sidebarContent}</div>
          </nav>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside
        className={`hidden sm:flex flex-col bg-bg-surface border-r border-border transition-all duration-base ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
