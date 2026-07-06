# Gold labelling workflow (cort_voc_db snippets)

Primary source for TRIFECTA manual annotation — **not** the preservare KWIC pool.

Policy and eval rules: [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md).

## 0. Corpus text overview

Export a catalogue of **source works** in the snippet pool (one row per `filename`):

```bash
uv run python scripts/export_corpus_overview.py --summary
```

Default output: `eval/corpus_texts_overview.csv` on scratch.

| Column | Meaning |
|--------|---------|
| `filename` | cort_voc source file (e.g. `chom003huis01_01.xml`) |
| `title` | Human-readable work title |
| `text_regime` | Heuristic Layer-0 tag (`RECIPE_PRACTICE`, `MEDICAL`, …) |
| `snippet_rows` | Rows in `food_snippets_for_annotation.csv` for this file |
| `distinct_doc_ids` | Distinct snippet ids |
| `gold_rows` | Hand-gold rows sourced from this file |
| `in_gold` | Whether any gold row references this file |

**Review the CSV** for `text_regime=UNKNOWN` and for works with many snippets but `gold_rows=0` (sampling gaps). Regime tags are heuristic — override in gold UI after picking rows.

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

**Verb-seeded gold** (frame verbs discover snippet, food noun is `target_word`):

```bash
# 25 rows stratified by PRESERVING / CURE / COOKING / INGESTION verbs
uv run python scripts/export_gold_candidates.py --source verb --limit 25 --summary

# 50/50 food + verb (recommended second tranche after noun-first gold)
uv run python scripts/export_gold_candidates.py --source mixed --limit 30 --summary

# Custom verb share on diverse export
uv run python scripts/export_gold_candidates.py --verb-share 0.4 --limit 50
```

Build verb-seeded `kwic_inputs` for batch/LLM:

```bash
uv run python scripts/build_kwic_inputs.py --source verb --limit 500
```

| Flag | Meaning |
|------|---------|
| `--source diverse` | Default: manual txt + food long CSV (optional `--verb-share`) |
| `--source mixed` | 50% verb-seeded + 50% food-seeded |
| `--source verb` | Frame-verb discovery only (wide snippets + thesaurus food in window) |
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

## 5. GijsBERT export

Mark food target `[TGT]…[/TGT]`, frame verb `[VRB]…[/VRB]`, or both:

```bash
uv run python scripts/export_gijsbert.py --mark-mode both
```

| `--mark-mode` | Use when |
|---------------|----------|
| `food` | Noun-centred KWIC (first gold tranche) |
| `verb` | Verb trigger only |
| `both` | Verb-seeded rows: model sees food + frame verb |
