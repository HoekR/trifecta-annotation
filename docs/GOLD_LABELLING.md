# Gold labelling CSV guide

Use the CSV workflow to curate the ~50-record `trifecta_gold` eval set. Column definitions follow the [TRIFECTA annotation guidelines](Annotation_Guidelines_final.pdf) (English) and [Annotation_Guidelines_NL.pdf](Annotation_Guidelines_NL.pdf) (Dutch).

## Web UI (recommended)

Hand-label rows in the browser instead of editing the CSV in Excel:

```bash
cd ~/develop/trifecta-annotation
uv sync --extra gold-ui
uv run trifecta-gold-ui
```

Open http://127.0.0.1:5050 — you get one snippet at a time with the **target word highlighted**, Step A/B fields, prev/next navigation, and progress (`N / 50 labelled`).

- **Save** — writes directly to `trifecta/gold_labelling.csv` on scratch.
- **Save & next** — save and jump to the next row.
- **LLM suggest** — optional draft from the pipeline (you must review; do not accept blindly).

When all rows are done:

```bash
uv run python scripts/import_gold_csv.py
```

## Export candidates

```bash
uv run python scripts/build_kwic_inputs.py
uv run python scripts/export_gold_candidates.py --limit 50
```

Writes `trifecta_gold_csv` (scratch tier: `trifecta/gold_labelling.csv`).

## CSV columns

| Column | Required when labelled | Values / notes |
|--------|------------------------|----------------|
| `record_id` | yes | Stable id; must match batch predictions |
| `corpus` | yes | e.g. `voc_recipes`, `recipe_web` |
| `target_word` | yes | Food term in context |
| `context_text` | yes | KWIC window |
| `date` | no | Year or date string for era metrics |
| `source_path` | no | Origin file if known |
| `labelled` | yes | `true` when row is ready to import |
| `dropped` | if early exit | `true` / `false` |
| `drop_reason` | if dropped | `metaphor`, `not_food_entity`, … |
| `is_food_entity` | if not dropped at A | `true` / `false` |
| `is_metaphor` | if not dropped at A | `true` / `false` |
| `formal_dimension` | no | `FOOD_Unit`, `FOOD_Constituent_Part`, `FOOD_Whole`, `OTHER` |
| `canonical_pref_label` | no | From `Food_terms` when matched |
| `ontology_match` | no | `true` / `false` |
| `step_a_reasoning` | recommended | Short justification |
| `selected_frame` | if passes A | `COOKING_CREATION`, `USING_CURE`, `USING_INGESTION`, `PRESERVING`, `NONE` |
| `lexical_unit` | if frame ≠ NONE | Frame trigger word |
| `step_b_reasoning` | recommended | Short justification |
| `notes` | no | Free-text reviewer notes |

**Dropout rows:** set `labelled=true`, fill Step A fields, set `dropped=true`, leave Step B empty.

**Pass-through rows:** set `labelled=true`, `dropped=false`, fill Step A and Step B.

If Step A marks metaphor or non-food, `dropped` is inferred as `true` unless you explicitly set `dropped=true` in the sheet.

## Import labelled CSV

```bash
uv run python scripts/import_gold_csv.py
```

Creates:

- `trifecta_gold` — parquet (`annotation_json` column)
- `trifecta_gold_jsonl` — JSONL mirror

## Re-export for editing

```bash
uv run python scripts/export_gold_csv.py
```

## Evaluate

```bash
uv run trifecta-batch --input-logical kwic_inputs --resume
uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations
```
