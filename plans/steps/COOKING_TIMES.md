# Cooking times in the cookbooks: assessment before building

**Status:** draft, **parked** by operator (9 Nov 2026: "agreed about the cooking
times, would require more work"). Nothing here is built beyond a feasibility test.

**Question:** how long were foods cooked, and did that change between 1790 and
1940? (A known historical claim, e.g. vegetables boiled far longer in the 19th
century, but never measured on this corpus.)

## What we have

- **Full texts of 21 printed cookbooks and household/medical books, 1790–1940:**
  KB cookbooks 1900–1913 (re-OCR), LDK2025 cookbooks 1910–1940, the Google Books
  batch of 9 Nov 2026 (`GOOGLE_BOOKS_2026_11` in `scripts/build_colonial_kwic.py`),
  and three 1930s cookbooks from `Dutch-historical-recipe-trends`. Iterated by
  `sources()` in `scripts/run_indies_harvest.py`.
- **Not usable for times:** the van Erp et al. newspaper recipe web (1940s–1990s)
  holds ingredient lists and quantities only, no instructions.

## Feasibility test (9 Nov 2026)

Regex for durations (minuten / uur / kwartier, number words, halves, ranges) in
sentences that contain a cooking verb (koken, braden, bakken, stoven, smoren,
gaar …), over the 21 texts:

| | |
|---|---|
| cooking-time statements | **2,281** (7 in the 1790 *kock*, 375–410 per LDK book) |
| with a food term in the same sentence | 1,851 |

**Extraction works. Attribution does not.** The first medians per food type
(e.g. poultry 120 → 8 minutes before/after 1900) are artefacts:

1. **Wrong subject.** The nearest food word is often not what is cooked:
   "kook ze in kokend water met *zout*" (the chicken), "schrap de *schubben*" (the salmon).
2. **Not cooking.** Durations of pressing ("den vorm 4 uur"), soaking, resting.
3. **Per-unit times and ranges.** "2 minuten per 100 Gr.", "1 uur à 5 kwartier",
   "+ 1½ à 2 uur".

## What it would take

| step | what | cost |
|---|---|---|
| T1 | **Recipe as the unit**: segment books into recipes (numbered recipes with headings in the LDK/KB books; "REG. 146. Citroen-soep" in the 1790 *kock*); the heading names the dish, i.e. the subject | moderate; structure varies per book (see the typography/structure lesson: validate markers as sequence, not by regex frequency) |
| T2 | **Duration grammar**: cooking verbs only (exclude weken, rusten, persen, laten staan); ranges → interval; per-unit → keep the unit | small |
| T3 | **Attribution**: duration → recipe heading → dish type (soup, vegetable, meat, fish, pastry); optionally main ingredient from the heading | small once T1 exists |
| T4 | **Optional, Step C**: a duration slot in the COOKING_CREATION frame, so the cascade extracts it with the qualia | prompt + gold work |
| T5 | **Analysis**: median and spread of cooking time per dish type per period, per book (normalise per book: one big book must not set the period) | small |

**Gate before T5:** hand-check ~100 extracted (dish, duration) pairs; attribution
precision ≥ 0.8 or stop.

## Related

- `plans/steps/INDIES_NAMES.md` (the same 21 texts)
- Memory note `project_cooking_times_parked`
