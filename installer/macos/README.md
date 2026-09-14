# JARVIS macOS installer

A lightweight DMG: `JARVIS.app` carries the JARVIS source and the `uv` Python manager (~22 MB). On first launch the app prepares Python 3.12 and all components, then starts JARVIS.

## Build

```bash
installer/macos/build_dmg.sh            # package HEAD
installer/macos/build_dmg.sh main       # package a branch, tag or commit
```

Output: `dist/JARVIS-<date>-<sha>-macOS.dmg` plus a `.sha256` file.

Only files tracked by git at the chosen ref are packaged (`git archive`). The build refuses to continue if it finds an API key file, `.env`, long-term memory, Private Brain data, certificates or a virtualenv in the package. `installer/`, `.github/` and `tests/` are left out.

| Variable | Purpose | Default |
|---|---|---|
| `UV_BIN` | uv binary to bundle (its architecture becomes the native one) | `command -v uv` |
| `BUNDLE_ID` | Bundle identifier | `id.kohenri.jarvis` |
| `SIGN_IDENTITY` | `Developer ID Application: …` for real signing | ad-hoc (`-`) |
| `NOTARY_PROFILE` | `notarytool` keychain profile; notarizes and staples the DMG | not set |
| `OUT_DIR` | Output folder | `dist/` |

Without a Developer ID the app is ad-hoc signed: macOS shows "unidentified developer" on first open, and users must right-click → **Open** once. For frictionless distribution, build with `SIGN_IDENTITY` and `NOTARY_PROFILE`.

## What the app does on launch (`launcher.sh`)

1. **Sync code** — copies the bundled source to `~/Library/Application Support/JARVIS/app` when the bundle version changes. `user-data.rsync-filter` protects user data from being overwritten or deleted:
   - `config/api_keys.json` and `config/certs/`
   - `memory/*.json`, `memory/*.jsonl` and `memory/private_brain/`
   - `uploads/`
   - user-installed plugins
2. **Python** — uses the bundled `uv` (or downloads a matching one on other architectures) to create `…/JARVIS/venv` with Python 3.12 (`--seed`, so JARVIS's own auto-installer can use pip). Dependencies are reinstalled only when `requirements.txt` changes. The Playwright Chromium install is optional and never blocks startup.
3. **Start** — `exec`s `main.py`, so microphone and camera prompts are attributed to JARVIS.app (usage strings in `Info.plist`).

Progress and failures are shown as macOS notifications and dialogs. Logs go to `~/Library/Logs/JARVIS/setup.log` and `jarvis.log`. A lock prevents a second click from racing the first-time setup.

Testing and repair overrides: `JARVIS_SUPPORT_DIR`, `JARVIS_LOG_DIR`, `JARVIS_SETUP_ONLY=1`, `JARVIS_NO_DIALOGS=1`.

## Uninstall

Delete `/Applications/JARVIS.app`. To remove all data as well, also delete `~/Library/Application Support/JARVIS` and `~/Library/Logs/JARVIS`.

## Known limitations

- The first launch needs internet and takes a few minutes on a fresh Mac.
- JARVIS runs on the bundled Python, so macOS may show "Python" in the menu bar while it runs.
- Only the macOS build is provided. Windows users follow the manual setup in the main README.
