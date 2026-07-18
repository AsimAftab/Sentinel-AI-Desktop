/** Auto-update via the Tauri updater plugin (no-ops in dev / plain browser). */

export interface UpdateInfo {
  version: string;
  install: () => Promise<void>;
}

function inTauri(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export async function checkForUpdate(): Promise<UpdateInfo | null> {
  if (!inTauri()) return null;
  try {
    const { check } = await import("@tauri-apps/plugin-updater");
    const update = await check();
    if (!update) return null;
    return {
      version: update.version,
      install: async () => {
        await update.downloadAndInstall();
        const { relaunch } = await import("@tauri-apps/plugin-process");
        await relaunch();
      },
    };
  } catch (err) {
    console.warn("update check failed", err);
    return null;
  }
}
