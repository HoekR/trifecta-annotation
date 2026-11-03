# Data lineage: local DVC mirrors

## Why this exists

In October 2026, `scripts/build_kwic_inputs.py` silently overwrote
`kwic_inputs.jsonl` on the scratch tier, destroying the only record of the
version that had fed an earlier GijsBERT training export. There was no
system record that this had happened — reconstructing it took manual
cross-referencing of a `.meta.toml` timestamp, row counts, and git commit
dates. This is the fix: a small, local, DVC-tracked mirror of the
critical-path datasets, plus a lineage overview command and an inline
staleness warning.

The underlying mechanism (`mirror_of` manifest field, `python -m data_io
overview`/`sync-mirrors`, inline staleness warning) lives in `data_io`
itself and is generic — it's vendored from `dighum_template`
(upstream: `republic_ner_matching/data_io`), not trifecta-specific code.
See `dighum_template/docs/SYNC-PROJECT.md` before editing `data_io/` files
directly: local changes there won't survive the next `--data-io` sync
unless also ported upstream. What *is* trifecta-specific is which four
datasets below declare a `mirror_of` entry, and the gold-save stamp in
`gold_labeller/store.py`.

This does **not** replace the scratch tier or the data manifest. Large raw
corpora stay external/dispersed exactly as before. Only a handful of small,
critical datasets get a local, content-hashed copy.

## What's tracked

Four scratch-tier datasets have a `<name>_mirror` entry (tier `local`,
`data_local/` in this repo) registered in `data_manifest.toml`:

- `kwic_inputs` → `kwic_inputs_mirror`
- `trifecta_gold_csv` → `trifecta_gold_csv_mirror`
- `trifecta_annotations` → `trifecta_annotations_mirror`
- `inception_nl_v2_iaa_agreed_gold` → `inception_nl_v2_iaa_agreed_gold_mirror`

Each mirror is a DVC-tracked (`.dvc` pointer file + content in the DVC
cache, pushed to a local remote on the scratch SSD) snapshot of the
corresponding live scratch file. `trifecta_gijsbert` is deliberately
**not** DVC-tracked — it's already committed directly to plain git, which
already preserves every version via normal commits; the silent-overwrite
problem only exists for files that live outside git on the scratch tier.

## Keeping mirrors in sync

Run after re-running an ingest/export script that touches one of the four
datasets above:

```
python -m data_io sync-mirrors          # re-add changed mirrors to DVC
python -m data_io sync-mirrors --push   # also dvc push to the scratch remote
```

It diffs each mirror's current DVC hash against the live scratch file's
hash, copies+re-adds only what changed, and reports what moved.

## Reading the lineage

```
python -m data_io overview <logical_name>
```

Walks the dataset's `parent` chain in `data_manifest.toml`, printing each
ancestor's tier/phase/description plus the DVC hash of any mirrored node,
and the current `trifecta-annotation` git commit. Example:

```
trifecta-annotation @ 8c61238b125cf2af643a2dc3664e2c483a99d740
Lineage for 'trifecta_annotations':
trifecta_annotations (scratch/semi) [dvc:6bae834907] — Full A→B→C pipeline outputs
  -> kwic_inputs (scratch/semi) [dvc:81330cbd2e] — Normalized KwicInput records for batch annotation
    -> food_snippets (scratch/frozen) — Working copy of food snippets CSV (ingest from OneDrive)
      -> food_snippets_source (hot/frozen) — Canonical food snippets CSV on OneDrive (cort_voc_db)
```

## Staleness warnings

`data_io.resolve()` automatically checks, for the four tracked datasets
only, whether the live scratch file still matches its local mirror's last
recorded DVC hash. If it's drifted (someone re-ran the ingest script and
didn't sync the mirror), it prints a `UserWarning` the first time that
dataset is resolved in a process — no separate command to remember to run.

Gold specifically also gets a forward stamp: every `gold_labeller` save
appends an entry to `data_local/_lineage_log.jsonl` recording which exact
`kwic_inputs` hash was live at the moment that gold was saved — so gold's
lineage is anchored at the point of labelling, not only at export time.

## Open items (not yet decided, see the governance plan)

- Whether to push the DVC remote anywhere beyond the local scratch-SSD
  remote already configured (`dvc remote list`).
- Whether any other scratch-tier dataset should join the critical-path set.
- Whether the staleness warning should ever block (exit non-zero) rather
  than just print.
