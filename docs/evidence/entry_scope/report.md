# Entry-scope production run: report (7 Nov 2026)

## Why
Selection-mode v2 ([../selection_modes_v2/report.md](../selection_modes_v2/report.md)) found that in structured recipe and medical works most real frames sit on food mentions with **no qualifying verb**, so the production verb_food harvest never selects them. This run collects exactly those mentions across the whole DBNL corpus.

## What ran
- **Works:** every DBNL TEI work whose work regime is RECIPE_PRACTICE or MEDICAL. That is 24 works; 22 have TEI entries, and 15 yielded rows.
- **Selection:** production `capped_candidates` routing, keeping `kwic_mode == "entry_scope"` rows only. A row is a food mention inside a TEI entry whose head carries a recipe/medical cue (`regime_from_tei_scope_head`), and not at an offset the verb route already selects.
- **Cap:** 500 rows per work, evenly spaced in document order. The cap was hit in 3 works.
- **Annotation:** the normal A→B→C cascade on local Ollama. 2,590 rows, 0 errors, about 3 h of wall time.
- **Outputs:** the logical names `entry_scope_kwic_inputs` and `entry_scope_annotations` (scratch). Canonical files are untouched. Raw tables: [report.md](report.md).

## Results
| regime | rows | survive Step A | real frame |
|---|---:|---:|---:|
| RECIPE_PRACTICE | 1,216 | 85% | **81%** (985) |
| MEDICAL | 1,374 | 61% | **51%** (699) |
| total | 2,590 | 72% | **65%** (1,684) |

The frames found were COOKING_CREATION 907, CURE 666, PRESERVING 65 and INGESTION 46.

1. **The route works.** The run produced 1,684 new frame rows, none of which the verb harvest can reach. It needed about 1.5 candidates per real frame, against about 2.9 in the production pipeline (PLAN §9i), so per call it is roughly twice as productive.
2. **Recipe works match v2** (81% here vs 86–88% in v2). The secreet-boek (84%), De volmaakte keuken-meid (92%) and Chomel (75%) all deliver.
3. **Medical is weaker and uneven.** Practical remedy books are excellent: Chirurgyns scheeps-Kist and the Pharmacopoeia editions reach 85–93%. Medical treatises are not: Ruysch's *ontleed- genees- en heelkundige werken* reaches only 25%, and Blankaart's treatises 49–56%. In those texts the entry heads match medical cues while the food mention is incidental.
4. **Reach is uneven.** Seven works with entries yielded 0 rows, among them two Pharmacopoeia editions, the Bataviasche apotheek and the Koock-boeck. Their entry heads apparently don't match the Dutch cue regexes; this is unverified, but Latin heads are a likely cause.

## Bug found and fixed during the run
The first pass position-binned rows into 500 document-wide bins. Clustered entries collapsed to one row per bin, so the secreet-boek kept 90 of 528 eligible rows and Chomel 269. It now picks evenly spaced rows only when a work is over the cap (commit 7442902). The 1,618 annotations from the first pass were reused through resume.

## Caveats
- "Real frame" is the pipeline's own verdict; there is no gold set. A hand check of about 100 rows would settle precision, especially for the medical treatises.
- Work regime is inferred. One wedding poem ("…Medic: Doctor…") was counted as MEDICAL; it has no entries, so it contributed nothing.
- These rows are **not yet merged** into the canonical annotations. TEI re-harvests don't resume-match old `record_id`s, so a merge needs deduplication against the existing Chomel, secreet-boek and keuken-meid rows first.

## Next
1. Hand-check a sample, weighted toward the MEDICAL treatises.
2. Check the cue regexes against the heads of the zero-yield works; Latin pharmacopoeia heads are the likely gap.
3. Decide on the merge (dedupe by work plus a context match).
4. Consider raising the cap for the three works that hit it, all of which have high yield.
