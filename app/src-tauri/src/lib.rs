use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

/// Handle to the bundled Sentinel Core service (killed when the window closes).
struct CoreProcess(Mutex<Option<Child>>);

fn spawn_core(app: &tauri::App) -> Option<Child> {
    let resource_dir = app.path().resource_dir().ok()?;
    let core_exe = resource_dir
        .join("binaries")
        .join("sentinel-core")
        .join("sentinel-core.exe");
    if !core_exe.exists() {
        // Dev mode: the core is run separately (`uv run python -m sentinel_core`).
        eprintln!("sentinel-core.exe not bundled; assuming dev core on :8721");
        return None;
    }
    let mut cmd = Command::new(&core_exe);
    cmd.current_dir(core_exe.parent().unwrap());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    match cmd.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("failed to spawn sentinel-core: {err}");
            None
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let child = spawn_core(app);
            app.manage(CoreProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.app_handle().try_state::<CoreProcess>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
