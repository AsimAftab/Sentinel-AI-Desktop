/** Mirrors sentinel_core/events.py */
export type EventType =
  | "ready"
  | "error"
  | "status"
  | "turn_started"
  | "routing"
  | "agent_started"
  | "agent_finished"
  | "tool_started"
  | "tool_finished"
  | "token"
  | "response"
  | "turn_finished"
  | "listening_for_wake_word"
  | "wake_word_detected"
  | "listening"
  | "transcribed"
  | "speaking"
  | "speech_finished";

export interface CoreEvent {
  type: EventType;
  session_id?: string;
  turn_id?: string;
  agent?: string;
  data: Record<string, unknown>;
  ts: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  pending?: boolean;
  via?: "text" | "voice";
}

export interface TraceItem {
  id: string;
  kind: "routing" | "agent" | "tool" | "transcribed" | "error";
  label: string;
  detail?: string;
  ts: number;
}

export type VoiceState =
  | "off"
  | "idle"
  | "listening_wake"
  | "listening"
  | "thinking"
  | "speaking";

export interface ProviderConfig {
  enabled: boolean;
  model: string | null;
  base_url: string | null;
  endpoint: string | null;
  deployment: string | null;
  api_version: string | null;
  timeout: number;
}

export interface Settings {
  primary_provider: string;
  fallback_enabled: boolean;
  temperature: number;
  providers: Record<string, ProviderConfig>;
  agent_providers: Record<string, string>;
  agent_temperatures: Record<string, number>;
  host: string;
  port: number;
  memory_ttl_hours: number;
}

export const PROVIDER_LABELS: Record<string, string> = {
  groq: "Groq",
  cerebras: "Cerebras",
  azure: "Azure OpenAI",
  openai: "OpenAI",
  ollama: "Ollama (local)",
  zhipu: "Zhipu AI",
};

export const PROVIDER_KEY_NAMES: Record<string, string> = {
  groq: "GROQ_API_KEY",
  cerebras: "CEREBRAS_API_KEY",
  zhipu: "ZHIPU_API_KEY",
  openai: "OPENAI_API_KEY",
  azure: "AZURE_OPENAI_API_KEY",
};
