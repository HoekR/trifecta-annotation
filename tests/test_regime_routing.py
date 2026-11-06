"""Genre-routed Step A sieve policy + TEI scope upgrade."""

from __future__ import annotations

from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.regime_routing import (
    needs_encoder_sieve,
    regime_from_tei_scope_head,
    routing_regime,
)
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.step_a_keepdrop import (
    DROP_LABEL,
    KEEP_LABEL,
    annotation_to_keepdrop_row,
    export_keepdrop_splits,
    step_a_keep_label,
)
from trifecta_annotation.tei_segmentation import (
    attach_tei_scope_to_rows,
    entry_for_offset,
    locate_in_stripped_text,
    parse_entries,
)
from trifecta_annotation.text_regime import TextRegime


def test_routing_regime_upgrades_unknown_from_tei_head() -> None:
    assert regime_from_tei_scope_head("Middel tegens de Aamborstigheit") == TextRegime.MEDICAL
    assert regime_from_tei_scope_head("Om te maken een Keersse") == TextRegime.RECIPE_PRACTICE
    assert (
        routing_regime(
            text_regime=TextRegime.UNKNOWN,
            tei_scope_head="Middel tegens de hik",
        )
        == TextRegime.MEDICAL
    )
    assert not needs_encoder_sieve(
        text_regime=TextRegime.UNKNOWN,
        tei_scope_head="Middel tegens de hik",
    )
    assert needs_encoder_sieve(text_regime=TextRegime.LITERARY)
    assert not needs_encoder_sieve(text_regime=TextRegime.RECIPE_PRACTICE)


def test_step_a_keep_label_and_export(tmp_path) -> None:
    keep = {
        "provenance": {
            "corpus": "t",
            "target_word": "brood",
            "context_text": "Neem brood.",
            "record_id": "k1",
            "text_regime": "RECIPE_PRACTICE",
            "source_path": "a.xml",
        },
        "step_a": {"is_food_entity": True, "is_metaphor": False, "reasoning": "x"},
        "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "neem", "reasoning": "x"},
        "dropped": False,
    }
    drop = {
        "provenance": {
            "corpus": "t",
            "target_word": "water",
            "context_text": "Het water is koud.",
            "record_id": "d1",
            "text_regime": "LITERARY",
            "source_path": "b.xml",
        },
        "step_a": {"is_food_entity": False, "is_metaphor": False, "reasoning": "x"},
        "dropped": True,
        "drop_reason": "not_food",
    }
    assert step_a_keep_label(keep) == KEEP_LABEL
    assert step_a_keep_label(drop) == DROP_LABEL
    row = annotation_to_keepdrop_row(keep)
    assert row is not None
    assert row["label"] == KEEP_LABEL
    assert "[TGT]" in row["text"]
    paths = export_keepdrop_splits([keep, drop], tmp_path)
    assert paths["train"].exists()
    assert paths["dev"].exists()
    assert paths["manifest"].exists()


class _AlwaysDrop:
    path = "dummy"

    def predict_keep(self, text: str) -> bool:
        return False


def test_annotate_record_sieve_skips_recipe_but_drops_literary(monkeypatch) -> None:
    called = {"n": 0}

    def _fake_validate(*args, **kwargs):
        called["n"] += 1
        from trifecta_annotation.schemas import EntityValidation

        return EntityValidation(is_food_entity=True, is_metaphor=False, reasoning="ok")

    monkeypatch.setattr("trifecta_annotation.pipeline.validate_entity", _fake_validate)
    monkeypatch.setattr(
        "trifecta_annotation.pipeline.classify_context",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("B should not run on sieve drop")),
    )

    literary = KwicInput(
        record_id="lit",
        corpus="t",
        target_word="brood",
        context_text="Het brood des levens.",
        text_regime=TextRegime.LITERARY,
    )
    out = annotate_record(literary, step_a_sieve=_AlwaysDrop())
    assert out.dropped is True
    assert out.drop_reason == "step_a_sieve"
    assert called["n"] == 0

    recipe = KwicInput(
        record_id="rec",
        corpus="t",
        target_word="brood",
        context_text="Neem brood met boter.",
        text_regime=TextRegime.RECIPE_PRACTICE,
    )
    # Without mocking B/C further, only assert sieve does not short-circuit RECIPE:
    # validate_entity is called (sieve skipped for direct-LLM regimes).
    called["n"] = 0

    def _fake_b(*args, **kwargs):
        from trifecta_annotation.schemas import FrameClassification, TrifectaFrame

        return FrameClassification(
            selected_frame=TrifectaFrame.NONE, lexical_unit="neem", reasoning="x"
        )

    monkeypatch.setattr("trifecta_annotation.pipeline.classify_context", _fake_b)
    out2 = annotate_record(recipe, step_a_sieve=_AlwaysDrop())
    assert called["n"] == 1
    assert out2.dropped is False


def test_locate_and_attach_tei_scope() -> None:
    xml = """<TEI.2><text><body>
<div type="chapter"><head>B.</head>
  <div type="section"><head>Middel tegens de Aamborstigheit.</head>
    <p>Neemt wyn ende honig met snuiftabak.</p>
  </div>
</div>
</body></text></TEI.2>"""
    from scripts.build_colonial_kwic import strip_tei

    stripped = strip_tei(xml)
    entries = parse_entries(xml, work_id="w.xml")
    located = locate_in_stripped_text(entries, stripped)
    assert located
    offset = stripped.lower().find("wyn")
    entry = entry_for_offset(located, offset)
    assert entry is not None
    assert "Aamborstigheit" in (entry.scope_head or entry.head or "")

    rows = [
        {
            "target_char_offset": offset,
            "text_regime": TextRegime.UNKNOWN.value,
            "target_word": "wyn",
        }
    ]
    stamped = attach_tei_scope_to_rows(rows, xml=xml, stripped_text=stripped, work_id="w.xml")
    assert stamped[0]["tei_scope_head"]
    assert stamped[0]["text_regime"] == TextRegime.MEDICAL.value
