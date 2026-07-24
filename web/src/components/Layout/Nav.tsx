import {
  Cog,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageCircle,
  MessageSquare,
  Music2,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useChatSessions } from "../../contexts/ChatSessionContext";
import { generateId } from "../../lib/utils";

const COLLAPSE_KEY = "ampy3:sidebar-collapsed";

const links = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/syncs", label: "Syncs", icon: Music2 },
  { path: "/chat", label: "Chat", icon: MessageSquare },
  { path: "/audit", label: "Audit Log", icon: ScrollText },
  {
    path: "/settings/config",
    label: "Settings",
    icon: Cog,
    sub: [
      { path: "/settings/config", label: "Config" },
      { path: "/settings/matching", label: "Match Rules" },
    ],
  },
];

export function Nav() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, requireAuth } = useAuth();
  const { sessions: chatSessions } = useChatSessions();
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
    path === "/settings/config" && location.pathname.startsWith("/settings")
      ? true
      : path === "/chat" && location.pathname.startsWith("/chat")
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
      <div className="flex items-center gap-2 p-4">
        <div className="h-8 w-8 rounded-lg bg-accent-500 text-accent-fg flex items-center justify-center font-bold text-sm shrink-0">
          A
        </div>
        {!collapsed && <span className="font-bold text-accent-700">Ampy3</span>}
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
                        {sub.label}
                      </Link>
                    );
                  })}
                </div>
              )}
              {!collapsed && link.path === "/chat" && active && chatSessions.length > 0 && (
                <div className="ml-2 mt-1 flex flex-col gap-0.5 border-l border-border pl-3">
                  <button
                    onClick={() => {
                      const newId = generateId();
                      navigate(`/chat/${newId}`);
                    }}
                    className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors duration-fast ${
                      location.pathname === "/chat"
                        ? "bg-accent-50 text-accent-700 font-medium"
                        : "text-fg-subtle hover:bg-bg-muted hover:text-fg"
                    }`}
                  >
                    <MessageCircle size={14} className="shrink-0" />
                    New Chat
                  </button>
                  {chatSessions.map((s) => {
                    const sessionActive = location.pathname === `/chat/${s.id}`;
                    return (
                      <Link
                        key={s.id}
                        to={`/chat/${s.id}`}
                        className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors duration-fast truncate ${
                          sessionActive
                            ? "bg-accent-50 text-accent-700 font-medium"
                            : "text-fg-subtle hover:bg-bg-muted hover:text-fg"
                        }`}
                        title={s.preview}
                      >
                        <span className="truncate">{s.preview}</span>
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
