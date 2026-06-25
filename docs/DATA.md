# Data bootstrap (manifest + provenance I/O)

This project uses the **DH data template**: `data_manifest.toml` + `data_io/` for path decoupling and provenance on pipeline outputs.

## Day-zero checklist

1. `cp data_manifest.toml.example data_manifest.toml` — fill tier roots and absolute paths to OneDrive/Downloads data.
2. Optional: `data_manifest.local.toml` (gitignored) for machine-specific overrides.
3. Copy `Annotation_Guidelines_final.pdf` into `docs/` locally (PDFs are not in git).
4. `uv sync`
5. `uv run python scripts/ingest_food_snippets.py`
6. `uv run python -m data_io.check`

## Tiers

| Tier | Typical use in TRIFECTA |
|------|-------------------------|
| **hot** | Sibling repos under `~/develop` (read-only inputs) |
| **warm** | Large corpora on external disk (optional) |
| **scratch** | Annotation JSONL, eval reports, batch checkpoints |

## Registered datasets

| Logical name | Phase | Description |
|--------------|-------|-------------|
| `food_terms` | frozen | `Food_terms.csv` on warm tier (`/Volumes/2tb disk/reference/`) |
| `voc_recipes` | frozen | VOC recipe corpus |
| `recipe_web` | frozen | 20th-c. newspaper recipes |
| `kwic_gold_review` | semi | KWIC calibration pool |
| `food_snippets_source` | frozen | OneDrive CSV (canonical, ~31k rows) |
| `food_snippets` | frozen | Scratch copy of food snippets CSV |
| `food_snippets_manual` | semi | Scratch copy of manual annotation txt (~106) |
| `kwic_inputs` | semi | Normalized `KwicInput` JSONL (write) |
| `trifecta_gold_csv` | semi | Gold labelling spreadsheet (CSV) |
| `trifecta_gold_jsonl` | frozen | Gold set JSONL mirror |
| `trifecta_gold` | frozen | Hand-labelled eval set parquet |
| `frame_classifications` | semi | Step B outputs (write) |
| `trifecta_annotations` | semi | Full A→B→C outputs (write) |
| `eval_reports` | semi | Eval metrics and markdown reports (write) |

## Code usage

```python
from data_io import resolve, save_semi_structured

food_path = resolve("food_terms")
out_path = resolve("frame_classifications")

save_semi_structured(
    records,
    logical_name="frame_classifications",
    parent_sources=["kwic_gold_review"],
    description="Step B macro-frame batch run.",
    script=__file__,
)
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATA_MANIFEST` | Override path to base manifest |
| `DATA_MANIFEST_OVERRIDE` | Merge additional TOML (e.g. SURF paths) |

## Archival integrity

- Never drop provenance fields from sidecars.
- Do not mutate `Food_terms.csv` in place — version outputs.
- Every annotation record carries `corpus`, `date`, `target_word`, `context_text`.
