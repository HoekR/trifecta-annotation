# Food harvest for colleagues: sharing the export and the starter notebook

**Status:** waiting on Rik's review of the notebook (10 Nov 2026).

**What:** the food-harvest export (`scripts/export_food_harvest.py` ->
`/Volumes/Extreme SSD/scratch/trifecta/exports/food_harvest/`) and its starter
notebook (`notebooks/food_harvest_starter.ipynb`, copied into the export), for
colleagues' collocation and name-shift work.

## Done (10 Nov 2026)

1. **The notebook runs end to end** on a copy of the export (14 code cells, ~20 s).
2. **README dependencies:** the export README said "pandas only"; it now lists
   pandas, pyarrow, matplotlib, jinja2. matplotlib added to the `dev` group here.
3. **Data folder relative to the notebook** (`DATA_SUBDIR = "."`, from the notebook's own
   folder: VS Code's `__vsc_ipynb_file__`, else the working directory), with a clear message
   when the data is not there. No environment variable, no fixed paths (AGENTS.md,
   dighum_template `wisdom/topics/local-config-not-env.md`). The repo copy has no data next
   to it, so review the export copy.
4. **Checked for sharing:** no KITLV film text in `plaintext/` (the Daum / Leiden
   files there are DBNL works); `names_over_time.csv` is counts only.
5. **Trifecta-event** (private repo, trifecta-project): `food_frames/` holds the
   results overview and the kg_mockup preview; the food harvest is held back.

## Next

1. **Rik reviews the notebook** for comprehensibility (open the export copy, so
   it runs as colleagues will see it).
2. **Into Trifecta-event** `food_frames/food_harvest/`: notebook, README,
   `works.csv`, `names_over_time.csv`. `mentions.parquet` (32 MB) and
   `plaintext.zip` (10 MB) once, or as a GitHub Release asset if re-exported
   often (every committed version stays in Git history). Not `mentions.csv`
   (66 MB, same data as the parquet).

## Later (not now)

**Let colleagues run it without installing anything.** Options, cheapest first:

- **Static HTML** of the executed notebook: read-only, a browser is enough.
  (nbconvert on Rik's Mac trips over an old `jupyter_contrib_nbextensions`
  setting; render in a clean environment.)
- **One-liner** in the README for those with a terminal:
  `uvx --with pandas,pyarrow,matplotlib,jinja2 jupyter lab`.
- **Colab:** quick, but the data is uploaded to Google. Cookbook texts are fine
  to share internally; never the KITLV films (they are not in the export).
- **Jupyter on the SURF VM**, behind the RAA nginx next to kg_mockup (`/jupyter/`,
  same pattern as `/kg/`, see kg_mockup `docs/DEPLOYMENT.md` §0b): data stays on
  SURF, but means user accounts and kernels on a shared VM. Worth it only if
  colleagues will actually run code repeatedly.
