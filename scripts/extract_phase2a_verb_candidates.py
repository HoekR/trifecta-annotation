#!/usr/bin/env python3
"""Phase 2a: Extract stratified verb-KWIC candidates for gold labelling quota.

Samples ~10 records per frame from trifecta_annotations where:
- A frame verb exists in context
- Verb frame matches (or conflicts coherently with) gold Step B frame
- Not already in spike set
- Reasonably balanced across frames + text regimes

Output: CSV ready for gold labeller notebook + JSONL for batch pipeline.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from dataclasses import asdict

import pandas as pd
from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.schemas import TrifectaFrame
from data_io import resolve, save_semi_structured


def extract_phase2a_candidates(
    records_per_frame: int = 10,
    exclude_spike: bool = True,
    output_csv: str | Path | None = None,
    output_jsonl: str | Path | None = None,
) -> tuple[list[dict], pd.DataFrame]:
    """Extract stratified verb-KWIC candidates for Phase 2a gold labelling.
    
    Returns:
        (list of JSONL-ready records, pandas DataFrame for CSV export)
    """
    lex = FrameVerbLexicon()
    ann_path = resolve("trifecta_annotations")
    
    # Load the registered spike set IDs if excluding.
    spike_ids = set()
    spike_candidates = None
    if exclude_spike:
        try:
            with resolve("verb_spike_candidates").open(encoding="utf-8") as handle:
                spike_candidates = json.load(handle)
            for frame, items in spike_candidates.items():
                for cand in items:
                    spike_ids.add(cand["record_id"])
        except FileNotFoundError:
            pass
    
    # Group by frame, tracking diversity
    by_frame: dict[TrifectaFrame, list[dict]] = defaultdict(list)
    
    with open(ann_path) as f:
        for line in f:
            rec = json.loads(line)
            
            # Skip if dropped or has error
            if rec.get("dropped") or rec.get("error"):
                continue
            
            prov = rec.get("provenance", {})
            context = prov.get("context_text", "")
            target_word = prov.get("target_word", "")
            original_record_id = prov.get("record_id", "")
            
            # Skip if in spike set
            if original_record_id in spike_ids:
                continue
            
            if not context or not target_word:
                continue
            
            # Find frame verbs
            verb_hits = lex.find_in_text(context)
            if not verb_hits:
                continue
            
            # Source Step B is a prior annotation prediction, not hand gold.
            source_step_b = rec.get("step_b", {}).get("selected_frame")
            if not source_step_b:
                continue
            
            try:
                source_frame_enum = TrifectaFrame(source_step_b)
            except ValueError:
                continue
            
            # Only process if the source frame is one of the tracked frames.
            if source_frame_enum == TrifectaFrame.NONE:
                continue
            
            # Use first verb hit's frame for grouping
            # (could refine to "best matching" but first-pass is simpler)
            hit = verb_hits[0]
            
            # Create candidate record
            candidate = {
                "record_id": original_record_id,
                "corpus": prov.get("corpus", ""),
                "target_word": target_word,
                "context_text": context,
                "date": prov.get("date"),
                "source_path": prov.get("source_path", ""),
                "text_regime": prov.get("text_regime", "unknown"),
                "frame_verb": hit.verb,
                "frame_verb_frame": hit.frame.value,
                "source_step_b": source_step_b,
                "verb_matches_source_step_b": hit.frame.value == source_step_b,
                "frame_verb_sources": list(hit.lexicon_sources),
                "step_c_status": "present" if rec.get("step_c") else "absent",
            }
            
            by_frame[source_frame_enum].append(candidate)
    
    # Stratify: sample up to records_per_frame per frame
    # Prioritize verb matches with the source Step B prediction.
    result = []
    for frame, candidates in by_frame.items():
        # Sort: prefer verb-matches-gold
        sorted_cands = sorted(
            candidates,
            key=lambda c: (
                c["verb_matches_source_step_b"],
                len(c["context_text"]),  # Prefer longer context
            ),
            reverse=True,
        )
        selected = sorted_cands[:records_per_frame]
        result.extend(selected)
    
    # Print summary
    print("=" * 70)
    print("PHASE 2a: VERB-KWIC GOLD QUOTA EXTRACTION")
    print("=" * 70)
    
    total_selected = len(result)
    print(f"\nTotal candidates extracted: {total_selected}")
    
    by_frame_selected = defaultdict(list)
    for cand in result:
        by_frame_selected[cand["source_step_b"]].append(cand)
    
    print(f"By frame:")
    for frame in [f.value for f in sorted(TrifectaFrame) if f != TrifectaFrame.NONE]:
        items = by_frame_selected.get(frame, [])
        matches = sum(1 for c in items if c["verb_matches_source_step_b"])
        print(f"  {frame:20} {len(items):2} candidates ({matches} verb-matches-source)")
    
    # Text regime breakdown
    regime_counts = defaultdict(int)
    for cand in result:
        regime_counts[cand["text_regime"]] += 1
    print(f"\nBy text regime:")
    for regime, count in sorted(regime_counts.items()):
        print(f"  {regime:20} {count}")
    
    # Create DataFrame for CSV export (gold labeller)
    df = pd.DataFrame(result)
    
    # Add empty Step C columns (to be filled by hand)
    step_c_columns = (
        "COOKING_CREATION_Method",
        "COOKING_CREATION_Process",
        "COOKING_CREATION_Food_Product",
        "COOKING_CREATION_Instrument",
        "PR_Technique",
        "PR_Medium",
        "PR_Food_Patient",
        "PR_Duration",
        "INGESTION_Context",
        "INGESTION_Ingestor",
        "INGESTION_Manner",
        "INGESTION_Food_Patient",
        "CURE_Affliction",
        "CURE_Food_Treatment",
        "CURE_Effect",
        "uncertainty_note",
    )
    for column in step_c_columns:
        df[column] = ""
    
    # Export the gold worksheet to its managed default unless explicitly overridden.
    if output_csv is None:
        output_csv = resolve("verb_phase2a_gold")
    output_csv = Path(output_csv).expanduser()
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"\n✓ CSV exported to {output_csv}")
    
    # Export JSONL inputs with a provenance sidecar.
    kwic_inputs = []
    for i, cand in enumerate(result):
        inp = {
            "record_id": f"{cand['record_id']}_verbkwic_phase2a_{i}",
            "corpus": cand["corpus"],
            "target_word": cand["frame_verb"],  # Verb is target
            "context_text": cand["context_text"],
            "date": cand["date"],
            "source_path": cand["source_path"],
            "original_noun": cand["target_word"],
            "source_step_b": cand["source_step_b"],
        }
        kwic_inputs.append(inp)

    if output_jsonl is None:
        output_jsonl = resolve("verb_phase2a_inputs")
    if Path(output_jsonl).expanduser().resolve() == resolve("verb_phase2a_inputs"):
        output_jsonl = save_semi_structured(
            kwic_inputs,
            logical_name="verb_phase2a_inputs",
            script=__file__,
        )
    else:
        output_jsonl = Path(output_jsonl).expanduser()
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with output_jsonl.open("w", encoding="utf-8") as handle:
            for record in kwic_inputs:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✓ JSONL exported to {output_jsonl}")
    
    print()
    return result, df


if __name__ == "__main__":
    import sys
    
    per_frame = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    output_csv = sys.argv[2] if len(sys.argv) > 2 else None
    output_jsonl = sys.argv[3] if len(sys.argv) > 3 else None
    
    candidates, df = extract_phase2a_candidates(
        records_per_frame=per_frame,
        output_csv=output_csv,
        output_jsonl=output_jsonl,
    )
