import { useEffect, useRef } from "react";
import { useSentinel } from "../state/store";
import { Badge } from "../components/ui";

const TONE: Record<string, "ok" | "err" | "accent" | "dim" | "warn"> = {
  error: "err",
  response: "ok",
  turn_started: "accent",
  wake_word_detected: "accent",
  transcribed: "warn",
};

export default function LogsView() {
  const events = useSentinel((s) => s.events);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [events]);

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-edge px-6 py-4">
        <h1 className="text-base font-semibold">Activity Log</h1>
        <p className="text-xs text-ink-faint">Live event stream from the core service</p>
      </header>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-4 font-mono text-xs">
        {events.length === 0 && <p className="text-ink-faint">No events yet.</p>}
        <div className="flex flex-col gap-1">
          {events.map((event, i) => (
            <div key={i} className="selectable flex items-baseline gap-2.5">
              <span className="shrink-0 text-ink-faint">
                {new Date(event.ts * 1000).toLocaleTimeString()}
              </span>
              <Badge tone={TONE[event.type] ?? "dim"}>{event.type}</Badge>
              {event.agent && <span className="text-accent-2">{event.agent}</span>}
              <span className="truncate text-ink-dim">
                {JSON.stringify(event.data).slice(0, 160)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
