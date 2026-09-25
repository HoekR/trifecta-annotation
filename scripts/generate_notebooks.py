#!/usr/bin/env python3
"""
Generate Jupyter notebooks from Python templates (no manual JSON editing).

Usage:
  uv run python scripts/generate_notebooks.py --name inspect_lexicon_csvs
  uv run python scripts/generate_notebooks.py --all
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import nbformat as nbf


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "notebooks"


def build_inspect_lexicon_csvs() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }

    nb["cells"] = []
    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# Inspect lexicon, collocation skeleton & GijsBERT dev\n",
                "\n",
                "Regenerate this notebook — do not hand-edit JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name inspect_lexicon_csvs\n",
                "```\n",
                "\n",
                "## Workflows\n",
                "\n",
                "1. **Lexicon CSV** — review `keep`, noise terms (`oncen`, `ponden`, …), confirm `FrameVerbLexicon` loading.\n",
                "2. **Collocation skeleton** — stream-search PMI collocates in `eval/collocation_skeleton.csv`.\n",
                "3. **Dev skeleton audit** — hand-gold dev targets vs corpus-wide verb collocates (GijsBERT export go/no-go).\n",
                "\n",
                "Paths use `data_io.resolve` only (see `data_manifest.toml`).\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Setup (manifest paths)"])
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "import json\n",
                "import re\n",
                "from pathlib import Path\n",
                "\n",
                "import pandas as pd\n",
                "\n",
                "from data_io import resolve\n",
                "from trifecta_annotation.frame_verbs import get_frame_verb_lexicon\n",
                "from trifecta_annotation.normalize import normalize_hist_dutch\n",
                "\n",
                "\n",
                "def _find_repo_root() -> Path:\n",
                "    cwd = Path.cwd().resolve()\n",
                "    for p in [cwd, *cwd.parents]:\n",
                "        if (p / 'trifecta_frame_verb_corpus.csv').exists():\n",
                "            return p\n",
                "    return cwd\n",
                "\n",
                "\n",
                "REPO_ROOT = _find_repo_root()\n",
                "GIJSBERT_DIR = Path(resolve('trifecta_gijsbert'))\n",
                "EVAL_DIR = Path(resolve('eval_reports'))\n",
                "\n",
                "LEXICON_CSV = REPO_ROOT / 'trifecta_frame_verb_corpus.csv'\n",
                "SKELETON_CSV = EVAL_DIR / 'collocation_skeleton.csv'\n",
                "DEV_JSONL = GIJSBERT_DIR / 'dev.jsonl'\n",
                "\n",
                "for label, path in [\n",
                "    ('lexicon', LEXICON_CSV),\n",
                "    ('skeleton', SKELETON_CSV),\n",
                "    ('dev', DEV_JSONL),\n",
                "]:\n",
                "    if not path.exists():\n",
                "        raise FileNotFoundError(f'Missing {label}: {path}')\n",
                "    print(label, path)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 1. Frame-verb lexicon CSV\n",
                "\n",
                "Repo-root review file. Only `keep=yes` rows load into the merged lexicon (plus guideline/manual/technique).\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "lex_df = pd.read_csv(LEXICON_CSV, dtype=str, keep_default_na=False)\n",
                "print('lexicon rows:', len(lex_df))\n",
                "lex_df.head(10)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def show_keep_status(df: pd.DataFrame) -> dict[str, int]:\n",
                "    keep = df['keep'].astype(str).str.strip().str.lower()\n",
                "    return {\n",
                "        'keep_yes': int(keep.isin({'yes', 'y', '1', 'true'}).sum()),\n",
                "        'keep_blank': int((keep == '').sum()),\n",
                "        'keep_no': int(keep.isin({'no', 'n', '0', 'false'}).sum()),\n",
                "    }\n",
                "\n",
                "\n",
                "show_keep_status(lex_df)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def lookup_lexicon_terms(terms: list[str]) -> pd.DataFrame:\n",
                "    terms_norm = pd.Series(terms, dtype='string').str.strip().str.lower()\n",
                "    hit = lex_df[lex_df['term_norm'].astype(str).str.lower().isin(terms_norm)]\n",
                "    return hit.sort_values('term_norm')\n",
                "\n",
                "\n",
                "terms_to_check = ['oncen', 'ponden', 'sullen', 'binnen', 'dingen', 'hoemen', 'breken']\n",
                "lookup_lexicon_terms(terms_to_check)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "### Loaded triggers (`FrameVerbLexicon`)\n",
                "\n",
                "Confirms runtime lexicon after CSV edits (`reload=True`).\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "lex = get_frame_verb_lexicon(reload=True)\n",
                "\n",
                "terms_to_check = [\n",
                "    'oncen', 'ponden', 'sullen', 'binnen', 'dingen', 'hoemen',\n",
                "    'breken', 'stampen', 'malen',\n",
                "]\n",
                "\n",
                "load_rows = pd.DataFrame(\n",
                "    {\n",
                "        'term': terms_to_check,\n",
                "        'in_lexicon': [lex.entry_for(t) is not None for t in terms_to_check],\n",
                "        'frame': [(lex.entry_for(t).frame.value if lex.entry_for(t) else '') for t in terms_to_check],\n",
                "        'sources': [(sorted(lex.entry_for(t).sources) if lex.entry_for(t) else []) for t in terms_to_check],\n",
                "    }\n",
                ")\n",
                "load_rows\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 2. Collocation skeleton (stream search)\n",
                "\n",
                "Large PMI table at `eval_reports/collocation_skeleton.csv`. Diagnostic only — does not control lexicon loading.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "_SKELETON_USECOLS = [\n",
                "    'target_norm',\n",
                "    'collocate_norm',\n",
                "    'collocate_type',\n",
                "    'pmi',\n",
                "    'frame_hint',\n",
                "    'in_frame_lexicon',\n",
                "    'cooc_count',\n",
                "    'target_snippet_count',\n",
                "    'rank_within_target',\n",
                "]\n",
                "\n",
                "\n",
                "def search_skeleton(\n",
                "    target_norm: str | None = None,\n",
                "    collocate_norm: str | None = None,\n",
                "    collocate_type: str | None = None,\n",
                "    topn: int = 25,\n",
                "    chunksize: int = 200_000,\n",
                ") -> pd.DataFrame:\n",
                "    target_norm = str(target_norm).strip().lower() if target_norm else None\n",
                "    collocate_norm = str(collocate_norm).strip().lower() if collocate_norm else None\n",
                "    collocate_type = str(collocate_type).strip().lower() if collocate_type else None\n",
                "\n",
                "    hits: list[pd.DataFrame] = []\n",
                "    for chunk in pd.read_csv(\n",
                "        SKELETON_CSV,\n",
                "        dtype=str,\n",
                "        usecols=_SKELETON_USECOLS,\n",
                "        chunksize=chunksize,\n",
                "        keep_default_na=False,\n",
                "    ):\n",
                "        mask = pd.Series(True, index=chunk.index)\n",
                "        if target_norm:\n",
                "            mask &= chunk['target_norm'].astype(str).str.lower().eq(target_norm)\n",
                "        if collocate_norm:\n",
                "            mask &= chunk['collocate_norm'].astype(str).str.lower().eq(collocate_norm)\n",
                "        if collocate_type:\n",
                "            mask &= chunk['collocate_type'].astype(str).str.lower().eq(collocate_type)\n",
                "        sub = chunk[mask]\n",
                "        if not sub.empty:\n",
                "            hits.append(sub)\n",
                "        if sum(len(x) for x in hits) >= topn:\n",
                "            break\n",
                "\n",
                "    if not hits:\n",
                "        return pd.DataFrame(columns=_SKELETON_USECOLS)\n",
                "\n",
                "    out = pd.concat(hits, ignore_index=True)\n",
                "    out['pmi_num'] = pd.to_numeric(out['pmi'], errors='coerce').fillna(-1)\n",
                "    out = out.sort_values(['pmi_num', 'rank_within_target'], ascending=[False, True])\n",
                "    return out.drop(columns=['pmi_num']).head(topn)\n",
                "\n",
                "\n",
                "search_skeleton(target_norm='bier', collocate_type='verb', topn=15)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "search_skeleton(collocate_norm='ponden', topn=20)\n",
                "search_skeleton(collocate_norm='oncen', topn=20)\n",
                "search_skeleton(target_norm='bier', collocate_norm='brouwen', topn=10)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 3. GijsBERT dev gold + skeleton audit\n",
                "\n",
                "Hand-gold dev split (`trifecta_gijsbert/dev.jsonl`). Compare **gold frame** vs **corpus-wide** top verb collocates per target.\n",
                "\n",
                "Skeleton = target-level prior from all `food_snippets_long` rows — not the verb in this specific snippet.\n",
                "\n",
                "**Go/no-go for wiring skeleton into `export_gijsbert.py`:**\n",
                "- **Coverage** — framed dev targets with ≥1 skeleton verb\n",
                "- **Hint alignment** — top skeleton `frame_hint` matches gold (when hint present)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def _marked_verb(text: str) -> str:\n",
                "    m = re.search(r'\\[VRB\\](.*?)\\[/VRB\\]', str(text), flags=re.DOTALL)\n",
                "    return m.group(1).strip() if m else ''\n",
                "\n",
                "\n",
                "dev = [json.loads(line) for line in DEV_JSONL.read_text(encoding='utf-8').splitlines() if line.strip()]\n",
                "dev_df = pd.DataFrame(dev)\n",
                "dev_df['target_norm'] = dev_df['target_word'].map(normalize_hist_dutch)\n",
                "dev_df['marked_verb'] = dev_df['text'].map(_marked_verb)\n",
                "framed = dev_df[dev_df['label'] != 'NONE'].copy()\n",
                "\n",
                "print('dev rows:', len(dev_df))\n",
                "print('NONE:', int((dev_df['label'] == 'NONE').sum()))\n",
                "print('framed:', len(framed))\n",
                "print('with [VRB] mark:', int((dev_df['marked_verb'] != '').sum()))\n",
                "framed[['record_id', 'target_norm', 'label', 'marked_verb']].head(12)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def skeleton_verbs_for_targets(\n",
                "    target_norms: list[str],\n",
                "    *,\n",
                "    topn_per_target: int = 3,\n",
                "    chunksize: int = 200_000,\n",
                ") -> pd.DataFrame:\n",
                "    \"\"\"One pass: top verb collocates per target_norm.\"\"\"\n",
                "    wanted = {str(t).strip().lower() for t in target_norms if str(t).strip()}\n",
                "    if not wanted:\n",
                "        return pd.DataFrame(columns=_SKELETON_USECOLS)\n",
                "\n",
                "    hits: list[pd.DataFrame] = []\n",
                "    for chunk in pd.read_csv(\n",
                "        SKELETON_CSV,\n",
                "        dtype=str,\n",
                "        usecols=_SKELETON_USECOLS,\n",
                "        chunksize=chunksize,\n",
                "        keep_default_na=False,\n",
                "    ):\n",
                "        sub = chunk[\n",
                "            chunk['target_norm'].astype(str).str.lower().isin(wanted)\n",
                "            & chunk['collocate_type'].astype(str).str.lower().eq('verb')\n",
                "        ]\n",
                "        if not sub.empty:\n",
                "            hits.append(sub)\n",
                "\n",
                "    if not hits:\n",
                "        return pd.DataFrame(columns=_SKELETON_USECOLS)\n",
                "\n",
                "    verbs = pd.concat(hits, ignore_index=True)\n",
                "    verbs['rank_num'] = pd.to_numeric(verbs['rank_within_target'], errors='coerce').fillna(9999)\n",
                "    verbs = verbs.sort_values(['target_norm', 'rank_num', 'pmi'], ascending=[True, True, False])\n",
                "    return verbs.groupby('target_norm', as_index=False).head(topn_per_target).drop(columns=['rank_num'])\n",
                "\n",
                "\n",
                "def dev_skeleton_audit(framed_df: pd.DataFrame, topn_per_target: int = 3) -> pd.DataFrame:\n",
                "    targets = framed_df['target_norm'].drop_duplicates().tolist()\n",
                "    skel = skeleton_verbs_for_targets(targets, topn_per_target=topn_per_target)\n",
                "\n",
                "    audit = framed_df[\n",
                "        ['record_id', 'target_norm', 'label', 'marked_verb', 'corpus']\n",
                "    ].drop_duplicates(subset=['record_id'])\n",
                "\n",
                "    if skel.empty:\n",
                "        audit = audit.assign(\n",
                "            skeleton_verb_rows=0,\n",
                "            top_skeleton_verbs='',\n",
                "            top_skeleton_hints='',\n",
                "        )\n",
                "    else:\n",
                "        agg = (\n",
                "            skel.groupby('target_norm', as_index=False)\n",
                "            .agg(\n",
                "                skeleton_verb_rows=('collocate_norm', 'count'),\n",
                "                top_skeleton_verbs=('collocate_norm', lambda s: ', '.join(s.astype(str))),\n",
                "                top_skeleton_hints=('frame_hint', lambda s: ', '.join(h for h in s.astype(str) if h)),\n",
                "            )\n",
                "        )\n",
                "        audit = audit.merge(agg, on='target_norm', how='left')\n",
                "        audit['skeleton_verb_rows'] = audit['skeleton_verb_rows'].fillna(0).astype(int)\n",
                "        audit['top_skeleton_verbs'] = audit['top_skeleton_verbs'].fillna('')\n",
                "        audit['top_skeleton_hints'] = audit['top_skeleton_hints'].fillna('')\n",
                "\n",
                "    audit['has_skeleton_verbs'] = audit['skeleton_verb_rows'] > 0\n",
                "    audit['hint_matches_gold'] = audit.apply(\n",
                "        lambda r: r['label'] in str(r['top_skeleton_hints']).split(', ')\n",
                "        if str(r['top_skeleton_hints']).strip()\n",
                "        else False,\n",
                "        axis=1,\n",
                "    )\n",
                "    return audit.sort_values(['label', 'target_norm', 'record_id'])\n",
                "\n",
                "\n",
                "audit_df = dev_skeleton_audit(framed)\n",
                "audit_df.head(20)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def audit_summary(audit: pd.DataFrame) -> pd.DataFrame:\n",
                "    rows = []\n",
                "    for label, grp in audit.groupby('label', sort=False):\n",
                "        n = len(grp)\n",
                "        covered = int(grp['has_skeleton_verbs'].sum())\n",
                "        hinted = int((grp['top_skeleton_hints'] != '').sum())\n",
                "        aligned = int(grp['hint_matches_gold'].sum())\n",
                "        rows.append(\n",
                "            {\n",
                "                'gold_frame': label,\n",
                "                'dev_rows': n,\n",
                "                'targets_with_skeleton_verbs': covered,\n",
                "                'coverage_pct': round(100 * covered / n, 1) if n else 0.0,\n",
                "                'rows_with_hints': hinted,\n",
                "                'hint_matches_gold': aligned,\n",
                "                'alignment_pct': round(100 * aligned / hinted, 1) if hinted else 0.0,\n",
                "            }\n",
                "        )\n",
                "    total = len(audit)\n",
                "    covered_all = int(audit['has_skeleton_verbs'].sum())\n",
                "    hinted_all = int((audit['top_skeleton_hints'] != '').sum())\n",
                "    aligned_all = int(audit['hint_matches_gold'].sum())\n",
                "    rows.append(\n",
                "        {\n",
                "            'gold_frame': 'ALL_FRAMED',\n",
                "            'dev_rows': total,\n",
                "            'targets_with_skeleton_verbs': covered_all,\n",
                "            'coverage_pct': round(100 * covered_all / total, 1) if total else 0.0,\n",
                "            'rows_with_hints': hinted_all,\n",
                "            'hint_matches_gold': aligned_all,\n",
                "            'alignment_pct': round(100 * aligned_all / hinted_all, 1) if hinted_all else 0.0,\n",
                "        }\n",
                "    )\n",
                "    return pd.DataFrame(rows)\n",
                "\n",
                "\n",
                "summary_df = audit_summary(audit_df)\n",
                "summary_df\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Drill into one gold frame\n",
                "audit_df[audit_df['label'] == 'INGESTION'][[\n",
                "    'target_norm', 'marked_verb', 'top_skeleton_verbs', 'top_skeleton_hints', 'hint_matches_gold'\n",
                "]]\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Mismatches: skeleton has hints but none match gold frame\n",
                "audit_df[\n",
                "    audit_df['top_skeleton_hints'].astype(str).str.strip().ne('')\n",
                "    & ~audit_df['hint_matches_gold']\n",
                "][['label', 'target_norm', 'marked_verb', 'top_skeleton_verbs', 'top_skeleton_hints']]\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Steering loop\n",
                "\n",
                "1. Edit `trifecta_frame_verb_corpus.csv` (`keep` + notes).\n",
                "2. `get_frame_verb_lexicon(reload=True)` — confirm loaded triggers.\n",
                "3. Re-export skeleton when lexicon changes should refresh `frame_hint`:\n",
                "   `uv run python scripts/export_collocation_skeleton.py --summary`\n",
                "4. Re-export GijsBERT splits after gold/silver changes:\n",
                "   `uv run python scripts/export_gijsbert.py ...`\n",
                "5. Regenerate this notebook after generator edits.\n",
            ]
        )
    )

    return nb


def build_gijsbert_none_silver_training() -> nbf.NotebookNode:
    """Notebook: KWIC NONE silver → GijsBERT export → train → eval checks."""
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = []

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# GijsBERT training sequence — NONE silver tranche + checks\n",
                "\n",
                "Regenerate — **do not hand-edit** the `.ipynb` JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name gijsbert_none_silver_training\n",
                "```\n",
                "\n",
                "## What this pipeline delivers\n",
                "\n",
                "| Stage | Output | Role |\n",
                "|-------|--------|------|\n",
                "| KWIC ingest | `food_snippets_long_kwic` | Deduped pool + `kwic_batch` |\n",
                "| `build_kwic_inputs` | `kwic_inputs.jsonl` | Clipped windows (~±180 chars) |\n",
                "| `batch_step_a` | `reizen_step_a.jsonl` | Step A only — **no Step B** on travel text |\n",
                "| Review CSV | `eval/step_a_dropout_review.csv` | You mark `accept` / `reject` |\n",
                "| Merge | `inception_silver_with_reizen_none.jsonl` | INCEpTION + reviewed NONE rows |\n",
                "| `export_gijsbert` | `train.jsonl`, `dev.jsonl` | Train = silver, dev = **hand gold** (unchanged) |\n",
                "| `train_gijsbert` | `models/gysbert-v2-…` | Fine-tuned checkpoint to compare |\n",
                "\n",
                "**Scope:** small reviewed tranches (25–200 rows), not bulk KWIC. "
                "Dev stays 157-row hand gold (~57% NONE); train gets a few extra NONE examples.\n",
                "\n",
                "Long LLM steps run in the **terminal** (Ollama). This notebook **checks** artifacts after each step.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Setup — manifest paths"])
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "import json\n",
                "import subprocess\n",
                "from collections import Counter\n",
                "from pathlib import Path\n",
                "\n",
                "import pandas as pd\n",
                "from data_io import resolve\n",
                "\n",
                "SCRATCH = Path(resolve('trifecta_gold')).parent\n",
                "EVAL = Path(resolve('eval_reports'))\n",
                "GIJSBERT_DIR = Path(resolve('trifecta_gijsbert'))\n",
                "MODELS_DIR = Path(resolve('trifecta_gijsbert_models'))\n",
                "\n",
                "PATHS = {\n",
                "    'kwic_long': Path(resolve('food_snippets_long_kwic')),\n",
                "    'kwic_inputs': Path(resolve('kwic_inputs')),\n",
                "    'step_a': SCRATCH / 'reizen_step_a.jsonl',\n",
                "    'dropout_review': EVAL / 'step_a_dropout_review.csv',\n",
                "    'inception_silver': SCRATCH / 'inception_annotations.jsonl',\n",
                "    'merged_silver': SCRATCH / 'inception_silver_with_reizen_none.jsonl',\n",
                "    'train_jsonl': GIJSBERT_DIR / 'train.jsonl',\n",
                "    'dev_jsonl': GIJSBERT_DIR / 'dev.jsonl',\n",
                "    'label_manifest': GIJSBERT_DIR / 'label_manifest.json',\n",
                "}\n",
                "\n",
                "for name, path in PATHS.items():\n",
                "    status = 'ok' if path.exists() else 'MISSING'\n",
                "    print(f'{status:7} {name:16} {path}')\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 0 — Prerequisites\n",
                "\n",
                "```bash\n",
                "uv run python -m data_io.check\n",
                "# Ollama running for Step A: ollama serve &  qwen2.5-coder:latest\n",
                "```\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "result = subprocess.run(\n",
                "    ['uv', 'run', 'python', '-m', 'data_io.check'],\n",
                "    capture_output=True,\n",
                "    text=True,\n",
                "    cwd=Path('..').resolve() if (Path.cwd() / 'scripts').exists() else Path.cwd(),\n",
                ")\n",
                "print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)\n",
                "if result.returncode:\n",
                "    print('WARN: manifest check returned', result.returncode)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 1 — Ingest KWIC xlsx + build `kwic_inputs`\n",
                "\n",
                "```bash\n",
                "# Ingest (skip legacy CSV copies if KWIC-only refresh)\n",
                "uv run python scripts/ingest_food_snippets.py --skip-csv --skip-long-csv --skip-txt\n",
                "\n",
                "# Small reizen pool for NONE pilot (~500 rows, clipped context)\n",
                "uv run python scripts/build_kwic_inputs.py --source kwic --kwic-batch reizen --limit 500\n",
                "```\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def check_kwic_pool() -> None:\n",
                "    p = PATHS['kwic_long']\n",
                "    if not p.exists():\n",
                "        print('SKIP: run ingest_food_snippets.py first')\n",
                "        return\n",
                "    df = pd.read_csv(p, usecols=['snippet', 'kwic_batch', 'matched_term'], dtype=str, nrows=50_000)\n",
                "    lens = df['snippet'].str.len()\n",
                "    print(f'long_kwic sample rows: {len(df):,}')\n",
                "    print(f'snippet chars p50/p90: {int(lens.median()):,} / {int(lens.quantile(0.9)):,}')\n",
                "    if 'kwic_batch' in df.columns:\n",
                "        reizen = df['kwic_batch'].str.contains('reizen', na=False).sum()\n",
                "        print(f'rows with reizen batch (sample): {reizen:,}')\n",
                "\n",
                "\n",
                "def check_kwic_inputs() -> None:\n",
                "    p = PATHS['kwic_inputs']\n",
                "    if not p.exists():\n",
                "        print('SKIP: run build_kwic_inputs.py --source kwic ...')\n",
                "        return\n",
                "    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]\n",
                "    lens = [len(r.get('context_text', '')) for r in rows]\n",
                "    batches = Counter(b for r in rows for b in str(r.get('kwic_batch') or '').split('|') if b)\n",
                "    print(f'kwic_inputs rows: {len(rows):,}')\n",
                "    print(f'context_text p50 chars: {sorted(lens)[len(lens) // 2]} (expect ~300–400 after clip)')\n",
                "    print('kwic_batch tags:', dict(batches.most_common(5)))\n",
                "\n",
                "\n",
                "check_kwic_pool()\n",
                "print()\n",
                "check_kwic_inputs()\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 2 — Step A batch (terminal; needs Ollama)\n",
                "\n",
                "Step A only — avoids Step B framing travel snippets as INGESTION.\n",
                "\n",
                "```bash\n",
                "uv run python scripts/batch_step_a.py \\\n",
                "  --input-logical kwic_inputs \\\n",
                "  --limit 200 --concurrency 2 --resume\n",
                "```\n",
                "\n",
                "Pilot: `--limit 25` (~30 s). Full tranche: 200 (~5–15 min with concurrency 2).\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def check_step_a() -> pd.DataFrame | None:\n",
                "    p = PATHS['step_a']\n",
                "    if not p.exists():\n",
                "        print('SKIP: run batch_step_a.py (Ollama)')\n",
                "        return None\n",
                "    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]\n",
                "    dropped = [r for r in rows if r.get('dropped')]\n",
                "    print(f'Step A rows: {len(rows)} | dropouts: {len(dropped)} ({100*len(dropped)/max(len(rows),1):.0f}%)')\n",
                "    reasons = Counter(r.get('drop_reason') for r in dropped)\n",
                "    print('drop_reason:', dict(reasons))\n",
                "    # sample dropouts\n",
                "    for r in dropped[:3]:\n",
                "        prov = r.get('provenance') or {}\n",
                "        a = r.get('step_a') or {}\n",
                "        print('---')\n",
                "        print(prov.get('target_word'), '|', r.get('drop_reason'), '|', (a.get('reasoning') or '')[:80])\n",
                "        print((prov.get('context_text') or '')[:160], '…')\n",
                "    return pd.DataFrame(rows)\n",
                "\n",
                "\n",
                "step_a_df = check_step_a()\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 3 — Review dropouts (human)\n",
                "\n",
                "```bash\n",
                "uv run python scripts/export_step_a_dropout_review.py\n",
                "```\n",
                "\n",
                "Open `eval/step_a_dropout_review.csv`. Fill **`verdict`**: `accept` | `reject`.\n",
                "\n",
                "**Review rule (NONE-scope):** accept when the target is **out of scope** for TRIFECTA "
                "frame labeling in this snippet (homograph, travel/catalog, false KWIC hit) — **not** "
                "whether Step A called it `metaphor`. Reject when real food context applies "
                "(e.g. `lever` as organ in recipe text).\n",
                "\n",
                "**Empty `verdict` is not accept** — only `accept`, `a`, `yes`, `y`, `k`, `keep` merge.\n",
                "\n",
                "| Column | Use |\n",
                "|--------|-----|\n",
                "| `recipe_context=true` | Often false NONE → scrutinize → **reject** |\n",
                "| `homonym_risk` / `homonym_hint` | Pre-score from homograph heuristics |\n",
                "| `step_a_metaphor` | Audit only — does **not** drive merge |\n",
                "| `homonym_check` | Optional: `food_sense` / `other_sense` / `metaphor` |\n",
                "\n",
                "Review ~50 rows/session; do **not** bulk-merge unreviewed dropouts at scale.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def check_dropout_review() -> pd.DataFrame | None:\n",
                "    p = PATHS['dropout_review']\n",
                "    if not p.exists():\n",
                "        print('SKIP: run export_step_a_dropout_review.py')\n",
                "        return None\n",
                "    df = pd.read_csv(p, dtype=str, keep_default_na=False)\n",
                "    verdicts = df['verdict'].str.strip().str.lower()\n",
                "    n_accept = verdicts.isin({'accept', 'a', 'yes', 'y', 'k', 'keep'}).sum()\n",
                "    n_reject = verdicts.isin({'reject', 'r', 'no', 'n', 'drop', 'skip'}).sum()\n",
                "    n_pending = len(df) - n_accept - n_reject\n",
                "    print(f'review rows: {len(df)} | accept: {n_accept} | reject: {n_reject} | pending: {n_pending}')\n",
                "    if n_pending:\n",
                "        print('Fill verdict before merge — pending record_ids:')\n",
                "        pending = df[verdicts.eq('') | (~verdicts.isin({\n",
                "            'accept','a','yes','y','k','keep','reject','r','no','n','drop','skip'\n",
                "        }))]\n",
                "        display(pending[['record_id', 'target_word', 'recipe_context', 'drop_reason', 'context_snippet']].head(10))\n",
                "    recipe_flag = df[df['recipe_context'].str.lower() == 'true']\n",
                "    if len(recipe_flag):\n",
                "        print(f'\\nrecipe_context=true rows to scrutinize: {len(recipe_flag)}')\n",
                "    return df\n",
                "\n",
                "\n",
                "try:\n",
                "    from IPython.display import display\n",
                "except ImportError:\n",
                "    display = print  # noqa: A001\n",
                "\n",
                "review_df = check_dropout_review()\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 4 — Merge silver + export GijsBERT splits\n",
                "\n",
                "```bash\n",
                "uv run python scripts/merge_silver_jsonl.py \\\n",
                "  --base \"$SCRATCH/inception_annotations.jsonl\" \\\n",
                "  --append \"$SCRATCH/reizen_step_a.jsonl\" \\\n",
                "  --review-csv \"$SCRATCH/eval/step_a_dropout_review.csv\" \\\n",
                "  --append-limit 200 \\\n",
                "  --output \"$SCRATCH/inception_silver_with_reizen_none.jsonl\" \\\n",
                "  --summary\n",
                "\n",
                "uv run python scripts/export_gijsbert.py \\\n",
                "  --silver-path \"$SCRATCH/inception_silver_with_reizen_none.jsonl\"\n",
                "```\n",
                "\n",
                "Or use `resolve()` paths from the setup cell instead of `$SCRATCH`.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def label_counts_jsonl(path: Path) -> Counter:\n",
                "    if not path.exists():\n",
                "        return Counter()\n",
                "    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]\n",
                "    return Counter(r.get('label') for r in rows)\n",
                "\n",
                "\n",
                "def check_gijsbert_splits() -> None:\n",
                "    if PATHS['merged_silver'].exists():\n",
                "        base_n = sum(1 for _ in open(PATHS['inception_silver']) if _.strip())\n",
                "        merged_n = sum(1 for _ in open(PATHS['merged_silver']) if _.strip())\n",
                "        print(f'merged silver: {merged_n} rows (+{merged_n - base_n} vs inception_annotations)')\n",
                "    else:\n",
                "        print('merged silver: MISSING — run merge_silver_jsonl.py')\n",
                "\n",
                "    train = label_counts_jsonl(PATHS['train_jsonl'])\n",
                "    dev = label_counts_jsonl(PATHS['dev_jsonl'])\n",
                "    if not train:\n",
                "        print('train.jsonl: MISSING — run export_gijsbert.py')\n",
                "        return\n",
                "    train_n = sum(train.values())\n",
                "    dev_n = sum(dev.values())\n",
                "    train_none = 100 * train.get('NONE', 0) / train_n\n",
                "    dev_none = 100 * dev.get('NONE', 0) / max(dev_n, 1)\n",
                "    print(f'\\ntrain labels ({train_n} rows):', dict(train.most_common()))\n",
                "    print(f'dev labels   ({dev_n} rows):', dict(dev.most_common()))\n",
                "    print(f'\\nNONE %  train: {train_none:.1f}%  |  dev: {dev_none:.1f}%')\n",
                "    print('Expect train NONE << dev NONE until silver grows; compare frames-only dev separately.')\n",
                "\n",
                "\n",
                "check_gijsbert_splits()\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Step 5 — Fine-tune GijsBERT (terminal; `gijsbert` extra)\n",
                "\n",
                "```bash\n",
                "uv run --extra gijsbert python scripts/train_gijsbert.py \\\n",
                "  --output-dir \"$(uv run python -c 'from data_io import resolve; print(resolve(\"trifecta_gijsbert_models\") / \"gysbert-v2-reizen-none\")')\" \\\n",
                "  --oversample-none 2 --class-weight-balance --none-weight-boost 2.0\n",
                "\n",
                "uv run --extra gijsbert python scripts/compare_gijsbert_runs.py\n",
                "```\n",
                "\n",
                "Compare **frames-only** dev (excl. NONE) and NONE F1 — not pooled accuracy alone.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def check_training_runs() -> None:\n",
                "    if not MODELS_DIR.exists():\n",
                "        print('No models dir:', MODELS_DIR)\n",
                "        return\n",
                "    runs = sorted(MODELS_DIR.iterdir())\n",
                "    print('Model runs:')\n",
                "    for run in runs:\n",
                "        metrics = run / 'dev_metrics.json'\n",
                "        flag = '✓' if metrics.exists() else ' '\n",
                "        print(f'  [{flag}] {run.name}')\n",
                "        if metrics.exists():\n",
                "            m = json.loads(metrics.read_text())\n",
                "            acc = m.get('accuracy') or m.get('eval_accuracy')\n",
                "            print(f'       pooled acc: {acc}')\n",
                "            if 'per_class' in m:\n",
                "                none = m['per_class'].get('NONE', {})\n",
                "                print(f'       NONE F1: {none.get(\"f1\")}')\n",
                "\n",
                "\n",
                "check_training_runs()\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Decision checklist (before scaling NONE silver)\n",
                "\n",
                "1. **Dropout quality** — mostly homograph noise (`mede`, canal `water`), not recipe CURE (`lever`)?\n",
                "2. **Train NONE %** — moved toward dev, or still ~12% vs ~57%?\n",
                "3. **Dev NONE F1** — improved vs `gysbert-v2-balanced-none` / `none-oversample-10`?\n",
                "4. **Frames-only dev** — did extra NONE hurt frame discrimination?\n",
                "\n",
                "Pilot (Jul 2026): `gysbert-v2-reizen-none` — 61.8% pooled dev, NONE F1 0.82; frames-only ~35%. "
                "NONE silver loop **validated**; defer further tranches unless targeting NONE at scale.\n",
                "\n",
                "Docs: [SNIPPETS.md](../docs/SNIPPETS.md) · [ANNOTATION_STRATEGY.md](../docs/ANNOTATION_STRATEGY.md)\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## State of affairs (10 Jul 2026)\n",
                "\n",
                "**Primary goal:** qualia for analysis (Step C), not more NONE silver or GijsBERT-as-replacement for qwen.\n",
                "\n",
                "### What works today\n",
                "\n",
                "| Capability | Status |\n",
                "|------------|--------|\n",
                "| Full pipeline A→B→C (`trifecta-annotate`, `trifecta-batch`) | **Production-ready** (LLM) |\n",
                "| Step B eval on frozen 157-row gold | **75%** qwen baseline; per-regime reporting |\n",
                "| Step A NONE silver loop (`reizen` pilot) | **Validated** — 200 Step A → 59 accepted |\n",
                "| GijsBERT macro-frame classifier | **Trained** — 61.8% pooled dev, NONE F1 0.82 |\n",
                "| INCEpTION silver with Step C | ~2,752 LLM `step_c` rows (exploration only) |\n",
                "\n",
                "### Gaps for qualia-for-analysis\n",
                "\n",
                "| Gap | Current |\n",
                "|-----|---------|\n",
                "| Hand gold with Step C | **13 / 157** rows |\n",
                "| Step C in `trifecta-eval` | **Not implemented** |\n",
                "| GijsBERT qualia | **Not planned** — Step C stays LLM |\n",
                "\n",
                "### Usable for analysis?\n",
                "\n",
                "- **Exploratory qualia:** yes — `trifecta-batch` on a KWIC slice; treat `step_c` as LLM hypotheses.\n",
                "- **Analytic claims (counts, trends):** not yet — need quota hand gold + Step C eval.\n",
                "\n",
                "See [PLAN.md](../PLAN.md) · milestone **m10**.\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Next — qualia for analysis (m10)\n",
                "\n",
                "1. **Quota gold Step C** — one frame first (PRESERVING or COOKING_CREATION): ~30–50 rows, all qualia fields.\n",
                "2. **Batch + eval** — `trifecta-batch` on gold slice; add Step C field-match to `trifecta-eval`.\n",
                "3. **Prompt / few-shot pass** — tune lowest-F1 qualia roles; re-run on gold only.\n",
                "4. **Analysis batch** — full A→B→C on bounded KWIC export → parquet for notebooks.\n",
                "\n",
                "```bash\n",
                "# Exploratory qualia now (LLM hypotheses — spot-check before aggregating)\n",
                "uv run trifecta-batch --input-logical kwic_inputs --output-logical trifecta_annotations --resume --concurrency 2\n",
                "\n",
                "# Gold labelling for Step C fields\n",
                "uv run python scripts/export_gold_candidates.py --limit 50\n",
                "```\n",
            ]
        )
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "def check_qualia_coverage() -> None:\n",
                "    from data_io import load_parquet, load_jsonl\n",
                "\n",
                "    gold = load_parquet('trifecta_gold')\n",
                "    n_gold = len(gold)\n",
                "    with_b = with_c = 0\n",
                "    frames: Counter[str] = Counter()\n",
                "    for raw in gold['annotation_json']:\n",
                "        ann = json.loads(raw) if isinstance(raw, str) else raw\n",
                "        if ann.get('step_b'):\n",
                "            with_b += 1\n",
                "            f = (ann.get('step_b') or {}).get('selected_frame', '?')\n",
                "            frames[f] += 1\n",
                "        if ann.get('step_c'):\n",
                "            with_c += 1\n",
                "    print(f'hand gold: {n_gold} rows | step_b: {with_b} | step_c: {with_c}')\n",
                "    print('gold frames:', dict(frames))\n",
                "\n",
                "    silver_path = PATHS['inception_silver']\n",
                "    if silver_path.exists():\n",
                "        rows = load_jsonl(silver_path)\n",
                "        sc = sum(1 for r in rows if r.get('step_c'))\n",
                "        framed = sum(1 for r in rows if r.get('step_b') and not r.get('dropped'))\n",
                "        print(f'\\nINCEpTION silver: {len(rows)} rows | framed: {framed} | step_c: {sc} (LLM, unvalidated)')\n",
                "\n",
                "    ann_path = Path(resolve('trifecta_annotations'))\n",
                "    if ann_path.exists():\n",
                "        rows = load_jsonl(ann_path)\n",
                "        sc = sum(1 for r in rows if r.get('step_c'))\n",
                "        print(f'batch output: {len(rows)} rows | step_c: {sc}')\n",
                "    else:\n",
                "        print('\\nbatch output: MISSING — run trifecta-batch for exploratory qualia')\n",
                "\n",
                "\n",
                "check_qualia_coverage()\n",
            ]
        )
    )

    return nb


def build_cooking_stepc_gold_lab() -> nbf.NotebookNode:
    """Notebook: COOKING_CREATION Step 5 gold lab — overview table + row editor."""
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = []

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# COOKING_CREATION Step C gold lab\n",
                "\n",
                "Regenerate — **do not hand-edit** the `.ipynb` JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name cooking_stepc_gold_lab\n",
                "```\n",
                "\n",
                "**Workflow:** export batch → label here (homonym + Step A/B/C) → save CSV → merge/import.\n",
                "\n",
                "Operator runbook: [docs/GOLD_LABELLING.md § Step 5](../docs/GOLD_LABELLING.md#step-5-runbook--cooking_creation-qualia-m10)\n",
                "\n",
                "## UX\n",
                "\n",
                "- **Overview table** (itables) — spreadsheet-style browse, filter, sort\n",
                "- **Row editor** (ipywidgets) — snippet context + guided fields\n",
                "- Use the **dropdown** or **Prev/Next** to jump rows after scanning the table\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Setup"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Dev deps (ipykernel, ipywidgets, itables) install with: uv sync\n",
                "from pathlib import Path\n",
                "\n",
                "from data_io import resolve\n",
                "from trifecta_annotation.gold_nb import GoldBatchEditor, RowLabeller\n",
                "\n",
                "BATCH_PATH = Path(resolve('clear_frame_examples'))\n",
                "\n",
                "editor = GoldBatchEditor(BATCH_PATH)\n",
                "editor.summary()\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Export batch (if missing)\n",
                "\n",
                "Run once in the terminal (writes `clear_frame_examples` — no `$SCRATCH`):\n",
                "\n",
                "```bash\n",
                "uv run python scripts/export_clear_frame_examples.py --summary --pool-summary \\\n",
                "  --frames COOKING_CREATION \\\n",
                "  --frame-quota \"COOKING_CREATION:30\" --limit 30\n",
                "```\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Progress overview"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "editor.summary()\n",
                "editor.show_overview(frame='COOKING_CREATION')\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Label rows\n",
                "\n",
                "1. Read the **snippet** (target highlighted).\n",
                "2. Set **homonym_check** (`food_sense` / `other_sense` / `metaphor`).\n",
                "3. Fill **Step A** and **Step B**.\n",
                "4. Fill **Step C qualia** only when stated in the snippet (leave blank otherwise).\n",
                "5. Check **labelled**, click **Save & next** — pending queue, auto-saves CSV.\n",
                "6. Jump rows via the **dropdown** or **Prev/Next** (after scanning the overview).\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "> **N.B.** The overview table is **browse-only** — not Excel-style inline edit.\n",
                "> Edits go through the row editor below.\n",
                ">\n",
                "> With `pending_only=True`, finished (`labelled=true`) rows drop out of the queue,\n",
                "> so you cannot reopen them. To fix a mistake (e.g. leftover `mede`):\n",
                "> set `pending_only=False`, re-run the cell, pick the row in the dropdown.\n",
                "> For dropped non-food rows also set **Advanced → frame → NONE**.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# pending_only=True = unfinished queue only. False = revisit labelled rows.\n",
                "labeller = RowLabeller(editor, frame_filter='COOKING_CREATION', pending_only=True)\n",
                "labeller.display()\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Save to disk (optional)"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Autosave is on by default — each Save / Save & next writes the batch CSV.\n",
                "# Run this only to confirm or if you passed autosave=False:\n",
                "saved = editor.save()\n",
                "print('Wrote', saved)\n",
                "editor.summary()\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Merge and import\n",
                "\n",
                "```bash\n",
                "uv run python scripts/merge_gold_batch.py \\\n",
                "  --batch-logical clear_frame_examples \\\n",
                "  --import-after\n",
                "```\n",
            ],
        ),
    )

    return nb


def build_verb_phase2a_gold_lab() -> nbf.NotebookNode:
    """Notebook: review source Step B predictions and label Phase 2a qualia."""
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = []

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# Verb Phase 2a gold lab\n",
                "\n",
                "Regenerate this notebook; do not hand-edit its JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name verb_phase2a_gold_lab\n",
                "```\n",
                "\n",
                "The source Step B prediction is read-only evidence, not gold. For every row, choose a human frame,\n",
                "verify the frame verb, fill only the qualia for that frame, then mark it reviewed.\n",
            ],
        ),
    )
    nb["cells"].append(nbf.v4.new_markdown_cell(["## Setup"]))
    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "from pathlib import Path\n",
                "\n",
                "from data_io import resolve\n",
                "from trifecta_annotation.verb_phase2a_nb import VerbPhase2aLabeller\n",
                "\n",
                "BATCH_PATH = Path(resolve('verb_phase2a_gold'))\n",
                "labeller = VerbPhase2aLabeller(BATCH_PATH)\n",
                "labeller.summary()\n",
            ],
        ),
    )
    nb["cells"].append(nbf.v4.new_markdown_cell(["## Review rows"]))
    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Save and Save & next write directly to the scratch worksheet.\n",
                "labeller.display()\n",
            ],
        ),
    )
    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Completion\n",
                "\n",
                "The notebook stores `reviewed_frame`, `reviewed_lexical_unit`, frame-specific qualia,\n",
                "`uncertainty_note`, and `reviewed=true`. It does not overwrite the source prediction.\n",
            ],
        ),
    )
    return nb


def build_step_c_review() -> nbf.NotebookNode:
    """Notebook: Step C gold vs pred review — configurable for few-shot picking."""
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = []

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# Step C review — matches & misses\n",
                "\n",
                "Regenerate — **do not hand-edit** the `.ipynb` JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name step_c_review\n",
                "```\n",
                "\n",
                "**Display:** plain pandas + `walk_details` (works in Cursor). "
                "No itables/widgets required.\n",
                "\n",
                "Compare hand gold `step_c` to predictions. "
                "Edit **CONFIG**, re-run load / filter cells.\n",
                "\n",
                "CLI: `uv run python scripts/export_step_c_review.py`\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Config\n",
                "\n",
                "Edit this cell, then re-run the cells below.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "from pathlib import Path\n",
                "from dataclasses import replace\n",
                "\n",
                "from data_io import resolve\n",
                "from trifecta_annotation.step_c_review import (\n",
                "    StepCReviewConfig,\n",
                "    load_review_frame,\n",
                "    review_summary,\n",
                "    save_review_frame,\n",
                "    show_review,\n",
                "    walk_details,\n",
                ")\n",
                "\n",
                "EVAL = Path(resolve('eval_reports'))\n",
                "\n",
                "# --- knobs (change for future frames / slices) ---\n",
                "CONFIG = StepCReviewConfig(\n",
                "    gold_path=None,\n",
                "    predictions_path=Path(resolve('gold_predictions')),\n",
                "    output_path=EVAL / 'step_c_review.csv',\n",
                "    frames=(),  # e.g. ('COOKING_CREATION',)\n",
                "    tiers=(),  # e.g. ('joint', 'partial_strong', 'miss')\n",
                "    fewshot_only=False,\n",
                "    fewshot_levels=('yes', 'maybe'),\n",
                "    min_hits=0,\n",
                "    frame_ok_only=False,\n",
                ")\n",
                "\n",
                "CONFIG\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Load"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "review = load_review_frame(CONFIG)\n",
                "review_summary(review)\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Compact table\n",
                "\n",
                "Pandas view (scrollable). Filter with the next cell if needed.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "show_review(review, CONFIG)  # prefer_itables=True only in classic Jupyter\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Filter with pandas (no widgets)\n",
                "\n",
                "Change the boolean mask, re-run.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Examples — uncomment one:\n",
                "# slice_ = review[review['tier'].isin(['joint', 'partial_strong'])]\n",
                "# slice_ = review[review['gold_frame'] == 'COOKING_CREATION']\n",
                "# slice_ = review[review['fewshot_candidate'].astype(str).str.len() > 0]\n",
                "slice_ = review.copy()\n",
                "\n",
                "print(review_summary(slice_))\n",
                "show_review(slice_, CONFIG)\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## Read rows in detail (gold vs pred)\n",
                "\n",
                "Step through with `start` / `n`. Longer predictions are often fine — "
                "exact-match scores understate quality when pred ⊃ gold.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "walk_details(slice_, start=0, n=5)\n",
                "# walk_details(slice_, start=5, n=5)  # next page\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## Few-shot shortlist + save"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "FEWSHOT = replace(\n",
                "    CONFIG,\n",
                "    fewshot_only=True,\n",
                "    # frames=('COOKING_CREATION',),\n",
                "    output_path=EVAL / 'step_c_fewshot_candidates.csv',\n",
                ")\n",
                "few = load_review_frame(FEWSHOT)\n",
                "print(review_summary(few))\n",
                "walk_details(few, start=0, n=10)\n",
                "\n",
                "path_all = save_review_frame(review, CONFIG)\n",
                "path_few = save_review_frame(few, FEWSHOT)\n",
                "print('all →', path_all)\n",
                "print('fewshot →', path_few)\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## How to use this\n",
                "\n",
                "1. `walk_details` — compare GOLD vs PRED side by side.\n",
                "2. If you prefer longer PRED text, treat exact-match misses as "
                "**style**, not necessarily wrong — note for soft scoring later.\n",
                "3. Pick record_ids for few-shots (or say “all yes”) and wire into Step C prompts.\n",
                "4. Optional: open the saved CSV in Cursor for search/notes.\n",
            ],
        ),
    )

    return nb


def build_ldk2025_cookbook_slice() -> nbf.NotebookNode:
    """Notebook: 20th-century cookbook corpus slice (LDK2025) — KWIC extraction, A→B→C batch & qualia analysis."""
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = []

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "# 20th-Century Cookbook Corpus Slice (1910–1940)\n",
                "\n",
                "Regenerate — **do not hand-edit** the `.ipynb` JSON:\n",
                "\n",
                "```bash\n",
                "uv run python scripts/generate_notebooks.py --name ldk2025_cookbook_slice\n",
                "```\n",
                "\n",
                "This notebook explores the 20th-century Dutch cookbook corpus (`LDK2025/corpus`):\n",
                "1. **Corpus Ingest & KWIC Discovery:** Parse recipe sections (1910, 1912, 1925, 1940) and match food vocabulary terms.\n",
                "2. **Slice Extraction:** Sample a focused KWIC input batch.\n",
                "3. **Pipeline Annotation (A→B→C):** Run the LLM annotation pipeline with Structured Outputs.\n",
                "4. **Qualia Analysis:** Inspect Step A entities, Step B macro-frames, and Step C preparation/preservation qualia.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## 1. Setup & Corpus Discovery"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "from pathlib import Path\n",
                "import re\n",
                "import json\n",
                "import pandas as pd\n",
                "from tqdm.auto import tqdm\n",
                "\n",
                "from data_io import resolve, load_jsonl, save_jsonl, save_parquet\n",
                "from trifecta_annotation.vocabulary import resolve_thesaurus_lookup\n",
                "from trifecta_annotation.schemas import KwicInput, TrifectaAnnotation\n",
                "from trifecta_annotation.pipeline import annotate_record\n",
                "from trifecta_annotation.analysis_export import annotations_to_analysis_frame\n",
                "\n",
                "corpus_dir = Path(resolve('ldk2025_cookbooks'))\n",
                "cookbook_files = sorted(corpus_dir.glob('*.txt'))\n",
                "print(f'Found {len(cookbook_files)} cookbook files in {corpus_dir}:')\n",
                "for f in cookbook_files:\n",
                "    print(f'  - {f.name} ({f.stat().st_size / 1024:.1f} KB)')\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## 2. Recipe Extraction & KWIC Matcher"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "thesaurus_lookup = resolve_thesaurus_lookup()\n",
                "print(f'Loaded food thesaurus with {len(thesaurus_lookup)} indexed surface terms.')\n",
                "\n",
                "PRESERVATION_TERMS = {\n",
                "    'inmaken', 'inmaak', 'wecken', 'pekelen', 'gepekelde', 'pekelvleesch', 'zouten', 'gezouten',\n",
                "    'zoutevisch', 'rooken', 'gerookte', 'rookworst', 'droogen', 'drogen', 'gedroogde',\n",
                "    'gelei', 'confituur', 'jam', 'azijn', 'inmaakazijn', 'steriliseeren', 'steriliseren',\n",
                "}\n",
                "\n",
                "def extract_recipe_snippets(\n",
                "    file_path: Path,\n",
                "    max_snippets_per_file: int = 15,\n",
                "    include_preservation: bool = True,\n",
                ") -> list[dict]:\n",
                "    text = file_path.read_text(encoding='utf-8', errors='replace')\n",
                "    year_match = re.search(r'\\d{4}', file_path.name)\n",
                "    year = year_match.group(0) if year_match else '1900'\n",
                "    \n",
                "    # Split by numbered recipes (e.g., '1. Radijsjes.', '2. Garnalen.')\n",
                "    raw_recipes = re.split(r'\\n\\s*\\d+\\.\\s+', text)\n",
                "    general_snippets = []\n",
                "    pres_snippets = []\n",
                "    \n",
                "    for idx, recipe in enumerate(raw_recipes[1:], start=1):\n",
                "        cleaned = re.sub(r'\\s+', ' ', recipe).strip()\n",
                "        if len(cleaned) < 40:\n",
                "            continue\n",
                "        \n",
                "        words = re.findall(r'\\b[a-zA-ZÀ-ÿ\\-]+\\b', cleaned.lower())\n",
                "        found_term = None\n",
                "        for w in words:\n",
                "            if len(w) > 2 and w in thesaurus_lookup:\n",
                "                found_term = w\n",
                "                break\n",
                "        \n",
                "        if not found_term:\n",
                "            continue\n",
                "\n",
                "        is_pres = any(pt in words or pt in cleaned.lower() for pt in PRESERVATION_TERMS)\n",
                "        rec = {\n",
                "            'record_id': f'ldk2025_{year}_rec{idx}_{found_term}',\n",
                "            'corpus': 'ldk2025_cookbooks',\n",
                "            'target_word': found_term,\n",
                "            'context_text': cleaned[:350],\n",
                "            'date': year,\n",
                "            'source_path': file_path.name,\n",
                "            'text_regime': 'RECIPE_PRACTICE',\n",
                "            'is_preservation_candidate': is_pres,\n",
                "        }\n",
                "        \n",
                "        if is_pres:\n",
                "            pres_snippets.append(rec)\n",
                "        else:\n",
                "            general_snippets.append(rec)\n",
                "\n",
                "    # Balance general preparation with explicit preservation recipes\n",
                "    if include_preservation and pres_snippets:\n",
                "        n_pres = min(len(pres_snippets), max(3, max_snippets_per_file // 2))\n",
                "        n_gen = min(len(general_snippets), max_snippets_per_file - n_pres)\n",
                "        return general_snippets[:n_gen] + pres_snippets[:n_pres]\n",
                "    return general_snippets[:max_snippets_per_file]\n",
                "\n",
                "all_candidates = []\n",
                "for f in cookbook_files:\n",
                "    extracted = extract_recipe_snippets(f, max_snippets_per_file=15, include_preservation=True)\n",
                "    all_candidates.extend(extracted)\n",
                "\n",
                "print(f'Extracted {len(all_candidates)} balanced candidate KWIC records across all 4 cookbooks.')\n",
                "df_candidates = pd.DataFrame(all_candidates)\n",
                "print(f\"Preservation candidates in pool: {df_candidates['is_preservation_candidate'].sum()} / {len(df_candidates)}\")\n",
                "display(df_candidates.head(10))\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## 3. Save Slice & Run Pipeline (A→B→C)"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "kwic_inputs_path = resolve('ldk2025_kwic_inputs')\n",
                "save_jsonl(all_candidates, kwic_inputs_path, script='ldk2025_cookbook_slice.ipynb')\n",
                "print(f'Wrote KWIC inputs -> {kwic_inputs_path}')\n",
                "\n",
                "# Run batch annotation (sample of 20 or full slice)\n",
                "sample_to_annotate = all_candidates[:20]\n",
                "annotations = []\n",
                "\n",
                "print(f'Annotating sample of {len(sample_to_annotate)} records with Ollama / Qwen...')\n",
                "for item in tqdm(sample_to_annotate):\n",
                "    inp = KwicInput.model_validate(item)\n",
                "    ann = annotate_record(inp)\n",
                "    annotations.append(ann.model_dump(mode='json'))\n",
                "\n",
                "annotations_path = resolve('ldk2025_annotations')\n",
                "save_jsonl(annotations, annotations_path, script='ldk2025_cookbook_slice.ipynb')\n",
                "print(f'Saved annotations -> {annotations_path}')\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(["## 4. Flatten & Qualia Analysis"]),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "df_analysis = annotations_to_analysis_frame(annotations)\n",
                "print(f'Analysis table shape: {df_analysis.shape}')\n",
                "\n",
                "# Macro-frame distribution\n",
                "print('\\n--- Step B Macro-Frame Counts ---')\n",
                "print(df_analysis['selected_frame'].value_counts())\n",
                "\n",
                "# Display Step C extracted fields\n",
                "cols_to_show = [\n",
                "    'target_word', 'date', 'selected_frame', 'lexical_unit',\n",
                "    'COOKING_CREATION_Method', 'COOKING_CREATION_Process', 'COOKING_CREATION_Food_Product',\n",
                "    'PR_Technique', 'PR_Medium', 'PR_Food_Patient',\n",
                "]\n",
                "display(df_analysis[cols_to_show].fillna(''))\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 5. Comparative Analysis: VOC Recipes vs 20th-Century Cookbooks\n",
                "\n",
                "Compare macro-frames, culinary triggers, and preparation processes across historical eras.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Load historical VOC analysis dataset for side-by-side comparison\n",
                "try:\n",
                "    df_voc_analysis = pd.read_parquet(resolve('trifecta_analysis'))\n",
                "    has_voc = True\n",
                "    print(f'Loaded {len(df_voc_analysis)} historical analysis records from trifecta_analysis.')\n",
                "except Exception as e:\n",
                "    has_voc = False\n",
                "    print(f'Could not load trifecta_analysis ({e}). Using slice data only.')\n",
                "\n",
                "if has_voc:\n",
                "    # 1. Macro-Frame Distribution Comparison\n",
                "    print('=' * 60)\n",
                "    print('1. MACRO-FRAME DISTRIBUTION (VOC vs 20th-C. Cookbooks)')\n",
                "    print('=' * 60)\n",
                "    voc_frames = df_voc_analysis['selected_frame'].value_counts(normalize=True).rename('VOC_share')\n",
                "    ldk_frames = df_analysis['selected_frame'].value_counts(normalize=True).rename('20c_Cookbooks_share')\n",
                "    frame_comp = pd.concat([voc_frames, ldk_frames], axis=1).fillna(0.0)\n",
                "    display(frame_comp.applymap(lambda v: f'{v:.1%}'))\n",
                "\n",
                "    # 2. Top Culinary Trigger Verbs (lexical_unit)\n",
                "    print('\\n' + '=' * 60)\n",
                "    print('2. TOP TRIGGER VERBS (lexical_unit)')\n",
                "    print('=' * 60)\n",
                "    voc_lus = df_voc_analysis[df_voc_analysis['selected_frame'] == 'COOKING_CREATION']['lexical_unit'].str.lower().value_counts().head(10).rename('VOC_Cooking_LUs')\n",
                "    ldk_lus = df_analysis[df_analysis['selected_frame'] == 'COOKING_CREATION']['lexical_unit'].str.lower().value_counts().head(10).rename('20c_Cooking_LUs')\n",
                "    display(pd.concat([voc_lus.reset_index(), ldk_lus.reset_index()], axis=1).fillna(''))\n",
                "\n",
                "    # 3. Preparation Processes (COOKING_CREATION_Process)\n",
                "    print('\\n' + '=' * 60)\n",
                "    print('3. TOP PREPARATION PROCESSES (COOKING_CREATION_Process)')\n",
                "    print('=' * 60)\n",
                "    voc_proc = df_voc_analysis[df_voc_analysis['COOKING_CREATION_Process'] != '']['COOKING_CREATION_Process'].str.lower().value_counts().head(8).rename('VOC_Processes')\n",
                "    ldk_proc = df_analysis[df_analysis['COOKING_CREATION_Process'] != '']['COOKING_CREATION_Process'].str.lower().value_counts().head(8).rename('20c_Processes')\n",
                "    display(pd.concat([voc_proc.reset_index(), ldk_proc.reset_index()], axis=1).fillna(''))\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "# Annotate the remaining candidates from all 4 cookbooks\n",
                "remaining_candidates = all_candidates[len(annotations):]\n",
                "\n",
                "if remaining_candidates:\n",
                "    print(f'Annotating remaining {len(remaining_candidates)} records with Ollama / Qwen...')\n",
                "    for item in tqdm(remaining_candidates):\n",
                "        inp = KwicInput.model_validate(item)\n",
                "        ann = annotate_record(inp)\n",
                "        annotations.append(ann.model_dump(mode='json'))\n",
                "\n",
                "    # Update saved annotations\n",
                "    annotations_path = resolve('ldk2025_annotations')\n",
                "    save_jsonl(\n",
                "        annotations,\n",
                "        logical_name='ldk2025_annotations',\n",
                "        script='ldk2025_cookbook_slice.ipynb',\n",
                "    )\n",
                "    print(f'Updated full annotations dataset ({len(annotations)} records) -> {annotations_path}')\n",
                "\n",
                "    # Re-generate analysis frame\n",
                "    df_analysis = annotations_to_analysis_frame(annotations)\n",
                "    print(f'Updated analysis frame: {df_analysis.shape}')\n",
                "    print('\\nUpdated Step B Counts across all cookbooks:')\n",
                "    print(df_analysis['selected_frame'].value_counts())\n",
                "else:\n",
                "    print('All candidate records are already annotated.')\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 6. Comprehensive Corpus Statistics (Full 3,663 Recipes)\n",
                "\n",
                "Overview of the entire 1910–1940 cookbook corpus:\n",
                "1. **Corpus & Volume Summary:** Total recipes, unique targets, frame counts across years.\n",
                "2. **Top Ingredients & Triggers:** Top 20 ingredients with their most frequent governing verbs and methods.\n",
                "3. **Macro-Frame Breakdown:** Annual distribution across 1910, 1912, 1925, and 1940.\n",
                "4. **Step C Qualia Fill Rates:** Coverage for all qualia role fields.\n",
                "5. **Resulting Food Products:** Top extracted culinary output dishes.\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_code_cell(
            source=[
                "import pandas as pd\n",
                "import numpy as np\n",
                "from data_io import resolve\n",
                "\n",
                "df_full = pd.read_parquet(resolve('ldk2025_analysis'))\n",
                "\n",
                "# 1. Corpus Volume & Timeline Breakdown\n",
                "print('=' * 70)\n",
                "print('1. CORPUS VOLUME & TIMELINE (1910–1940)')\n",
                "print('=' * 70)\n",
                "timeline = df_full.groupby('date').agg(\n",
                "    recipes=('record_id', 'count'),\n",
                "    unique_targets=('target_word', 'nunique'),\n",
                "    cooking_creation=('selected_frame', lambda s: (s == 'COOKING_CREATION').sum()),\n",
                "    preserving=('selected_frame', lambda s: (s == 'PRESERVING').sum()),\n",
                "    cure=('selected_frame', lambda s: (s == 'CURE').sum()),\n",
                "    dropped=('dropped', 'sum')\n",
                ")\n",
                "display(timeline)\n",
                "\n",
                "# 2. Top 20 Food Targets & Their Dominant Cooking Triggers\n",
                "print('\\n' + '=' * 70)\n",
                "print('2. TOP 20 INGREDIENTS & DOMINANT PREPARATION TRIGGERS')\n",
                "print('=' * 70)\n",
                "top_targets = df_full['target_word'].value_counts().head(20).index\n",
                "target_stats = []\n",
                "for target in top_targets:\n",
                "    sub = df_full[df_full['target_word'] == target]\n",
                "    top_verbs = sub['lexical_unit'].str.lower().value_counts().head(3).index.tolist()\n",
                "    top_methods = sub[sub['COOKING_CREATION_Method'] != '']['COOKING_CREATION_Method'].str.lower().value_counts().head(2).index.tolist()\n",
                "    target_stats.append({\n",
                "        'target_word': target,\n",
                "        'count': len(sub),\n",
                "        'top_trigger_verbs': ', '.join(top_verbs),\n",
                "        'top_methods': ', '.join(top_methods[:2])\n",
                "    })\n",
                "display(pd.DataFrame(target_stats))\n",
                "\n",
                "# 3. Macro-Frame Distribution across Eras (Crosstab)\n",
                "print('\\n' + '=' * 70)\n",
                "print('3. MACRO-FRAME DISTRIBUTION PER YEAR')\n",
                "print('=' * 70)\n",
                "frame_xtab = pd.crosstab(df_full['date'], df_full['selected_frame'], margins=True)\n",
                "display(frame_xtab)\n",
                "\n",
                "# 4. Qualia Extraction Coverage\n",
                "print('\\n' + '=' * 70)\n",
                "print('4. STEP C QUALIA EXTRACTION FILL RATES')\n",
                "print('=' * 70)\n",
                "qualia_cols = [\n",
                "    'COOKING_CREATION_Method', 'COOKING_CREATION_Process', 'COOKING_CREATION_Food_Product',\n",
                "    'PR_Technique', 'PR_Medium', 'PR_Food_Patient',\n",
                "    'CURE_Affliction', 'CURE_Food_Treatment',\n",
                "    'INGESTION_Context', 'INGESTION_Manner'\n",
                "]\n",
                "fill_rates = []\n",
                "for col in qualia_cols:\n",
                "    non_empty = (df_full[col].astype(str).str.strip() != '').sum()\n",
                "    fill_rates.append({\n",
                "        'field': col,\n",
                "        'filled_count': non_empty,\n",
                "        'fill_rate': f'{non_empty / len(df_full):.1%}'\n",
                "    })\n",
                "display(pd.DataFrame(fill_rates))\n",
                "\n",
                "# 5. Top 15 Resulting Food Products (COOKING_CREATION_Food_Product)\n",
                "print('\\n' + '=' * 70)\n",
                "print('5. TOP 15 RESULTING DISHES & PRODUCTS (COOKING_CREATION_Food_Product)')\n",
                "print('=' * 70)\n",
                "top_products = df_full[df_full['COOKING_CREATION_Food_Product'] != '']['COOKING_CREATION_Food_Product'].value_counts().head(15)\n",
                "display(top_products.to_frame(name='count'))\n",
            ],
        ),
    )

    nb["cells"].append(
        nbf.v4.new_markdown_cell(
            [
                "## 7. Summary & Observations\n",
                "\n",
                "- **Frame distribution:** In 20th-century recipe practice, `COOKING_CREATION` dominates along with selective `PRESERVING`.\n",
                "- **Step C Qualia clarity:** Modern 20th-century Dutch syntax leads to cleaner method and product spans.\n",
                "- **Integration:** This corpus provides a natural modern bridge for comparative historical analyses against the VOC corpora.\n",
            ],
        ),
    )

    return nb


NB_BUILDERS: dict[str, Callable[[], nbf.NotebookNode]] = {
    "inspect_lexicon_csvs": build_inspect_lexicon_csvs,
    "gijsbert_none_silver_training": build_gijsbert_none_silver_training,
    "cooking_stepc_gold_lab": build_cooking_stepc_gold_lab,
    "verb_phase2a_gold_lab": build_verb_phase2a_gold_lab,
    "step_c_review": build_step_c_review,
    "ldk2025_cookbook_slice": build_ldk2025_cookbook_slice,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Generate all notebooks")
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        help=f"Notebook name(s). Available: {', '.join(sorted(NB_BUILDERS))}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write notebooks (default: ./notebooks)",
    )
    args = parser.parse_args()

    names = list(NB_BUILDERS)
    if not args.all:
        if args.name:
            names = args.name
        else:
            names = ["inspect_lexicon_csvs"]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        if name not in NB_BUILDERS:
            raise SystemExit(f"Unknown notebook builder: {name}")
        nb = NB_BUILDERS[name]()
        out_path = args.output_dir / f"{name}.ipynb"
        nbf.write(nb, out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
