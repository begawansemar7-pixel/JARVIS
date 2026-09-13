# JARVIS Strategy Research

Consulting-grade research method for JARVIS: hypothesis-driven, MECE, triangulated, cited.

## Flow

`Frame → Issue tree → Hypotheses → Gather evidence → Analyze → Synthesize → Stress-test → Communicate`

## Primary commands

- `Riset pasar …` / `Market study on …`
- `Market sizing …`
- `Commercial due diligence on …`
- `Benchmark kompetitor …`
- `… lalu buatkan laporan / deck` — exports through `ceo_document`

## Components

| Component | Role |
|---|---|
| `SKILL.md` | Operating procedure the model follows |
| `actions/strategy_research.py` | `gather_evidence` (search, credibility tiers, excerpts, triangulation, dossier) and `size_market` (scenarios + sensitivity) |
| `research/` | Evidence, source-tier, sizing and dossier modules |
| `config/research_sources.json` | Source credibility tiers (edit to add trusted domains) |
| `../../tools/strategy_research_tools.yaml` | Machine-readable tool contract |

Dossiers are saved in `~/Documents/JARVIS/Research/<date>_<topic>/`.
