# JARVIS Private Brain / Confidential Knowledge Fabric

The Private Brain is JARVIS's policy-first knowledge boundary for internal and confidential information.

## Security model

- `PUBLIC` — unrestricted knowledge.
- `INTERNAL` — organization-only knowledge.
- `CONFIDENTIAL` — sensitive business information.
- `SECRET` — highly restricted strategic information.
- `TOP_SECRET` — crown-jewel information; private-runtime only.

Retrieval must apply authorization **before** context is passed to an LLM. Classification is not a substitute for encryption, identity, network controls, or organizational policy.

## Intended flow

```text
Document -> classify -> encrypt/store -> chunk/embed -> ACL-filtered retrieval -> policy check -> LLM
```

The first implementation provides the policy primitives in `knowledge/private_brain.py`. A production deployment should connect these primitives to an encrypted object store, vector database, KMS/secrets manager, identity provider, DLP layer, and immutable audit log.

## Runtime integration

JARVIS uses the Private Brain through the `private_brain` action (`actions/private_brain.py`), which the action loader discovers automatically.

| Operation | Side effect | Behaviour |
|---|---|---|
| `search` | A0 | ACL filter → local decrypt → keyword scoring → cloud boundary → provenance-tagged excerpts |
| `list` | A0 | Authorized documents; titles above the cloud limit are withheld |
| `ingest` | A2 | Stores a UTF-8 text file (≤ 2 MB) encrypted; undoable via `core/undo` |
| `forget` | A2 | Irreversible delete, only after on-screen confirmation (`core/confirm`) |

| Module | Responsibility |
|---|---|
| `config.py` | Loads and validates `config/private_brain.json` (the single source of policy) |
| `keys.py` | Vault key from the OS credential store via `keyring`; `JARVIS_PRIVATE_BRAIN_KEY` overrides it for headless runs |
| `audit.py` | `AuditLogger` — append-only JSONL, file mode 0600, ids/decisions/reasons only |
| `brain.py` | `PrivateBrain` service: encrypted documents *and* encrypted index, retrieval, deletion |

### Reference folders (`~/Documents/TempJarvis`)

Files placed in a configured reference folder are read **in place**: never copied into the vault, never cached on disk, never modified or deleted by JARVIS. Supported: `.txt .md .markdown .csv .json .docx .pptx .pdf` (≤ 25 MB each, ≤ 1000 files per folder). Changes are picked up on the next search.

| Location | Classification | Reaches the live (cloud) model? |
|---|---|---|
| `TempJarvis/…` | folder level from config (default `CONFIDENTIAL`) | Yes — excerpts matching a search |
| `TempJarvis/SECRET/…` | `SECRET` | No — counted as withheld only |
| `TempJarvis/TOP_SECRET/…` | `TOP_SECRET` | No — counted as withheld only |

A top-level subfolder named after a level can only **raise** the classification. Hidden files, Office lock files (`~$…`), symlinks, password-protected and unreadable files are skipped. `forget` refuses reference files; remove the file from the folder instead. Add more folders, or restrict one to roles, under `reference_folders` in `config/private_brain.json`.

Local data lives in `memory/private_brain/` (git-ignored). Configure the local principal, storage paths and cloud limit in `config/private_brain.json`; invalid levels or `log_content: true` are rejected at load time.

Known limits: retrieval is keyword-based (no embeddings yet), there is no private runtime, so `SECRET`/`TOP_SECRET` content is never returned to the live model, and the conversation itself (including excerpts the model has seen) is governed by the general memory rules, not by this package.

## Development

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q tests/test_private_brain*.py tests/test_vault.py
```

## Cloud routing

By default, `CONFIDENTIAL` is the highest classification allowed into a cloud LLM context. `SECRET` and `TOP_SECRET` require a private/sovereign runtime unless an explicit security policy changes this boundary.

## Non-negotiable rules

1. Never put confidential documents into system prompts or source code.
2. Never bypass ACL filtering because a user asks for the data.
3. Never expose retrieved chunks to a lower-clearance subject.
4. Keep provenance and document version metadata with every retrieval.
5. Log access decisions without logging secret document contents.
6. Revoke access by policy/identity; do not rely on deleting embeddings alone.
