import { UserRound } from "lucide-react";
import { Link } from "react-router-dom";

export function AuthNotice() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-warning-700/30 bg-warning-50/10 p-4 text-sm text-warning-700">
      <UserRound size={18} className="shrink-0 text-warning-700" />
      <div className="min-w-0">
        <p className="font-medium">Connect your YouTube Music account</p>
        <p className="text-warning-800">
          Your personalized home feed is hidden until you paste your account credentials. Set it up
          in{" "}
          <Link
            to="/settings/sources"
            className="font-medium underline underline-offset-2 hover:text-warning-900"
          >
            Settings → Sources
          </Link>
          . Charts, moods, and search still work without it.
        </p>
      </div>
    </div>
  );
}
