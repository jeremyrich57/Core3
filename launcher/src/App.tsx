import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import "./App.css";

type Settings = {
  sourceDir: string;
  gameDir: string;
  serverHost: string;
  serverPort: number;
  manifestUrl: string;
};

type Status = { sourceProblem: string | null; installed: boolean };
type Progress = { message: string; done: number; total: number };

const MAX_LOG_LINES = 200;

function errorText(e: unknown): string {
  return typeof e === "string" ? e : e instanceof Error ? e.message : JSON.stringify(e);
}

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const logEnd = useRef<HTMLDivElement>(null);

  const addLog = useCallback((line: string) => {
    setLog((l) => [...l, line].slice(-MAX_LOG_LINES));
  }, []);

  const refresh = useCallback(async () => {
    setSettings(await invoke<Settings>("get_settings"));
    setStatus(await invoke<Status>("get_status"));
  }, []);

  useEffect(() => {
    refresh();
    const unlisten = listen<Progress>("progress", ({ payload }) => {
      if (payload.total > 0) setProgress(payload);
      else addLog(payload.message);
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, [refresh, addLog]);

  useEffect(() => logEnd.current?.scrollIntoView(), [log]);

  async function run(command: "install_client" | "play") {
    setBusy(true);
    setProgress(null);
    try {
      await invoke(command);
    } catch (e) {
      addLog(`Error: ${errorText(e)}`);
    } finally {
      setBusy(false);
      setProgress(null);
      setStatus(await invoke<Status>("get_status"));
    }
  }

  async function saveSettings(next: Settings) {
    try {
      await invoke("save_settings", { settings: next });
      await refresh();
      addLog("Settings saved.");
      setShowSettings(false);
    } catch (e) {
      addLog(`Error saving settings: ${errorText(e)}`);
    }
  }

  if (!settings || !status) return <main className="app loading">Loading…</main>;

  const needsInstall = !status.installed;
  const canInstall = needsInstall && !status.sourceProblem;
  const pct = progress && progress.total > 0 ? Math.floor((progress.done / progress.total) * 100) : 0;

  return (
    <main className="app">
      <header>
        <h1>Core3 Launcher</h1>
        <button className="link" onClick={() => setShowSettings((s) => !s)} disabled={busy}>
          {showSettings ? "Close settings" : "Settings"}
        </button>
      </header>

      {showSettings ? (
        <SettingsForm initial={settings} onSave={saveSettings} onCancel={() => setShowSettings(false)} />
      ) : (
        <section className="home">
          <div className="server">
            Server <strong>{settings.serverHost}:{settings.serverPort}</strong>
          </div>

          {needsInstall && (
            <p className={status.sourceProblem ? "notice warn" : "notice"}>
              {status.sourceProblem ??
                `First run: the game will be set up in ${settings.gameDir} using the files from ${settings.sourceDir}. Your original install is not changed.`}
            </p>
          )}

          <button
            className="primary"
            disabled={busy || (needsInstall && !canInstall)}
            onClick={() => run(needsInstall ? "install_client" : "play")}
          >
            {busy ? "Working…" : needsInstall ? "Install" : "Play"}
          </button>

          <div className="progress" aria-hidden={!progress}>
            {progress && (
              <>
                <div className="bar">
                  <div className="fill" style={{ width: `${pct}%` }} />
                </div>
                <div className="caption">
                  {progress.message} — {pct}%
                </div>
              </>
            )}
          </div>
        </section>
      )}

      <section className="log">
        {log.map((line, i) => (
          <div key={i} className={line.startsWith("Error") ? "err" : undefined}>
            {line}
          </div>
        ))}
        <div ref={logEnd} />
      </section>
    </main>
  );
}

function SettingsForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: Settings;
  onSave: (s: Settings) => void;
  onCancel: () => void;
}) {
  const [s, setS] = useState(initial);
  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => setS((prev) => ({ ...prev, [key]: value }));

  async function pick(key: "sourceDir" | "gameDir") {
    const dir = await open({ directory: true, defaultPath: s[key] || undefined });
    if (typeof dir === "string") set(key, dir);
  }

  return (
    <form
      className="settings"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(s);
      }}
    >
      <label>
        Existing SWGEmu install (read only)
        <div className="row">
          <input value={s.sourceDir} onChange={(e) => set("sourceDir", e.target.value)} />
          <button type="button" onClick={() => pick("sourceDir")}>Browse</button>
        </div>
      </label>
      <label>
        Game folder (managed by the launcher)
        <div className="row">
          <input value={s.gameDir} onChange={(e) => set("gameDir", e.target.value)} />
          <button type="button" onClick={() => pick("gameDir")}>Browse</button>
        </div>
      </label>
      <div className="row">
        <label className="grow">
          Server address
          <input value={s.serverHost} onChange={(e) => set("serverHost", e.target.value.trim())} />
        </label>
        <label className="port">
          Port
          <input
            type="number"
            min={1}
            max={65535}
            value={s.serverPort}
            onChange={(e) => set("serverPort", Number(e.target.value))}
          />
        </label>
      </div>
      <label>
        Patch manifest (URL or local path)
        <input value={s.manifestUrl} onChange={(e) => set("manifestUrl", e.target.value)} />
      </label>
      <div className="row end">
        <button type="button" className="link" onClick={onCancel}>Cancel</button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
}
