"""Present the running process as "JARVIS" instead of "python".

JARVIS runs on a regular Python interpreter, so macOS takes the menu-bar name
from the interpreter's bundle. Overwriting CFBundleName in the main bundle's
info dictionary *before* the NSApplication (i.e. QApplication) is created makes
the menu bar, the application menu and "Quit" show JARVIS. The Qt side then sets
the application/display name and the Dock icon.

Everything here is best-effort: on other platforms, or when PyObjC is missing,
it silently does nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "JARVIS"


def apply_native_identity(name: str = APP_NAME) -> bool:
    """Call before QApplication is constructed. Returns True when applied."""
    if sys.platform != "darwin":
        return False
    try:
        from Foundation import NSBundle
    except ImportError:
        return False
    bundle = NSBundle.mainBundle()
    applied = False
    for info in (bundle.localizedInfoDictionary(), bundle.infoDictionary()):
        if info is None:
            continue
        try:
            info["CFBundleName"] = name
            info["CFBundleDisplayName"] = name
            applied = True
        except (TypeError, ValueError, AttributeError):  # immutable on some Python builds
            continue
    return applied


def apply_qt_identity(app, name: str = APP_NAME, icon_path: Path | None = None) -> None:
    """Call right after QApplication is constructed."""
    app.setApplicationName(name)
    app.setApplicationDisplayName(name)
    if icon_path is not None and Path(icon_path).is_file():
        from PyQt6.QtGui import QIcon

        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)  # also becomes the Dock icon on macOS


__all__ = ["APP_NAME", "apply_native_identity", "apply_qt_identity"]
