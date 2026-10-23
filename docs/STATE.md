# Current Project State (SvZ)

Last updated: 2026-09-17 15:21

```mermaid
flowchart TD
    classDef done fill:#2e7d32,stroke:#1b5e20,color:#fff,stroke-width:2px;
    classDef inprogress fill:#f57c00,stroke:#e65100,color:#fff,stroke-width:2px;
    classDef todo fill:#424242,stroke:#212121,color:#ddd,stroke-width:1px,stroke-dasharray: 5 5;
    classDef blocked fill:#c62828,stroke:#b71c1c,color:#fff,stroke-width:2px;

    PIPE["PIPE: A→B→C pipeline + gold UIs"] ::: done
    EVAL["EVAL: Gold eval benchmark (make eval-all)"] ::: done
    M10["M10: Step 5 / m10 qualia-for-analysis"] ::: inprogress
    M10_FS["M10-FS: m10 — few-shot calibration PRESERVING/CURE/INGESTION"] ::: done
    M10_AN["M10-AN: m10 — corpus analysis notebooks"] ::: todo
    E0["E0: Embedding hybrid — scope"] ::: done
    E1["E1: Embedding — chunk + embed helpers"] ::: done
    E2["E2: Embedding — gold exemplars"] ::: done
    E3["E3: Embedding — hybrid export + LU anchor"] ::: done
    E4["E4: Embedding — vs KWIC compare"] ::: done
    E5["E5: Embedding — adopt re-ranker / scale / stop"] ::: done
    GIJS["GIJS: GijsBERT Step B / NONE pre-filter wiring"] ::: todo
    G0["G0: Gold candidate feedback — scope"] ::: done
    G1["G1: Gold feedback — shared target filter helper"] ::: done
    G2["G2: Gold feedback — build lemma priors from gold"] ::: done
    G3["G3: Gold feedback — wire filter into exporters"] ::: done
    G4["G4: Gold feedback — dry-run & adopt"] ::: done
    G5["G5: Gold feedback — labelling runbook note"] ::: done
    PIPE --> EVAL
    EVAL --> M10
    M10 --> M10_FS
    M10 --> M10_AN
    E0 --> E1
    E1 --> E2
    E2 --> E3
    E3 --> E4
    E4 --> E5
    M10 --> G0
    G0 --> G1
    G1 --> G2
    G2 --> G3
    G3 --> G4
    G4 --> G5
```

## Overall Progress

- [x] PIPE: A→B→C pipeline + gold UIs — trifecta-annotate/batch production-ready; gold-ui + stepc-ui ready (PLAN.md)
- [x] EVAL: Gold eval benchmark (make eval-all) — 308-row gold; Step A/B/C metrics frozen 28 Aug 2026
- [/] M10: Step 5 / m10 qualia-for-analysis — Resume quota labelling: merge g4 → rebuild priors → CURE-first priors-on export (~20–30)
- [x] M10-FS: m10 — few-shot calibration PRESERVING/CURE/INGESTION — Few-shots recalibrated excl. review idx 18/45/46; fresh gold batch — soft micro 18.8%→30.3%
- [ ] M10-AN: m10 — corpus analysis notebooks — PLAN Next (3): trifecta_analysis + ldk2025_cookbook_slice.ipynb
- [x] E0: Embedding hybrid — scope — plans/steps/EMBEDDING_CANDIDATES.md
- [x] E1: Embedding — chunk + embed helpers
- [x] E2: Embedding — gold exemplars — 150 exemplars → embedding_exemplars
- [x] E3: Embedding — hybrid export + LU anchor — passage-limit 2000; frame quotas; INGESTION fallback
- [x] E4: Embedding — vs KWIC compare — denylist 0% vs 13.4%
- [x] E5: Embedding — adopt re-ranker / scale / stop — Adopted KWIC re-ranker; spot-check OK; make batch-kwic-reranked
- [ ] GIJS: GijsBERT Step B / NONE pre-filter wiring — Deferred per PLAN — ready offline, not wired into trifecta-batch
- [x] G0: Gold candidate feedback — scope — plans/steps/GOLD_CANDIDATE_FEEDBACK.md — sampling open-loop diagnosed
- [x] G1: Gold feedback — shared target filter helper — gold_target_filter.py + tests; exporters unchanged until G3
- [x] G2: Gold feedback — build lemma priors from gold — build_gold_lemma_priors.py + gold_lemma_priors manifest; blocked=6 (mede+bloed/bloem/huid/munt/noot)
- [x] G3: Gold feedback — wire filter into exporters — wired GoldTargetFilter into clear-frame + preservare + regime; batch report; --no-lemma-priors escape; tests green
- [x] G4: Gold feedback — dry-run & adopt — Adopted lemma priors default on; labelled 18/18 g4_clear_frame_filtered (13 ING+5 CURE); dropped 6 allen false hits
- [x] G5: Gold feedback — labelling runbook note — GOLD_LABELLING.md Step 0 closed loop (priors → label → import → rebuild)

## Active Focus

M10 Step C quota labelling — merge g4, rebuild priors, CURE-first export (priors on)

## Key Intermediate Results & Metrics

- **eval — Step A entity accuracy:** 91.7%
- **eval — Step A metaphor accuracy:** 93.1%
- **eval — Dropout agreement:** 87.5%
- **eval — Step B frame accuracy:** 69.0% (F1 COOKING 0.84, PRESERVING 0.86, CURE 0.52, INGESTION 0.56, NONE 0.50)
- **eval — Step C soft micro accuracy:** 30.3% (was 18.8% pre few-shot refresh)
- **eval — Step C soft joint accuracy:** 12.9%
- **gold — Hand gold with Step C:** 93 / 308 total gold
- **gijsbert — GijsBERT pooled dev:** 67.2% overall; frames-only 61.5%
- **E4 — Denylist target rate (emb vs KWIC):** 0.0 vs 0.134
- **E5a — Step A FOOD rate n=100:** hybrid 0.87 · reranked 0.86 · KWIC baseline 0.69
- **E5a — KWIC re-ranked frame_hint:** 125×4 frames
- **E5a — Operator spot-check:** e5_spotcheck.csv reviewed — all look good (2026-09-16)
- **m10fs — Step C soft micro by frame (post few-shot):** INGESTION 45.5 · PRESERVING 30.9 · CURE 20.8 · COOKING 25.8
- **g2 — G2 — Hard-blocked lemmas (default thresholds):** 6
- **g2 — G2 — Distinct labelled lemmas in priors:** 153
- **g4 — G4 dry-run hard-skips (564 denylist + 307 prior):** 871
- **g4 — G4 labelled clear-frame rows (13 INGESTION + 5 CURE):** 18

## Blockers / Open Questions

- [ ] Analytic claims blocked until more trusted Step C hand gold

## Next Actions

- Merge/import g4_clear_frame_filtered (18 labelled) into gold
- Rebuild gold_lemma_priors (build_gold_lemma_priors.py --summary)
- Export CURE-first ~20–30 clear-frame batch (priors on, guideline verbs only)
- Label in trifecta-stepc-ui → merge/import → rebuild priors again
- Clear chat before next major step

<!-- Manual notes below this line are preserved by scripts/svz.py render. -->
## Notes
