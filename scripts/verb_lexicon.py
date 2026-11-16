"""Verb lexicon work (plans/steps/VERB_LEXICON.md). Read-only on corpus data; writes review files only.

    uv run python scripts/verb_lexicon.py c3-sample     # list-independent reference sample for Rik to mark
    uv run python scripts/verb_lexicon.py candidates    # generators b (silver), c (gold), f (mined), a (forms)
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from data_io import resolve
from trifecta_annotation.normalize import normalize_hist_dutch as norm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "verb_lexicon"
SEED = 20261113
C3_PER_STRATUM = 28          # 9 strata -> 252; about half are expected to be non-food homonyms (noot, zult, hart, oog)
_SENT_END = re.compile(r"(?<=[.!?;:])\s+")


def _sentence_around(context: str, target: str) -> str:
    """The sentence(s) holding the target, target marked [[...]]; falls back to the whole context."""
    i = context.lower().find(target.lower())
    if i < 0:
        return context
    marked = context[:i] + "[[" + context[i:i + len(target)] + "]]" + context[i + len(target):]
    parts = _SENT_END.split(marked)
    hit = next((k for k, p in enumerate(parts) if "[[" in p), None)
    if hit is None:
        return marked
    # one sentence either side: the evoking word may sit in the previous clause
    return " ".join(parts[max(0, hit - 1):hit + 2]).strip()


def c3_sample() -> None:
    out = OUT / "c3_sample.csv"
    if out.exists():
        raise SystemExit(f"{out} exists: the C3 sample is frozen.")
    rows = defaultdict(list)
    with open(resolve("triangulation_b_kwic_inputs"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                rows[r["stratum"]].append(r)
    rng = random.Random(SEED)
    picked = []
    for stratum in sorted(rows):
        for r in rng.sample(rows[stratum], min(C3_PER_STRATUM, len(rows[stratum]))):
            picked.append({
                "id": r["record_id"], "stratum": stratum, "work": r["source_path"],
                "target": r["target_word"], "passage": _sentence_around(r["context_text"], r["target_word"]),
                # Rik fills these in. is_food first (y/n); the rest only when y:
                "is_food": "", "evoking_word": "", "evoking_kind": "", "frame": "", "notes": "",
            })
    rng.shuffle(picked)          # so the marking order doesn't follow genre
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(picked).to_csv(out, index=False)
    print(f"wrote {len(picked)} passages -> {out}")
    print(pd.DataFrame(picked).stratum.value_counts().to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["c3-sample", "candidates", "lemmas", "variation-check", "review-xlsx",
                                    "review-xlsx-2", "export"])
    cmd = ap.parse_args().cmd
    {"c3-sample": c3_sample, "candidates": candidates, "lemmas": lemmas, "variation-check": variation_check, "review-xlsx": review_xlsx,
     "export": export,
     "review-xlsx-2": lambda: review_xlsx(REVIEW_XLSX_2, carry_from=REVIEW_XLSX)}[cmd]()


ANNOTATION_SOURCES = ["trifecta_annotations", "dbnl_sweep_annotations", "weak_regime_verb_annotations",
                      "entry_scope_annotations", "colonial_annotations", "handdownload_annotations"]
REAL = {"COOKING_CREATION", "INGESTION", "CURE", "PRESERVING"}
_TOKEN = re.compile(r"[a-zà-ÿ][a-zà-ÿ'\-]*")


def _lu_tokens(lu: str) -> list[str]:
    return [t.strip("'-") for t in _TOKEN.findall(norm(lu)) if len(t.strip("'-")) >= 2]


def candidates() -> None:
    """One row per candidate form: which generators propose it, with what frame, how often.

    Generators without a dictionary (VERB_LEXICON.md V1): b silver LUs, c gold LUs, f the auto-kept mined
    list, plus the current lexicon. The food target word itself is never a candidate (that is the noun
    anchor, not the trigger). No POS filtering here: that is V0, applied to this table afterwards.
    """
    from trifecta_annotation.frame_verbs import _DEFAULT_LEXICON
    from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

    terms = load_food_terms()
    food = set(alt_label_index(terms)) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    gen = defaultdict(lambda: defaultdict(Counter))      # form -> generator -> frame counts
    examples = defaultdict(list)

    def add(form, generator, frame, example=None):
        if not form or form in food:
            return
        gen[form][generator][frame] += 1
        if example and len(examples[form]) < 3:
            examples[form].append(example)

    for name in ANNOTATION_SOURCES:                                              # b: silver
        try:
            fh = open(resolve(name), encoding="utf-8")
        except (FileNotFoundError, KeyError):
            continue
        with fh:
            for line in fh:
                a = json.loads(line)
                b = a.get("step_b") or {}
                frame, lu = b.get("selected_frame"), b.get("lexical_unit") or ""
                if frame not in REAL or not lu:
                    continue
                target = norm(a["provenance"]["target_word"])
                ctx = a["provenance"]["context_text"]
                for t in _lu_tokens(lu):
                    if t != target:
                        i = ctx.lower().find(t)
                        add(t, "silver", frame, ctx[max(0, i - 80):i + 80].replace("\n", " ") if i >= 0 else None)
    for s in pd.read_parquet(resolve("trifecta_gold"))["annotation_json"]:       # c: gold
        a = json.loads(s)
        b = a.get("step_b") or {}
        frame, lu = b.get("selected_frame"), b.get("lexical_unit") or ""
        if frame in REAL and lu:
            target = norm(a["provenance"]["target_word"])
            for t in _lu_tokens(lu):
                if t != target:
                    add(t, "gold", frame)
    mined = pd.read_csv(ROOT / "trifecta_frame_verb_corpus.csv")                   # f: auto-kept mined list
    for r in mined[mined.keep.astype(str).str.lower().eq("yes")].itertuples():
        for t in [r.term_norm, *[x.strip() for x in str(r.historic_forms).split(",") if pd.notna(r.historic_forms)]]:
            add(norm(t), "mined", r.frame_hint)
    for form, entry in _DEFAULT_LEXICON.entries.items():                         # the current list
        src = "lexicon_mined" if all(s.startswith("corpus:") for s in entry.sources) else "lexicon_manual"
        add(form, src, entry.frame.value)

    rows = []
    for form, by in gen.items():
        frames = sum(by.values(), Counter())
        rows.append({
            "form": form, "frame": frames.most_common(1)[0][0],
            "frame_counts": ";".join(f"{f}:{n}" for f, n in frames.most_common()),
            "generators": ";".join(sorted(by)), "n_generators": len(by),
            "silver_n": sum(by.get("silver", Counter()).values()), "gold_n": sum(by.get("gold", Counter()).values()),
            "in_lexicon": any(g.startswith("lexicon") for g in by),
            "examples": " || ".join(examples[form]),
        })
    df = pd.DataFrame(rows).sort_values(["silver_n", "gold_n"], ascending=False)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "candidates_raw.csv", index=False)
    print(f"{len(df)} candidate forms; by generator set:")
    print(df.generators.value_counts().head(15).to_string())
    print("silver_n >= 3:", int((df.silver_n >= 3).sum()), "| not in lexicon and silver_n >= 3:",
          int(((df.silver_n >= 3) & ~df.in_lexicon).sum()))


def lemmas() -> None:
    """Lemma review list (VERB_LEXICON.md, "few lemmas, many forms").

    Forms the V0 probe calls verb or ambiguous (`candidates_scored.csv`) are mapped to known lemmas through
    their paradigms (`verb_forms.forms_for`) on the loose spelling key (`spelling_key.loose_key`).
    Known lemmas: the manual lexicon's infinitives, the IRREGULAR table, the light verbs, and mined
    infinitives the probe confirms as verbs. Forms that map nowhere are grouped by a rough stem key as
    possible new lemmas. Rik decides per lemma; the forms follow.
    """
    from scripts.verb_probe import LIGHT_VERBS
    from trifecta_annotation.frame_verbs import _DEFAULT_LEXICON
    from trifecta_annotation.spelling_key import loose_key
    from trifecta_annotation.verb_forms import IRREGULAR, forms_for

    sc = pd.read_csv(OUT / "candidates_scored.csv")
    verbish = sc[sc.verdict.isin(["verb", "ambiguous"])].copy()
    known: dict[str, tuple[str, str]] = {}            # lemma -> (frame, source)
    for form, e in _DEFAULT_LEXICON.entries.items():
        if form.endswith("en") and " " not in form:
            if not all(x.startswith("corpus:") for x in e.sources):
                known[form] = (e.frame.value, "lexicon_manual")
    for lem in IRREGULAR:
        known.setdefault(lem, ("", "irregular_table"))
    for lem in LIGHT_VERBS:
        known.setdefault(lem, ("", "light_verb"))
    mined_verbs = sc[(sc.verdict == "verb") & sc.in_lexicon & sc.form.str.endswith("en") & ~sc.form.isin(list(known))]
    for r in mined_verbs.itertuples():
        known.setdefault(r.form, (r.frame, "lexicon_mined_confirmed"))

    key2lem: dict[str, set[str]] = defaultdict(set)
    for lem in known:
        for f in forms_for(lem):
            key2lem[loose_key(f)].add(lem)
    verbish["lemmas"] = verbish.form.map(lambda f: ";".join(sorted(key2lem.get(loose_key(f), set()))))

    # Spelling variants of one lemma (eten/eeten, drinken/drincken) become one row, keyed by the lemma's
    # loose key. The key can also merge different lemmas (legen 'to empty' / leggen 'to lay'): such rows
    # list every member in `variants` for Rik to split.
    by_lkey: dict[str, list[str]] = defaultdict(list)
    for lem in known:
        by_lkey[loose_key(lem)].append(lem)
    rows = []
    for lk, members in sorted(by_lkey.items()):
        lem = min(members, key=lambda m: (m != m.replace("ae", "aa").replace("ck", "k"), len(m), m))
        frame = next((known[m][0] for m in members if known[m][0]), "")
        src = ";".join(sorted({known[m][1] for m in members}))
        mine = verbish[verbish.lemmas.str.split(";").map(lambda xs: bool(set(xs) & set(members)))]
        fc = Counter()
        for cell in mine.frame_counts.dropna():
            for part in cell.split(";"):
                f, n = part.rsplit(":", 1)
                fc[f] += int(n)
        rows.append({
            "lemma": lem, "variants": ", ".join(sorted(members)), "source": src, "lexicon_frame": frame,
            "silver_frames": ";".join(f"{f}:{n}" for f, n in fc.most_common(3)),
            "forms_found": len(mine), "silver_n": int(mine.silver_n.sum()), "gold_n": int(mine.gold_n.sum()),
            "forms": ", ".join(mine.sort_values("silver_n", ascending=False).form.head(15)),
            "shared_with": ";".join(sorted({x for c in mine.lemmas for x in c.split(";")} - set(members))),
            # Rik (13 Nov): rather too large than too small; the list feeds collocation, which is sieved later.
            # So the default is keep; Rik marks only what must go.
            "proposed": "keep", "rik_decision": "", "rik_frame": "",
        })
    lem_df = pd.DataFrame(rows).sort_values("silver_n", ascending=False)
    lem_df.to_csv(OUT / "lemma_review.csv", index=False)

    un = verbish[verbish.lemmas.eq("")].copy()
    def stem_key(f: str) -> str:
        k = loose_key(f)
        k = re.sub(r"^(ge|be|ver|ont)", "", k) if len(k) > 6 else k
        return re.sub(r"(den|ten|de|te|en|dt|t|d|e)$", "", k)
    un["stem_key"] = un.form.map(stem_key)
    grp = un.groupby("stem_key").agg(forms=("form", lambda s: ", ".join(s)), n_forms=("form", "size"),
                                     silver_n=("silver_n", "sum"), gold_n=("gold_n", "sum"),
                                     frame=("frame", lambda s: s.mode().iat[0]),
                                     example=("examples", lambda s: next((x for x in s if isinstance(x, str) and x), "")))
    grp = grp.reset_index().sort_values("silver_n", ascending=False)
    AUX = {"wor", "wer", "heb", "hef", "had", "is", "zyn", "zal", "zul", "gan", "gat", "ztan", "kom", "kan",
           "mot", "mog", "wil", "zou", "was", "war"}
    lemma_stems = {stem_key(m): lem for lem in known for m in [lem]}
    def proposal(row) -> str:
        if row.stem_key in AUX:
            return "drop-aux"
        if row.stem_key in lemma_stems:
            return f"forms-of+{lemma_stems[row.stem_key]}"
        for pre in ("ver", "toe", "be", "ont", "ge", "op", "af", "in", "uit", "door", "over"):
            base = row.stem_key[len(pre):] if row.stem_key.startswith(pre) else None
            if base and base in lemma_stems:
                return f"prefix+{lemma_stems[base]}"
        return "keep"                     # recall first (Rik, 13 Nov): sieving comes later
    grp = grp[grp.silver_n >= 3].copy()   # the tail below 3 silver occurrences is left out
    grp["proposed"] = grp.apply(proposal, axis=1)
    grp["rik_lemma"] = ""
    grp["rik_frame"] = ""
    grp["rik_decision"] = ""
    grp.to_csv(OUT / "new_lemma_candidates.csv", index=False)
    print(f"known lemmas: {len(lem_df)} ({lem_df.source.value_counts().to_dict()}); "
          f"verb/ambiguous forms: {len(verbish)}, mapped: {int(verbish.lemmas.ne('').sum())}, "
          f"unmapped: {len(un)} in {len(grp)} stem groups "
          f"(silver_n mapped {int(verbish[verbish.lemmas.ne('')].silver_n.sum())} vs unmapped {int(un.silver_n.sum())})")
    print(lem_df.head(25)[["lemma", "source", "lexicon_frame", "silver_frames", "forms_found", "silver_n", "forms"]].to_string(index=False))
    print(grp.head(30)[["stem_key", "forms", "silver_n", "frame"]].to_string(index=False))


def _phonetic(term: str) -> str:
    """Soundex-style key for Dutch on top of `loose_key`: voiced/voiceless pairs and vowel quality merged."""
    from trifecta_annotation.spelling_key import loose_key
    k = loose_key(term)
    for a, b in (("sch", "s"), ("ch", "g"), ("ph", "f"), ("ij", "y"), ("ei", "y"), ("ey", "y"), ("au", "ou"),
                 ("ui", "u"), ("ue", "u"), ("ie", "i"), ("th", "t"), ("c", "k"), ("q", "k"), ("x", "ks")):
        k = k.replace(a, b)
    k = k.translate(str.maketrans({"d": "t", "z": "s", "v": "f", "w": "f"}))
    return re.sub(r"(.)\1+", r"\1", k)


# visual confusions of OCR/HTR (not sound): long s read as f, minims, c/e, rn/m, cl/d, h/b, l/t
_OCR = [("s", "f"), ("f", "s"), ("u", "n"), ("n", "u"), ("rn", "m"), ("m", "rn"), ("c", "e"), ("e", "c"),
        ("ij", "ii"), ("ii", "ij"), ("cl", "d"), ("h", "b"), ("b", "h"), ("l", "t"), ("t", "l"), ("i", "l")]


def variation_check() -> None:
    """Rik (13 Nov): most spelling variation is soundex-like; HTR/OCR adds visual confusions. Measured on the
    41 probe works: what a phonetic key adds beyond `loose_key`, and how often OCR-confusion variants of
    known verb forms occur. Read-only; writes variation_check.md and two reading samples."""
    from scripts.verb_probe import LIGHT_VERBS, load_texts
    from trifecta_annotation.frame_verbs import _DEFAULT_LEXICON
    from trifecta_annotation.spelling_key import loose_key
    from trifecta_annotation.verb_forms import IRREGULAR, forms_for

    texts = load_texts()
    counts = Counter()
    for text, _ in texts.values():
        counts.update(w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]+", text))
    lemmas_ = {f for f, e in _DEFAULT_LEXICON.entries.items()
               if f.endswith("en") and " " not in f and not all(x.startswith("corpus:") for x in e.sources)}
    lemmas_ |= set(IRREGULAR) | set(LIGHT_VERBS)
    forms = {f for lem in lemmas_ for f in forms_for(lem)}
    lk = {loose_key(f) for f in forms}
    ph = {_phonetic(f): f for f in forms}
    vocab = [w for w in counts if len(w) >= 3]
    by_loose = {w for w in vocab if loose_key(w) in lk}
    by_phon = {w for w in vocab if w not in by_loose and _phonetic(w) in ph}
    form_set = set(forms) | by_loose
    ocr_hits = {}
    for w in vocab:
        if w in form_set or w in by_phon:
            continue
        for a, b in _OCR:
            i = w.find(a)
            while i >= 0:
                cand = w[:i] + b + w[i + len(a):]
                if cand in form_set:
                    ocr_hits[w] = (cand, f"{a}->{b}")
                    break
                i = w.find(a, i + 1)
            if w in ocr_hits:
                break
    tok = lambda ws: sum(counts[w] for w in ws)
    rng = random.Random(SEED)
    ph_sample = rng.sample(sorted(by_phon), min(40, len(by_phon)))
    pd.DataFrame([{"token": w, "n": counts[w], "matches_form": ph[_phonetic(w)], "rik_same_word": ""}
                  for w in ph_sample]).to_csv(OUT / "read_phonetic_matches.csv", index=False)
    ocr_top = sorted(ocr_hits, key=lambda w: -counts[w])[:40]
    pd.DataFrame([{"token": w, "n": counts[w], "as_form": ocr_hits[w][0], "confusion": ocr_hits[w][1],
                   "rik_is_ocr_error": ""} for w in ocr_top]).to_csv(OUT / "read_ocr_matches.csv", index=False)
    lines = ["# Spelling variation check: phonetic key and OCR/HTR confusions", "",
             f"Vocabulary of the 41 probe works: {len(vocab):,} types (≥ 3 letters), {sum(counts.values()):,} tokens. "
             f"Known verb paradigms: {len(lemmas_)} lemmas, {len(forms):,} generated forms.", "",
             "| matched by | types | tokens |", "|---|---|---|",
             f"| loose_key (LotA rules + squeezed doubles) | {len(by_loose):,} | {tok(by_loose):,} |",
             f"| phonetic key, *additionally* | {len(by_phon):,} | {tok(by_phon):,} |",
             f"| OCR/HTR confusion of a matched form, *additionally* | {len(ocr_hits):,} | {tok(ocr_hits):,} |", "",
             "Precision is unknown until read: `read_phonetic_matches.csv` (40 random) and `read_ocr_matches.csv` "
             "(40 most frequent). Confusions in the OCR sample:", "",
             pd.Series([ocr_hits[w][1] for w in ocr_hits]).value_counts().head(12).to_frame("types").to_markdown(), "",
             "Most frequent phonetic additions:", "",
             ", ".join(f"{w} ({counts[w]}) → {ph[_phonetic(w)]}" for w in sorted(by_phon, key=lambda w: -counts[w])[:30]), "",
             "Most frequent OCR additions:", "",
             ", ".join(f"{w} ({counts[w]}) → {ocr_hits[w][0]} [{ocr_hits[w][1]}]" for w in ocr_top[:30]), ""]
    (OUT / "variation_check.md").write_text("\n".join(lines))
    print("\n".join(lines))


REVIEW_XLSX = OUT / "verb_lexicon_review.xlsx"
REVIEW_XLSX_2 = OUT / "verb_lexicon_review_2.xlsx"     # continues the first, decisions carried over
FRAMES = ["COOKING_CREATION", "INGESTION", "CURE", "PRESERVING", "NONE"]


_MERGE_RX = re.compile(r"(?:merge\s+with|participi\w*\s+of|past tense of|corruption of|variant of|derives from|"
                       r"usual form is|should be added to)\s+([\w\[\]|/()-]+)", re.I)
_DROP_RX = re.compile(r"not a verb|auxiliary|not food related|not part of food|not in the frame", re.I)


def _infinitive(forms: str, proposed: str) -> str:
    """A proposed lemma for a group of unmapped forms: the known lemma if the proposal names one, else the
    most frequent non-participle form in -en, else stem + en (marked '?')."""
    if "+" in str(proposed):
        return str(proposed).split("+", 1)[1]
    fs = [f.strip() for f in str(forms).split(",") if f.strip()]
    inf = [f for f in fs if f.endswith("en") and not f.startswith(("ge", "ghe")) and not f.endswith(("den", "ten"))]
    inf = inf or [f for f in fs if f.endswith("en") and not f.startswith(("ge", "ghe"))]
    if inf:
        return inf[0]
    base = re.sub(r"^(ge|ghe)", "", fs[0]) if fs else ""
    return re.sub(r"(dt|t|d|e)$", "", base) + "en?" if base else ""


def read_as(decision: str, note: str, lemma_guess: str, prev_lemma: str = "") -> str:
    """How a review row is read back (rule agreed with Rik, 13 Nov; review_overrides.csv)."""
    decision, note = (decision or "").strip(), (note or "").strip()
    m = _MERGE_RX.search(note)
    if m:
        return f"merge → {m.group(1).strip('.,;')}"
    if re.search(r"same as previous", note, re.I) and prev_lemma:
        return f"merge → {prev_lemma}"
    if re.search(r"stem (?:is|key is)", note, re.I):
        # Only the lemma name was wrong; a drop outside the agreed table (overrides) is Rik's to confirm.
        return f"check: drop, or keep as {lemma_guess}?" if decision == "drop" else f"keep as {lemma_guess}"
    if _DROP_RX.search(note):
        return "drop"
    return decision or ""


def _overrides() -> dict[str, tuple[str, str]]:
    f = OUT / "review_overrides.csv"
    if not f.exists():
        return {}
    o = pd.read_csv(f).fillna("")
    out = {}
    for r in o.itertuples():
        if r.lemma == "*":
            continue
        for k in [r.lemma, *[x for x in str(r.match_forms).split(";") if x]]:
            out[(r.sheet, k)] = (r.lemma, r.decision, r.flag)
    return out


def review_xlsx(dest: Path = REVIEW_XLSX, carry_from: Path | None = None) -> None:
    """One workbook for Rik's review: a read-me sheet plus one sheet per task, with dropdowns.

    Refuses to overwrite an existing workbook, so filled-in decisions are never lost; move it aside to rebuild.
    Empty decision = the proposal stands (default keep: "rather too large than too small").
    `carry_from`: an earlier workbook whose filled-in cells are copied over (matched on the row key)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    if dest.exists():
        raise SystemExit(f"{dest} exists (it may hold your decisions). Move it aside to rebuild.")
    lem = pd.read_csv(OUT / "lemma_review.csv")
    new = pd.read_csv(OUT / "new_lemma_candidates.csv")
    c3 = pd.read_csv(OUT / "c3_sample.csv")
    ph = pd.read_csv(OUT / "read_phonetic_matches.csv")

    wb = Workbook()
    rm = wb.active
    rm.title = "Read me"
    text = [
        ("Verb lexicon review (plans/steps/VERB_LEXICON.md)", True),
        ("Principle: rather too large than too small. The list feeds collocation, which is sieved later.", False),
        ("An empty decision cell means: the proposal stands (mostly 'keep'). Mark only what must change.", False),
        ("", False),
        ("Order and rough time:", True),
        ("1 Lemmas (183 rows, ~30 min): known lemmas with all forms found. Drop what is not food-related; "
         "fix the frame if wrong; 'split' where two words were merged (e.g. legen/leggen).", False),
        ("2 New lemmas (476 rows; the top ~120 by silver count matter most, ~45 min): verb forms that map to no "
         "known lemma. Name the lemma, keep or drop, set the frame. 'drop-aux' and 'forms-of+X' are proposals.", False),
        ("3 C3 passages (252 rows, ~1.5 h, can be done in parts): the reference that is independent of any list. "
         "First is_food (y/n). Only if y: the word that evokes the frame, its kind, and the frame.", False),
        ("4 Phonetic diag (40 rows, ~5 min, optional): soundex matches; mark same_word = y where it really is a "
         "variant of the verb form. Those become rules, never soundex matching.", False),
        ("", False),
        ("Columns you fill are yellow. Dropdowns: decision, frame, kind, y/n.", False),
    ]
    for i, (t, bold) in enumerate(text, 1):
        c = rm.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    rm.column_dimensions["A"].width = 120

    fill = PatternFill("solid", fgColor="FFF2CC")
    head = Font(bold=True)

    old = pd.read_excel(carry_from, sheet_name=None, dtype=str) if carry_from else {}
    ovr = _overrides()

    def carry(name, df, key, cols):
        """Copy filled-in cells from the earlier workbook, matched on `key`."""
        if name not in old:
            return df
        o = old[name].fillna("").drop_duplicates(key).set_index(key)
        for c in cols:
            if c in o.columns:
                df[c] = df[key].map(o[c]).fillna(df.get(c, "")).replace({float("nan"): ""})
        return df

    def sheet(name, df, cols, fill_cols, widths, lists, hidden=()):
        ws = wb.create_sheet(name)
        ws.append(cols)
        for r in df[cols].itertuples(index=False):
            ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in r])
        for j, col in enumerate(cols, 1):
            ws.cell(row=1, column=j).font = head
            ws.column_dimensions[get_column_letter(j)].width = widths.get(col, 14)
            ws.column_dimensions[get_column_letter(j)].hidden = col in hidden
            if col in fill_cols:
                for i in range(2, len(df) + 2):
                    ws.cell(row=i, column=j).fill = fill
            if col in lists:
                dv = DataValidation(type="list", formula1='"' + ",".join(lists[col]) + '"', allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"{get_column_letter(j)}2:{get_column_letter(j)}{len(df) + 1}")
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    def apply_overrides(df, sheet_name, lemma_col, forms_col=None):
        """Rik's decisions from chat (review_overrides.csv) win over the cells; matched on lemma or a listed form."""
        for i in df.index:
            # Sheet 2 matches on observed forms only: a proposed lemma like 'brengen' also heads opbrengen.
            cands = [x.strip() for x in str(df.at[i, forms_col]).split(",")] if forms_col else [df.at[i, lemma_col]]
            hit = next((ovr[(sheet_name, c)] for c in cands if (sheet_name, c) in ovr), None)
            if hit:
                lemma, d, flag = hit
                df.at[i, "read_as"] = (f"{d} as {lemma}" if d == "keep" else d) + (f" ({flag})" if flag else "")
        return df

    lem = lem.rename(columns={"rik_decision": "decision", "rik_frame": "frame_fix"}).assign(notes="")
    if old:
        lem = carry("1 Lemmas", lem, "lemma", ["decision", "frame_fix", "notes"])
        if "1 Lemmas" in old:
            of = old["1 Lemmas"].fillna("").drop_duplicates("lemma").set_index("lemma")["forms"]
            def added(r):
                before = {x.strip() for x in str(r.forms if isinstance(r.forms, str) else "").split(",")}
                after = {x.strip() for x in str(of.get(r.lemma, "")).split(",")}
                return ", ".join(sorted(after - before - {""}))
            lem["your_added_forms"] = lem.apply(added, axis=1)
        prev = [""] + lem.lemma.tolist()[:-1]
        lem["read_as"] = [read_as(r.decision, r.notes, r.lemma, p) for r, p in zip(lem.itertuples(), prev)]
        lem = apply_overrides(lem, "1 Lemmas", "lemma")
    lem = lem.rename(columns={"forms": "seen in silver"})
    c1 = ["lemma", "variants", "lexicon_frame", "silver_frames", "seen in silver", "forms_found", "silver_n",
          "gold_n", "proposed"] + (["your_added_forms", "read_as"] if old else []) + ["decision", "frame_fix", "notes"]
    sheet("1 Lemmas", lem, c1, {"decision", "frame_fix", "notes"},
          {"lemma": 16, "variants": 22, "lexicon_frame": 18, "silver_frames": 30, "seen in silver": 50,
           "your_added_forms": 30, "read_as": 22, "notes": 30},
          {"decision": ["keep", "drop", "split"], "frame_fix": FRAMES})
    new = new.rename(columns={"rik_lemma": "lemma", "rik_decision": "decision", "rik_frame": "frame_fix"}).assign(notes="")
    new["proposed_lemma"] = [_infinitive(f, p) for f, p in zip(new.forms, new.proposed)]
    if old:
        new = carry("2 New lemmas", new, "stem_key", ["lemma", "decision", "frame_fix", "notes"])
        new["read_as"] = [read_as(r.decision, r.notes, r.lemma or r.proposed_lemma) for r in new.itertuples()]
        new = apply_overrides(new, "2 New lemmas", "proposed_lemma", "forms")
    new = new.rename(columns={"forms": "seen in silver", "lemma": "lemma_fix"})
    c2 = ["proposed_lemma", "seen in silver", "silver_n", "gold_n", "frame", "example", "proposed"] + \
         (["read_as"] if old else []) + ["lemma_fix", "decision", "frame_fix", "notes", "stem_key"]
    sheet("2 New lemmas", new, c2, {"lemma_fix", "decision", "frame_fix", "notes"},
          {"proposed_lemma": 16, "seen in silver": 45, "frame": 18, "example": 60, "proposed": 16,
           "read_as": 22, "lemma_fix": 16, "notes": 30},
          {"decision": ["keep", "drop", "merge"], "frame_fix": FRAMES}, hidden={"stem_key"})
    if old:
        c3 = carry("3 C3 passages", c3, "id", ["is_food", "evoking_word", "evoking_kind", "frame", "notes"])
        ph = carry("4 Phonetic diag", ph.rename(columns={"rik_same_word": "same_word"}), "token", ["same_word"])
    sheet("3 C3 passages", c3,
          ["id", "stratum", "target", "passage", "is_food", "evoking_word", "evoking_kind", "frame", "notes"],
          {"is_food", "evoking_word", "evoking_kind", "frame", "notes"},
          {"id": 12, "passage": 80, "evoking_word": 16, "evoking_kind": 14, "frame": 18, "notes": 30},
          {"is_food": ["y", "n"], "evoking_kind": ["verb", "noun", "construction", "heading", "implicit", "none"],
           "frame": FRAMES})
    sheet("4 Phonetic diag", ph.rename(columns={"rik_same_word": "same_word"}),
          ["token", "n", "matches_form", "same_word"], {"same_word"}, {"token": 16, "matches_form": 16},
          {"same_word": ["y", "n"]})
    wb.save(dest)
    print(f"wrote {dest}: lemmas {len(lem)}, new lemmas {len(new)}, C3 {len(c3)}, phonetic {len(ph)}")


LEXICON_ASSET = ROOT / "trifecta_annotation" / "assets" / "verb_lexicon.csv"
AMBIGUOUS_SHARE = 0.8            # VERB_LEXICON.md: a form the probe reads as a verb < 80% of the time is ambiguous


def _split_forms(cell: str) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[,;]", str(cell or "")) if x.strip()}


def _top_frame(cell: str) -> str:
    parts = [p.rsplit(":", 1) for p in str(cell or "").split(";") if ":" in p]
    return max(parts, key=lambda p: int(p[1]))[0] if parts else ""


def reviewed_lemmas() -> tuple[dict[str, dict], set[str]]:
    """Rik's decisions per lemma, from `verb_lexicon_review_2.xlsx` + `review_overrides.csv` (overrides win).

    Empty decision = the proposal stands ("keep unless", 13 Nov). Notes are read with `read_as`;
    `forms-of+X` / `merge` / "merge with X" put the row's forms under lemma X."""
    x = pd.read_excel(REVIEW_XLSX_2, sheet_name=None, dtype=str)
    s1, s2 = x["1 Lemmas"].fillna(""), x["2 New lemmas"].fillna("")
    lem: dict[str, dict] = {}
    merges: list[tuple[str, set[str], str]] = []

    def put(name: str, decision: str, frame: str, forms: set[str], source: str, flag: str = "") -> None:
        name = name.strip().lower().rstrip("?").strip()
        if not name:
            return
        e = lem.setdefault(name, {"decision": decision, "frame": "", "forms": set(), "sources": set(),
                                  "flags": set()})
        e["decision"] = decision                      # called in order sheet 1, sheet 2, overrides: last wins
        e["frame"] = frame.strip() or e["frame"]
        e["forms"] |= forms | {name}
        e["sources"].add(source)
        if flag:
            e["flags"].add(flag)

    def resolve_decision(d: str, name: str) -> tuple[str, str, str]:
        """-> (decision, lemma, flag)."""
        if d.startswith("merge"):
            return "merge", d.split("→", 1)[1].strip(" .,;"), ""
        if d.startswith("check"):
            return "keep", name, "check"            # Rik's to confirm; kept meanwhile (rather too large)
        if d.startswith("keep as "):
            return "keep", d[len("keep as "):].split(" (")[0].strip(), ""
        return ("drop" if d == "drop" else "keep"), name, ""

    prev = ""
    for r in s1.to_dict("records"):
        d = read_as(r["decision"], r["notes"], r["lemma"], prev)
        prev = r["lemma"]
        forms = _split_forms(r["variants"]) | _split_forms(r["seen in silver"]) | _split_forms(r.get("your_added_forms", ""))
        frame = r["frame_fix"] or r["lexicon_frame"] or _top_frame(r["silver_frames"])
        dec, name, flag = resolve_decision(d, r["lemma"])
        if dec == "merge":
            merges.append((name, forms, frame))
        else:
            put(name, dec, frame, forms, "lemmas", flag)
    for r in s2.to_dict("records"):
        name = r["lemma_fix"] or r["proposed_lemma"]
        raw = r["decision"] or r["proposed"]
        forms = _split_forms(r["seen in silver"])
        frame = r["frame_fix"] or r["frame"]
        if raw.startswith("forms-of+") or raw == "merge":
            merges.append((raw.split("+", 1)[1] if "+" in raw else name, forms, frame))
            continue
        raw = {"drop-aux": "drop"}.get(raw, "keep" if raw.startswith("prefix+") else raw)
        dec, name, flag = resolve_decision(read_as(raw, r["notes"], name), name)
        if dec == "merge":
            merges.append((name, forms, frame))
        else:
            put(name, dec, frame, forms, "new_lemmas", flag)
    for target, forms, frame in merges:
        t = target.strip().lower()
        if t in lem:
            lem[t]["forms"] |= forms
        else:
            put(t, "keep", frame, forms, "merge")
    ovr = pd.read_csv(OUT / "review_overrides.csv", dtype=str).fillna("")
    dropped_forms: set[str] = set()
    for o in ovr.to_dict("records"):
        if o["lemma"] == "*":
            continue
        name, forms = o["lemma"].strip().lower(), _split_forms(o["match_forms"])
        if o["decision"] == "drop-form":
            # a wrong form under a kept lemma (weg / wech under wegnemen): remove the form, keep the lemma
            for e in lem.values():
                e["forms"] -= forms
            dropped_forms.update(forms)
            continue
        # An override is authoritative for the forms it lists: take them out of every other lemma first
        # (kopen dropped -> 'kocht' must not survive under a sheet lemma 'verkogten'), and inherit the frame
        # of the sheet row they came from when the override gives none (zweten <- sheet row 'sweeten').
        inherited = ""
        for other, e in lem.items():
            if other != name and e["forms"] & (forms | {name}):
                inherited = inherited or e["frame"]
                e["forms"] -= forms | {name}
                if o["decision"] == "drop":
                    # the same lemma under another spelling (smyten for smijten, verkogten for kopen's
                    # past tense): Rik dropped the lemma, not just the forms he happened to list
                    e["decision"] = "drop"
        frame = o.get("frame", "") or inherited
        put(name, "keep" if o["decision"] == "split" else o["decision"], frame, forms, "override", o["flag"])
        lem[name]["flags"].discard("check")          # an override is Rik's decision: nothing left to check
    return lem, dropped_forms


def export() -> None:
    """V3: the reviewed trigger list, one row per form -> trifecta_annotation/assets/verb_lexicon.csv.

    Forms per kept lemma: the forms Rik saw or added, plus the paradigm (`verb_forms.forms_for`, including the
    vv/w and final -c rules) restricted to forms that occur in the 41 probe works. Generated forms the probe
    calls 'not verb' are left out; forms the probe reads as a verb < 80% of the time, or listed homographs,
    are flagged `ambiguous`. Dropped lemmas are written too (decision=drop), so the loader can remove their
    forms from the older manual list. A form claimed by a kept and a dropped lemma stays kept."""
    from scripts.verb_probe import HOMOGRAPHS, load_texts
    from trifecta_annotation.frame_verbs import _manual_lexicon
    from trifecta_annotation.verb_forms import forms_for

    lem, dropped_forms = reviewed_lemmas()
    manual = _manual_lexicon()
    vocab: Counter = Counter()
    for text, _ in load_texts().values():
        vocab.update(w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ']+", text))
    sc = pd.read_csv(OUT / "candidates_scored.csv")
    verdict = dict(zip(sc.form, sc.verdict))
    share = dict(zip(sc.form, sc.verb_share))
    rows: dict[str, dict] = {}
    for name, e in sorted(lem.items()):
        frame = e["frame"] or (manual[name].frame.value if name in manual else "")
        flags = set(e["flags"]) | ({"no-frame"} if not frame else set())
        generated = {f for f in forms_for(name) if vocab[f] > 0 and verdict.get(f) != "not verb"}
        for f in sorted((e["forms"] | generated) - {""} - dropped_forms):
            if len(f) < 3 or " " in f:
                continue
            ff = set(flags)
            if f in HOMOGRAPHS or verdict.get(f) == "ambiguous" or (f in share and share[f] < AMBIGUOUS_SHARE):
                ff.add("ambiguous")
            row = {"form": f, "lemma": name, "frame": frame or "NONE", "decision": e["decision"],
                   "flags": ";".join(sorted(ff)), "origin": "reviewed" if f in e["forms"] else "paradigm",
                   "lemma_sources": ";".join(sorted(e["sources"])), "freq_probe_works": vocab[f]}
            old = rows.get(f)
            if old is None or (old["decision"] == "drop" and e["decision"] == "keep"):
                rows[f] = row
            elif old["lemma"] != name and e["decision"] == old["decision"]:
                old["flags"] = ";".join(sorted(set(filter(None, old["flags"].split(";"))) | {f"shared:{name}"}))
    df = pd.DataFrame(rows.values()).sort_values(["decision", "lemma", "form"])
    LEXICON_ASSET.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(LEXICON_ASSET, index=False)
    keep = df[df.decision == "keep"]
    print(f"wrote {LEXICON_ASSET}: lemmas kept {keep.lemma.nunique()}, dropped {df[df.decision == 'drop'].lemma.nunique()}; "
          f"forms kept {len(keep)} ({keep.origin.value_counts().to_dict()}), dropped {int((df.decision == 'drop').sum())}")
    print("flags on kept forms:", Counter(x for c in keep["flags"] for x in c.split(";") if x))
    print("kept forms by frame:", keep.frame.value_counts().to_dict())


if __name__ == "__main__":
    main()
