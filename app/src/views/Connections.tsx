import { Calendar, Mail, Music2 } from "lucide-react";
import { Badge, Card, SectionTitle } from "../components/ui";

const SERVICES = [
  {
    icon: Music2,
    name: "Spotify",
    detail:
      "Set SPOTIPY_CLIENT_ID / SECRET / REDIRECT_URI, then ask Sentinel to play something — the browser opens once to authorize.",
  },
  {
    icon: Calendar,
    name: "Google Meet & Calendar",
    detail:
      "Place credentials.json in the Sentinel data folder, then ask Sentinel to schedule a meeting — Google sign-in opens once.",
  },
  {
    icon: Mail,
    name: "Gmail",
    detail: "Shares the Google sign-in above. Ask Sentinel to check or send email.",
  },
];

export default function ConnectionsView() {
  return (
    <div className="h-full overflow-y-auto px-8 py-6">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 text-base font-semibold">Connections</h1>
        <p className="mb-6 text-xs text-ink-faint">
          Services authorize on first use — there's nothing to pre-connect. Tokens are encrypted
          and stored locally.
        </p>

        <SectionTitle>Available services</SectionTitle>
        <div className="flex flex-col gap-3">
          {SERVICES.map(({ icon: Icon, name, detail }) => (
            <Card key={name}>
              <div className="flex items-start gap-3.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent-2">
                  <Icon size={18} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{name}</span>
                    <Badge tone="dim">authorizes on first use</Badge>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-ink-dim">{detail}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
