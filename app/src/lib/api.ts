import type { Settings } from "./types";

export const CORE_HTTP = "http://127.0.0.1:8721";
export const CORE_WS = "ws://127.0.0.1:8721/ws";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${CORE_HTTP}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<{ status: string; version: string; providers: Record<string, string> }>("/health"),
  getSettings: () => request<Settings>("/settings"),
  putSettings: (overrides: Record<string, unknown>) =>
    request<Settings>("/settings", { method: "PUT", body: JSON.stringify({ overrides }) }),
  putSecret: (name: string, value: string) =>
    request<{ saved: string }>("/secrets", { method: "POST", body: JSON.stringify({ name, value }) }),
  voiceStart: () => request<{ running: boolean; state: string }>("/voice/start", { method: "POST" }),
  voiceStop: () => request<{ running: boolean }>("/voice/stop", { method: "POST" }),
  voiceStatus: () => request<{ running: boolean; state: string }>("/voice/status"),

  getConnections: () => request<Connection[]>("/connections"),
  authorizeSpotify: () =>
    request<{ authorized: boolean }>("/connections/spotify/authorize", { method: "POST" }),

  listApps: () => request<InstalledApp[]>("/system/apps"),
  getWorkspaces: () => request<Record<string, Workspace>>("/workspaces"),
  saveWorkspace: (name: string, workspace: Workspace) =>
    request<Record<string, Workspace>>(`/workspaces/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(workspace),
    }),
  deleteWorkspace: (name: string) =>
    request<Record<string, Workspace>>(`/workspaces/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
  openWorkspace: (name: string) =>
    request<{ result: string }>(`/workspaces/${encodeURIComponent(name)}/open`, {
      method: "POST",
    }),
};

export interface InstalledApp {
  name: string;
  app_id: string;
}

export interface Connection {
  id: string;
  label: string;
  detail: string;
  /** Secret names this connector needs. Empty for file-based auth (Google). */
  keys: string[];
  /** Credentials are present. */
  configured: boolean;
  /** Subset of keys still unset — drives the "needs X, Y" hint. */
  missing: string[];
  /** OAuth actually completed. Differs from `configured` for Spotify/Google. */
  authorized: boolean;
  /** Show an Authorize button (Spotify only for now). */
  can_authorize: boolean;
}

export interface Workspace {
  apps: InstalledApp[];
  urls: string[];
}
