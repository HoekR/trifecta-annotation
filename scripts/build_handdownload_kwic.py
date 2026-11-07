"""KWIC extraction for the two hand-downloaded scholarly editions.

`Tbouck van wondre` (1513) and `Een notabel boecxken van cokeryen` (ca. 1514)
have no transcription in the PD dump (see docs/CORPUS_ACQUISITION.md); Rik
downloaded the DBNL scholarly-edition XML for each by hand. These are later
editorial transcriptions (Frencken 1934; Jansen Sieben & van der Molen-
Willebrands), not the PD originals, so they are kept as a separate input/
output pair rather than folded into `colonial_kwic_inputs` — same reasoning
as keeping `kb_row`/`dbnl_ti_id` separate in `dbnl_genre.py`: different
provenance, don't silently merge.

    uv run python scripts/build_handdownload_kwic.py
"""

from __future__ import annotations

from pathlib import Path

from data_io.jsonl_io import save_semi_structured

from scripts.build_colonial_kwic import build_term_pattern, scan_text, structural_units_for_document
from trifecta_annotation.tei_segmentation import attach_tei_scope_to_rows, render_tei
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

WORKS: dict[str, tuple[str, int]] = {
    "fren007tbou01": ("Tbouck van wondre (Frencken ed., 1934, of the 1513 original)", 1513),
    "_not001nota01": ("Een notabel boecxken van cokeryen (Jansen Sieben ed. of the ca. 1514 original)", 1514),
}


def main() -> None:
    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    from scripts.build_colonial_kwic import AMBIGUOUS_FUNCTION_WORDS
    all_terms -= AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})

    rows: list[dict] = []
    for work_id, (title, year) in WORKS.items():
        xml_path = Path.home() / "Downloads" / f"{work_id}_01.xml"
        if not xml_path.exists():
            print(f"missing: {xml_path}")
            continue
        xml = xml_path.read_text(encoding="utf-8", errors="replace")
        rendered = render_tei(xml, work_id=f"{work_id}_01.xml")
        text = rendered.text
        units = structural_units_for_document(
            text, title=title, source_path=f"{work_id}_01.xml",
            corpus="dbnl_hand_download_2026",
        )
        hits = scan_text(
            text, pattern=pattern, canonical=canonical,
            source_path=f"{work_id}_01.xml", title=title,
            corpus="dbnl_hand_download_2026", date=str(year),
            regime=infer_text_regime(
                corpus="dbnl_hand_download_2026",
                title=title,
                source_path=f"{work_id}_01.xml",
            ),
            units=units,
        )[:60]
        hits = attach_tei_scope_to_rows(hits, located=rendered.located)
        rows.extend(hits)
        print(f"  {len(hits):4d}  {title}")

    out = save_semi_structured(
        rows, logical_name="handdownload_kwic_inputs",
        parent_sources=[], description="KWIC from hand-downloaded Tbouck/notabel editions",
        script="scripts/build_handdownload_kwic.py",
    )
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
