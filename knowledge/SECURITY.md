# Private Brain Security Contract

JARVIS Private Brain follows a defense-in-depth model inspired by the NIST AI Risk Management Framework: protect confidentiality, integrity, and availability; document governance; and continuously monitor risks.

## Required controls

- Identity and MFA at the application boundary.
- RBAC/ABAC before retrieval.
- Encryption at rest and in transit.
- External key management for production secrets.
- Document classification and provenance.
- Retrieval-time ACL filtering.
- DLP/output policy checks before external transmission.
- Redacted audit logging.
- Versioning and revocation.
- Human approval for consequential disclosure.

## Threats explicitly considered

- Unauthorized retrieval from RAG knowledge bases.
- Prompt injection attempting to bypass document ACLs.
- Cross-tenant/cross-role retrieval leakage.
- Accidental inclusion of secrets in prompts or logs.
- Data exfiltration through generated responses or tools.
- Stale or revoked documents remaining retrievable.

`SECRET` and `TOP_SECRET` material is not automatically safe merely because it is encrypted. The deployment must place it behind an appropriate private/sovereign model runtime and network boundary.
