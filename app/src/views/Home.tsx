import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Mic, MicOff, Route, Send, Sparkles, User, Wrench } from "lucide-react";
import { useSentinel } from "../state/store";
import { Badge, Button } from "../components/ui";
import type { TraceItem, VoiceState } from "../lib/types";

const VOICE_HINT: Record<VoiceState, string> = {
  off: "Voice is off",
  idle: "Starting…",
  listening_wake: 'Say "Hey Jarvis"',
  listening: "Listening — speak now",
  thinking: "Thinking…",
  speaking: "Speaking — say the wake word to interrupt",
};

function TraceRow({ item }: { item: TraceItem }) {
  const icon = {
    routing: <Route size={12} />,
    agent: <Bot size={12} />,
    tool: <Wrench size={12} />,
    transcribed: <Mic size={12} />,
    error: <Sparkles size={12} />,
  }[item.kind];
  return (
    <div className="fade-up flex items-center gap-2 text-xs text-ink-dim" title={item.detail}>
      <span className={item.kind === "error" ? "text-err" : "text-accent-2"}>{icon}</span>
      <span className={`truncate ${item.kind === "error" ? "text-err" : ""}`}>{item.label}</span>
      {item.detail && <span className="truncate text-ink-faint">· {item.detail}</span>}
    </div>
  );
}

export default function HomeView() {
  const { messages, streaming, busy, trace, connected, voice, voiceBusy, voiceError, sendChat, toggleVoice } =
    useSentinel();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming, trace]);

  const submit = () => {
    if (!draft.trim() || busy) return;
    sendChat(draft);
    setDraft("");
  };

  const voiceOn = voice !== "off";

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-edge px-6 py-4">
        <div>
          <h1 className="text-base font-semibold">Assistant</h1>
          <p className="text-xs text-ink-faint">{voiceOn ? VOICE_HINT[voice] : "Type below, or turn on voice"}</p>
        </div>
        <div className="flex items-center gap-3">
          {voiceError && <Badge tone="err">{voiceError.slice(0, 60)}</Badge>}
          <Button
            variant={voiceOn ? "danger" : "primary"}
            onClick={toggleVoice}
            disabled={voiceBusy || !connected}
            className="flex items-center gap-2"
          >
            {voiceBusy ? <Loader2 size={15} className="animate-spin" /> : voiceOn ? <MicOff size={15} /> : <Mic size={15} />}
            {voiceOn ? "Stop voice" : "Start voice"}
          </Button>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {messages.length === 0 && !streaming && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div
              className={`flex h-20 w-20 items-center justify-center rounded-full bg-accent/15 ${
                voice === "listening" || voice === "listening_wake" ? "orb-listening" : ""
              } ${voice === "speaking" ? "orb-speaking" : ""}`}
            >
              <Sparkles size={30} className="text-accent-2" />
            </div>
            <div>
              <p className="text-sm font-medium text-ink">How can I help?</p>
              <p className="mt-1 max-w-sm text-xs text-ink-faint">
                Weather, web search, Spotify, meetings, email, notes — by voice or text.
              </p>
            </div>
          </div>
        )}

        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`fade-up flex gap-3 ${message.role === "user" ? "flex-row-reverse" : ""}`}
            >
              <div
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                  message.role === "user" ? "bg-panel-2 text-ink-dim" : "bg-accent/15 text-accent-2"
                }`}
              >
                {message.role === "user" ? <User size={13} /> : <Bot size={13} />}
              </div>
              <div
                className={`selectable max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  message.role === "user"
                    ? "rounded-tr-sm bg-accent font-medium text-accent-ink"
                    : "rounded-tl-sm border border-edge bg-panel text-ink"
                }`}
              >
                {message.text}
                {message.via === "voice" && message.role === "user" && (
                  <Mic size={11} className="ml-2 inline opacity-60" />
                )}
              </div>
            </div>
          ))}

          {streaming && (
            <div className="fade-up flex gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent-2">
                <Bot size={13} />
              </div>
              <div className="selectable max-w-[80%] rounded-2xl rounded-tl-sm border border-edge bg-panel px-4 py-2.5 text-sm leading-relaxed">
                {streaming}
                <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse rounded-sm bg-accent-2 align-middle" />
              </div>
            </div>
          )}

          {busy && trace.length > 0 && (
            <div className="ml-10 flex flex-col gap-1.5 rounded-xl border border-edge bg-panel/60 px-3.5 py-2.5">
              {trace.slice(-5).map((item) => (
                <TraceRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>

      <footer className="border-t border-edge px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2.5">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
            placeholder={connected ? "Ask Sentinel anything…" : "Waiting for core service…"}
            disabled={!connected}
            className="selectable flex-1 rounded-xl border border-edge bg-panel px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-50"
          />
          <Button onClick={submit} disabled={!connected || busy || !draft.trim()} className="h-11 w-11 !p-0">
            {busy ? <Loader2 size={16} className="mx-auto animate-spin" /> : <Send size={16} className="mx-auto" />}
          </Button>
        </div>
      </footer>
    </div>
  );
}
