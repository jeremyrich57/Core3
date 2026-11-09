mod client;
mod patch;
mod progress;
mod settings;

use serde::Serialize;
use tauri::AppHandle;

use settings::Settings;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Status {
    /// None if the source folder is a usable SWGEmu install, otherwise why not.
    source_problem: Option<String>,
    installed: bool,
}

#[tauri::command]
fn get_settings(app: AppHandle) -> Settings {
    settings::load(&app)
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: Settings) -> Result<(), String> {
    settings::save(&app, &settings)
}

#[tauri::command]
async fn get_status(app: AppHandle) -> Status {
    let s = settings::load(&app);
    tauri::async_runtime::spawn_blocking(move || Status {
        source_problem: client::check_source(&s.source_dir).err(),
        installed: client::is_installed(&s.game_dir),
    })
    .await
    .unwrap_or(Status { source_problem: None, installed: false })
}

#[tauri::command]
async fn install_client(app: AppHandle) -> Result<(), String> {
    let s = settings::load(&app);
    tauri::async_runtime::spawn_blocking(move || client::install(&app, &s.source_dir, &s.game_dir))
        .await
        .map_err(|e| e.to_string())?
}

/// Download the selected server's patches, write the client config, and start the game.
#[tauri::command]
async fn play(app: AppHandle) -> Result<(), String> {
    let s = settings::load(&app);
    if !client::is_installed(&s.game_dir) {
        return Err("The game is not installed yet.".into());
    }
    let server = s.server()?;
    let custom = patch::sync(&app, &server.manifest_url, &s.game_dir).await?;
    client::write_config(&s.game_dir, server, &custom)?;
    client::launch(&s.game_dir, client::EXECUTABLE, &client::game_arguments(server))?;
    progress::log(&app, &format!("Started SWG -> {} ({}:{})", server.name, server.host, server.port));
    Ok(())
}

/// Open the client's own options tool on the launcher's game folder.
#[tauri::command]
fn open_game_settings(app: AppHandle) -> Result<(), String> {
    let s = settings::load(&app);
    if !client::is_installed(&s.game_dir) {
        return Err("Install the game first.".into());
    }
    client::launch(&s.game_dir, client::SETUP_EXECUTABLE, &[])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            get_status,
            install_client,
            play,
            open_game_settings
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
