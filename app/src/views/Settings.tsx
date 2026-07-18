import { useEffect, useState, type ReactNode } from "react";
import { Check, Loader2 } from "lucide-react";
import { useSentinel } from "../state/store";
import { Button, Input, SectionTitle, SettingRow, Toggle } from "../components/ui";
import { PROVIDER_KEY_NAMES, PROVIDER_LABELS } from "../lib/types";

function Panel({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-edge bg-panel px-5 py-2">{children}</div>;
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "ok" ? "bg-ok" : status.startsWith("error") ? "bg-err" : "bg-ink-faint/40";
  const title = status === "ok" ? "Ready" : status.startsWith("error") ? status : "No key configured";
  return <span title={title} className={`inline-block h-2 w-2 shrink-0 rounded-full ${color}`} />;
}

function ProviderRow({ name }: { name: string }) {
  const { settings, providers, saveSettings, saveSecret } = useSentinel();
  const [key, setKey] = useState("");
  const [model, setModel] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const config = settings?.providers[name];
  if (!config) return null;
  const status = providers[name] ?? "unknown";
  const keyName = PROVIDER_KEY_NAMES[name];

  const flash = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 1200);
  };

  const commit = async () => {
    setSaving(true);
    try {
      if (key.trim() && keyName) {
        await saveSecret(keyName, key.trim());
        setKey("");
      }
      if (model !== null && model.trim() !== (config.model ?? "")) {
        await saveSettings({ providers: { [name]: { model: model.trim() || null } } });
        setModel(null);
      }
      flash();
    } finally {
      setSaving(false);
    }
  };

  const dirty = Boolean(key.trim()) || (model !== null && model.trim() !== (config.model ?? ""));

  return (
    <SettingRow
      label={PROVIDER_LABELS[name] ?? name}
      description={config.model ?? "default model"}
    >
      <StatusDot status={status} />
      <Input
        placeholder="model"
        value={model ?? config.model ?? ""}
        onChange={(e) => setModel(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        className="w-36 !py-1.5 text-xs"
      />
      {keyName && (
        <Input
          type="password"
          placeholder={status === "ok" ? "key saved" : "API key"}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && commit()}
          className="w-40 !py-1.5 text-xs"
        />
      )}
      <Button
        variant="ghost"
        onClick={commit}
        disabled={saving || !dirty}
        className="!px-2.5 !py-1.5"
        title="Save"
      >
        {saving ? (
          <Loader2 size={13} className="animate-spin" />
        ) : saved ? (
          <Check size={13} className="text-ok" />
        ) : (
          "Save"
        )}
      </Button>
    </SettingRow>
  );
}

export default function SettingsView() {
  const { settings, refreshSettings, saveSettings } = useSentinel();
  const [temperature, setTemperature] = useState<number | null>(null);

  useEffect(() => {
    refreshSettings().catch(() => undefined);
  }, [refreshSettings]);

  if (!settings) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-faint">
        <Loader2 size={16} className="mr-2 animate-spin" /> Loading settings…
      </div>
    );
  }

  const temp = temperature ?? settings.temperature;

  return (
    <div className="h-full overflow-y-auto px-8 py-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-base font-semibold">Settings</h1>
        <p className="mt-0.5 mb-7 text-xs text-ink-faint">
          Changes apply immediately. API keys go to the Windows Credential Manager, never to files.
        </p>

        <SectionTitle>Model</SectionTitle>
        <Panel>
          <SettingRow label="Provider" description="Which service powers Sentinel's thinking">
            <select
              value={settings.primary_provider}
              onChange={(e) => saveSettings({ primary_provider: e.target.value })}
              className="rounded-lg border border-edge bg-bg py-1.5 pl-3 text-sm focus:border-accent focus:outline-none"
            >
              {Object.keys(settings.providers).map((name) => (
                <option key={name} value={name}>
                  {PROVIDER_LABELS[name] ?? name}
                </option>
              ))}
            </select>
          </SettingRow>

          <SettingRow
            label="Automatic fallback"
            description="Try other configured providers if the primary fails"
          >
            <Toggle
              checked={settings.fallback_enabled}
              onChange={(v) => saveSettings({ fallback_enabled: v })}
            />
          </SettingRow>

          <SettingRow label="Creativity" description="Low = precise, high = exploratory">
            <span className="w-8 text-right font-mono text-xs text-ink-dim">{temp.toFixed(1)}</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={temp}
              onChange={(e) => setTemperature(Number(e.target.value))}
              onMouseUp={() => saveSettings({ temperature: temp })}
              className="w-40"
            />
          </SettingRow>
        </Panel>

        <div className="mt-7" />
        <SectionTitle>Providers</SectionTitle>
        <Panel>
          {Object.keys(settings.providers)
            .filter((name) => name !== "ollama" || settings.providers[name].enabled)
            .map((name) => (
              <ProviderRow key={name} name={name} />
            ))}
        </Panel>
      </div>
    </div>
  );
}
