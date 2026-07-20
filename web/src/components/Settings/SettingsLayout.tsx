import { Settings as SettingsIcon } from "lucide-react";
import { Outlet } from "react-router-dom";

export function SettingsLayout() {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="border-b border-border bg-bg-surface shrink-0">
        <div className="max-w-7xl mx-auto px-8 pt-6 pb-4">
          <div className="flex items-center gap-3">
            <SettingsIcon size={28} className="text-fg-muted" />
            <h1 className="text-3xl font-bold text-fg">Settings</h1>
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        <Outlet />
      </div>
    </div>
  );
}
