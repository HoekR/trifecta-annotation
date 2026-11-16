# T1b re-harvest with the reviewed verb lexicon (V3): selection, not frames

*16 Nov 2026. `uv run python scripts/triangulation_sample.py harvest --tag v3` → `triangulation_b_v3_*`
(the original inputs are untouched, md5 checked; they are the parent of the C3 sample). Estimate:
`estimate_v3.md`. No LLM calls.*

## Expectation, written before the run

- The verb share rises most in RECIPE/MEDICAL, where verbs evoke the frame, and little in the literary
  strata.
- An even rise would be the proximity signature.
- This run measures **selection, not frames**. "Food only" shrinks automatically as the verb share rises.

## Result: the expectation was wrong

| stratum | old list | new list | factor |
|---|---:|---:|---:|
| RECIPE | 6.0% | 27.3% | ×4.6 |
| MEDICAL | 4.9% | 29.2% | ×6.0 |
| poëzie | 2.3% | 35.4% | ×15 |
| drama | 2.5% | 35.8% | ×14 |
| proza | 2.3% | 32.4% | ×14 |
| non-fictie | 1.7% | 20.2% | ×12 |
| **total** | **4.2%** (1,870) | **27.6%** (12,249) | ×6.6 |

The verb-centred annotation cost would go from ~4,716 to ~31,050 LLM calls.

## Checked against Rik's C3 labels (the same occurrences; 69 marked)

| C3 `is_food` | selected, old | selected, new |
|---|---:|---:|
| y (18) | 2 | 4 |
| n (51) | 1 | **17** |
| precision of selection | 2/3 | **4/21** |

**Selected non-food targets:** body parts and homographs (*hart* ×5, *voet* ×3, *bloed/bloet*, *been*, *oog*,
*zult* ×2, *Louw*, *Lams*, *rugge*).

**Through:**
- light verbs: *bleef, laet, Deed, maakt, gezet, doen, blijven*;
- unreviewed defaults: *staet* (sheet lemma `sta[ae]n`, which escaped the `staan` drop), *wacht, stort,
  klopte, verlost* (under `lossen`), *tap* (noun);
- the flagged *behandeling*.

## Diagnosis: two causes, of different kinds

1. **Gate (Claude's change in V3):** `reviewed` passes `_passes_guideline_gate`. That opened selection to every
   "keep unless" lemma, including light verbs and defaults Rik never saw.
2. **Noun list (hidden by the old narrow gate):** body-part food terms (*hart, voet, bloed, oog, been*:
   offal/cure) are verb-selected by any nearby verb in literary text (C3 pattern 1).

Rough count: excluding light and flagged verbs → 3 food of 11 selected. Better, but still poor, and n is
tiny. The verb side alone doesn't fix it.

## Status: deferred, Rik to decide

Options:
- (a) narrow the gate for selection: unflagged, non-light reviewed verbs; light/flagged only with a
  guideline verb or in a preferred regime;
- (b) restrict body-part terms to recipe/medical contexts on the noun side;
- (c) fix list items: `sta[ae]n` drop, *tap* / *behandeling* drop-form, the *lossen/verlost* merge.

Each would be checked against the C3 labels, not against reachability.

## v3b: options a–c applied (Rik, 16 Nov) → `triangulation_b_v3b_*`, `estimate_v3b.md`

| stratum | old | v3 | **v3b** |
|---|---:|---:|---:|
| MEDICAL | 4.9% | 29.2% | **28.5%** |
| RECIPE | 6.0% | 27.3% | **27.3%** |
| drama | 2.5% | 35.8% | 9.5% |
| jeugdliteratuur | 4.0% | 34.2% | 12.2% |
| non-fictie | 1.7% | 20.2% | 7.4% |
| poëzie | 2.3% | 35.4% | 12.1% |
| proza | 2.3% | 32.4% | 9.4% |
| sec - letterkunde | 4.5% | 25.8% | 12.2% |
| sec - taalkunde | 2.7% | 32.9% | 10.8% |
| **total** | 4.2% (1,870) | 27.6% (12,249) | **19.5% (8,632)** |

- The gain now sits where it was expected: RECIPE ×4.6, MEDICAL ×5.8; literary about ×4.
- Verb-centred cost: ~4.7k (old) → ~31k (v3) → **~20.9k** LLM calls.

**C3 labels (n small):**

| | old | v3 | v3b |
|---|---|---|---|
| food selected | 2/18 | 4/18 | **4/18** |
| non-food selected | 1/51 | 17/51 | **1/51** |
| precision of selection | 2/3 | 4/21 | **4/5** |

**Still noisy in the literary strata (1,902 selected; a sample of 12 read by Claude: at most 1–2 real):**
- **Noun homographs:** *hert/herte* (204: "heart"), *zult* (122: "will"), *voren* (77), names (*Griet, Vloten*),
  *blad*.
- **Unflagged generic verbs**, never seen in review ("keep unless" defaults): *stellen* 104, *beschrijven* 35,
  *vinden* 29, *loopen* 26, *ontfangen* 24, *bestellen* 23, *leven* 21. These are C4 reading items for Rik
  (light/drop).

**Status:** v3b adopted as the current selection (Rik to confirm); the remaining items are listed for review.
