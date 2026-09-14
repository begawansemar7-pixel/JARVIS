#!/bin/bash
# Build JARVIS.app and a distributable DMG for macOS.
#
#   installer/macos/build_dmg.sh [git-ref]        # default: HEAD
#
# Only files tracked by git at <ref> are packaged (`git archive`), so local
# secrets (config/api_keys.json), memory, virtualenvs and caches never ship.
#
# Optional environment:
#   UV_BIN            uv binary to bundle (default: `command -v uv`)
#   BUNDLE_ID         default: id.kohenri.jarvis
#   SIGN_IDENTITY     "Developer ID Application: …" for real signing (default: ad-hoc "-")
#   NOTARY_PROFILE    notarytool keychain profile; when set, the DMG is notarized and stapled
#   OUT_DIR           default: <repo>/dist

set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
HERE="$ROOT/installer/macos"
REF="${1:-HEAD}"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
BUNDLE_ID="${BUNDLE_ID:-id.kohenri.jarvis}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"

git -C "$ROOT" rev-parse --verify --quiet "$REF^{commit}" >/dev/null || { echo "Unknown git ref: $REF" >&2; exit 1; }
[ -n "$UV_BIN" ] && [ -x "$UV_BIN" ] || { echo "uv not found; install it or set UV_BIN" >&2; exit 1; }

SHORT_SHA="$(git -C "$ROOT" rev-parse --short "$REF")"
VERSION="$(date +%Y.%m.%d)"
BUILD="$(git -C "$ROOT" rev-list --count "$REF")"
FULL_VERSION="$VERSION+$SHORT_SHA"
ARCH="$(file -b "$UV_BIN" | grep -o 'arm64\|x86_64' | head -1)"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/dmg/JARVIS.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/app" "$APP/Contents/Resources/bin"

echo "==> Packaging $REF ($FULL_VERSION)"
git -C "$ROOT" archive --format=tar "$REF" | tar -x -C "$APP/Contents/Resources/app"
rm -rf "$APP/Contents/Resources/app/installer" "$APP/Contents/Resources/app/.github" "$APP/Contents/Resources/app/tests"
echo "$FULL_VERSION" >"$APP/Contents/Resources/app/.jarvis_version"

# Refuse to ship anything that looks like a secret or personal data.
LEAKS="$(cd "$APP/Contents/Resources/app" && find . \( -name 'api_keys.json' -o -name '*.env' -o -name 'long_term.json' \
  -o -path './memory/private_brain*' -o -path './config/certs*' -o -name '.venv' \) -print)"
if [ -n "$LEAKS" ]; then
  echo "Refusing to build: sensitive files in package:" >&2
  echo "$LEAKS" >&2
  exit 1
fi

install -m 0755 "$HERE/launcher.sh" "$APP/Contents/MacOS/JARVIS"
install -m 0644 "$HERE/user-data.rsync-filter" "$APP/Contents/Resources/user-data.rsync-filter"
install -m 0755 "$UV_BIN" "$APP/Contents/Resources/bin/uv"
sed -e "s/@BUNDLE_ID@/$BUNDLE_ID/" -e "s/@VERSION@/$VERSION/" -e "s/@BUILD@/$BUILD/" \
  "$HERE/Info.plist.template" >"$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" >/dev/null

echo "==> Icon"
ICONSET="$STAGE/JARVIS.iconset"
mkdir -p "$ICONSET"
sips -s format png "$ROOT/config/jarvis.ico" --out "$STAGE/icon.png" >/dev/null
for size in 16 32 64 128 256 512; do
  sips -z "$size" "$size" "$STAGE/icon.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  half=$((size / 2))
  [ "$half" -ge 16 ] && cp "$ICONSET/icon_${size}x${size}.png" "$ICONSET/icon_${half}x${half}@2x.png"
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/JARVIS.icns"

echo "==> Signing ($([ "$SIGN_IDENTITY" = "-" ] && echo ad-hoc || echo "$SIGN_IDENTITY"))"
SIGN_ARGS=(--force --timestamp=none -s "$SIGN_IDENTITY")
[ "$SIGN_IDENTITY" != "-" ] && SIGN_ARGS=(--force --options runtime --timestamp -s "$SIGN_IDENTITY")
codesign "${SIGN_ARGS[@]}" "$APP/Contents/Resources/bin/uv"
codesign "${SIGN_ARGS[@]}" "$APP"
codesign --verify --strict "$APP"

echo "==> DMG"
ln -s /Applications "$STAGE/dmg/Applications"
cat >"$STAGE/dmg/Read Me First.txt" <<EOF
JARVIS $FULL_VERSION — created by Ko Henri

INSTALL
1. Drag JARVIS into the Applications folder.
2. Open Applications, right-click JARVIS and choose Open (first time only:
   this build is not notarized by Apple, so macOS asks for confirmation).
3. First launch downloads Python and JARVIS components (about 5 minutes,
   internet required). You will see notifications while it works.
4. Enter your Gemini API key when JARVIS asks, and allow microphone access.

WHERE THINGS LIVE
  App code & Python : ~/Library/Application Support/JARVIS
  Logs              : ~/Library/Logs/JARVIS
  Your settings, API key and memory are kept when you install a newer version.

UNINSTALL
  Delete /Applications/JARVIS.app, then (to remove all data)
  ~/Library/Application Support/JARVIS and ~/Library/Logs/JARVIS.

Requirements: macOS 12 or newer. Built for $ARCH (other Macs download a
matching Python manager on first launch).
EOF

mkdir -p "$OUT_DIR"
DMG="$OUT_DIR/JARVIS-$VERSION-$SHORT_SHA-macOS.dmg"
rm -f "$DMG"
hdiutil create -volname "JARVIS" -srcfolder "$STAGE/dmg" -ov -format UDZO -quiet "$DMG"
[ "$SIGN_IDENTITY" != "-" ] && codesign --force --timestamp -s "$SIGN_IDENTITY" "$DMG"

if [ -n "${NOTARY_PROFILE:-}" ]; then
  [ "$SIGN_IDENTITY" != "-" ] || { echo "Notarization requires SIGN_IDENTITY" >&2; exit 1; }
  echo "==> Notarizing"
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi

shasum -a 256 "$DMG" | tee "$DMG.sha256"
echo "==> Built $DMG ($(du -h "$DMG" | cut -f1))"
