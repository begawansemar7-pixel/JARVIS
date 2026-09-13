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

## Cloud routing

By default, `CONFIDENTIAL` is the highest classification allowed into a cloud LLM context. `SECRET` and `TOP_SECRET` require a private/sovereign runtime unless an explicit security policy changes this boundary.

## Non-negotiable rules

1. Never put confidential documents into system prompts or source code.
2. Never bypass ACL filtering because a user asks for the data.
3. Never expose retrieved chunks to a lower-clearance subject.
4. Keep provenance and document version metadata with every retrieval.
5. Log access decisions without logging secret document contents.
6. Revoke access by policy/identity; do not rely on deleting embeddings alone.
