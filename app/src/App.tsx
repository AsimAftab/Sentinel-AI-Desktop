import { useEffect, useState } from "react";
import { DownloadCloud, MessageSquare, Plug, ScrollText, Settings as SettingsIcon, Shield } from "lucide-react";
import { useSentinel } from "./state/store";
import { Badge } from "./components/ui";
import { checkForUpdate, type UpdateInfo } from "./lib/updater";
import HomeView from "./views/Home";
import SettingsView from "./views/Settings";
import ConnectionsView from "./views/Connections";
import LogsView from "./views/Logs";
import "./index.css";

type View = "home" | "connections" | "settings" | "logs";

const NAV: { id: View; label: string; icon: typeof MessageSquare }[] = [
  { id: "home", label: "Assistant", icon: MessageSquare },
  { id: "connections", label: "Connections", icon: Plug },
  { id: "settings", label: "Settings", icon: SettingsIcon },
  { id: "logs", label: "Activity Log", icon: ScrollText },
];

export default function App() {
  const [view, setView] = useState<View>("home");
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [installing, setInstalling] = useState(false);
  const { connect, connected, coreVersion, voice } = useSentinel();

  useEffect(() => {
    connect();
    checkForUpdate().then(setUpdate);
  }, [connect]);

  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-edge bg-panel">
        <div className="flex items-center gap-2.5 px-4 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15">
            <Shield size={18} className="text-accent-2" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-wide">Sentinel AI</div>
            <div className="text-xs text-ink-faint">{coreVersion ? `core ${coreVersion}` : "desktop"}</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3 pt-2">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                view === id
                  ? "bg-accent/15 font-medium text-accent-2"
                  : "text-ink-dim hover:bg-panel-2 hover:text-ink"
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        {update && (
          <button
            onClick={() => {
              setInstalling(true);
              update.install().catch(() => setInstalling(false));
            }}
            disabled={installing}
            className="mx-3 mb-2 flex items-center gap-2 rounded-lg bg-accent/15 px-3 py-2.5 text-left text-xs font-medium text-accent-2 transition-colors hover:bg-accent/25 disabled:opacity-60"
          >
            <DownloadCloud size={14} className={installing ? "animate-bounce" : ""} />
            {installing ? "Installing update…" : `Update to v${update.version}`}
          </button>
        )}
        <div className="border-t border-edge px-4 py-3.5">
          {connected ? (
            <Badge tone="ok">
              <span className="h-1.5 w-1.5 rounded-full bg-ok" /> Core connected
            </Badge>
          ) : (
            <Badge tone="err">
              <span className="h-1.5 w-1.5 rounded-full bg-err" /> Core offline
            </Badge>
          )}
          {voice !== "off" && (
            <div className="mt-2">
              <Badge tone="accent">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-2" /> Voice {voice.replace(/_/g, " ")}
              </Badge>
            </div>
          )}
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        {view === "home" && <HomeView />}
        {view === "connections" && <ConnectionsView />}
        {view === "settings" && <SettingsView />}
        {view === "logs" && <LogsView />}
      </main>
    </div>
  );
}
