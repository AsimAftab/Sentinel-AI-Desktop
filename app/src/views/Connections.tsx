import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, MessageCircle, Music2, Search, Sparkles, User } from "lucide-react";
import { api, type Connection } from "../lib/api";
import { useSentinel } from "../state/store";
import { Badge, Button, Card, Input, SectionTitle } from "../components/ui";

const ICONS: Record<string, typeof Music2> = {
  spotify: Music2,
  google: User,
  telegram: MessageCircle,
  tavily: Search,
  elevenlabs: Sparkles,
};

/** Trim the shared prefix so three Spotify fields don't all read "SPOTIPY_…". */
function fieldLabel(key: string): string {
  return key
    .replace(/^(SPOTIPY|TELEGRAM)_/, "")
    .replace(/_API_KEY$/, " key")
    .replace(/_/g, " ")
    .toLowerCase();
}

function ConnectorCard({ connection, onSaved }: { connection: Connection; onSaved: () => void }) {
  const { saveSecret } = useSentinel();
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [authorizing, setAuthorizing] = useState(false);
  const Icon = ICONS[connection.id] ?? Sparkles;
  const filled = connection.keys.filter((k) => values[k]?.trim());

  const authorize = async () => {
    setAuthorizing(true);
    setError(null);
    try {
      await api.authorizeSpotify();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAuthorizing(false);
    }
  };

  const commit = async () => {
    if (!filled.length) return;
    setSaving(true);
    setError(null);
    try {
      for (const key of filled) {
        await saveSecret(key, values[key].trim());
      }
      setValues({});
      setSaved(true);
      setTimeout(() => setSaved(false), 1400);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const status = connection.authorized ? (
    <Badge tone="ok">connected</Badge>
  ) : connection.configured ? (
    <Badge tone="warn">needs authorization</Badge>
  ) : connection.keys.length === 0 ? (
    <Badge tone="dim">needs credentials.json</Badge>
  ) : connection.missing.length < connection.keys.length ? (
    <Badge tone="warn">incomplete</Badge>
  ) : (
    <Badge tone="dim">not configured</Badge>
  );

  return (
    <Card>
      <div className="flex items-start gap-3.5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent-2">
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{connection.label}</span>
            {status}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-ink-dim">{connection.detail}</p>

          {connection.keys.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {connection.keys.map((key) => (
                <Input
                  key={key}
                  type="password"
                  placeholder={connection.missing.includes(key) ? fieldLabel(key) : "saved"}
                  value={values[key] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && commit()}
                  className="w-44 !py-1.5 text-xs"
                />
              ))}
              <Button
                variant="ghost"
                onClick={commit}
                disabled={saving || !filled.length}
                className="!px-2.5 !py-1.5"
                title="Save to Windows Credential Manager"
              >
                {saving ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : saved ? (
                  <Check size={13} className="text-ok" />
                ) : (
                  "Save"
                )}
              </Button>
            </div>
          )}

          {connection.can_authorize && (
            <div className="mt-3 flex items-center gap-2">
              <Button onClick={authorize} disabled={authorizing} className="!py-1.5 text-xs">
                {authorizing ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 size={13} className="animate-spin" /> Waiting for sign-in…
                  </span>
                ) : (
                  "Authorize"
                )}
              </Button>
              <span className="text-xs text-ink-faint">
                Opens Spotify in your browser — sign in once.
              </span>
            </div>
          )}

          {error && <p className="mt-2 text-xs text-err">{error}</p>}
        </div>
      </div>
    </Card>
  );
}

export default function ConnectionsView() {
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .getConnections()
      .then((c) => {
        setConnections(c);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="h-full overflow-y-auto px-8 py-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 text-base font-semibold">Connections</h1>
        <p className="mb-6 text-xs text-ink-faint">
          Keys go straight to the Windows Credential Manager, never to a file. Services that use
          OAuth still authorize in the browser the first time you use them.
        </p>

        <SectionTitle>Services</SectionTitle>
        {error && <p className="mb-3 text-xs text-err">Could not reach the core service: {error}</p>}
        {connections === null && !error ? (
          <p className="text-xs text-ink-faint">Loading…</p>
        ) : (
          <div className="flex flex-col gap-3">
            {(connections ?? []).map((connection) => (
              <ConnectorCard key={connection.id} connection={connection} onSaved={load} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
