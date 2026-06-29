"""Thesaurus build tests (vectorized, no manifest)."""

import pandas as pd

from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.thesaurus import (
    alt_label_index,
    build_thesaurus,
    thesaurus_summary,
)


def test_normalize_hist_dutch_long_s() -> None:
    assert normalize_hist_dutch("ſuiker") == "suiker"


def test_build_thesaurus_explodes_alt_labels() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["ajuin", "suiker"],
            "Alt_label": ["aiuyn, ajuyn", None],
            "Type": ["vegetable", "preservative"],
        },
    )
    frame = build_thesaurus(food_terms=food)
    norms = set(frame["alias_norm"])
    assert "ajuin" in norms
    assert "aiuyn" in norms
    assert "suiker" in norms


def test_build_thesaurus_denylist() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["mede", "brood"],
            "Alt_label": [None, None],
            "Type": [None, "grain"],
        },
    )
    frame = build_thesaurus(food_terms=food)
    mede = frame[frame["alias_norm"] == "mede"].iloc[0]
    brood = frame[frame["alias_norm"] == "brood"].iloc[0]
    assert mede["keep_for_trifecta"] == "no"
    assert brood["keep_for_trifecta"] == "yes"


def test_alt_label_index_kept_only() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["mede", "brood"],
            "Alt_label": [None, "broots"],
            "Type": [None, "grain"],
        },
    )
    frame = build_thesaurus(food_terms=food)
    index = alt_label_index(frame, kept_only=True)
    assert "brood" in index
    assert "broots" in index
    assert "mede" not in index


def test_filter_long_snippets_frame() -> None:
    import pandas as pd

    from trifecta_annotation.thesaurus import filter_long_snippets_frame

    frame = pd.DataFrame(
        {
            "matched_term": ["Suiker", "mede", "Bier"],
            "snippet": ["wat suiker", "met mede", "het bier"],
        },
    )
    lookup = {"suiker": "suiker", "bier": "bier"}
    filtered = filter_long_snippets_frame(frame, lookup)
    assert len(filtered) == 2
    assert set(filtered["matched_term"].str.lower()) == {"suiker", "bier"}


def test_thesaurus_summary() -> None:
    food = pd.DataFrame({"Pref_label": ["brood"], "Alt_label": [None], "Type": ["grain"]})
    summary = thesaurus_summary(build_thesaurus(food_terms=food))
    assert summary["rows"] >= 1
    assert summary["pref_labels"] == 1


def test_kwic_input_prefills_canonical_from_thesaurus() -> None:
    from trifecta_annotation.gold_io import kwic_input_to_candidate_row
    from trifecta_annotation.schemas import KwicInput

    row = kwic_input_to_candidate_row(
        KwicInput(
            record_id="x",
            corpus="cort_voc_db",
            target_word="aiuyn",
            context_text="met aiuyn",
        ),
        thesaurus_lookup={"aiuyn": "ajuin"},
    )
    assert row["canonical_pref_label"] == "ajuin"
    assert row["ontology_match"] == "true"


def test_decompose_compounds_whitespace_head() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["witte kool", "kool", "bloemkool"],
            "Alt_label": [None, None, None],
            "Type": ["vegetable", "vegetable", "vegetable"],
        },
    )
    frame = build_thesaurus(food_terms=food)
    witte_kool = frame[frame["alias_norm"].eq("witte kool")].iloc[0]
    assert witte_kool["keep_for_trifecta"] == "no"
    assert witte_kool["drop_reason"] == "compound_decomposed"
    kool = frame[frame["alias_norm"].eq("kool")]
    assert not kool.empty
    assert (kool["keep_for_trifecta"] == "yes").any()
    bloemkool = frame[frame["alias_norm"].eq("bloemkool")].iloc[0]
    assert bloemkool["keep_for_trifecta"] == "yes"


def test_decompose_compounds_agglutinative_and_lookup() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["broodsuiker", "brood", "suiker", "savoij-kool"],
            "Alt_label": [None, None, None, None],
            "Type": [None, "grain", "preservative", "vegetable"],
        },
    )
    frame = build_thesaurus(food_terms=food)
    broodsuiker = frame[frame["alias_norm"].eq("broodsuiker")].iloc[0]
    assert broodsuiker["keep_for_trifecta"] == "no"
    index = alt_label_index(frame, kept_only=True)
    assert index["suiker"] == "suiker"
    savoij = frame[frame["alias_norm"].eq("savoij-kool")].iloc[0]
    assert savoij["keep_for_trifecta"] == "no"
    assert "kool" in index


def test_build_thesaurus_can_disable_decompose() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["witte kool"],
            "Alt_label": [None],
            "Type": ["vegetable"],
        },
    )
    frame = build_thesaurus(food_terms=food, decompose_compounds=False)
    row = frame[frame["alias_norm"].eq("witte kool")].iloc[0]
    assert row["keep_for_trifecta"] == "yes"


def test_snippet_freq_column_and_filter() -> None:
    food = pd.DataFrame(
        {
            "Pref_label": ["brood", "ajuin", "suiker"],
            "Alt_label": [None, None, None],
            "Type": ["grain", "vegetable", "preservative"],
        },
    )
    snippets = pd.DataFrame(
        {
            "matched_term": ["brood", "brood", "Brood", "suiker"],
            "snippet": ["a", "b", "c", "d"],
        },
    )
    frame = build_thesaurus(food_terms=food, snippets=snippets, min_snippet_freq=1)
    assert "snippet_freq" in frame.columns
    brood = frame[frame["alias_norm"].eq("brood")].iloc[0]
    suiker = frame[frame["alias_norm"].eq("suiker")].iloc[0]
    ajuin = frame[frame["alias_norm"].eq("ajuin")].iloc[0]
    assert int(brood["snippet_freq"]) == 3
    assert int(suiker["snippet_freq"]) == 1
    assert int(ajuin["snippet_freq"]) == 0
    assert brood["keep_for_trifecta"] == "yes"
    assert suiker["keep_for_trifecta"] == "yes"
    assert ajuin["keep_for_trifecta"] == "no"
    assert ajuin["drop_reason"] == "low_snippet_freq"
    assert frame.iloc[0]["alias_norm"] == "brood"
