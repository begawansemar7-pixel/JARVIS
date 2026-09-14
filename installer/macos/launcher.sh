#!/bin/bash
# JARVIS.app launcher (Contents/MacOS/JARVIS).
#
# The bundle is read-only. On launch the app code is synced to
#   ~/Library/Application Support/JARVIS/app
# (preserving user data such as config/api_keys.json and memory), a Python 3.12
# environment is prepared once with the bundled `uv`, and JARVIS is exec'd from
# there so macOS attributes microphone/camera permission prompts to JARVIS.app.
#
# Environment overrides (mainly for testing and repair):
#   JARVIS_SUPPORT_DIR   where the app, venv and Python live
#   JARVIS_LOG_DIR       where setup.log and jarvis.log go
#   JARVIS_SETUP_ONLY=1  prepare everything, then exit without starting JARVIS
#   JARVIS_NO_DIALOGS=1  no notifications/dialogs (headless)

set -uo pipefail

# LaunchServices may start a script-based app under Rosetta on Apple Silicon. The
# x86_64 preference is inherited by child processes, so `uname -p` then reports
# i386 and libraries such as rubicon-objc (used by pyautogui) break. Re-run the
# launcher natively before doing anything else.
if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = "1" ] && [ -z "${JARVIS_NATIVE_REEXEC:-}" ]; then
  export JARVIS_NATIVE_REEXEC=1
  exec /usr/bin/arch -arm64 /bin/bash "$0" "$@"
fi

RES_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
SUPPORT="${JARVIS_SUPPORT_DIR:-$HOME/Library/Application Support/JARVIS}"
LOGS="${JARVIS_LOG_DIR:-$HOME/Library/Logs/JARVIS}"
APP_DIR="$SUPPORT/app"
VENV="$SUPPORT/venv"
SETUP_LOG="$LOGS/setup.log"
PYTHON_VERSION="3.12"

mkdir -p "$SUPPORT" "$LOGS"
chmod 700 "$SUPPORT" 2>/dev/null || true

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$SETUP_LOG"; }

notify() {
  [ "${JARVIS_NO_DIALOGS:-}" = "1" ] && return 0
  osascript -e "display notification \"$1\" with title \"JARVIS\"" >/dev/null 2>&1 || true
}

fail() {
  log "ERROR: $1"
  if [ "${JARVIS_NO_DIALOGS:-}" != "1" ]; then
    osascript -e "display dialog \"JARVIS could not start: $1

Details are in:
$SETUP_LOG\" buttons {\"OK\"} default button 1 with icon stop with title \"JARVIS\"" >/dev/null 2>&1 || true
  fi
  exit 1
}

# One launcher at a time (a second click during first-time setup must not race).
LOCK="$SUPPORT/.launch.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rm -rf "$LOCK" && mkdir "$LOCK" || fail "another launch is in progress"
  else
    notify "JARVIS is already starting..."
    exit 0
  fi
fi
trap 'rm -rf "$LOCK"' EXIT

# ── 1. App code ───────────────────────────────────────────────────────────────
BUNDLE_VERSION="$(cat "$RES_DIR/app/.jarvis_version" 2>/dev/null || echo unknown)"
INSTALLED_VERSION="$(cat "$SUPPORT/.installed_version" 2>/dev/null || echo none)"
if [ "${BUNDLE_VERSION}" != "${INSTALLED_VERSION}" ] || [ ! -f "$APP_DIR/main.py" ]; then
  log "Installing app code ${BUNDLE_VERSION} (was ${INSTALLED_VERSION})"
  notify "Installing JARVIS ${BUNDLE_VERSION}..."
  mkdir -p "$APP_DIR"
  # User data is protected by the filter file: excluded paths are never deleted.
  rsync -a --delete --filter="merge $RES_DIR/user-data.rsync-filter" \
    "$RES_DIR/app/" "$APP_DIR/" >>"$SETUP_LOG" 2>&1 || fail "copying the application files failed"
  echo "${BUNDLE_VERSION}" >"$SUPPORT/.installed_version"
fi

# ── 2. uv (Python manager) ────────────────────────────────────────────────────
UV="$RES_DIR/bin/uv"
if ! "$UV" --version >/dev/null 2>&1; then
  UV="$SUPPORT/bin/uv"
  if ! "$UV" --version >/dev/null 2>&1; then
    UV="$(command -v uv 2>/dev/null || true)"
  fi
  if [ -z "$UV" ] || ! "$UV" --version >/dev/null 2>&1; then
    log "Bundled uv is not runnable on $(uname -m); downloading uv"
    notify "Downloading the Python manager for this Mac..."
    mkdir -p "$SUPPORT/bin"
    curl -LsSf https://astral.sh/uv/install.sh | \
      env UV_INSTALL_DIR="$SUPPORT/bin" UV_NO_MODIFY_PATH=1 sh >>"$SETUP_LOG" 2>&1 \
      || fail "downloading uv failed (check the internet connection)"
    UV="$SUPPORT/bin/uv"
  fi
fi

# ── 3. Python environment and dependencies ────────────────────────────────────
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$SUPPORT/python}"
REQ_HASH="$(shasum -a 256 "$APP_DIR/requirements.txt" | cut -d' ' -f1)"
if [ ! -x "$VENV/bin/python" ] || [ "$(cat "$SUPPORT/.requirements.sha256" 2>/dev/null)" != "$REQ_HASH" ]; then
  log "Preparing Python $PYTHON_VERSION environment"
  notify "First-time setup: downloading Python and components. This takes a few minutes..."
  if [ ! -x "$VENV/bin/python" ]; then
    "$UV" venv --seed --python "$PYTHON_VERSION" "$VENV" >>"$SETUP_LOG" 2>&1 \
      || fail "creating the Python environment failed (check the internet connection)"
  fi
  "$UV" pip install --python "$VENV/bin/python" -r "$APP_DIR/requirements.txt" >>"$SETUP_LOG" 2>&1 \
    || fail "installing JARVIS components failed (check the internet connection)"
  # Browser automation engine: useful but optional — never block startup on it.
  "$VENV/bin/python" -m playwright install chromium >>"$SETUP_LOG" 2>&1 \
    || log "WARNING: Playwright Chromium install failed; browser control will be unavailable"
  echo "$REQ_HASH" >"$SUPPORT/.requirements.sha256"
  log "Setup complete"
  notify "Setup complete. Starting JARVIS..."
fi

if [ "${JARVIS_SETUP_ONLY:-}" = "1" ]; then
  log "Setup-only run finished"
  exit 0
fi

# ── 4. Start JARVIS ───────────────────────────────────────────────────────────
rm -rf "$LOCK"
trap - EXIT
cd "$APP_DIR" || fail "application folder is missing"
# JARVIS writes its key file world-readable; keep secrets private to this user.
[ -f "$APP_DIR/config/api_keys.json" ] && chmod 600 "$APP_DIR/config/api_keys.json"
export PYTHONUNBUFFERED=1
log "Starting JARVIS ${BUNDLE_VERSION} (arch $(uname -m), processor $(uname -p), translated=$(sysctl -n sysctl.proc_translated 2>/dev/null || echo n/a))"
exec "$VENV/bin/python" "$APP_DIR/main.py" >>"$LOGS/jarvis.log" 2>&1
