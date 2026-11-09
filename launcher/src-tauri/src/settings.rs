use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// Defaults a fresh install starts with. Players can change them in Settings.
pub const DEFAULT_SERVER_HOST: &str = "127.0.0.1";
pub const DEFAULT_SERVER_PORT: u16 = 44453;
pub const DEFAULT_MANIFEST_URL: &str =
    "https://github.com/jeremyrich57/Core3/releases/download/patches/manifest.json";

/// Where an existing SWG install is commonly found, used to pre-fill the source folder.
const SOURCE_CANDIDATES: &[&str] = &[
    r"C:\SWGEmu",
    r"C:\Program Files (x86)\SWGEmu",
    r"C:\Program Files\SWGEmu",
    r"C:\Program Files (x86)\StarWarsGalaxies",
];

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
#[serde(default, rename_all = "camelCase")]
pub struct Settings {
    /// Existing SWG/SWGEmu install the client files are taken from. Never modified.
    pub source_dir: String,
    /// Launcher-managed game folder the client runs from.
    pub game_dir: String,
    pub server_host: String,
    pub server_port: u16,
    /// http(s) URL or local path of the patch manifest.json.
    pub manifest_url: String,
}

fn settings_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
    Ok(dir.join("settings.json"))
}

pub fn load(app: &AppHandle) -> Settings {
    let mut s: Settings = settings_path(app)
        .ok()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default();

    if s.source_dir.is_empty() {
        if let Some(found) = SOURCE_CANDIDATES
            .iter()
            .find(|d| Path::new(d).join("SWGEmu.exe").is_file())
        {
            s.source_dir = found.to_string();
        }
    }
    if s.game_dir.is_empty() {
        if let Ok(dir) = app.path().app_local_data_dir() {
            s.game_dir = dir.join("game").to_string_lossy().into_owned();
        }
    }
    if s.server_host.is_empty() {
        s.server_host = DEFAULT_SERVER_HOST.into();
    }
    if s.server_port == 0 {
        s.server_port = DEFAULT_SERVER_PORT;
    }
    if s.manifest_url.is_empty() {
        s.manifest_url = DEFAULT_MANIFEST_URL.into();
    }
    s
}

pub fn save(app: &AppHandle, s: &Settings) -> Result<(), String> {
    let path = settings_path(app)?;
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(s).map_err(|e| e.to_string())?;
    std::fs::write(path, text).map_err(|e| e.to_string())
}
