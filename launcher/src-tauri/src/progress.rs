use serde::Serialize;
use tauri::{AppHandle, Emitter};

/// Sent to the UI as the "progress" event. `total == 0` means a plain log line.
#[derive(Clone, Serialize)]
pub struct Progress<'a> {
    pub message: &'a str,
    pub done: u64,
    pub total: u64,
}

pub fn log(app: &AppHandle, message: &str) {
    report(app, message, 0, 0);
}

pub fn report(app: &AppHandle, message: &str, done: u64, total: u64) {
    let _ = app.emit("progress", Progress { message, done, total });
}
