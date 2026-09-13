from pathlib import Path

from engineering.code_intelligence import rank_context, scan_repository
from engineering.model_router import choose
from engineering.memory import create_session, add_event


def test_code_intelligence_finds_python_symbols(tmp_path: Path):
    src = tmp_path / "actions" / "demo.py"
    src.parent.mkdir()
    src.write_text("import json\n\ndef dev_agent(x):\n    return x\n", encoding="utf-8")
    inventory = scan_repository(tmp_path)
    assert inventory
    assert "dev_agent" in inventory[0].symbols
    ranked = rank_context(inventory, "fix dev_agent")
    assert ranked[0]["path"] == "actions/demo.py"


def test_model_router_is_deterministic():
    assert choose("classify symbols").tier == "fast"
    assert choose("redesign architecture and security boundary", risk="high").tier == "reasoning"
    assert choose("implement a small feature").tier == "standard"


def test_engineering_memory_session():
    session = create_session("/tmp/jarvis-test", "fix bug", "plan", "gemini-flash-latest")
    add_event(session, "planned", files=["a.py"])
    assert session["status"] == "running"
    assert session["events"][-1]["event"] == "planned"
