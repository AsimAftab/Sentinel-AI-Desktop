use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::Manager;

/// Handle to the bundled Sentinel Core service (killed on quit).
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

fn kill_core(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<CoreProcess>() {
        if let Some(mut child) = state.0.lock().unwrap().take() {
            let _ = child.kill();
        }
    }
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let child = spawn_core(app);
            app.manage(CoreProcess(Mutex::new(child)));

            // Tray icon: shows Sentinel is running; closing the window only
            // hides it (voice keeps listening). Quit here really exits.
            let show = MenuItem::with_id(app, "show", "Show Sentinel", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Sentinel", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Sentinel AI is running")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main_window(app),
                    "quit" => {
                        kill_core(app);
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main_window(tray.app_handle());
                    }
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Hide to tray instead of exiting; the core (and voice
                // pipeline) keeps running in the background.
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                // Covers OS shutdown/logoff and any other exit path.
                kill_core(app);
            }
        });
}
