"""Minimal Notion REST client for JARVIS meeting notes.

Uses an internal integration token (https://www.notion.so/profile/integrations).
The target page or database must be shared with the integration
(page menu → Connections → add the integration).

Handles the API limits that matter here: 100 blocks per append request,
2 000 characters per rich-text item, and HTTP 429 rate limiting (Retry-After).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MAX_BLOCKS_PER_REQUEST = 100
MAX_TEXT_LENGTH = 2000
_ID_RE = re.compile(r"([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


class NotionError(Exception):
    """A Notion request failed; the message is safe to show (never contains the token)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def normalize_id(value: str) -> str:
    """Accept a raw id, a dashed UUID or a Notion URL and return a dashed UUID."""
    matches = _ID_RE.findall(str(value or ""))
    if not matches:
        raise ValueError("not a Notion page or database id")
    raw = (matches[-1][0] or matches[-1][1]).replace("-", "").lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


# -- block builders -------------------------------------------------------------------

def rich_text(text: str, bold: bool = False) -> list[dict]:
    text = str(text or "")
    parts = [text[i:i + MAX_TEXT_LENGTH] for i in range(0, len(text), MAX_TEXT_LENGTH)] or [""]
    return [{"type": "text", "text": {"content": part}, "annotations": {"bold": bold}} for part in parts]


def paragraph(text: str, bold_prefix: str = "") -> dict:
    content = (rich_text(bold_prefix, bold=True) if bold_prefix else []) + rich_text(text)
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": content}}


def heading(text: str, level: int = 2) -> dict:
    kind = f"heading_{max(1, min(3, level))}"
    return {"object": "block", "type": kind, kind: {"rich_text": rich_text(text)}}


def bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_text(text)}}


def todo(text: str, checked: bool = False) -> dict:
    return {"object": "block", "type": "to_do", "to_do": {"rich_text": rich_text(text), "checked": checked}}


def callout(text: str, emoji: str = "🎙️") -> dict:
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": rich_text(text), "icon": {"type": "emoji", "emoji": emoji}}}


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


# -- client ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Target:
    kind: str   # "page" | "database"
    id: str


class NotionClient:
    def __init__(self, token: str, session=None, max_retries: int = 3, sleep=time.sleep):
        if not token or not str(token).strip():
            raise ValueError("Notion token is missing")
        if session is None:
            import requests
            session = requests.Session()
        self._token = str(token).strip()
        self._session = session
        self._max_retries = max_retries
        self._sleep = sleep

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.request(method, f"{API_BASE}{path}", headers=headers, json=json, timeout=30)
            except Exception as e:
                raise NotionError(f"could not reach Notion ({type(e).__name__})") from None
            if response.status_code == 429 and attempt < self._max_retries:
                self._sleep(float(response.headers.get("Retry-After", 1)))
                continue
            if response.status_code >= 500 and attempt < self._max_retries:
                self._sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                try:
                    body = response.json()
                    detail = f"{body.get('code', '')}: {body.get('message', '')}".strip(": ")
                except ValueError:
                    detail = response.text[:200]
                raise NotionError(f"Notion {method} {path.split('?')[0]} failed ({response.status_code}) {detail}",
                                  status=response.status_code)
            return response.json() if response.content else {}
        raise NotionError("Notion rate limit persisted; try again later")

    # -- API ------------------------------------------------------------------
    def resolve_target(self, value: str) -> Target:
        """A shared database becomes a database target; anything else is treated as a page."""
        target_id = normalize_id(value)
        try:
            self.retrieve_database(target_id)
            return Target("database", target_id)
        except NotionError as e:
            if e.status in (400, 404):
                return Target("page", target_id)
            raise

    def retrieve_database(self, database_id: str) -> dict:
        return self._request("GET", f"/databases/{database_id}")

    def create_page(self, target: Target, title: str, when_iso: str | None = None) -> dict:
        if target.kind == "database":
            schema = self.retrieve_database(target.id).get("properties", {})
            title_prop = next((name for name, p in schema.items() if p.get("type") == "title"), None)
            if not title_prop:
                raise NotionError("the Notion database has no title property")
            properties = {title_prop: {"title": rich_text(title)}}
            date_prop = next((name for name, p in schema.items() if p.get("type") == "date"), None)
            if date_prop and when_iso:
                properties[date_prop] = {"date": {"start": when_iso}}
            parent = {"database_id": target.id}
        else:
            properties = {"title": {"title": rich_text(title)}}
            parent = {"page_id": target.id}
        return self._request("POST", "/pages", {"parent": parent, "properties": properties,
                                               "icon": {"type": "emoji", "emoji": "🎙️"}})

    def append_blocks(self, block_id: str, blocks: list[dict], after: str | None = None) -> list[dict]:
        """Append in chunks of 100; returns the created blocks in order."""
        created: list[dict] = []
        anchor = after
        for start in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            body = {"children": blocks[start:start + MAX_BLOCKS_PER_REQUEST]}
            if anchor:
                body["after"] = anchor
            results = self._request("PATCH", f"/blocks/{block_id}/children", body).get("results", [])
            created.extend(results)
            if anchor and results:
                anchor = results[-1].get("id", anchor)   # keep later chunks in order
        return created

    def delete_block(self, block_id: str) -> None:
        self._request("DELETE", f"/blocks/{block_id}")

    def update_callout(self, block_id: str, text: str, emoji: str) -> None:
        self._request("PATCH", f"/blocks/{block_id}",
                      {"callout": {"rich_text": rich_text(text), "icon": {"type": "emoji", "emoji": emoji}}})


__all__ = ["NotionClient", "NotionError", "Target", "bullet", "callout", "divider", "heading",
           "normalize_id", "paragraph", "rich_text", "todo"]
