import sys

import pytest

from core import app_identity


def test_noop_outside_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert app_identity.apply_native_identity() is False


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS bundle identity")
def test_macos_bundle_name_becomes_jarvis():
    Foundation = pytest.importorskip("Foundation")
    assert app_identity.apply_native_identity() is True
    assert Foundation.NSBundle.mainBundle().infoDictionary()["CFBundleName"] == "JARVIS"


def test_qt_identity_sets_names_and_ignores_missing_icon(tmp_path):
    class FakeApp:
        def __init__(self):
            self.calls = {}

        def setApplicationName(self, value):
            self.calls["name"] = value

        def setApplicationDisplayName(self, value):
            self.calls["display"] = value

        def setWindowIcon(self, icon):  # pragma: no cover - must not be called
            self.calls["icon"] = icon

    app = FakeApp()
    app_identity.apply_qt_identity(app, icon_path=tmp_path / "missing.ico")
    assert app.calls == {"name": "JARVIS", "display": "JARVIS"}
