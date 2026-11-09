//! Syncs the custom TREs listed in the patch manifest (built by tools/patch/build.py)
//! into the game folder.

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::AppHandle;
use tokio::io::AsyncWriteExt;

use crate::progress;

const SUPPORTED_SCHEMA: u32 = 1;
/// Records which custom TREs the launcher installed, so removed patches get deleted.
const STATE_FILE: &str = "launcher_patches.json";

#[derive(Deserialize)]
struct Manifest {
    schema: u32,
    /// Highest client search priority first.
    files: Vec<Entry>,
}

#[derive(Deserialize)]
struct Entry {
    name: String,
    size: u64,
    sha256: String,
}

#[derive(Serialize, Deserialize, Default)]
struct State {
    /// Manifest the files came from, so switching servers never reuses another server's patches.
    #[serde(default)]
    manifest: String,
    files: Vec<String>,
}

/// Where the manifest and the files next to it come from.
enum Source {
    Http(String),
    Local(PathBuf),
}

impl Source {
    fn parse(manifest: &str) -> (Source, String) {
        let manifest = manifest.trim();
        if manifest.starts_with("http://") || manifest.starts_with("https://") {
            let base = manifest.rsplit_once('/').map(|(b, _)| b).unwrap_or(manifest);
            (Source::Http(base.to_string()), manifest.to_string())
        } else {
            let path = PathBuf::from(manifest.strip_prefix("file://").unwrap_or(manifest));
            let base = path.parent().map(Path::to_path_buf).unwrap_or_default();
            (Source::Local(base), path.to_string_lossy().into_owned())
        }
    }
}

fn http() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .user_agent(concat!("core3-launcher/", env!("CARGO_PKG_VERSION")))
        .build()
        .map_err(|e| e.to_string())
}

async fn fetch_manifest(source: &Source, location: &str) -> Result<Manifest, String> {
    let text = match source {
        Source::Http(_) => {
            let resp = http()?
                .get(location)
                .send()
                .await
                .and_then(|r| r.error_for_status())
                .map_err(|e| format!("Fetching patch manifest: {e}"))?;
            resp.text().await.map_err(|e| e.to_string())?
        }
        Source::Local(_) => fs::read_to_string(location)
            .map_err(|e| format!("Reading patch manifest {location}: {e}"))?,
    };
    let manifest: Manifest =
        serde_json::from_str(&text).map_err(|e| format!("Invalid patch manifest: {e}"))?;
    if manifest.schema != SUPPORTED_SCHEMA {
        return Err(format!(
            "Patch manifest schema {} is not supported; update the launcher.",
            manifest.schema
        ));
    }
    for e in &manifest.files {
        let safe = e.name.ends_with(".tre")
            && !e.name.contains(['/', '\\', ':'])
            && !e.name.starts_with('.');
        if !safe {
            return Err(format!("Patch manifest has an invalid file name: {}", e.name));
        }
    }
    Ok(manifest)
}

fn sha256_file(path: &Path) -> Option<String> {
    let mut f = fs::File::open(path).ok()?;
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 20];
    loop {
        let n = f.read(&mut buf).ok()?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    Some(hex::encode(h.finalize()))
}

fn is_current(path: &Path, e: &Entry) -> bool {
    fs::metadata(path).map(|m| m.len() == e.size).unwrap_or(false)
        && sha256_file(path).is_some_and(|h| h.eq_ignore_ascii_case(&e.sha256))
}

async fn fetch_file(app: &AppHandle, source: &Source, e: &Entry, dest: &Path) -> Result<(), String> {
    let part = dest.with_extension("tre.part");
    let mut hasher = Sha256::new();
    let mut done = 0u64;
    let label = format!("Downloading {}", e.name);
    {
        let mut out = tokio::fs::File::create(&part).await.map_err(|err| err.to_string())?;
        match source {
            Source::Http(base) => {
                let url = format!("{base}/{}", e.name);
                let resp = http()?
                    .get(&url)
                    .send()
                    .await
                    .and_then(|r| r.error_for_status())
                    .map_err(|err| format!("Downloading {}: {err}", e.name))?;
                let mut stream = resp.bytes_stream();
                while let Some(chunk) = stream.next().await {
                    let chunk = chunk.map_err(|err| format!("Downloading {}: {err}", e.name))?;
                    hasher.update(&chunk);
                    out.write_all(&chunk).await.map_err(|err| err.to_string())?;
                    done += chunk.len() as u64;
                    progress::report(app, &label, done, e.size);
                }
            }
            Source::Local(base) => {
                let data = tokio::fs::read(base.join(&e.name))
                    .await
                    .map_err(|err| format!("Reading {}: {err}", e.name))?;
                hasher.update(&data);
                out.write_all(&data).await.map_err(|err| err.to_string())?;
                done = data.len() as u64;
                progress::report(app, &label, done, e.size);
            }
        }
        out.flush().await.map_err(|err| err.to_string())?;
    }

    let hash = hex::encode(hasher.finalize());
    if done != e.size || !hash.eq_ignore_ascii_case(&e.sha256) {
        let _ = fs::remove_file(&part);
        return Err(format!(
            "{} failed verification (got {done} bytes, sha256 {hash}); the published patch may be mid-update, try again.",
            e.name
        ));
    }
    fs::rename(&part, dest).map_err(|err| format!("Installing {}: {err}", e.name))
}

fn read_state(game: &Path) -> State {
    fs::read_to_string(game.join(STATE_FILE))
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default()
}

/// Bring the custom TREs in `game` in line with the manifest. Returns their names,
/// highest priority first. If the manifest can't be reached, keeps what is installed.
pub async fn sync(app: &AppHandle, manifest_url: &str, game: &str) -> Result<Vec<String>, String> {
    let game = Path::new(game);
    let previous = read_state(game);

    if manifest_url.trim().is_empty() {
        finish(app, game, &previous, manifest_url, Vec::new(), 0)?;
        return Ok(Vec::new());
    }

    let (source, location) = Source::parse(manifest_url);
    let manifest = match fetch_manifest(&source, &location).await {
        Ok(m) => m,
        Err(e) if matches!(source, Source::Http(_)) && e.contains("404") => {
            progress::log(app, "No patches have been published for this server yet.");
            finish(app, game, &previous, manifest_url, Vec::new(), 0)?;
            return Ok(Vec::new());
        }
        Err(e) if previous.manifest == manifest_url && !previous.files.is_empty() => {
            progress::log(app, &format!("{e}\nUsing the patches already installed."));
            return Ok(previous.files);
        }
        Err(e) => return Err(e),
    };

    let mut updated = 0;
    for e in &manifest.files {
        let dest = game.join(&e.name);
        if !is_current(&dest, e) {
            fetch_file(app, &source, e, &dest).await?;
            updated += 1;
        }
    }

    let names: Vec<String> = manifest.files.iter().map(|e| e.name.clone()).collect();
    finish(app, game, &previous, manifest_url, names.clone(), updated)?;
    Ok(names)
}

/// Delete custom TREs that are no longer listed, record the current set, and report.
fn finish(
    app: &AppHandle,
    game: &Path,
    previous: &State,
    manifest_url: &str,
    names: Vec<String>,
    updated: usize,
) -> Result<(), String> {
    for old in previous.files.iter().filter(|n| !names.contains(n)) {
        let _ = fs::remove_file(game.join(old));
        progress::log(app, &format!("Removed old patch {old}"));
    }
    let count = names.len();
    let state = State { manifest: manifest_url.to_string(), files: names };
    let state = serde_json::to_string_pretty(&state).map_err(|e| e.to_string())?;
    fs::write(game.join(STATE_FILE), state).map_err(|e| e.to_string())?;

    progress::log(
        app,
        &match (count, updated) {
            (0, _) => "No custom patches.".to_string(),
            (n, 0) => format!("{n} custom patch file(s) up to date."),
            (n, u) => format!("Updated {u} of {n} custom patch file(s)."),
        },
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_manifest_locations() {
        let (s, loc) = Source::parse("https://example.org/releases/download/patches/manifest.json");
        assert!(matches!(s, Source::Http(ref b) if b == "https://example.org/releases/download/patches"));
        assert!(loc.ends_with("manifest.json"));
        let (s, _) = Source::parse(r"\\wsl.localhost\Ubuntu\repo\build\patches\manifest.json");
        assert!(matches!(s, Source::Local(ref b) if b.ends_with("patches")));
    }
}
