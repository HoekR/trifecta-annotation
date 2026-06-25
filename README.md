# TRIFECTA annotation pipeline

Multi-stage LLM pipeline for **TRIFECTA** (Qualia-style FrameNet) annotation of historical Dutch food texts, **17th–20th century**.

Standalone repository — [`hist-text-utils`](https://github.com/HoekR/hist-text-utils) remains a **general** text/KWIC library (optional `[kwic]` extra only).

## Features

- **Gated pipeline:** Step A (entity) → Step B (macro-frame) → Step C (qualia roles)
- **Structured outputs:** Pydantic + `instructor` (Ollama local / vLLM on SURF)
- **Data template:** `data_manifest.toml` + `data_io` — manifest paths, tier mounts, provenance sidecars

## Setup

```bash
cd ~/develop/trifecta-annotation
cp data_manifest.toml.example data_manifest.toml   # edit tier roots + OneDrive paths
# Place annotation guidelines PDF in docs/ (not tracked in git)
uv sync
uv run python -m data_io.check
```

Ollama: `ollama pull qwen2.5-coder:32b-instruct`

## Quick test (Step B)

```bash
uv run trifecta-classify \
  --target vlierbessen \
  --context "Dit sap van vlierbessen is krachtig en dient om de hoest te verzachten bij koorts."
```

## Full pipeline

```bash
uv run trifecta-annotate \
  --target zout \
  --context "men behoefd een hand vol zout" \
  --corpus voc_recipes

# Ingest TRIFECTA snippets (OneDrive + Downloads → scratch)
uv run python scripts/ingest_food_snippets.py
uv run python scripts/build_kwic_inputs.py

# Gold labelling (CSV) — diverse sample recommended
uv run python scripts/export_gold_candidates.py --limit 50 --summary
# … label in spreadsheet …
uv run python scripts/import_gold_csv.py

uv run trifecta-batch --input-logical kwic_inputs --resume
uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations
```

## Related data (sibling repos)

| Repo | Manifest key |
|------|----------------|
| `recepten-preservare-analysis` | `food_terms`, `voc_recipes`, `kwic_gold_review` |
| `Dutch-historical-recipe-trends` | `recipe_web` |

## Documentation

| Doc | Contents |
|-----|----------|
| [PLAN.md](PLAN.md) | **Authoritative project plan** + milestone status |
| [docs/README.md](docs/README.md) | Documentation map (guidelines PDFs) |
| [docs/TRIFECTA.md](docs/TRIFECTA.md) | Architecture summary |
| [docs/GOLD_LABELLING.md](docs/GOLD_LABELLING.md) | Gold CSV labelling workflow |
| [docs/DATA.md](docs/DATA.md) | Manifest bootstrap |
| [AGENTS.md](AGENTS.md) | Agent / LLM coding instructions |

## Layout

```
trifecta-annotation/
├── PLAN.md
├── data_manifest.toml
├── data_io/                  # manifest + provenance I/O (DH template)
├── trifecta_annotation/      # TRIFECTA pipeline code
│   ├── schemas.py
│   ├── step_a.py
│   ├── step_b.py
│   ├── step_c/
│   ├── pipeline.py
│   ├── batch.py
│   ├── eval.py
│   ├── adapters/
│   └── prompts/
└── tests/
```

## Provenance

EU grant TRIFECTA (see Dutch-historical-recipe-trends). Frame guidelines inspired by FrameNet Brasil Qualia structures.
