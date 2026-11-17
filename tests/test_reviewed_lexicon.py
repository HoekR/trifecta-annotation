"""V3 of plans/steps/VERB_LEXICON.md: the reviewed trigger list is loaded, is authoritative, and is matched
with inflected and enclitic forms."""

from pathlib import Path

import pandas as pd

from trifecta_annotation.clear_frame_examples import score_snippet_for_frame
from trifecta_annotation.frame_verbs import (
    REVIEWED_LEXICON_PATH,
    FrameVerbLexicon,
    build_merged_lexicon,
    get_frame_verb_lexicon,
    load_reviewed_lexicon,
)
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TextRegime, TrifectaFrame

NO_TECHNIQUE = Path("/nonexistent/technique.csv")


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "verb_lexicon.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def _row(form, lemma, frame="COOKING_CREATION", decision="keep", flags=""):
    return {"form": form, "lemma": lemma, "frame": frame, "decision": decision, "flags": flags,
            "origin": "reviewed", "lemma_sources": "lemmas", "freq_probe_works": 1}


def test_load_splits_kept_and_dropped_and_strips_shared_flags(tmp_path: Path) -> None:
    p = _write(tmp_path, [_row("kookt", "koken", flags="ambiguous;shared:sieden"),
                          _row("kocht", "kopen", decision="drop")])
    kept, dropped = load_reviewed_lexicon(p)
    assert set(kept) == {"kookt"} and dropped == {"kocht"}
    assert kept["kookt"].canonical_lemma == "koken"
    assert kept["kookt"].flags == {"ambiguous"}


def test_reviewed_list_is_authoritative_and_replaces_auto_kept_corpus_list(tmp_path: Path) -> None:
    manual = build_merged_lexicon(technique_assoc_path=NO_TECHNIQUE, include_corpus=False, include_reviewed=False)
    some_manual = next(iter(manual))
    p = _write(tmp_path, [_row(some_manual, "x", decision="drop"), _row("kookt", "koken", frame="CURE")])
    merged = build_merged_lexicon(technique_assoc_path=NO_TECHNIQUE, reviewed_path=p)
    assert some_manual not in merged                      # Rik's drop removes a manual form too
    assert merged["kookt"].frame == TrifectaFrame.CURE    # Rik's frame wins
    assert not any(s.startswith("corpus:") for e in merged.values() for s in e.sources)


def test_enclitic_forms_match_their_host_but_not_agent_nouns(tmp_path: Path) -> None:
    p = _write(tmp_path, [_row("kookt", "koken"), _row("doet", "doen"), _row("giet", "gieten")])
    lex = FrameVerbLexicon(technique_assoc_path=NO_TECHNIQUE, include_corpus=False, reviewed_path=p)
    hits = lex.find_in_text("en kooktse tot een syroop; doet'er zout by; de gieter; doetmen")
    got = [(h.verb.lower(), h.lemma, "enclitic" in h.flags) for h in hits]
    assert ("kookt", "koken", True) in got
    assert ("doet", "doen", True) in got
    assert sum(1 for g in got if g[0] == "doet") == 2           # doet'er and doetmen
    assert all(h.verb.lower() != "giet" for h in hits)          # 'gieter' is a watering can


def test_separable_verb_takes_the_compound_lemma_only_when_the_particle_closes_the_clause(tmp_path: Path) -> None:
    p = _write(tmp_path, [_row("legt", "leggen", frame="NONE"), _row("leggen", "leggen", frame="NONE"),
                          _row("inleggen", "inleggen", frame="PRESERVING"), _row("opleggen", "opleggen")])
    lex = FrameVerbLexicon(technique_assoc_path=NO_TECHNIQUE, include_corpus=False, reviewed_path=p)
    [h] = lex.find_in_text("Neemt roode Most; legt'er de Peeren in, zynde geschilt")
    assert h.lemma == "inleggen" and h.frame == TrifectaFrame.PRESERVING and "separable:leggen" in h.flags
    [h] = lex.find_in_text("en legt ze in kout water")          # preposition + noun phrase
    assert h.lemma == "leggen"
    h = lex.find_in_text("men legt ze om'er goud op te leggen")[0]
    assert h.lemma == "leggen"                                   # op belongs to the infinitive


def test_shipped_list_round_trips_into_the_default_lexicon() -> None:
    assert REVIEWED_LEXICON_PATH.exists()
    df = pd.read_csv(REVIEWED_LEXICON_PATH, dtype=str).fillna("")
    lex = get_frame_verb_lexicon()
    kept = df[df.decision == "keep"]
    missing = [f for f in kept.form if normalize_hist_dutch(f) not in lex.entries]
    assert not missing, missing[:10]
    assert not (set(df[df.decision == "drop"].form) - set(kept.form)) & set(lex.entries)


def test_paradigm_form_carries_its_lemma() -> None:
    entry = get_frame_verb_lexicon().entry_for("haalt")
    assert entry is not None and entry.canonical_lemma == "halen"


def test_core_verb_bonus_counts_inflected_forms_via_lemma() -> None:
    snippet = "Neemt de hoenders, en kookt die in water met wat zout tot ze gaar zijn."
    cand = score_snippet_for_frame(snippet, ["hoenders"], TrifectaFrame.COOKING_CREATION,
                                   regime=TextRegime.RECIPE_PRACTICE)
    assert cand is not None and "core_verb" in cand.reasons


def test_weak_reviewed_verb_needs_a_preferred_regime() -> None:
    # 'bleef' (blijven, flagged light) next to a food term: not a trigger in literary text, fine in a recipe
    snippet = "Hy bleef by het brood en de boter, en sprak niet."
    lit = score_snippet_for_frame(snippet, ["brood"], TrifectaFrame.COOKING_CREATION, regime=TextRegime.LITERARY)
    assert lit is None or "bleef" not in lit.discovery_verb.lower()


def test_body_part_terms_are_food_only_in_recipe_and_medical_texts() -> None:
    from trifecta_annotation.clear_frame_examples import body_part_terms, food_terms_for_regime

    assert {"hart", "voet", "oog", "bloed"} <= body_part_terms()
    terms = ["hart", "brood", "voet"]
    assert food_terms_for_regime(terms, TextRegime.LITERARY) == ["brood"]
    assert food_terms_for_regime(terms, TextRegime.RECIPE_PRACTICE) == terms


def test_never_terms_are_no_target_even_in_recipes() -> None:
    from trifecta_annotation.clear_frame_examples import food_terms_for_regime

    terms = ["zult", "brood", "blad"]
    assert food_terms_for_regime(terms, TextRegime.RECIPE_PRACTICE) == ["brood", "blad"]
    assert food_terms_for_regime(terms, TextRegime.LITERARY) == ["brood"]

