#!/usr/bin/env python3
"""Discover candidate verb-KWIC records from existing annotations.

Finds records where frame verbs appear in context, groups by frame,
and extracts ~5-10 candidates per frame for evaluation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from dataclasses import asdict

from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.schemas import TrifectaFrame
from data_io import resolve


def extract_candidates(
    max_per_frame: int = 5,
    output_path: str | Path | None = None,
) -> dict[str, list[dict]]:
    """Extract verb-KWIC candidates from trifecta_annotations.
    
    Returns grouped candidates by frame, formatted as KwicInput-compatible dicts.
    """
    lex = FrameVerbLexicon()
    ann_path = resolve("trifecta_annotations")
    
    # Group records by frame verb
    by_frame: dict[TrifectaFrame, list[dict]] = defaultdict(list)
    verb_to_frames: dict[str, set[TrifectaFrame]] = defaultdict(set)
    
    with open(ann_path) as f:
        for line in f:
            rec = json.loads(line)
            
            # Only process records that weren't dropped
            if rec.get("dropped"):
                continue
            
            prov = rec.get("provenance", {})
            context = prov.get("context_text", "")
            target_word = prov.get("target_word", "")
            
            if not context or not target_word:
                continue
            
            # Find frame verbs in context
            verb_hits = lex.find_in_text(context)
            if not verb_hits:
                continue
            
            # Record this candidate
            for hit in verb_hits:
                verb_to_frames[hit.verb].add(hit.frame)
                
                # Only add one entry per record (use first hit's frame)
                if len(by_frame[hit.frame]) < max_per_frame * 2:  # Oversample for filtering
                    candidate = {
                        "record_id": prov.get("record_id", ""),
                        "corpus": prov.get("corpus", ""),
                        "target_word": target_word,
                        "context_text": context,
                        "date": prov.get("date"),
                        "source_path": prov.get("source_path", ""),
                        "frame_verb": hit.verb,
                        "frame_verb_frame": hit.frame.value,
                        "frame_verb_sources": hit.lexicon_sources,
                        "source_step_b": rec.get("step_b", {}).get("selected_frame"),
                    }
                    by_frame[hit.frame].append(candidate)
    
    # Filter to top N per frame (prefer records where verb frame matches Step B prediction)
    result = {}
    for frame, candidates in by_frame.items():
        # Sort: prefer records where verb frame matches Step B frame
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                c["frame_verb_frame"] == c["source_step_b"],
                len(c["context_text"]),  # Prefer longer context for richer collocates
            ),
            reverse=True,
        )
        result[frame.value] = sorted_candidates[:max_per_frame]
    
    # Print summary
    print("=== VERB-KWIC CANDIDATE DISCOVERY ===\n")
    total_candidates = sum(len(v) for v in result.values())
    print(f"Total candidates extracted: {total_candidates}")
    print(f"Frames covered: {list(result.keys())}\n")
    
    for frame, candidates in sorted(result.items()):
        print(f"{frame}: {len(candidates)} candidates")
        for i, cand in enumerate(candidates, 1):
            match_indicator = "✓" if cand["frame_verb_frame"] == cand["source_step_b"] else "?"
            print(
                f"  {i}. {cand['frame_verb']} → {cand['frame_verb_frame']} "
                f"[source Step B: {cand['source_step_b']}] {match_indicator}"
            )
            print(f"     target: {cand['target_word']}")
            print(f"     context: {cand['context_text'][:80]}...")
        print()
    
    print(f"Unique verbs found:")
    for verb, frames in sorted(verb_to_frames.items()):
        frame_names = [f.value for f in frames]
        print(f"  {verb}: {frame_names}")
    print()
    
    # Save to the registered verb-spike dataset unless explicitly overridden.
    if output_path is None:
        output_path = resolve("verb_spike_candidates")
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    print(f"✓ Candidates saved to {output_path}")
    
    return result


if __name__ == "__main__":
    import sys
    
    max_per_frame = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    output = sys.argv[2] if len(sys.argv) > 2 else None
    
    extract_candidates(max_per_frame=max_per_frame, output_path=output)
