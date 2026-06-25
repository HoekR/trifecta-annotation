# Gold labelling workflow (cort_voc_db snippets)

Primary source for TRIFECTA manual annotation — **not** the preservare KWIC pool.

## 1. Ingest sources to scratch

Copies OneDrive CSV + Downloads txt to scratch tier:

```bash
uv run python scripts/ingest_food_snippets.py
```

| Manifest key | Scratch path |
|--------------|--------------|
| `food_snippets` | `trifecta/food_snippets_for_annotation.csv` (~31k rows) |
| `food_snippets_manual` | `trifecta/snippets_for_annotation.txt` (~106 curated snippets) |

Canonical paths (absolute, in manifest):

- `food_snippets_source` — OneDrive CSV
- `food_snippets_manual_source` — `~/Downloads/snippets_for_annotation.txt`

## 2. Build kwic_inputs

Default: **manual subset only** (rows whose snippet text matches the txt file):

```bash
uv run python scripts/build_kwic_inputs.py
```

Full corpus (optional):

```bash
uv run python scripts/build_kwic_inputs.py --all-snippets
```

`target_word` is the **leftmost** food term from `original_found_terms` that appears in the snippet. Other matches go in `candidate_terms` / gold CSV `notes` for reviewer override.

## 3. Export diverse gold labelling sheet (recommended)

Default: **50 diverse examples** — mix of your curated txt snippets + stratified picks across works and target words:

```bash
uv run python scripts/export_gold_candidates.py --limit 50 --summary
```

| Flag | Meaning |
|------|---------|
| `--source diverse` | Default: ~half from manual txt, half stratified from full CSV |
| `--source manual` | Only your 106-line txt subset |
| `--seed 42` | Reproducible sample |
| `--no-manual-seed` | Stratified sample only, no curated txt priority |

Other sources:

```bash
uv run python scripts/export_gold_candidates.py --source kwic_inputs --limit 50
```

## 4. Label, import, eval

See column reference in the main [GOLD_LABELLING.md](GOLD_LABELLING.md).

```bash
uv run python scripts/import_gold_csv.py
uv run trifecta-batch --input-logical kwic_inputs --resume
uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations
```
