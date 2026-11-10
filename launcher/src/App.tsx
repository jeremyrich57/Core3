import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import "./App.css";

type Server = {
  name: string;
  host: string;
  port: number;
  manifestUrl: string;
};

type Settings = {
  sourceDir: string;
  gameDir: string;
  servers: Server[];
  selectedServer: number;
  uiTextSize: string;
};

type Status = { sourceProblem: string | null; installed: boolean };
type Progress = { message: string; done: number; total: number };

const MAX_LOG_LINES = 200;
const NEW_SERVER: Server = { name: "", host: "", port: 44453, manifestUrl: "" };

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

  useEffect(() => {
    // Braces matter: newer WebView2 returns a Promise from scrollIntoView, and React would
    // treat a returned value as the effect's cleanup function and crash calling it.
    logEnd.current?.scrollIntoView();
  }, [log]);

  async function run(command: "install_client" | "play" | "open_game_settings") {
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

  async function saveSettings(next: Settings): Promise<boolean> {
    try {
      await invoke("save_settings", { settings: next });
      await refresh();
      return true;
    } catch (e) {
      addLog(`Error saving settings: ${errorText(e)}`);
      return false;
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
        <nav>
          {!showSettings && (
            <button className="link" onClick={() => run("open_game_settings")} disabled={busy || needsInstall}>
              Game settings
            </button>
          )}
          <button className="link" onClick={() => setShowSettings((s) => !s)} disabled={busy}>
            {showSettings ? "Close settings" : "Launcher settings"}
          </button>
        </nav>
      </header>

      {showSettings ? (
        <SettingsForm
          initial={settings}
          onSave={async (s) => {
            if (await saveSettings(s)) {
              addLog("Settings saved.");
              setShowSettings(false);
            }
          }}
          onCancel={() => setShowSettings(false)}
        />
      ) : (
        <section className="home">
          <label className="server-pick">
            Server
            <select
              value={settings.selectedServer}
              disabled={busy}
              onChange={(e) => saveSettings({ ...settings, selectedServer: Number(e.target.value) })}
            >
              {settings.servers.map((s, i) => (
                <option key={i} value={i}>
                  {s.name} — {s.host}:{s.port}
                </option>
              ))}
            </select>
          </label>

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
  // Index of the server being edited; servers.length means a new one.
  const [editing, setEditing] = useState<number | null>(null);

  async function pick(key: "sourceDir" | "gameDir") {
    const dir = await open({ directory: true, defaultPath: s[key] || undefined });
    if (typeof dir === "string") setS((prev) => ({ ...prev, [key]: dir }));
  }

  function saveServer(index: number, server: Server) {
    setS((prev) => {
      const servers = [...prev.servers];
      servers[index] = server;
      return { ...prev, servers };
    });
    setEditing(null);
  }

  function removeServer(index: number) {
    setS((prev) => {
      const servers = prev.servers.filter((_, i) => i !== index);
      let selected = prev.selectedServer;
      if (index < selected || selected >= servers.length) selected = Math.max(0, selected - 1);
      return { ...prev, servers, selectedServer: selected };
    });
  }

  if (editing !== null) {
    return (
      <ServerForm
        initial={s.servers[editing] ?? NEW_SERVER}
        isNew={editing >= s.servers.length}
        onSave={(server) => saveServer(editing, server)}
        onCancel={() => setEditing(null)}
      />
    );
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
          <input value={s.sourceDir} onChange={(e) => setS({ ...s, sourceDir: e.target.value })} />
          <button type="button" onClick={() => pick("sourceDir")}>Browse</button>
        </div>
      </label>
      <label>
        Game folder (managed by the launcher)
        <div className="row">
          <input value={s.gameDir} onChange={(e) => setS({ ...s, gameDir: e.target.value })} />
          <button type="button" onClick={() => pick("gameDir")}>Browse</button>
        </div>
      </label>

      <label>
        In-game text size
        <select value={s.uiTextSize} onChange={(e) => setS({ ...s, uiTextSize: e.target.value })}>
          <option value="">Normal</option>
          <option value="large">Large (about 1.2x)</option>
          <option value="larger">Larger (about 1.4x)</option>
        </select>
        <span className="muted small">For high-resolution screens. Some tight windows may clip text.</span>
      </label>

      <div className="servers">
        <div className="servers-head">
          <span>Servers</span>
          <button type="button" onClick={() => setEditing(s.servers.length)}>Add server</button>
        </div>
        {s.servers.map((server, i) => (
          <div key={i} className="server-row">
            <div className="grow">
              <strong>{server.name}</strong>
              <span className="muted"> {server.host}:{server.port}</span>
              {server.manifestUrl && <div className="muted small">Custom patches: {server.manifestUrl}</div>}
            </div>
            <button type="button" onClick={() => setEditing(i)}>Edit</button>
            <button
              type="button"
              disabled={s.servers.length === 1}
              title={s.servers.length === 1 ? "Keep at least one server" : undefined}
              onClick={() => removeServer(i)}
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      <div className="row end">
        <button type="button" className="link" onClick={onCancel}>Cancel</button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
}

function ServerForm({
  initial,
  isNew,
  onSave,
  onCancel,
}: {
  initial: Server;
  isNew: boolean;
  onSave: (s: Server) => void;
  onCancel: () => void;
}) {
  const [server, setServer] = useState(initial);
  const set = <K extends keyof Server>(key: K, value: Server[K]) => setServer((prev) => ({ ...prev, [key]: value }));
  const valid = server.name.trim() !== "" && server.host.trim() !== "" && server.port > 0 && server.port <= 65535;

  return (
    <form
      className="settings"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSave({ ...server, name: server.name.trim(), host: server.host.trim(), manifestUrl: server.manifestUrl.trim() });
      }}
    >
      <h2>{isNew ? "Add server" : `Edit ${initial.name}`}</h2>
      <label>
        Name
        <input autoFocus value={server.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Friends server" />
      </label>
      <div className="row">
        <label className="grow">
          Address
          <input value={server.host} onChange={(e) => set("host", e.target.value)} placeholder="IP or hostname" />
        </label>
        <label className="port">
          Port
          <input
            type="number"
            min={1}
            max={65535}
            value={server.port}
            onChange={(e) => set("port", Number(e.target.value))}
          />
        </label>
      </div>
      <details className="advanced" open={initial.manifestUrl !== ""}>
        <summary>Advanced</summary>
        <label>
          Custom patch manifest (optional)
          <input
            value={server.manifestUrl}
            onChange={(e) => set("manifestUrl", e.target.value)}
            placeholder="Leave empty to use the default patches"
          />
        </label>
        <div className="muted small">URL or local path of a manifest.json from tools/patch/build.py.</div>
      </details>
      <div className="row end">
        <button type="button" className="link" onClick={onCancel}>Back</button>
        <button type="submit" disabled={!valid}>{isNew ? "Add" : "Done"}</button>
      </div>
    </form>
  );
}
