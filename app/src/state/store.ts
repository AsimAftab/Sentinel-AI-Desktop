import { create } from "zustand";
import { api, CORE_WS } from "../lib/api";
import type { ChatMessage, CoreEvent, Settings, TraceItem, VoiceState } from "../lib/types";

let nextId = 0;
const uid = () => `${Date.now()}-${nextId++}`;

interface SentinelState {
  connected: boolean;
  coreVersion: string;
  providers: Record<string, string>;
  sessionId: string | null;

  messages: ChatMessage[];
  streaming: string; // in-flight assistant text
  busy: boolean;
  trace: TraceItem[];
  events: CoreEvent[]; // raw feed for Logs view

  voice: VoiceState;
  voiceBusy: boolean;
  voiceError: string | null;

  settings: Settings | null;

  connect: () => void;
  sendChat: (text: string) => void;
  toggleVoice: () => Promise<void>;
  refreshSettings: () => Promise<void>;
  saveSettings: (overrides: Record<string, unknown>) => Promise<void>;
  saveSecret: (name: string, value: string) => Promise<void>;
}

let socket: WebSocket | null = null;
let retryTimer: number | undefined;

export const useSentinel = create<SentinelState>((set, get) => ({
  connected: false,
  coreVersion: "",
  providers: {},
  sessionId: null,
  messages: [],
  streaming: "",
  busy: false,
  trace: [],
  events: [],
  voice: "off",
  voiceBusy: false,
  voiceError: null,
  settings: null,

  connect: () => {
    if (socket && socket.readyState <= WebSocket.OPEN) return;
    socket = new WebSocket(CORE_WS);

    socket.onopen = async () => {
      set({ connected: true });
      try {
        const health = await api.health();
        set({ coreVersion: health.version, providers: health.providers });
        const status = await api.voiceStatus();
        set({ voice: status.running ? (status.state as VoiceState) : "off" });
      } catch {
        /* health is cosmetic */
      }
    };

    socket.onclose = () => {
      set({ connected: false, voice: "off" });
      window.clearTimeout(retryTimer);
      retryTimer = window.setTimeout(() => get().connect(), 2000);
    };

    socket.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as CoreEvent;
      handleEvent(event, set, get);
    };
  },

  sendChat: (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !socket || socket.readyState !== WebSocket.OPEN) return;
    set((s) => ({
      messages: [...s.messages, { id: uid(), role: "user", text: trimmed, via: "text" }],
      busy: true,
      streaming: "",
      trace: [],
    }));
    socket.send(JSON.stringify({ type: "chat", text: trimmed }));
  },

  toggleVoice: async () => {
    set({ voiceBusy: true, voiceError: null });
    try {
      if (get().voice === "off") {
        const res = await api.voiceStart();
        set({ voice: res.running ? "listening_wake" : "off" });
      } else {
        await api.voiceStop();
        set({ voice: "off" });
      }
    } catch (err) {
      set({ voiceError: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ voiceBusy: false });
    }
  },

  refreshSettings: async () => {
    set({ settings: await api.getSettings() });
  },

  saveSettings: async (overrides) => {
    const settings = await api.putSettings(overrides);
    set({ settings });
  },

  saveSecret: async (name, value) => {
    await api.putSecret(name, value);
    const health = await api.health();
    set({ providers: health.providers });
  },
}));

type Set = (fn: (s: SentinelState) => Partial<SentinelState>) => void;

function pushTrace(set: Set, item: Omit<TraceItem, "id" | "ts">, ts: number) {
  set((s) => ({ trace: [...s.trace.slice(-30), { ...item, id: uid(), ts }] }));
}

function handleEvent(
  event: CoreEvent,
  set: (partial: Partial<SentinelState> | ((s: SentinelState) => Partial<SentinelState>)) => void,
  get: () => SentinelState,
) {
  set((s) => ({ events: [...s.events.slice(-500), event] }));
  const data = event.data ?? {};

  switch (event.type) {
    case "ready":
      set({ sessionId: event.session_id ?? null });
      break;

    case "turn_started": {
      // Voice turns inject the user message here (text turns already added it).
      const text = String(data.text ?? "");
      const last = get().messages.at(-1);
      if (!(last?.role === "user" && last.text === text)) {
        set((s) => ({
          messages: [...s.messages, { id: uid(), role: "user", text, via: "voice" }],
        }));
      }
      set({ busy: true, streaming: "", trace: [] });
      break;
    }

    case "routing": {
      const agent = String(data.next_agent ?? "");
      pushTrace(
        set,
        {
          kind: "routing",
          label: agent === "FINISH" ? "Composing reply" : `Routed to ${agent}`,
          detail: String(data.task ?? "") || undefined,
        },
        event.ts,
      );
      break;
    }

    case "agent_started":
      pushTrace(set, { kind: "agent", label: `${event.agent} working…` }, event.ts);
      break;

    case "tool_started":
      pushTrace(
        set,
        { kind: "tool", label: String(data.tool ?? "tool"), detail: String(data.input ?? "") },
        event.ts,
      );
      break;

    case "token":
      set((s) => ({ streaming: s.streaming + String(data.text ?? "") }));
      break;

    case "response": {
      const text = String(data.text ?? "");
      set((s) => ({
        messages: [...s.messages, { id: uid(), role: "assistant", text }],
        streaming: "",
      }));
      break;
    }

    case "turn_finished":
      set({ busy: false, streaming: "" });
      break;

    case "error":
      pushTrace(set, { kind: "error", label: "Error", detail: String(data.message ?? "") }, event.ts);
      set({ busy: false });
      break;

    case "transcribed":
      pushTrace(set, { kind: "transcribed", label: `Heard: "${String(data.text ?? "")}"` }, event.ts);
      break;

    case "listening_for_wake_word":
      set({ voice: "listening_wake" });
      break;
    case "wake_word_detected":
    case "listening":
      set({ voice: "listening" });
      break;
    case "speaking":
      set({ voice: "speaking" });
      break;
    case "speech_finished":
      set({ voice: "listening_wake" });
      break;

    default:
      break;
  }
}
