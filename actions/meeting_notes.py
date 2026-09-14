"""Meeting notes to Notion, started and stopped only on the user's request.

Side-effect class A3 (AGENTS.md §9): the conversation transcript and an AI summary
are sent to the user's Notion workspace, a third-party service. Recording never
starts by itself; the user explicitly asks for it, and JARVIS says out loud that it
is recording. Exchanges that used a sensitive tool (Private Brain) are redacted.
"""
from __future__ import annotations

from integrations.meeting_notes import MeetingError, get_recorder


def _language() -> str:
    try:
        from memory.memory_manager import load_memory

        entry = load_memory().get("identity", {}).get("language", {})
        return (entry.get("value", "") if isinstance(entry, dict) else str(entry)).strip()
    except Exception:
        return ""


def _log(player, text: str) -> None:
    if player:
        try:
            player.write_log(f"SYS: {text}")
        except Exception:
            pass


def meeting_notes(parameters: dict, player=None) -> str:
    params = parameters or {}
    operation = str(params.get("operation") or "status").strip().lower()
    recorder = get_recorder()
    try:
        if operation == "start":
            m = recorder.start(title=str(params.get("title") or ""), lang=_language())
            _log(player, f"Meeting notes recording to Notion: {m.title}")
            return (f"Recording started: '{m.title}'. Every exchange from now on is written to Notion. "
                    "Tell the user in one short sentence, in their language, that you are now taking "
                    "meeting notes in Notion and they can say stop when finished.")
        if operation == "stop":
            result = recorder.stop()
            _log(player, f"Meeting notes saved: {result['title']} ({result['turns']} turns)")
            lines = [f"Recording stopped. '{result['title']}' saved to Notion with {result['turns']} "
                     f"transcript lines and {result['action_items']} action item(s)."]
            if result["summary"]:
                lines.append(f"Summary: {result['summary']}")
            if result["errors"]:
                lines.append("Problems: " + "; ".join(result["errors"]) + f". Local copy: {result['backup']}")
            lines.append("Tell the user briefly; do not read the Notion link aloud.")
            return "\n".join(lines)
        if operation == "status":
            m = recorder.meeting
            if m is None:
                return "No meeting is being recorded."
            status = f"Recording '{m.title}' since {m.started_at:%H:%M}: {len(m.turns)} lines, {m.flushed} in Notion."
            if m.last_error:
                status += f" Last Notion error: {m.last_error}"
            return status
        return f"Unknown operation '{operation}'. Use start, stop or status."
    except MeetingError as e:
        return f"Meeting notes: {e}"
    except Exception as e:
        print(f"[MeetingNotes] {operation} failed: {type(e).__name__}: {e}")
        return f"Meeting notes {operation} failed ({type(e).__name__})."


TOOL = {
    "name": "meeting_notes",
    "description": (
        "Records the conversation as meeting notes in the user's Notion workspace, only when the user asks. "
        "operation=start when they say 'mulai catat rapat', 'catat meeting ini ke Notion', 'start meeting "
        "notes' (optional title); operation=stop when they say 'selesai catat', 'stop recording', 'rapat "
        "selesai' — this writes the summary, decisions and action items; operation=status to check. Never "
        "start recording on your own initiative. While recording, parts that used private_brain are redacted."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "description": "start | stop | status"},
            "title": {"type": "STRING", "description": "start: meeting title, e.g. 'Weekly OKR review'."},
        },
        "required": ["operation"],
    },
    "handler": meeting_notes,
}
