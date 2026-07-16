# Collocation skeleton and frame-verb growth

Target-centred **usage skeletons** from `food_snippets_long` KWICs: which verbs, preps, and adjectives co-occur with each food lemma, scored by PMI. Optional FastText similarity. Feeds the **frame-verb lexicon** via the collocation miner (no hand-maintained verb lists).

Policy context: [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §2 (Layer 2 = local scenario, not verb label alone). Snippet ingest: [SNIPPETS.md](SNIPPETS.md).

---

## 1. What it is for

| Use | Not for |
|-----|---------|
| Data-driven **food → verb** partners (*bier* + *drinken*, *koren* + *malen*) | Auto Step B labels |
| Homograph / sense hints (different collocate profiles per target) | Replacing hand gold |
| **Prioritised queue** for frame-verb lexicon growth | Full manual verb hunting |
| Few-shot / GijsBERT hint material (high-confidence pairs) | **Blind** skeleton → `[VRB]` in `export_gijsbert.py` (see §6) |

**Precision-first:** high PMI + high anchor agreement → auto-promote; borderline rows stay in the review CSV (`keep` blank).

---

## 2. Pipeline overview

```text
food_snippets_long (one matched_term per row)
        │
        ├─► export_collocation_skeleton.py
        │         mine_collocations (±5 tokens, PMI)
        │         optional FastText rank (--train-fasttext / --fasttext-model)
        │         → eval/collocation_skeleton.csv
        │
        └─► build_frame_verb_lexicon.py --collocation-miner
                  mine_collocation_verb_candidates
                  (food target + unknown verb + nearby anchor frame vote)
                  auto_keep when freq ≥ 5 and agreement ≥ 0.75
                  → trifecta_frame_verb_corpus.csv (merge with recipe gloss rows)
                            │
                            ▼
                  frame_verbs.py merged lexicon (keep=yes rows)
                            │
                            ▼
                  verb_kwic, clear_frame_examples, collocation frame_hint column
```

**Parallel paths** (unchanged):

| Source | Script flag | `notes` | Default `keep` |
|--------|-------------|---------|----------------|
| Recipe bracket glosses | (always) | `recipe_gloss` | `yes` |
| Wide prose snippets | `--prose-miner` | `prose_miner_review` | manual |
| Long KWIC collocations | `--collocation-miner` | `collocation_miner` | auto when thresholds pass |

---

## 3. Frame-verb lexicon layers

Merged in `frame_verbs.py` (manual wins on frame clash):

1. **Guideline** — Annotation Guidelines NL v3 `.v` LUs (`koken`, `drinken`, …)
2. **Manual** — historic extras (`pekelen`, `brouwen`, `malen`, …)
3. **Technique** — cort-voc `technique_term_association.csv` → PRESERVING
4. **Corpus** — `trifecta_frame_verb_corpus.csv` (`keep=yes` only by default)

Historic variants map via `SUGGESTED_CANONICAL_LEMMA` (`sieden` → `koken`, `stooten` → `stampen`).

`collocation_skeleton.csv` column `frame_hint` is a **lexicon lookup**, not semantic inference. Unknown verbs get an empty `frame_hint` until promoted through the corpus CSV.

---

## 4. Collocation skeleton export

```bash
# Full skeleton (verbs + prep + adj), scratch default
uv run python scripts/export_collocation_skeleton.py --summary

# Verb-only, one target
uv run python scripts/export_collocation_skeleton.py --verbs-only --targets bier,appel

# Stratified by text_regime
uv run python scripts/export_collocation_skeleton.py --by-regime

# Optional FastText boost (needs gensim)
uv sync --extra collocations
uv run python scripts/export_collocation_skeleton.py --train-fasttext --verbs-only
```

**Output:** `eval/collocation_skeleton.csv`

| Column | Meaning |
|--------|---------|
| `target_norm` / `target_lemma` | Food keyword (historic / thesaurus lemma) |
| `collocate_norm` / `collocate_type` | Partner token (`verb`, `prep`, `adj`) |
| `text_regime` | `ALL` (pooled) or per-regime when `--by-regime` |
| `cooc_count`, `pmi` | Window co-occurrence and PMI |
| `frame_hint`, `in_frame_lexicon` | From merged frame-verb lexicon |
| `fasttext_sim` | Optional distributional boost |
| `rank_within_target` | PMI (+ sim) rank per target |

**Interpretation:** same target, different collocate profiles = different usage buckets (e.g. *bier* + *drinken* vs *bier* + *brouwerij* / *ketels*). Step B still uses the **full snippet** (Layer 2), not the verb row alone.

---

## 5. Lexicon growth (collocation miner)

```bash
# Rebuild corpus CSV: recipe glosses + collocation promotions
uv run python scripts/build_frame_verb_lexicon.py \
  --collocation-miner \
  --summary \
  --output-path trifecta_frame_verb_corpus.csv
```

**Promotion rule** (same as prose miner `auto_keep_mask`):

- Verb **not** already in merged lexicon
- Co-occurs with a food target in ±`--collocation-window` tokens (default 5)
- Same snippet has a **seed anchor** verb within `--max-window` chars (default 120)
- `snippet_freq` ≥ `--collocation-min-freq` (default 5)
- `anchor_agreement` ≥ `--collocation-min-agreement` (default 0.75)

Rows with `keep=yes` load into `frame_verbs.py` on next run. Rows with blank `keep` need manual review (homograph `-en` noise, industrial vs prep ambiguity).

**Review CSV columns:** `term_norm`, `historic_forms`, `frame_hint`, `snippet_freq`, `anchor_agreement`, `anchor_frames` (includes top food targets), `keep`, `notes`.

---

## 6. GijsBERT export audit (9 Jul 2026)

**Question:** Can corpus-wide skeleton `frame_hint` fill missing `[VRB]` marks in `export_gijsbert.py`?

**Method:** `notebooks/inspect_lexicon_csvs.ipynb` §3 — hand-gold **dev** framed rows (68) vs top verb collocates per `target_norm` in `eval/collocation_skeleton.csv` (target-level PMI prior, not snippet-local).

| Gold frame | Dev rows | Skeleton coverage | Hint alignment (of rows with hints) |
|------------|----------|-------------------|-------------------------------------|
| COOKING_CREATION | 23 | 52% | **Good** (7/7) |
| INGESTION | 24 | 71% | **Medium** (3/6) |
| CURE | 16 | 56% | **Zero** (0/3) |
| PRESERVING | 5 | 80% | **Zero** (0/2) |
| **ALL_FRAMED** | 68 | 62% | **56.6%** (10/18) |

**Coverage gap:** only **25/49** unique framed dev targets have any skeleton verb rows.

**Decision:** **Do not** wire blind skeleton → GijsBERT export yet. Overall hint alignment (~57%) is too low; CURE/PRESERVING fail; INGESTION confusions match GijsBERT errors (`bier` → `brouwen` COOKING hint vs gold INGESTION).

**Still valid uses:** lexicon growth (`--collocation-miner`), skeleton review, few-shots when **snippet-local** + lexicon-filtered.

**Revisit when:** snippet-local verb pick (nearest verb in ±5 tokens, `frame_verbs` / denylist filter) or per-regime skeleton; re-run §3 audit — gate ≥60% ALL_FRAMED alignment **and** non-zero CURE/PRESERVING before export integration.

```bash
uv run python scripts/generate_notebooks.py --name inspect_lexicon_csvs
# → Run All; inspect audit_summary + hint mismatches
```

---

## 7. Operational workflow

1. **Ingest** snippets — `scripts/ingest_food_snippets.py` (see [SNIPPETS.md](SNIPPETS.md)).
2. **Export skeleton** — scan gaps (`in_frame_lexicon=false`, high PMI).
3. **Grow lexicon** — `build_frame_verb_lexicon.py --collocation-miner`; inspect `keep` blank rows only.
4. **Re-export skeleton** — `frame_hint` column updates after corpus reload.
5. **Downstream** — verb-KWIC pool, `clear_frame_examples`, optional few-shots.

Do **not** maintain a parallel hand list of verbs. Let recipe glosses + collocation miner + exception review drive growth.

---

## 8. Code map

| Module / script | Role |
|-----------------|------|
| `trifecta_annotation/collocation_skeleton.py` | PMI mining, FastText, skeleton export API |
| `trifecta_annotation/collocation_lexicon.py` | Target-centred verb promotion → corpus CSV |
| `trifecta_annotation/frame_verb_corpus.py` | Prose miner, `auto_keep_mask`, corpus load |
| `trifecta_annotation/frame_verbs.py` | Merged lexicon |
| `scripts/export_collocation_skeleton.py` | Skeleton CSV CLI |
| `scripts/build_frame_verb_lexicon.py` | Corpus CSV CLI (`--collocation-miner`) |
| `scripts/generate_notebooks.py` | Regenerate `inspect_lexicon_csvs.ipynb` (§3 dev audit) |
| `scripts/verb_lexicon_summary.py` | Lexicon counts |

---

## 9. Scratch outputs

| Path | Description |
|------|-------------|
| `eval/collocation_skeleton.csv` | Target ↔ collocate review / mining prior |
| `trifecta_frame_verb_corpus.csv` | Corpus-grown verbs (gitignored; local review) |

---

*Last updated: 9 July 2026 — GijsBERT dev skeleton audit (56.6% hint alignment; no blind export wire-up).*
