# JARVIS SWE Model Router

## Objective

Select an appropriate model for each engineering task instead of treating every task as equally expensive.

## Routing Dimensions

- reasoning complexity;
- context size;
- code generation difficulty;
- verification criticality;
- latency sensitivity;
- cost sensitivity;
- provider availability.

## Task Tiers

| Tier | Tasks | Preferred behavior |
|---|---|---|
| fast | classify, summarize, extract symbols | cheapest reliable model |
| standard | code edit, test generation, routine debug | balanced coding model |
| reasoning | architecture, difficult debugging, migration | strongest available model |
| review | security / high-impact review | strong independent model |

## Routing Contract

```python
ModelChoice(
    provider="ollama",
    model="qwen-coder",
    tier="standard",
    reason="routine code modification",
)
```

The router returns a decision and reason. It does not directly execute the model request.

## Fallback

If a preferred model is unavailable, fall back within the same tier. Never silently downgrade a high-risk review to a low-capability model; surface the downgrade.

## Current Implementation

The first JARVIS SWE patch keeps the existing Gemini-backed `dev_agent` compatible. Routing metadata is introduced as a pure-Python policy layer so later providers can be added without rewriting the action interface.

## Future

- token/cost telemetry;
- per-tool routing;
- benchmark-driven routing;
- provider health scores;
- task-specific model capability registry;
- automatic model selection from historical success rate.
