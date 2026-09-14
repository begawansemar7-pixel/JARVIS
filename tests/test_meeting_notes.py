import json
import threading
from datetime import datetime, timedelta

import pytest

from actions import meeting_notes as action
from core.action_loader import _validate
from integrations import meeting_notes as mn
from integrations.meeting_notes import REDACTED, MeetingError, MeetingRecorder, MeetingSettings
from integrations.notion import MAX_TEXT_LENGTH, NotionClient, NotionError, Target, normalize_id, rich_text


# -- fakes ------------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.content = json.dumps(self._body).encode()
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


class FakeNotion:
    """In-memory stand-in for NotionClient used by the recorder tests."""

    def __init__(self, fail_appends=0):
        self.pages = []
        self.blocks = {}          # page_id -> list of (id, block)
        self.deleted = []
        self.callouts = {}
        self.fail_appends = fail_appends
        self._ids = iter(f"b{i}" for i in range(10_000))
        self.lock = threading.Lock()

    def create_page(self, target, title, when_iso=None):
        page = {"id": f"page{len(self.pages)}", "url": f"https://notion.so/page{len(self.pages)}", "title": title}
        self.pages.append(page)
        self.blocks[page["id"]] = []
        return page

    def append_blocks(self, block_id, blocks, after=None):
        with self.lock:
            if self.fail_appends:
                self.fail_appends -= 1
                raise NotionError("Notion PATCH /blocks failed (503)", status=503)
            created = [{"id": next(self._ids), **b} for b in blocks]
            items = self.blocks[block_id]
            if after:
                index = next(i for i, (bid, _) in enumerate(items) if bid == after) + 1
                items[index:index] = [(c["id"], c) for c in created]
            else:
                items.extend((c["id"], c) for c in created)
            return created

    def delete_block(self, block_id):
        self.deleted.append(block_id)
        for items in self.blocks.values():
            items[:] = [(bid, b) for bid, b in items if bid != block_id]

    def update_callout(self, block_id, text, emoji):
        self.callouts[block_id] = (text, emoji)

    def texts(self, page_id):
        out = []
        for _, b in self.blocks[page_id]:
            body = b[b["type"]]
            out.append((b["type"], "".join(r["text"]["content"] for r in body.get("rich_text", []))))
        return out


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 14, 9, 0)

    def __call__(self):
        self.now += timedelta(minutes=1)
        return self.now


def make_recorder(tmp_path, notion=None, summarizer=None, **settings):
    notion = notion or FakeNotion()
    cfg = MeetingSettings(flush_interval_seconds=settings.get("flush_interval_seconds", 3600),
                          flush_min_turns=settings.get("flush_min_turns", 100),
                          backup_dir=tmp_path / "Meetings")
    summarizer = summarizer or (lambda transcript, lang: {
        "summary": "Agreed to pilot the data center.", "decisions": ["Pilot 30MW"],
        "action_items": ["Draft term sheet — Budi — Friday"]})
    rec = MeetingRecorder(cfg, lambda: (notion, Target("page", "p")), summarizer, clock=Clock())
    return rec, notion


# -- Notion client ----------------------------------------------------------------------

def test_normalize_id_accepts_urls_and_uuids():
    raw = "0123456789abcdef0123456789abcdef"
    expected = "01234567-89ab-cdef-0123-456789abcdef"
    assert normalize_id(raw) == expected
    assert normalize_id(f"https://www.notion.so/Meeting-Notes-{raw}?v=abc") == expected
    assert normalize_id(expected.upper()) == expected
    with pytest.raises(ValueError):
        normalize_id("not an id")


def test_rich_text_splits_at_notion_limit():
    parts = rich_text("x" * (MAX_TEXT_LENGTH * 2 + 5))
    assert [len(p["text"]["content"]) for p in parts] == [MAX_TEXT_LENGTH, MAX_TEXT_LENGTH, 5]


def test_client_sends_auth_and_version_and_retries_rate_limit():
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "0"}), FakeResponse(200, {"id": "page1"})])
    sleeps = []
    client = NotionClient("secret-token", session=session, sleep=sleeps.append)
    page = client.create_page(Target("page", "p1"), "Weekly review")
    assert page["id"] == "page1" and sleeps == [0.0] and len(session.calls) == 2
    call = session.calls[-1]
    assert call["headers"]["Authorization"] == "Bearer secret-token"
    assert call["headers"]["Notion-Version"] == "2022-06-28"
    assert call["json"]["parent"] == {"page_id": "p1"}


def test_client_errors_do_not_leak_token():
    session = FakeSession([FakeResponse(401, {"code": "unauthorized", "message": "API token is invalid."})])
    with pytest.raises(NotionError) as exc:
        NotionClient("secret-token", session=session).append_blocks("b", [{"type": "divider", "divider": {}}])
    assert exc.value.status == 401 and "secret-token" not in str(exc.value)


def test_database_target_uses_title_and_date_properties():
    schema = {"properties": {"Name": {"type": "title"}, "When": {"type": "date"}, "Tags": {"type": "multi_select"}}}
    session = FakeSession([FakeResponse(200, schema), FakeResponse(200, {"id": "page1"})])
    NotionClient("t", session=session).create_page(Target("database", "db1"), "Standup", "2026-09-14T09:00+07:00")
    body = session.calls[-1]["json"]
    assert body["parent"] == {"database_id": "db1"}
    assert set(body["properties"]) == {"Name", "When"}


def test_resolve_target_falls_back_to_page_on_404():
    raw = "0123456789abcdef0123456789abcdef"
    session = FakeSession([FakeResponse(404, {"code": "object_not_found", "message": "no"})])
    assert NotionClient("t", session=session).resolve_target(raw).kind == "page"


def test_append_blocks_chunks_by_100_and_keeps_order_after_anchor():
    blocks = [{"type": "divider", "divider": {}}] * 150
    session = FakeSession([FakeResponse(200, {"results": [{"id": f"a{i}"} for i in range(100)]}),
                           FakeResponse(200, {"results": [{"id": f"c{i}"} for i in range(50)]})])
    created = NotionClient("t", session=session).append_blocks("page", blocks, after="heading")
    assert len(created) == 150
    assert [len(c["json"]["children"]) for c in session.calls] == [100, 50]
    assert session.calls[0]["json"]["after"] == "heading" and session.calls[1]["json"]["after"] == "a99"


# -- recorder ---------------------------------------------------------------------------

def test_nothing_recorded_until_started(tmp_path):
    rec, notion = make_recorder(tmp_path)
    rec.add_exchange("hello", "hi")
    assert notion.pages == [] and not rec.active


def test_full_meeting_lifecycle(tmp_path):
    rec, notion = make_recorder(tmp_path)
    m = rec.start("Weekly OKR review", lang="Indonesian")
    rec.add_exchange("Status proyek data center?", "Pilot 30MW sesuai jadwal.")
    rec.add_exchange("Siapa buat term sheet?", "Budi, Jumat ini.")
    result = rec.stop()

    assert result["turns"] == 4 and result["action_items"] == 1 and result["errors"] == []
    texts = notion.texts(m.page_id)
    kinds = [k for k, _ in texts]
    assert kinds[:2] == ["callout", "heading_2"]                    # summary lands under the Summary heading
    assert ("paragraph", "Agreed to pilot the data center.") in texts
    assert ("to_do", "Draft term sheet — Budi — Friday") in texts
    assert ("paragraph", "Ringkasan akan muncul saat rapat selesai.") not in texts  # placeholder removed
    summary_pos = texts.index(("paragraph", "Agreed to pilot the data center."))
    transcript_pos = texts.index(("heading_2", "Transkrip"))
    assert summary_pos < transcript_pos
    assert any("Anda: " in t and "Status proyek" in t for _, t in texts[transcript_pos:])
    assert "✅" in next(iter(notion.callouts.values()))[1]
    backup = (tmp_path / "Meetings").glob("*.md")
    content = next(backup).read_text()
    assert "Pilot 30MW sesuai jadwal." in content and "- [ ] Draft term sheet" in content
    assert not rec.active


def test_private_brain_exchange_is_redacted_everywhere(tmp_path):
    seen = {}

    def summarizer(transcript, lang):
        seen["transcript"] = transcript
        return {"summary": "ok", "decisions": [], "action_items": []}

    rec, notion = make_recorder(tmp_path, summarizer=summarizer)
    m = rec.start("Strategy")
    rec.note_tool("private_brain")
    rec.add_exchange("What does the merger file say?", "The target is NusantaraNet at 2 trillion.")
    rec.note_tool("web_search")
    rec.add_exchange("Weather tomorrow?", "Sunny.")
    rec.stop()

    all_text = " ".join(t for _, t in notion.texts(m.page_id))
    assert "NusantaraNet" not in all_text and "merger file" not in all_text
    assert all_text.count(REDACTED) == 2 and "Sunny." in all_text
    assert "NusantaraNet" not in seen["transcript"] and "Sunny." in seen["transcript"]
    assert "NusantaraNet" not in next((tmp_path / "Meetings").glob("*.md")).read_text()


def test_sensitive_flag_does_not_leak_into_next_exchange(tmp_path):
    rec, notion = make_recorder(tmp_path)
    m = rec.start("t")
    rec.note_tool("private_brain")
    rec.add_exchange("secret q", "secret a")
    rec.add_exchange("public q", "public a")
    rec.flush()
    texts = [t for _, t in notion.texts(m.page_id)]
    assert any("public a" in t for t in texts)


def test_notion_outage_keeps_turns_and_retries(tmp_path):
    rec, notion = make_recorder(tmp_path, notion=FakeNotion())
    m = rec.start("t")
    notion.fail_appends = 1
    rec.add_exchange("q1", "a1")
    assert rec.flush() == 0 and "503" in m.last_error and m.flushed == 0
    assert rec.flush() == 2 and m.flushed == 2 and m.last_error == ""


def test_stop_reports_unsent_turns_and_keeps_local_copy(tmp_path):
    notion = FakeNotion()
    rec, _ = make_recorder(tmp_path, notion=notion)
    rec.start("t")
    rec.add_exchange("q1", "a1")
    notion.fail_appends = 99
    result = rec.stop()
    assert any("could not be sent" in e for e in result["errors"])
    assert "a1" in next((tmp_path / "Meetings").glob("*.md")).read_text()


def test_background_flusher_sends_without_caller_waiting(tmp_path):
    rec, notion = make_recorder(tmp_path, flush_interval_seconds=0.05, flush_min_turns=1)
    m = rec.start("t")
    rec.add_exchange("q", "a")
    for _ in range(100):
        if m.flushed == 2:
            break
        threading.Event().wait(0.02)
    assert m.flushed == 2
    rec.stop()


def test_cannot_start_twice_and_stop_without_meeting(tmp_path):
    rec, _ = make_recorder(tmp_path)
    rec.start("one")
    with pytest.raises(MeetingError):
        rec.start("two")
    rec.stop()
    with pytest.raises(MeetingError):
        rec.stop()


def test_start_failure_is_reported_and_leaves_no_meeting(tmp_path):
    cfg = MeetingSettings(backup_dir=tmp_path)

    def connect():
        raise NotionError("Notion POST /pages failed (404) object_not_found", status=404)

    rec = MeetingRecorder(cfg, connect)
    with pytest.raises(MeetingError, match="404"):
        rec.start("t")
    assert not rec.active and not rec._starting   # a later start is not blocked


def test_backup_file_is_private(tmp_path):
    rec, _ = make_recorder(tmp_path)
    m = rec.start("t")
    assert (m.backup_path.stat().st_mode & 0o777) == 0o600
    rec.stop()


# -- action -----------------------------------------------------------------------------

def test_action_contract_and_flow(tmp_path, monkeypatch):
    assert _validate(action, "meeting_notes.py").valid
    rec, notion = make_recorder(tmp_path)
    monkeypatch.setattr(action, "get_recorder", lambda: rec)
    monkeypatch.setattr(action, "_language", lambda: "Indonesian")
    assert action.meeting_notes({"operation": "status"}) == "No meeting is being recorded."
    assert action.meeting_notes({"operation": "start", "title": "Board prep"}).startswith("Recording started")
    rec.add_exchange("q", "a")
    assert "Recording 'Board prep'" in action.meeting_notes({"operation": "status"})
    out = action.meeting_notes({"operation": "stop"})
    assert "1 action item" in out and "Agreed to pilot" in out


def test_action_reports_missing_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr("memory.config_manager.load_api_keys", lambda: {})
    rec = MeetingRecorder(MeetingSettings(backup_dir=tmp_path), mn.notion_connect)
    monkeypatch.setattr(action, "get_recorder", lambda: rec)
    out = action.meeting_notes({"operation": "start"})
    assert "Notion is not configured" in out
