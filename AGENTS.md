# Agent instructions — trifecta-annotation

Read **`PLAN.md`**, **`docs/README.md`**, **`docs/TRIFECTA.md`**, and **`data_manifest.toml`** before pipeline work.

**Hand labelling / Step C gold:** follow **`docs/GOLD_LABELLING.md` § Step 5 runbook** end-to-end — do not reconstruct workflow from PLAN alone.

## Data paths

- Use `from data_io import resolve, save_semi_structured` — no absolute paths in scripts.
- Register new datasets in `data_manifest.toml` before referencing them in code.
- After manifest edits: `uv run python -m data_io.check`
- Keep `PLAN.md` dataset table in sync with `[datasets.*]` keys.
- **No path fallbacks**: if `resolve("logical_name")` fails, add the dataset to `data_manifest.toml` — never substitute `REPO_ROOT / "trifecta/..."`, scratch guesses, or `Path(resolve("other_key")).parent` hacks.

## Outputs

- Semi-structured: `save_semi_structured(..., logical_name=..., script=__file__)`
- Frozen eval sets: `save_parquet(df, logical_name=..., script=__file__)`

## TRIFECTA pipeline

- Steps A → B → C; early dropout on Step A.
- Structured outputs only (`instructor` + Pydantic) — no free-text frame labels in production code.
- Era = provenance on records, not separate pipelines.

## Other repos

| Repo | Use |
|------|-----|
| `hist-text-utils` | Optional KWIC/snippet helpers — keep generic, do not add TRIFECTA here |
| `recepten-preservare-analysis` | Food ontology + VOC calibration data |
| `Dutch-historical-recipe-trends` | 20th-c. corpus |
