# Documentation map

Reference material for TRIFECTA annotation work in this repository.

| Document | Language | Description |
|----------|----------|-------------|
| `docs/Annotation_Guidelines_final.pdf` | English | Official guidelines — **not in git**; copy locally from OneDrive/KNAW |
| `docs/Annotation_Guidelines_NL.pdf` | Dutch | Dutch translation — place locally if available |
| [TRIFECTA.md](TRIFECTA.md) | English | Pipeline architecture summary (Steps A–C, infrastructure) |
| [SNIPPETS.md](SNIPPETS.md) | English | cort_voc_db snippet ingest + kwic_inputs |
| [GOLD_LABELLING.md](GOLD_LABELLING.md) | English | Gold CSV labelling workflow |
| [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) | English | **Why** gold/eval evolved: regimes, preservare, disagreements, model compare |
| [DATA.md](DATA.md) | English | Data manifest bootstrap and dataset registry |
| [../PLAN.md](../PLAN.md) | English | Authoritative project plan and milestones |

## Gold labelling workflow

1. Read the annotation guidelines PDF before labelling.
2. Ingest snippets: `uv run python scripts/ingest_food_snippets.py`
3. Build inputs: `uv run python scripts/build_kwic_inputs.py`
4. Export candidates: `uv run python scripts/export_gold_candidates.py --limit 106`
5. Label in Excel/Numbers using [GOLD_LABELLING.md](GOLD_LABELLING.md).
6. Import: `uv run python scripts/import_gold_csv.py`
7. Evaluate: `uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations`

Details: [SNIPPETS.md](SNIPPETS.md). Strategy and rationale: [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md).

If the Dutch PDF uses a different filename on your machine, place it at `docs/Annotation_Guidelines_NL.pdf` or update this table.
