use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// The server a fresh install starts with. Players can edit it or add more in Settings.
pub const DEFAULT_SERVER_NAME: &str = "Local";
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

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(default, rename_all = "camelCase")]
pub struct Server {
    pub name: String,
    pub host: String,
    pub port: u16,
    /// http(s) URL or local path of the server's patch manifest.json; empty = no custom patches.
    pub manifest_url: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
#[serde(default, rename_all = "camelCase")]
pub struct Settings {
    /// Existing SWG/SWGEmu install the client files are taken from. Never modified.
    pub source_dir: String,
    /// Launcher-managed game folder the client runs from.
    pub game_dir: String,
    pub servers: Vec<Server>,
    /// Index into `servers` of the one Play connects to.
    pub selected_server: usize,

    // Single-server fields from launcher 0.1.0, migrated into `servers` on load.
    #[serde(skip_serializing)]
    server_host: String,
    #[serde(skip_serializing)]
    server_port: u16,
    #[serde(skip_serializing)]
    manifest_url: String,
}

impl Settings {
    pub fn server(&self) -> Result<&Server, String> {
        self.servers
            .get(self.selected_server)
            .ok_or_else(|| "Choose a server first.".to_string())
    }
}

fn settings_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
    Ok(dir.join("settings.json"))
}

pub fn load(app: &AppHandle) -> Settings {
    let s: Settings = settings_path(app)
        .ok()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default();
    let default_game = app
        .path()
        .app_local_data_dir()
        .map(|d| d.join("game").to_string_lossy().into_owned())
        .unwrap_or_default();
    fill_defaults(s, default_game)
}

fn fill_defaults(mut s: Settings, default_game_dir: String) -> Settings {
    if s.source_dir.is_empty() {
        if let Some(found) = SOURCE_CANDIDATES
            .iter()
            .find(|d| Path::new(d).join("SWGEmu.exe").is_file())
        {
            s.source_dir = found.to_string();
        }
    }
    if s.game_dir.is_empty() {
        s.game_dir = default_game_dir;
    }
    if s.servers.is_empty() {
        let legacy = !s.server_host.is_empty();
        s.servers.push(Server {
            name: DEFAULT_SERVER_NAME.into(),
            host: if legacy { s.server_host.clone() } else { DEFAULT_SERVER_HOST.into() },
            port: if s.server_port != 0 { s.server_port } else { DEFAULT_SERVER_PORT },
            manifest_url: if legacy { s.manifest_url.clone() } else { DEFAULT_MANIFEST_URL.into() },
        });
    }
    if s.selected_server >= s.servers.len() {
        s.selected_server = 0;
    }
    s
}

pub fn save(app: &AppHandle, s: &Settings) -> Result<(), String> {
    for server in &s.servers {
        if server.name.trim().is_empty() || server.host.trim().is_empty() || server.port == 0 {
            return Err("Every server needs a name, address and port.".into());
        }
    }
    let path = settings_path(app)?;
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(s).map_err(|e| e.to_string())?;
    std::fs::write(path, text).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn migrates_single_server_settings() {
        let old = r#"{"sourceDir":"C:\\SWG","gameDir":"D:\\game","serverHost":"swg.example.org","serverPort":44463,"manifestUrl":"C:\\m.json"}"#;
        let s = fill_defaults(serde_json::from_str(old).unwrap(), String::new());
        assert_eq!(s.servers.len(), 1);
        assert_eq!(s.servers[0].host, "swg.example.org");
        assert_eq!(s.servers[0].port, 44463);
        assert_eq!(s.servers[0].manifest_url, "C:\\m.json");
        let saved = serde_json::to_string(&s).unwrap();
        assert!(!saved.contains("serverHost"));
    }

    #[test]
    fn fresh_settings_get_a_default_server() {
        let s = fill_defaults(Settings::default(), "G".into());
        assert_eq!(s.game_dir, "G");
        assert_eq!(s.servers[0].host, DEFAULT_SERVER_HOST);
        assert_eq!(s.server().unwrap().port, DEFAULT_SERVER_PORT);
    }
}
