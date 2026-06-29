# Gold labelling workflow (cort_voc_db snippets)

Primary source for TRIFECTA manual annotation — **not** the preservare KWIC pool.

## 1. Ingest sources to scratch

Copies OneDrive CSVs + Downloads txt to scratch tier:

```bash
uv run python scripts/ingest_food_snippets.py
```

| Manifest key | Scratch path |
|--------------|--------------|
| `food_snippets` | `trifecta/food_snippets_for_annotation.csv` (~31k rows, legacy wide format) |
| `food_snippets_long` | `trifecta/food_snippets_long.csv` (~172k rows, **one keyword per row**) |
| `food_snippets_manual` | `trifecta/snippets_for_annotation.txt` (~106 curated snippets) |

Canonical paths (absolute, in manifest):

- `food_snippets_source` — wide OneDrive CSV
- `food_snippets_long_source` — exploded long CSV (`matched_term` column)
- `food_snippets_manual_source` — `~/Downloads/snippets_for_annotation.txt`

## 2. Build kwic_inputs

Default: **long CSV** (explicit `matched_term` per row — avoids noisy leftmost guessing from `original_found_terms`):

```bash
uv run python scripts/build_kwic_inputs.py
```

Other sources:

```bash
uv run python scripts/build_kwic_inputs.py --source manual   # curated txt only
uv run python scripts/build_kwic_inputs.py --source wide     # legacy wide CSV
```

For the wide CSV, `target_word` was the **leftmost** term from `original_found_terms` (often noisy). The long CSV uses the pre-matched `matched_term` for each row.

## 3. Export diverse gold labelling sheet (recommended)

Default: **50 diverse examples** — mix of curated txt snippets + stratified picks from `food_snippets_long`:

```bash
uv run python scripts/export_gold_candidates.py --limit 50 --summary
```

| Flag | Meaning |
|------|---------|
| `--source diverse` | Default: ~half from manual txt, half stratified from long CSV |
| `--source manual` | Only your 106-line txt subset |
| `--snippet-format wide` | Legacy: sample from wide `food_snippets` instead |
| `--seed 42` | Reproducible sample |
| `--no-manual-seed` | Stratified sample only, no curated txt priority |

Other sources:

```bash
uv run python scripts/export_gold_candidates.py --source kwic_inputs --limit 50
uv run python scripts/export_gold_candidates.py --source long --limit 50
```

**Note:** re-exporting replaces `gold_labelling.csv` and changes `record_id` values (`doc_id__keyword`). Back up any in-progress labels first.

## 4. Label, import, eval

See column reference in the main [GOLD_LABELLING.md](GOLD_LABELLING.md).

```bash
uv run python scripts/import_gold_csv.py
uv run trifecta-batch --input-logical kwic_inputs --resume
uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations
```
