//! The stock SWGEmu client: validating a source install, linking it into the
//! launcher's game folder, writing the client .cfg files, and starting it.

use std::fs;
use std::path::Path;
use std::process::Command;

use tauri::AppHandle;

use crate::progress;
use crate::settings::Server;

pub const EXECUTABLE: &str = "SWGEmu.exe";
/// The client's graphics/sound/controls options tool; it saves options.cfg itself.
pub const SETUP_EXECUTABLE: &str = "SWGEmu_Setup.exe";

const CLIENT_FILES: &str = include_str!("../resources/client_files.txt");

/// Copied from the source install on first install if present; the client edits options.cfg itself.
const SEED_CONFIGS: &[&str] = &["swgemu_preload.cfg", "options.cfg"];

/// Stock TRE search order from SWGEmu's swgemu_live.cfg (key, file). Higher priority wins.
const STOCK_SEARCH_TREES: &[(&str, &str)] = &[
    ("searchTree_00_25", "default_patch.tre"),
    ("searchTree_01_24", "patch_sku1_14_00.tre"),
    ("searchTree_00_23", "patch_14_00.tre"),
    ("searchTree_01_22", "patch_sku1_13_00.tre"),
    ("searchTree_00_21", "patch_13_00.tre"),
    ("searchTree_01_20", "patch_sku1_12_00.tre"),
    ("searchTree_00_19", "patch_12_00.tre"),
    ("searchTree_00_18", "patch_11_03.tre"),
    ("searchTree_01_17", "data_sku1_07.tre"),
    ("searchTree_00_16", "patch_11_02.tre"),
    ("searchTree_01_15", "data_sku1_06.tre"),
    ("searchTree_00_14", "patch_11_01.tre"),
    ("searchTree_00_14", "patch_11_00.tre"),
    ("searchTree_01_13", "data_sku1_05.tre"),
    ("searchTree_01_13", "data_sku1_04.tre"),
    ("searchTree_01_13", "data_sku1_03.tre"),
    ("searchTree_01_13", "data_sku1_02.tre"),
    ("searchTree_01_13", "data_sku1_01.tre"),
    ("searchTree_01_13", "data_sku1_00.tre"),
    ("searchTree_00_12", "patch_10.tre"),
    ("searchTree_00_11", "patch_09.tre"),
    ("searchTree_00_10", "patch_08.tre"),
    ("searchTree_00_9", "patch_07.tre"),
    ("searchTree_00_8", "patch_06.tre"),
    ("searchTree_00_7", "patch_05.tre"),
    ("searchTree_00_6", "patch_04.tre"),
    ("searchTree_00_5", "patch_03.tre"),
    ("searchTree_00_4", "patch_02.tre"),
    ("searchTree_00_3", "patch_01.tre"),
    ("searchTree_00_2", "patch_00.tre"),
    ("searchTree_00_1", "data_other_00.tre"),
    ("searchTree_00_1", "data_static_mesh_01.tre"),
    ("searchTree_00_1", "data_static_mesh_00.tre"),
    ("searchTree_00_1", "data_texture_07.tre"),
    ("searchTree_00_1", "data_texture_06.tre"),
    ("searchTree_00_1", "data_texture_05.tre"),
    ("searchTree_00_1", "data_texture_04.tre"),
    ("searchTree_00_1", "data_texture_03.tre"),
    ("searchTree_00_1", "data_texture_02.tre"),
    ("searchTree_00_1", "data_texture_01.tre"),
    ("searchTree_00_1", "data_texture_00.tre"),
    ("searchTree_00_1", "data_skeletal_mesh_01.tre"),
    ("searchTree_00_1", "data_skeletal_mesh_00.tre"),
    ("searchTree_00_1", "data_animation_00.tre"),
    ("searchTree_00_1", "data_sample_04.tre"),
    ("searchTree_00_1", "data_sample_03.tre"),
    ("searchTree_00_1", "data_sample_02.tre"),
    ("searchTree_00_1", "data_sample_01.tre"),
    ("searchTree_00_1", "data_sample_00.tre"),
    ("searchTree_00_1", "data_music_00.tre"),
    ("searchTree_00_0", "bottom.tre"),
];
const STOCK_MAX_PRIORITY: usize = 26;

struct ClientFile {
    path: &'static str,
    size: u64,
}

impl ClientFile {
    /// TREs and the executable must match exactly; small loose files (MOTD, loading
    /// screens) vary between SWGEmu installs and only need to exist.
    fn strict(&self) -> bool {
        self.path.ends_with(".tre") || self.path == EXECUTABLE
    }

    fn matches(&self, dir: &Path) -> bool {
        match fs::metadata(dir.join(self.path)) {
            Ok(m) => m.is_file() && (!self.strict() || m.len() == self.size),
            Err(_) => false,
        }
    }
}

fn client_files() -> Vec<ClientFile> {
    CLIENT_FILES
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#'))
        .filter_map(|l| {
            let mut parts = l.trim().split(';');
            let path = parts.next()?;
            let size = parts.next()?.parse().ok()?;
            Some(ClientFile { path, size })
        })
        .collect()
}

/// Ok if `dir` holds a complete SWGEmu client; otherwise a message naming what is wrong.
pub fn check_source(dir: &str) -> Result<(), String> {
    if dir.is_empty() {
        return Err("Choose the folder of your existing SWGEmu install.".into());
    }
    let dir = Path::new(dir);
    let bad: Vec<&str> = client_files()
        .iter()
        .filter(|f| !f.matches(dir))
        .map(|f| f.path)
        .collect();
    match bad.len() {
        0 => Ok(()),
        n => Err(format!(
            "{} is not a complete SWGEmu install: {} file(s) missing or the wrong size ({}{}).",
            dir.display(),
            n,
            bad.iter().take(3).cloned().collect::<Vec<_>>().join(", "),
            if n > 3 { ", ..." } else { "" }
        )),
    }
}

pub fn is_installed(game_dir: &str) -> bool {
    !game_dir.is_empty() && client_files().iter().all(|f| f.matches(Path::new(game_dir)))
}

/// Hard-link (or copy, across drives) the stock client from `source` into `game`.
pub fn install(app: &AppHandle, source: &str, game: &str) -> Result<(), String> {
    check_source(source)?;
    let (source, game) = (Path::new(source), Path::new(game));
    fs::create_dir_all(game).map_err(|e| format!("Cannot create {}: {e}", game.display()))?;

    let files = client_files();
    let total: u64 = files.iter().map(|f| f.size).sum();
    let mut done = 0;
    let mut copied = 0;

    for f in &files {
        let (from, to) = (source.join(f.path), game.join(f.path));
        if !f.matches(game) {
            if let Some(parent) = to.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            let _ = fs::remove_file(&to);
            if fs::hard_link(&from, &to).is_err() {
                fs::copy(&from, &to).map_err(|e| format!("Copying {}: {e}", f.path))?;
                copied += 1;
            }
        }
        done += f.size;
        progress::report(app, &format!("Installing {}", f.path), done, total);
    }

    for name in SEED_CONFIGS {
        let (from, to) = (source.join(name), game.join(name));
        if !to.exists() && from.is_file() {
            fs::copy(&from, &to).map_err(|e| format!("Copying {name}: {e}"))?;
        }
    }

    progress::log(
        app,
        &if copied == 0 {
            format!("Installed {} files (linked, no extra disk space used).", files.len())
        } else {
            format!("Installed {} files ({copied} copied).", files.len())
        },
    );
    Ok(())
}

/// Write the .cfg files that point the client at the server and add the custom TREs
/// (highest priority first) above the stock search order.
/// `font_locale` selects the large-text fonts from the custom TRE (None = stock fonts).
pub fn write_config(
    game: &str,
    server: &Server,
    custom_tres: &[String],
    font_locale: Option<&str>,
) -> Result<(), String> {
    let game = Path::new(game);
    let write = |name: &str, text: String| {
        fs::write(game.join(name), text).map_err(|e| format!("Writing {name}: {e}"))
    };

    let mut includes = vec!["swgemu_login.cfg", "swgemu_live.cfg"];
    includes.extend(SEED_CONFIGS.iter().filter(|f| game.join(f).is_file()));
    write(
        "swgemu.cfg",
        includes.iter().map(|f| format!(".include \"{f}\"\n")).collect(),
    )?;

    write(
        "swgemu_login.cfg",
        format!(
            "[ClientGame]\n\tloginServerAddress0={}\n\tloginServerPort0={}\n",
            server.host, server.port
        ),
    )?;

    let n = custom_tres.len();
    let mut live = String::from("# Generated by the Core3 launcher; changes are overwritten.\n\n[SharedFile]\n");
    live += &format!("\tmaxSearchPriority={}\n", STOCK_MAX_PRIORITY + n);
    for (i, name) in custom_tres.iter().enumerate() {
        live += &format!("\tsearchTree_00_{}={name}\n", STOCK_MAX_PRIORITY + n - 1 - i);
    }
    for (key, name) in STOCK_SEARCH_TREES {
        live += &format!("\t{key}={name}\n");
    }
    live += "\n[SharedNetwork]\n\tnetworkHandlerDispatchThrottle=true\n";
    live += "\n[ClientUserInterface]\n\tmessageOfTheDayTable=live_motd\n";
    if let Some(locale) = font_locale {
        live += &format!("\n[SharedGame]\n\tfontLocale={locale}\n");
    }
    write("swgemu_live.cfg", live)
}

/// Command line for SWGEmu.exe. The client must get "-- -s <section> key=value ..." settings:
/// started without arguments it doesn't set up its TRE search paths and crashes with
/// "appearance/defaultappearance.apt could not be found". Same as the SWGEmu launchpad.
pub fn game_arguments(server: &Server) -> Vec<String> {
    [
        "--".to_string(),
        "-s".into(),
        "ClientGame".into(),
        format!("loginServerAddress0={}", server.host),
        format!("loginServerPort0={}", server.port),
        "-s".into(),
        "Station".into(),
        "gameFeatures=34929".into(),
    ]
    .to_vec()
}

pub fn launch(game: &str, executable: &str, args: &[String]) -> Result<(), String> {
    let exe = Path::new(game).join(executable);
    Command::new(&exe)
        .args(args)
        .current_dir(game)
        // Windows "installer detection" forces a UAC prompt for unsigned 32-bit programs
        // named like an installer (SWGEmu_Setup.exe). Neither tool needs admin rights.
        .env("__COMPAT_LAYER", "RunAsInvoker")
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("Could not start {}: {e}", exe.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_client_file_list() {
        let files = client_files();
        assert_eq!(files.len(), 72);
        assert!(files.iter().any(|f| f.path == EXECUTABLE && f.strict()));
        // Every TRE the client searches must be installed (the list also has two unused hotfix TREs).
        assert!(STOCK_SEARCH_TREES.iter().all(|(_, t)| files.iter().any(|f| f.path == *t)));
    }

    #[test]
    fn custom_tres_get_top_priority() {
        let dir = std::env::temp_dir().join("core3_launcher_cfg_test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("options.cfg"), "").unwrap();
        let s = Server { host: "example.org".into(), port: 44453, ..Default::default() };
        let game = dir.to_str().unwrap();

        write_config(game, &s, &["b.tre".into(), "a.tre".into()], None).unwrap();

        let live = fs::read_to_string(dir.join("swgemu_live.cfg")).unwrap();
        assert!(live.contains("maxSearchPriority=28\n"));
        assert!(live.find("searchTree_00_27=b.tre").unwrap() < live.find("searchTree_00_26=a.tre").unwrap());
        assert!(live.contains("searchTree_00_25=default_patch.tre"));
        assert!(!live.contains("fontLocale"));
        let login = fs::read_to_string(dir.join("swgemu_login.cfg")).unwrap();
        assert!(login.contains("loginServerAddress0=example.org") && login.contains("loginServerPort0=44453"));
        let main = fs::read_to_string(dir.join("swgemu.cfg")).unwrap();
        assert_eq!(main, ".include \"swgemu_login.cfg\"\n.include \"swgemu_live.cfg\"\n.include \"options.cfg\"\n");

        write_config(game, &s, &["a.tre".into()], Some("l1")).unwrap();
        let live = fs::read_to_string(dir.join("swgemu_live.cfg")).unwrap();
        assert!(live.contains("[SharedGame]\n\tfontLocale=l1\n"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn game_arguments_set_login_server() {
        let s = Server { host: "example.org".into(), port: 44453, ..Default::default() };
        let args = game_arguments(&s);
        assert_eq!(args[0], "--");
        assert!(args.contains(&"loginServerAddress0=example.org".to_string()));
        assert!(args.contains(&"loginServerPort0=44453".to_string()));
    }
}
