"""Tests for Excel gold_fixes merge."""

from trifecta_annotation.gold_io import (
    apply_gold_fix_row,
    build_gold_fixes_rows,
    merge_gold_csv_with_fixes,
    merge_gold_csv_with_fixes_xlsx,
)


def test_build_gold_fixes_dedupes_record_ids() -> None:
    rows = build_gold_fixes_rows(
        [
            {"record_id": "a", "target_word": "boter", "issue": "frame", "context_snippet": "x"},
            {"record_id": "a", "target_word": "boter", "issue": "step_a", "context_snippet": "x"},
        ],
    )
    assert len(rows) == 1
    assert "frame" in str(rows[0]["issue"])
    assert "step_a" in str(rows[0]["issue"])


def test_apply_custom_verdict_updates_frame(tmp_path) -> None:
    gold_row = {
        "record_id": "a",
        "corpus": "cort_voc_db",
        "target_word": "boter",
        "context_text": "boter",
        "selected_frame": "NONE",
        "labelled": True,
        "notes": "",
    }
    fix_row = {
        "record_id": "a",
        "verdict": "custom",
        "review_notes": "trade context",
        "selected_frame": "INGESTION",
        "lexical_unit": "eten",
    }
    out = apply_gold_fix_row(gold_row, fix_row)
    assert out is not None
    assert out["selected_frame"] == "INGESTION"
    assert "review: trade context" in out["notes"]


def test_merge_gold_fixes_from_xlsx(tmp_path) -> None:
    gold_csv = tmp_path / "gold.csv"
    gold_csv.write_text(
        "record_id,corpus,target_word,context_text,date,source_path,dropped,drop_reason,"
        "is_food_entity,is_metaphor,formal_dimension,canonical_pref_label,ontology_match,"
        "step_a_reasoning,selected_frame,lexical_unit,step_b_reasoning,"
        "COOKING_CREATION_Method,COOKING_CREATION_Process,COOKING_CREATION_Food_Product,"
        "CURE_Affliction,CURE_Food_Treatment,INGESTION_Context,INGESTION_Ingestor,INGESTION_Manner,"
        "PR_Technique,PR_Medium,PR_Food_Patient,labelled,notes\n"
        "a,cort,boter,ctx,,,false,,true,false,,,,,NONE,,,,,,,,,,,,,,true,\n",
        encoding="utf-8",
    )
    xlsx = tmp_path / "fixes.xlsx"
    import pandas as pd

    pd.DataFrame(
        [
            {
                "record_id": "a",
                "target_word": "boter",
                "issue": "gold=NONE; pred=INGESTION",
                "context_snippet": "ctx",
                "gold_frame": "NONE",
                "pred_frame": "INGESTION",
                "gold_dropped": False,
                "pred_dropped": False,
                "verdict": "keep_gold",
                "review_notes": "list context",
            },
        ],
    ).to_excel(xlsx, sheet_name="gold_fixes", index=False)

    _, applied, out = merge_gold_csv_with_fixes(
        gold_csv_path=gold_csv,
        fixes_path=xlsx,
    )
    assert applied == ["a"]
    text = out.read_text(encoding="utf-8")
    assert "review: list context" in text
    assert "NONE" in text


def test_adopt_gold_verdict_alias_maps_to_keep_gold() -> None:
    gold_row = {
        "record_id": "a",
        "corpus": "cort_voc_db",
        "target_word": "deeg",
        "context_text": "deeg",
        "selected_frame": "NONE",
        "dropped": True,
        "labelled": True,
        "notes": "orig",
    }
    fix_row = {"record_id": "a", "verdict": "adopt_gold", "review_notes": "metaphor ok"}
    out = apply_gold_fix_row(gold_row, fix_row)
    assert out is not None
    assert out["selected_frame"] == "NONE"
    assert out["dropped"] is True
    assert "review: metaphor ok" in out["notes"]


def test_verdict_shorthand_prefixes() -> None:
    from trifecta_annotation.gold_io import normalize_gold_fix_verdict

    assert normalize_gold_fix_verdict("k") == "keep_gold"
    assert normalize_gold_fix_verdict("keep") == "keep_gold"
    assert normalize_gold_fix_verdict("keep_gold") == "keep_gold"
    assert normalize_gold_fix_verdict("wij") == "custom"
    assert normalize_gold_fix_verdict("wijzigen") == "custom"
    assert normalize_gold_fix_verdict("adopt_pred") == "adopt_pred"
