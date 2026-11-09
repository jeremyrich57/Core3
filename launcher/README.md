# Core3 Launcher

Windows launcher for the Core3 server. Built with [Tauri v2](https://tauri.app): Rust backend in `src-tauri/`, React + TypeScript UI in `src/`.

## What it does

1. **Install:** checks an existing SWGEmu install (the "source", never modified) against `src-tauri/resources/client_files.txt` and hard-links its files into a launcher-managed game folder. Linking is instant and uses no extra disk space; it copies instead if the folders are on different drives.
2. **Play:**
   - downloads changed custom TREs listed in the patch manifest (built by `tools/patch/build.py`) and verifies their sha256
   - writes `swgemu_login.cfg` (server address) and `swgemu_live.cfg` (stock TREs plus custom TREs at top priority)
   - starts `SWGEmu.exe`

Settings live in `%APPDATA%\com.jeremyrich.core3launcher\settings.json`. The default game folder is `%LOCALAPPDATA%\com.jeremyrich.core3launcher\game`.

## Development (Windows)

Needs Node, Rust (MSVC toolchain) and the Visual Studio C++ build tools.

```powershell
cd launcher
npm install
npm run tauri dev      # run with hot reload
npm run tauri build    # -> src-tauri\target\release\bundle\nsis\*-setup.exe
cd src-tauri; cargo test
```

### Testing patches without publishing

Set **Settings → Patch manifest** to a local path, for example the build output in WSL:

```
\\wsl.localhost\Ubuntu\home\jrich\repos\Core3\build\patches\manifest.json
```

Then `python3 tools/patch/build.py --install ~/tre` in WSL and click Play. The client and server both get the new TRE.
