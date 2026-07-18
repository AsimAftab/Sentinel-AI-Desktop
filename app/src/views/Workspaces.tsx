import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Play, Plus, Trash2, X } from "lucide-react";
import { api, type InstalledApp, type Workspace } from "../lib/api";
import { Button, Card, Input, SectionTitle } from "../components/ui";

export default function WorkspacesView() {
  const [workspaces, setWorkspaces] = useState<Record<string, Workspace>>({});
  const [apps, setApps] = useState<InstalledApp[] | null>(null);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<InstalledApp[]>([]);
  const [saving, setSaving] = useState(false);
  const [launching, setLaunching] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    api.getWorkspaces().then(setWorkspaces).finally(() => setLoading(false));
    api.listApps().then(setApps).catch(() => setApps([]));
  }, []);

  const matches = useMemo(() => {
    if (!apps || query.trim().length < 2) return [];
    const q = query.toLowerCase();
    return apps
      .filter((a) => a.name.toLowerCase().includes(q))
      .filter((a) => !selected.some((s) => s.app_id === a.app_id))
      .slice(0, 8);
  }, [apps, query, selected]);

  const save = async () => {
    if (!name.trim() || selected.length === 0) return;
    setSaving(true);
    try {
      setWorkspaces(await api.saveWorkspace(name.trim(), { apps: selected, urls: [] }));
      setName("");
      setSelected([]);
      setQuery("");
      setStatus(`Saved "${name.trim()}" — try saying: "open my ${name.trim()} workspace"`);
    } finally {
      setSaving(false);
    }
  };

  const launch = async (workspaceName: string) => {
    setLaunching(workspaceName);
    setStatus(null);
    try {
      const res = await api.openWorkspace(workspaceName);
      setStatus(res.result);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setLaunching(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-faint">
        <Loader2 size={16} className="mr-2 animate-spin" /> Loading workspaces…
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto px-8 py-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-base font-semibold">Workspaces</h1>
        <p className="mt-0.5 mb-6 text-xs text-ink-faint">
          Named app groups. Launch them here, or by voice: "Open my dev workspace".
        </p>

        {status && (
          <div className="mb-4 rounded-lg border border-edge bg-panel px-3.5 py-2.5 text-xs text-ink-dim">
            {status}
          </div>
        )}

        {Object.keys(workspaces).length > 0 && (
          <>
            <SectionTitle>Your workspaces</SectionTitle>
            <div className="mb-7 flex flex-col gap-3">
              {Object.entries(workspaces).map(([wsName, ws]) => (
                <Card key={wsName}>
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{wsName}</div>
                      <div className="mt-0.5 truncate text-xs text-ink-faint">
                        {ws.apps.map((a) => a.name).join(" · ") || "no apps"}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        onClick={() => launch(wsName)}
                        disabled={launching !== null}
                        className="flex items-center gap-1.5 !px-3 !py-1.5 text-xs"
                      >
                        {launching === wsName ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Play size={13} />
                        )}
                        Launch
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => api.deleteWorkspace(wsName).then(setWorkspaces)}
                        className="!px-2.5 !py-1.5"
                        title="Delete workspace"
                      >
                        <Trash2 size={13} />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}

        <SectionTitle>New workspace</SectionTitle>
        <Card>
          <div className="flex flex-col gap-3">
            <Input
              placeholder='Name — e.g. "dev", "study", "gaming"'
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            {selected.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {selected.map((app) => (
                  <span
                    key={app.app_id}
                    className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-1 text-xs text-accent-2"
                  >
                    {app.name}
                    <button
                      onClick={() => setSelected(selected.filter((s) => s.app_id !== app.app_id))}
                      className="hover:text-ink"
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <Input
              placeholder={apps === null ? "Loading installed apps…" : "Search apps to add…"}
              value={query}
              disabled={apps === null}
              onChange={(e) => setQuery(e.target.value)}
            />
            {matches.length > 0 && (
              <div className="flex flex-col overflow-hidden rounded-lg border border-edge">
                {matches.map((app) => (
                  <button
                    key={app.app_id}
                    onClick={() => {
                      setSelected([...selected, app]);
                      setQuery("");
                    }}
                    className="flex items-center gap-2 px-3 py-2 text-left text-sm text-ink-dim hover:bg-panel-2 hover:text-ink"
                  >
                    <Plus size={13} className="text-accent-2" />
                    {app.name}
                  </button>
                ))}
              </div>
            )}

            <div>
              <Button
                onClick={save}
                disabled={saving || !name.trim() || selected.length === 0}
                className="flex items-center gap-1.5"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Save workspace
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
