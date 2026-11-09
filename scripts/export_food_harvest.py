"""Export the food harvest for collocation / statistics exploration by colleagues.

Every annotated food mention from every annotation source (curated corpus,
initial exploration, DBNL sweep, entry scope, weak-regime verb run once
annotated), labelled with its outcome, as:

  mentions.csv / mentions.parquet  one row per mention: left | keyword | right,
                                   normalised term, frame or NONE / DROPPED, genre, year...
  works.csv                        one row per work (metadata + counts)
  plaintext/<genre>/<year>_<work>.txt one plain-text document per work (its unique contexts),
  plaintext.zip                       zipped; loads in #LancsBox X (genre folders = sub-corpora) or Voyant
  README.md, food_harvest_starter.ipynb

Rows are deduplicated on (work, context, target word) across sources. Rerunnable;
writes only under the output directory.

    uv run python scripts/export_food_harvest.py [--out DIR]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import work_stem
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path("/Volumes/Extreme SSD/scratch/trifecta/exports/food_harvest")
NOTEBOOK = ROOT / "notebooks" / "food_harvest_starter.ipynb"
SOURCES = {
    "trifecta_annotations": "Curated corpus",
    "colonial_annotations": "Initial exploration",
    "handdownload_annotations": "Initial exploration",
    "dbnl_sweep_annotations": "DBNL sweep",
    "entry_scope_annotations": "Entry scope",
    "weak_regime_verb_annotations": "Weak-regime verb",
}


def _jsonl(path: Path):
    for line in path.open(encoding="utf-8"):
        if line.strip() and not line.startswith("---"):
            yield json.loads(line)


def _year(value) -> int | None:
    m = re.search(r"\b(1[2-9]\d\d)\b", str(value or ""))
    return int(m.group(1)) if m else None


def split_kwic(context: str, word: str) -> tuple[str, str, str]:
    """(left, keyword, right) around the occurrence of `word` nearest the middle of
    the window (harvest windows are centred on the target). Keyword extended to the
    whole token, so 'koffie' in 'koffiekan' yields 'koffiekan'."""
    text = re.sub(r"\s+", " ", context or "").strip()
    if not word:
        return text, "", ""
    hits = list(re.finditer(re.escape(word), text, re.IGNORECASE))
    if not hits:
        return text, "", ""
    mid = len(text) / 2
    m = min(hits, key=lambda h: abs((h.start() + h.end()) / 2 - mid))
    s, e = m.start(), m.end()
    while s > 0 and text[s - 1].isalnum():
        s -= 1
    while e < len(text) and text[e].isalnum():
        e += 1
    return text[:s].rstrip(), text[s:e], text[e:].lstrip()


def _slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")[:n] or "untitled"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out: Path = args.out

    terms = load_food_terms()
    canonical = alt_label_index(terms)
    vocab = {str(r["Pref_label"]).strip().lower(): r for _, r in terms.iterrows()}
    work_year: dict[str, int] = {}
    for rec in load_genre_records():
        y = _year(rec.get("year"))
        if y and rec.get("ti_id"):
            work_year.setdefault(work_stem(rec["ti_id"]), y)
    current_scope = {r["record_id"] for r in _jsonl(Path(resolve("entry_scope_kwic_inputs")))}

    regime_cache: dict[tuple, str] = {}
    seen: set[tuple] = set()
    rows: list[dict] = []
    stats: Counter = Counter()
    for logical, label in SOURCES.items():
        path = Path(resolve(logical))
        if not path.exists():
            continue
        for r in _jsonl(path):
            pv = r["provenance"]
            if logical == "entry_scope_annotations" and pv["record_id"] not in current_scope:
                continue
            sp = pv.get("source_path") or ""
            stem = work_stem(sp)
            word = (pv.get("target_word") or "").strip()
            key = (stem, pv.get("context_text"), word.lower())
            if key in seen:
                stats["duplicate across sources"] += 1
                continue
            seen.add(key)
            frame = (r.get("step_b") or {}).get("selected_frame")
            status = ("error" if r.get("error") else "dropped" if r.get("dropped")
                      else "frame" if frame not in (None, "NONE") else "no_frame")
            ck = (pv.get("corpus"), stem)
            if ck not in regime_cache:
                regime_cache[ck] = infer_text_regime(corpus=pv.get("corpus"), title=pv.get("title"),
                                                     source_path=sp).value
            year = _year(pv.get("date")) or work_year.get(stem)
            pref = canonical.get(word.lower(), word.lower())
            v = vocab.get(pref)
            ctx_clean = re.sub(r"\s+", " ", html.unescape(pv.get("context_text") or "")).strip()  # DBNL keeps &nbsp; etc.
            left, kw, right = split_kwic(ctx_clean, word)
            step_c = {k: v_ for k, v_ in (r.get("step_c") or {}).items() if k not in ("frame",)}
            rows.append({
                "mention_id": pv["record_id"],
                "source": label,
                "work_id": stem,
                "title": pv.get("title") or sp,
                "year": year,
                "decade": (year // 10 * 10) if year else None,
                "genre": regime_cache[ck],
                "target_word": word,
                "keyword": kw or word,
                "pref_label": pref,
                "food_type": v["Type"] if v is not None and isinstance(v["Type"], str) else "",
                "eng_translation": v["Eng_translation"] if v is not None and isinstance(v["Eng_translation"], str) else "",
                "status": status,
                "frame": frame if status == "frame" else ("NONE" if status == "no_frame" else ""),
                "drop_reason": r.get("drop_reason") or "",
                "selection_mode": pv.get("kwic_mode") or "",
                "discovery_verb": pv.get("discovery_verb") or "",
                "frame_elements": json.dumps(step_c, ensure_ascii=False) if step_c else "",
                "left": left,
                "right": right,
                "context": ctx_clean,
            })
            stats[f"{label}: {status}"] += 1

    df = pd.DataFrame(rows)
    df["year"] = df["year"].astype("Int64")
    df["decade"] = df["decade"].astype("Int64")
    if out.exists():
        shutil.rmtree(out)
    (out / "plaintext").mkdir(parents=True)
    df.to_csv(out / "mentions.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(out / "mentions.parquet", index=False)

    works = (df.groupby("work_id")
             .agg(title=("title", "first"), year=("year", "first"), genre=("genre", "first"),
                  sources=("source", lambda s: ", ".join(sorted(set(s)))),
                  mentions=("mention_id", "size"), frames=("status", lambda s: int((s == "frame").sum())))
             .reset_index().sort_values(["year", "work_id"]))
    works.to_csv(out / "works.csv", index=False, encoding="utf-8-sig")

    # Plain text (LancsBox / Voyant): one document per work, its unique contexts in document order of appearance.
    by_work: dict[str, list[str]] = defaultdict(list)
    for wid, ctx in zip(df["work_id"], df["context"]):
        if ctx and ctx not in by_work[wid]:
            by_work[wid].append(ctx)
    meta = works.set_index("work_id")
    for wid, ctxs in by_work.items():
        m = meta.loc[wid]
        year = "" if pd.isna(m["year"]) else str(int(m["year"]))
        d = out / "plaintext" / (m["genre"] or "UNKNOWN")
        d.mkdir(exist_ok=True)
        (d / f"{year or 'undated'}_{_slug(m['title'])}_{_slug(wid, 20)}.txt").write_text(
            "\n\n".join(ctxs) + "\n", encoding="utf-8")
    with zipfile.ZipFile(out / "plaintext.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted((out / "plaintext").rglob("*.txt")):
            zf.write(f, f.relative_to(out / "plaintext"))

    if NOTEBOOK.exists():
        shutil.copy(NOTEBOOK, out / NOTEBOOK.name)
    counts = df["status"].value_counts().to_dict()
    frames = df.loc[df["status"] == "frame", "frame"].value_counts().to_dict()
    readme = README.format(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        n=len(df), works=len(works), counts=counts, frames=frames,
        sources=", ".join(df["source"].value_counts().index),
        dup=stats["duplicate across sources"],
        dated=f"{df['year'].notna().mean():.0%}",
        genres=", ".join(f"{k} {v}" for k, v in df["genre"].value_counts().items()),
    )
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote {len(df)} mentions, {len(works)} works -> {out}")
    print("status:", counts)
    print("frames:", frames)


README = """# Food harvest: mentions of food terms in printed Dutch texts

Generated {generated} by `trifecta-annotation/scripts/export_food_harvest.py`
(rerun it to refresh; the weak-regime run adds rows once annotated).

{n} food mentions from {works} works. Sources: {sources}. Dated (edition year): {dated}.
Outcome: {counts}. Frames: {frames}.
Genres: {genres}. {dup} duplicate mentions across sources were merged.

## Files

| file | what |
|---|---|
| `mentions.csv` (UTF-8 with BOM) / `mentions.parquet` | one row per mention, see columns below |
| `works.csv` | one row per work: title, edition year, genre, sources, mentions, frames |
| `plaintext/`, `plaintext.zip` | one plain-text document per work (its unique contexts), one folder per genre. For collocation statistics use **#LancsBox X** (local; load each genre folder as a sub-corpus; log-Dice / MI / GraphColl). For a quick visual overview **Voyant Tools** (note: voyant-tools.org means uploading the texts; a local Voyant server avoids that) |
| `food_harvest_starter.ipynb` | loading, concordance filtering, first collocation measures (pandas only) |

## Columns of `mentions`

- `mention_id`, `source`, `work_id`, `title`, `year` (edition year), `decade`, `genre`
- `target_word` (as harvested), `keyword` (the whole token in the text, e.g. *koffiekan*),
  `pref_label` (normalised term from the food vocabulary: use this to pool spelling variants),
  `food_type`, `eng_translation` (from the vocabulary; often empty)
- `status`: `frame` (a food frame was found), `no_frame` (food word, but no food frame),
  `dropped` (Step A judged the mention not about food), `error`
- `frame`: COOKING_CREATION / INGESTION / CURE / PRESERVING, or NONE; `frame_elements`: JSON of
  Step C slots (e.g. `CURE_Affliction`) where extracted
- `selection_mode` (how the mention was selected: `verb_food`, `entry_scope`, or empty = older noun
  harvest), `discovery_verb`
- `left`, `keyword`, `right`: the context split at the keyword; `context`: the whole window
  (about 180 characters either side)

## Read before counting

- **A sample, unevenly spread.** Works were sampled (at most 10, later 50, mentions per work in the
  sweep; one large household dictionary, Chomel 1743, dominates the curated corpus). Normalise per
  work or per genre before comparing periods; `works.csv` gives the denominators.
- **The selection is not neutral.** Most rows were selected because a food word sits near a food
  verb (`selection_mode`), so collocates of verbs are over-represented by design. Compare `frame`
  against `no_frame` / `dropped` rows, which went through the same selection, rather than against
  general Dutch.
- **Windows overlap.** Two mentions close together share text; a collocate can be counted twice.
  The plain-text documents keep each context once per work, but overlapping windows still repeat text.
- **Spelling varies** (suycker, suijcker, suiker): pool on `pref_label`, or normalise yourself.
- **Labels are model output.** Frames come from a local LLM cascade; treat them as a strong hint,
  not ground truth. Genre is a work-level inference (UNKNOWN is mostly literature, children's books
  and songs). Dates are edition years, not composition dates.
"""


if __name__ == "__main__":
    main()
