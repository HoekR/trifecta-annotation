# Ground production Step C with embedding retrieval (hybrid)

**Status:** planned, not started · deferred to next session

**Workflow:** After each G-step, stop and ask the operator for decisions. **Do not start the next step until the operator says `go`.**

**Goal:** Reduce hallucinated-substitution misses in production Step C (LLM) by requiring the final field value to match a real literal span from `context_text` when one exists, using the embedding-exemplar-retrieval machinery from [PLAN.md §9c](../../PLAN.md) (`trifecta_annotation/stepc_embedding_retrieval.py`).

**Out of scope for this track:** full replacement of the LLM for Step C (user decision: hybrid grounding, not replacement — avoids needing a calibrated empty-vs-answer threshold); any change to Step A/B.

---

## Background

The embedding-exemplar-retrieval prototype beat the fine-tuned span extractor on a leave-one-out eval over gold (EM 0.612 / soft 0.681), but that eval only ever scored *positive* answer rows — it has no mechanism to decide "this field has no answer," which the LLM does naturally today. There's also no fair apples-to-apples number yet against the LLM's current blended production accuracy (23.7% soft micro, from `make eval-all`).

**Decision (locked):** hybrid grounding, not full replacement. Keep the LLM's presence/absence judgment and its draft answer (today's behavior, unchanged); require the final value to match a real literal span from `context_text` when one exists — directly targeting the failure mode that motivated this whole investigation (`project_step_c_grounding_prototype` memory: most LLM Step C misses are hallucinated substitutions, not wording variants). This can only improve precision (a wording-variant mismatch gets corrected to the real span) without reducing recall (an ungrounded-but-correct answer is left alone, not blanked).

Production Step C flow today: `trifecta_annotation/pipeline.py` → `step_c/__init__.py::fill_qualia` → one of `step_c/using_cure.py` / `cooking_creation.py` / `using_ingestion.py` / `preserving.py`, each a thin wrapper around `llm.py::structured_completion`. One LLM call per frame returns a Pydantic `FrameQualia` (`CureQualia` / `CookingCreationQualia` / `IngestionQualia` / `PreservingQualia`, in `schemas.py`), with one `lexical_unit` field plus 2–5 frame-specific string fields. All four share the same shape (free-text strings, empty = "not stated"), so grounding applies generically via `model_fields` introspection — no per-frame special-casing.

---

## Steps

### G0 — Threshold calibration — **TODO**

Not guessed — same A/B method used for the sub-word-candidate penalty in §9c (try e.g. 0.0/0.75/0.85/0.92, measure against G1's eval, keep whichever wins). Must happen before G2 (wiring).

### G1 — Grounding module + cheap verification — **TODO**

New module `trifecta_annotation/step_c_grounding.py`:

- `ground_value(value, context_text, target_word) -> (value, grounded: bool)` — three tiers:
  1. Empty value → unchanged (LLM's "not stated" judgment is honored, not second-guessed — this is what makes it safe to skip an empty-vs-answer threshold).
  2. Value already a literal case-insensitive substring of `context_text` (reuse `find_span` from `stepc_span_export.py`) → unchanged, no embedding call.
  3. Otherwise: embed the LLM's draft value, generate candidates via `ngram_candidates` (reused from `stepc_embedding_retrieval.py` — same punctuation-safe n-grams + penalized sub-word candidates), take the nearest candidate. Above threshold (G0) → replace with the grounded span. Below → keep the LLM's original value, mark `grounded=False` (visible in output/eval, never silently dropped).
- `ground_frame_qualia(qualia, context_text, target_word, *, embedder) -> FrameQualia` — applies `ground_value` to every field in `qualia.model_fields` except `{"frame", "lexical_unit"}`, returns a new instance (`model_copy(update=...)`).

**Verification — no new LLM calls needed:** re-score the existing `gold_predictions.jsonl` (already scored against `trifecta_gold` for the current 23.7%-soft-micro baseline) by applying `ground_frame_qualia` post-hoc to its `step_c` fields, write `gold_predictions_grounded.jsonl`, run the existing `uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions_grounded.jsonl` unchanged. Compare `step_c_micro_accuracy` / `step_c_soft_micro_accuracy` and per-field/per-frame breakdowns before vs. after. Reuses `trifecta_annotation/eval.py`'s existing scoring (`_score_step_c_pair`, `evaluate`, `run_eval`) — automatically apples-to-apples with every number already in PLAN.md/GOLD_LABELLING.md.

Script: `scripts/eval_stepc_grounding.py` — loads `gold_predictions`, applies grounding, writes the grounded predictions file, shells out to (or calls directly) the existing eval CLI so before/after print side by side in one run.

### G2 — Adopt or stop — **TODO**

Only if G1 shows a real improvement (not just plausible-sounding) does this proceed to wiring. If it doesn't help, stop here and document the negative result with the same discipline as §9a/§9b (PLAN.md), not a buried TODO.

### G3 — Wire into the live pipeline — **TODO, gated on G2**

One hook point: `step_c/__init__.py::fill_qualia()` — after getting `qualia` from the frame-specific filler (unchanged), call `ground_frame_qualia` before returning. Thread a `ground: bool = True` parameter down through `fill_qualia` → `pipeline.annotate_record` so the un-grounded path stays available (e.g. for future re-comparison), defaulting to on once G2 approves it.

---

## Operator notes

- Prefer advising commands; user runs anything that calls the LLM or touches production data.
- No new dependency needed (embedder already in stack from §9c / the KWIC embedding pilot).
- Write up the outcome (adopt or stop) in PLAN.md and docs/DECISIONS.md either way, matching how §9a/§9b/§9c were documented.
