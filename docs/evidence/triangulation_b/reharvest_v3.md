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

## v3c: Rik's round-3 review (verb_lexicon_review_3.xlsx) → `triangulation_b_v3c_*`, `estimate_v3c.md`

**Decisions:**
- Verbs: 24 drop; 27 light (including *bewaren, leggen, zetten, smaken*, changed from drop after the cost
  check); 8 kept as full triggers, with no light and no ambiguous flag (*eten, suikeren, melken, drinken,
  koken, gebruiken, bakken, voeden*).
- Nouns: 16 recipe-only, 9 never (`assets/restricted_food_terms.csv`, column `scope`).
- The 8 `check` lemmas are kept.

| stratum | old | v3b | **v3c** |
|---|---:|---:|---:|
| RECIPE | 6.0% | 27.3% | **26.6%** |
| MEDICAL | 4.9% | 28.5% | **26.4%** |
| drama | 2.5% | 9.5% | **1.2%** |
| jeugdliteratuur | 4.0% | 12.2% | 3.5% |
| non-fictie | 1.7% | 7.4% | 2.2% |
| poëzie | 2.3% | 12.1% | 3.6% |
| proza | 2.3% | 9.4% | 3.6% |
| sec - letterkunde | 4.5% | 12.2% | 8.0% |
| sec - taalkunde | 2.7% | 10.8% | 3.6% |
| **total** | 4.2% (1,870) | 19.5% (8,632) | **16.1% (7,163)** |

- C3: food 4/18 and non-food 1/51 selected, the same as v3b.
- Verb-centred cost: ~16.9k LLM calls.
- The recipe/medical gain is kept (×4.4 and ×5.4). The literary strata are back near the old level.

**Open:** the 8 full-trigger verbs in non-recipe strata, 105 contexts in
`docs/evidence/verb_lexicon/keep_verbs_contexts.xlsx`, for Rik to read (food_relevant y/n).

## Keep-verb contexts read (Rik, 16 Nov; `keep_verbs_contexts.xlsx`, 83 of 105 marked)

| verb | food-relevant | not | decision |
|---|---:|---:|---|
| koken | 14 | 1 | full trigger (*Kook* in *kookhuizen*: stem now gated) |
| drinken | 13 | 2 | full trigger |
| eten | 10 | 5 | full trigger |
| bakken | 8 | 3 | full trigger (*bak/bakken* as noun: stem gated) |
| voeden | 3 | 1 | full trigger |
| gebruiken | 4 | 11 | **light** |
| suikeren | 0 | 8 | **light**. The hits were the noun *suiker* listed as a verb form; *suiker/suyker/zuiker* and *melk/melc* removed as forms |

**Form-level gating:** a new override decision, `flag-form`. *kook, bak, gebruik* (imperative stem = noun) are
gated; the lemmas stay full triggers.

**Tested and rejected: same sentence / tighter window.** "Not the same context" was the most common reason for
*n*.
- A `. ! ?` boundary between verb and food term removed 9 of 31 *n* but also 7 of 52 *y*: precision 63% → 67%,
  recall −13%.
- A 40-char window: 14 *n* vs 12 *y* removed.
- Historical punctuation is no sentence marker (Rik). The surface can't separate these, so the later stages
  (Step A, LLM), which read the context, have to.
- **Sheet error (Claude):** the highlighted verb was the first substring match. *eten* in *vergheten*, *eet* in
  *eetwaren* were highlighted wrongly; the matcher itself compares whole words.
