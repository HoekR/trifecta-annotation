# Evaluating the cascade without new random gold: structure, triangulation, two levels

**Status:** in progress (12 Nov 2026). E1 and T1 done (G1: verb-only insufficient for reach); T1b next.
**Owner:** Rik (decisions, labelling); Claude (scripts, runs, reports).
**Evidence lands in:** `docs/evidence/<step>/` (script + `report.md` + `rows.csv` per step).

---

## 1. Question

Where does the Step A→B cascade go wrong on DBNL texts, and how can we measure that without adding more
random sentence gold, which has not helped before?

Sub-questions:

1. Does the frame live where we grade it? (sentence vs entry head, food noun vs verb)
2. Do the two harvest routes (food-first, verb-first) find the same frames, and agree on them?
3. Can document structure (entry heads, later layout and article type) serve as a reference that needs
   no gold?

## 2. What we know (E1, done)

`scripts/eval_gold_by_position.py` → `docs/evidence/gold_by_position/`.

| Finding | Number |
|---|---|
| TEI gold rows located in their entry | 360 of 505 (55 work not in zip, 65 not located, 25 before the first entry) |
| Step B agreement, located rows with a prediction | **0.48** (95% CI 0.42–0.54, n=280); 0.53 where gold has a real frame |
| The headline usually quoted | 75% (July baseline, a different 157 rows) |
| Rows under a frame-implying heading | 57 of 280: the gold barely samples the structural habitat |
| Gold equals the heading's frame | 31 of 57: the heading states the entry's purpose, not the sentence label |
| Production heading cue (`regime_from_tei_scope_head`) flags | 0/33 cooking, 2/8 preserving, 12/16 cure heads |
| INGESTION→NONE errors (22) | about 11 have an explicit verb nearby (anchoring problem), about 4 are implicit, about 6 have debatable gold |

Interpretation:
- The gold is KWIC-shaped, comes from about 60 curated works, and is not representative of DBNL at large.
- Errors concentrate on DROPPED/NONE/INGESTION boundaries, not under unseen purpose headings.
- Two unit mismatches recur:
  - heading vs sentence;
  - food noun (the *Ingestibles* element) vs the verb that evokes the frame.

## 2b. Step back: what the attempts shared (16 Nov 2026)

The lens is from dighum_template `wisdom/topics/step-back-review.md`: when different approaches all fail,
that agreement is a result. The diagnostic question is *what did all the attempts have in common?*

| Series | Attempts | Shared assumption | Outcome |
|---|---|---|---|
| Step C qualia | bigger model, grounding, BERT span extraction, mBERT/XLM-R, retrieval, frame-selective | sentence/snippet as unit | goal is in the title (PLAN §9e) |
| Step B PRESERVING/CURE | few-shots ×2, two-stage split classifier, heading as context (handful, below) | one frame per occurrence, decided per sentence | see T3: two levels |
| `text_regime` readings | genre-effect reading, failed-inference reading (both retracted) | the field means what its name says | mode marker, a bug (PLAN §9i) |
| Cooking times | duration regex + nearest food word | sentence as unit for attribution | needs recipe as unit (COOKING_TIMES.md) |

Across the series, selection, classification, extraction and attribution all share
`KwicInput.context_text`, a KWIC window. The unit is built into the I/O contract, not into any one
step. T3 is the matching redesign.

Caveat: this is retrodiction, so the lens could not fail here. Its predictions are tested in T3 (done as a
handful) and in VERB_LEXICON.md §4.

The C5 rule there is retracted (16 Nov) and kept in T8. T1 as *triangulation* stands: the food route finds
frames the verb route doesn't (G1). What T1 cannot do is judge the vocabulary. Verb reachability is
proximity, so it rises with any list. Whether a frame is verb-reachable is structural and genre-dependent
(T8).

## 3. Scope

- **In:** DBNL TEI works, structured by `render_tei` entries and heads. This is most of the corpus.
- **Out until T6:**
  - 20th-century cookbooks (OCR without TEI);
  - newspapers (Delpher).
  - No result here transfers to them.

## 4. Steps

Dependencies: T1 → T1b → T5. T2 → T3 → T4a. T6 runs independently.

### T1 — Reachability over the existing harvests (done, 12 Nov 2026)

`scripts/triangulate_harvests.py` → `docs/evidence/triangulation/`.

- **What:** over 1,435 sweep works with both routes, check whether each food-first row has a hit from
  the *uncapped* verb pool within ±150 chars.
- **Measures:** the share of food-first frames unreachable by verb. Trial on 20 works: 13 of 14.
- **Result:**
  - 1,438 works; 7,803 food-first rows located (970 not located).
  - **1,060 of 1,166 food-first frames (91%, CI 89–92%) have no uncapped verb hit within ±150 chars.**
    G1 → verb-only is insufficient for reach.
  - Unverified: whether those frames are right. Food-first yield is 15%, so T1b must read them.
  - Cross-check: 209 neighbour pairs, 67% same label (60–73%), 80% on frame vs no frame.
    - Weak by design: the pairs compare *different* target words.
    - Of the 20 'food no frame, verb frame' rows, most of the sample is the verb side lending its frame
      to a neighbouring body-part word (*hart*, *oog*, *herten*).
    - One case is a structural one: the heading *Van het Eten en Drinken* over a word list.
  - Status: adopted (G1). Evidence: `docs/evidence/triangulation/`.
- **Limit:** the label cross-check is too thin. The sweep cap is 10/work, and the weak-regime harvest
  dropped contexts the sweep had already annotated, so the routes meet only as neighbours.
- **Decision:** if most food-first frames are unreachable by verb, the verb-only production route is
  insufficient on its own. That gives a reason to keep a food-first route (cost question, see
  `project_pipeline_economics`).

### T0 — Verb lexicon (prerequisite for T1b's annotation)

The verb route's word list is infinitive-only and partly junk. See [VERB_LEXICON.md](VERB_LEXICON.md). T1's 91% and T1b's 4.2% are measured with that list, so T1b is re-selected after the fix and goes back to G2.

### T1b — Passage-first triangulation on a stratified sample

**Progress (12 Nov 2026): steps 1–3 done, waiting at G2.**
- `scripts/triangulation_sample.py`; frozen sample `docs/evidence/triangulation_b/works.csv` (39 works, seed
  20261112). Strata: RECIPE 4 (all eligible under 3 MB), MEDICAL 5, and the 7 DBNL genres; one work per
  series; no poetry/drama in RECIPE/MEDICAL, because a wedding poem "… Medic: Doctor" was inferred MEDICAL.
- **Design correction:** Step A/B see only `target_word` + `context_text`. The verb reaches only the
  sieve. So the routes differ in *selection* and *context centring*, not in what the LLM is told.
  - Each occurrence is annotated once (noun-centred).
  - Verb-selected occurrences are annotated a second time, verb-centred, to test centring alone.
  - Verb-in-prompt is T5.
- Counts: 44,372 food-noun occurrences, of which 1,870 (4.2%) are verb-selected; 1,567 verb-centred rows.
  Annotating everything costs ~189k LLM calls, so that is not proposed.
  See `docs/evidence/triangulation_b/estimate.md`.

- **What:**
  1. Sample about 40 DBNL works, with a fixed seed and the list frozen in `docs/evidence/triangulation_b/works.csv`.
     - Stratify by DBNL/GGC genre (`load_genre_records`), not `text_regime`: 2,862 of 3,203 sweep works
        are UNKNOWN.
     - About 10 RECIPE/MEDICAL works, about 30 spread over the other genres.
     - Mid-sized: no zero-hit works, no outliers of 500+ hits.
  2. Harvest both routes **uncapped**, keeping already-annotated contexts.
     - Every food-noun occurrence gets a food-anchored row.
     - Where the verb pool hits the same clause, the identical passage also gets a verb-anchored row
       (`discovery_verb`, `frame_hint`).
  3. **Gate:** report the row counts and estimated LLM calls (about 5.3/row, minus the Step A sieve)
     before annotating. Rik decides.
  4. Annotate both. Compare on identical passages.
- **Measures:**
  - reachability per route;
  - same-passage agreement (Wilson CI);
  - the disagreement list, which Rik reads.
- **Decision:**
  - Most frames reachable by only one route → keep both routes, report yield per route.
  - The verb-anchored label wins most of the read disagreements → T5.
  - Neither → the window/unit is wrong; move to the entry level (T3).
- **Caveat:** both routes use the same Step B model. Independence comes from the anchor, not the judge.

### T2 — Widen the heading cue

- **What:** broaden `regime_from_tei_scope_head`. The `HEAD_FRAME` regexes in
  `eval_gold_by_position.py` are a starting point and are themselves unvalidated.
- **Validation:** read and score a random sample of about 100 entry heads from the TEI works, by
  sequence and position, not by frequency. Not on the sentence gold.
- **Then:** count what the entry-scope harvest missed with the old cue (heads newly flagged × entries
  never harvested).
- **Decision:** ship the cue when precision on the head sample is ≥ the old cue's and recall is clearly
  higher. Otherwise keep the old one and record why.

### T3 — Two-level cascade (design, then prototype)

1. **Entry level:** heading → the entry's purpose (cooking / cure / preserving / none). Unit: the
   entry. This reaches recipes that name their goal only in the title (§9e: 71% of 3,326 recipes).
2. **Sentence level:** the existing cascade, with the entry's purpose passed in as *context*, not as
   the answer. Don't overwrite sentence labels with the heading frame (31 of 57 would be wrong).

- **Prototype:** on the T1b sample works, pass the entry purpose into Step B and compare with and without
  it on the same rows.
- **Decision:** adopt only if the sentence-level result does not get worse and the entry level adds
  frames the sentence route can't reach.

**Test design caveats (Rik, 16 Nov):**
- (a) **Not universal:** recipes also occur outside entry-structured books. Always report coverage, i.e.
  the share of the target rows that sit in works with headings at all.
- (b) **Headings are not always findable:** heading detection has its own error. Evaluate on rows whose
  heading was found and checked by hand, and report not-found rows separately.
- (c) **Entry structure ≠ cooking:** dictionaries, herbals and pharmacopoeias have the same structure. The
  heading's purpose must be classified, not assumed.

Stratify by *structure present* × *heading found and verified* × *genre*, with n per cell. Claim only for
the cells where it helps.

**Handful result, PRESERVING/CURE (16 Nov):** `docs/evidence/heading_context/handful.md`.
- 18 three-frame confusions; at most 2–5 could be fixed by passing the heading in. 5 had the heading in
  the context already. So the prototype run is not justified for this question as posed.
- Gold splits COOKING_CREATION / CURE on the same entry type (*Syrupus*, *Oleum*, *Trochisci*).
- **Rik's reading:** both frames apply, at different levels:
  - COOKING_CREATION = the procedure (sentence);
  - CURE = the purpose (heading/entry).
- Weak first check (record-id verbs): purpose verbs in the sentence → gold CURE; procedure only → gold
  COOKING_CREATION.
- **Implication for T3:** the entry level is not a hint for the sentence label but a label of its own.
  "Don't overwrite sentence labels" is then not a precaution but the design.
- **To do:** read the full contexts of the split rows.

### T4 — Gold of a different unit

- **T4a, heading gold:** about 150 entry heads, stratified by work and genre, labelled with the entry's
  purpose. About an afternoon for Rik. This is the reference for T2 and for level 1 of T3.
- **T4b, disagreement gold:** the T1b disagreements, labelled.
- **T4c, guidelines for the debatable cases:** trade, idiom, remedy ingredient, production (*bier
  brouwen*). Decide whether they count as INGESTION before they count as model errors.
- No more random sentence gold.

### T5 — Verb-aware INGESTION

- **What:** give Step B the verb that evokes the frame (the discovery verb, or a parsed verb–object link)
  for food-anchored rows.
- **First:** a handful test on the ~11 explicit misses from E1. If the label doesn't change there, stop.
- **Then:** the T1b sample, same rows with and without the verb.
- **Later option:** a dependency parser for Dutch would replace the ±150-char window with an actual
  verb–object link. None has been run on DBNL so far.

### T6 — Structure for sources without TEI

- **20th-century cookbooks:** headings from layout (ALTO font size, bold, position). Validate markers as
  a sequence and by position (typography-hides-structure lesson).
- **Newspapers** (`DELPHER_KRANTEN.md`):
  - the unit is the article;
  - KB's article segmentation and article type (advertisement, recipe column, market report) carry the
    framing;
  - the article heading plays the role of the entry head.
- **Then:** repeat T1b/T3 per source type. Results do not carry over between source types.

### T7 — Re-measure the headline

- **What:** freeze a test set by work (works never used for prompts or few-shots). Report Step B
  agreement with CI per source type and genre.
- **Until then:** don't quote 75% for DBNL texts. Quote 0.48 (E1) with its scope.
- **Record:** add entries to a claims ledger (claim, evidence path, date, status: adopted / deferred /
  retracted).

### T8 — Where frames live, by genre (added 16 Nov 2026, Rik)

- **Question:** per genre, what evokes the frame? The options are a verb, a heading or entry, a noun, a
  construction, or nothing explicit. That decides which route can reach it at all. Reach is structural, not
  a matter of vocabulary.
- **Why genre:**
  - C3 (69 passages): RECIPE 5/6 food, MEDICAL 2/8, literary/linguistic strata about 10/55.
  - Headings evoke frames only in the recipe and medical strata.
  - Entry structure differs between dictionary, formulary and prose (`project_genre_predicate`: unit
    density is not a genre classifier).
- **Data, no new run:**
  - C3 (`evoking_kind` × stratum, `c3_prefill.csv`);
  - gold by position (head / near_head / body × genre, E1);
  - T1 rows with `pool_verbs`. The T1 run with the new list was stopped; the 20-work trial is in
    `$TMPDIR` only. Re-run per genre if needed.
- **Measure:**
  - evoking kind × genre, and position in the entry × genre, with n and CI;
  - **not** verb reachability as a yardstick for the vocabulary.
- **Decision:** routing per genre (verb route, entry/heading route, food route), as input to T3's two
  levels and to the cost question (`project_pipeline_economics`).
- Compatible with "don't stratify the sweep by `text_regime`" (§6): this stratifies the *analysis*, not
  the harvest.

**First result (17 Nov 2026): the annotated v3d set, 4,045 passages, 0 errors.**
Source: `docs/evidence/triangulation_b/report_v3d.md`.

Share of passages that get a real frame (cooking, eating, cure, preserving):

| genre | food word + verb nearby | food word only |
|---|---:|---:|
| recipe books | 84% (80–88%) | **94%** (90–97%) |
| medical books | 54% (49–60%) | 48% (42–55%) |
| prose | 73% (64–80%) | 18% (13–23%) |
| drama | 77% (50–92%) | 8% (5–13%) |
| poetry | 59% (48–68%) | 16% (12–22%) |
| non-fiction | 47% (39–55%) | 6% (4–11%) |
| secondary literature (literary studies) | 70% (64–76%) | 42% (36–49%) |
| secondary literature (linguistics) | 42% (29–55%) | 13% (9–18%) |
| youth literature | 69% (42–87%) | 27% (21–34%) |

- **Recipe books:** every food word is in a frame; the genre evokes it, so a verb adds nothing (Rik: "to be
  expected"). Route: harvest all food words, no verb filter.
- **Literary and other genres:** a verb nearby multiplies the frame share by 4–10. Route: verb filter.
- **Medical books:** a verb barely helps (54% vs 48%). This is the open case; a likely reason is that
  remedies (food as cure) and plain description are mixed in one book.
- **Whether context is centred on the food word or the verb** rarely changes the label: 82% of 1,004 pairs agree (79–84%).
  Disagreements are mostly cooking↔cure and cooking↔eating, the two-level overlap from the heading test.
- **Precision, read by Rik (17 Nov 2026; `triangulation_b/reading_v3d.xlsx`, built by
  `scripts/reading_sheet.py`).** Food-only frames, 100 random:

  | genre | right | not food | wrong frame | unsure |
  |---|---:|---:|---:|---:|
  | recipe books (29) | **27 (93%, 78–98%)** | 1 | 0 | 1 |
  | medical books (16) | **4 (25%, 10–49%)** | 10 | 0 | 2 |
  | all other genres (55) | **18 (33%, 22–46%)** | 29 | 5 | 3 |

  - **Recipe books:** the food route is right. Its weighted ~11.8k frames are real; this is where the
    food route earns its keep.
  - **Medical books:** 9 of the 10 'not food' are body parts (*hooft* ×3, *gal* ×2, *maag*, *borst*,
    *herssenen*, *vet*). The model labels the passage CURE, correctly, but the word is the patient's body,
    not food. Cause: body parts are scoped 'recipe-only', and `RECIPE_REGIMES` includes MEDICAL.
  - **Other genres:** two thirds wrong: idioms (*vleesch en bloed*, *vlees of vis*), metaphor (*brood* for
    living, *vleesch des Heeren*), language examples, names. Without a verb, the food route outside recipe
    books mostly finds noise; the verb filter stays.
  - CURE is the weakest label (6 of 21 right), mostly because of the body parts.
- **Decision (Rik, 17 Nov): body parts are food in recipe books only**, not in medical books (new scope
  `recipe-books-only` for the 72 body-part rows of `assets/restricted_food_terms.csv`; the round-3 nouns
  stay `recipe-only`, i.e. recipe and medical). **And the scopes now apply to the food route too**
  (`term_allowed`, used in `triangulation_sample.py harvest`): until now only the verb route honoured
  them, so the food-only sample held body parts and even 'never' words (*voren*, *zult*).
  Effect measured on the v3d rows, no new run:

  | | food-only rows excluded | verb-selected rows excluded |
  |---|---:|---:|
  | recipe books | 4 of 200 | 0 of 300 |
  | medical books | 93 of 200 | **145 of 300** |
  | other genres | 50–79% per genre (102–158 of 200) | 0 |

  Most excluded: *bloed* 182, *hert* 89, *hart* 86, *noot* 86, *hooft* 75, *oogen* 64, *hoofd* 57,
  *maag* 51, *oog* 50.
  - In the reading: 22 of 100 rows excluded, 18 of them 'not food' (9 of 10 in medical books).
  - Precision on what remains: recipe books 25/27 (93%), medical books 3 of 6, other genres 18/47 (38%).
    Outside recipe books the food route is still mostly noise, but there is much less of it.
  - **Medical books:** half of their verb-selected rows were body parts too. The route question for
    medical books must be re-asked on the filtered rows.
  - Production harvests (`build_colonial_kwic.py` `scan_text`) don't apply the scopes yet.
- **Centring disagreements: not contradictions (Rik).** 24 of 183 read, then stopped: 8 'both', 7 'unsure',
  only 2 clearly one side. Four notes say the same thing: the two windows straddle a sentence boundary
  (period or semicolon), so each centring reads a *different* sentence and both labels can be right for
  their window. Centring is a window effect, not a model error; not worth reading further.
- **Verb-route precision outside recipe books (Rik, 18 Nov 2026), the counterpart of the food-only reading.**
  96 noun-centred frames from verb-selected occurrences in the extended set (v3f), 12 per genre, recipe books
  left out (`scripts/reading_sheet.py verb`, `reading_verb_v3f.xlsx`).
  - Right **69/96 = 72% [62–80%]**, not food 23, wrong frame 1, unsure 3. The food route there: 18/47 = 38%
    [26–53%]. The intervals don't overlap: the verb roughly doubles precision.
  - By genre, mostly 8–11 of 12. **Studies of language is the exception: 4/12**. There the verb is in a proverb
    or a gloss (*knollen voor citroenen verkopen*, *al moes* = aalmoes, *teelt* of herbs).
  - Medical books 9/12, in line with the frame-share result (verb 87% vs food-only 64%).
  - 'not food' errors are homonyms and idioms: *spruiten* (to grow), *vleesch en bloet*, *sout* for 'sou[dt]'.
  - Rik's recurring note, **'change of context'** (about 10 rows): right frame, but the passage moves on within
    the window. The same window effect as the centring disagreements.
  - **For the routing decision:** the verb route outside recipe books gives about 3 real frames in 4; the
    extra food-only passages there give about 1 in 7 (≈1,850 real frames for ≈13.5k passages, ≈13 h).
- **DECIDED (Rik, 18 Nov 2026): routing per genre.** Recipe books get every food word (food route). All other
  genres, medical books included, get verb-selected occurrences only.
  - **Why:** the food-only passages outside recipe books would add ≈1,850 real frames but ≈11,600 wrong ones,
    diluting every per-genre count.
  - **Scope:** over the 95 sample works (v3f harvest) that is 20,354 passages: 16,985 from recipe books and
    3,369 verb-selected elsewhere. 16,410 food-only occurrences outside recipe books are dropped.
  - **Known costs:**
    - studies of language stays weak even on the verb route (4/12);
    - the 'change of context' window effect is untouched.
- **Full routed run: paused (Rik, 19 Nov 2026, ~08:15).**
  - **Progress:** 7,905 of 20,354 rows (2,397 reused from v3f, 5,508 new); 12,449 left, ≈17 h at 5 s/row.
  - **Errors:** 14 'Request timed out'; these are retried on resume.
  - **Resume** (one instance only, never two at once on the same file):
    `uv run python scripts/triangulation_sample.py annotate --tag routed`, plus `scripts/run_progress.py`
    for the hourly report (it now also logs what Ollama has loaded and free memory).
    A half-written last line is repaired on resume.
  - **Open:** overnight speed varied from 5 to 33 s/row on identical passages (same two cookbooks, mean
    context 366 chars). It is not sleep and not thermal throttling, so the cause is machine- or server-side,
    still unknown. Before resuming, check that `ollama ps` shows only `qwen2.5-coder:latest`.

**Retracted here (16 Nov 2026): the C5 decision rule from VERB_LEXICON.md §4.** The answer was wrong; the
question stands, as T8.
- **Why:** reachability ("a verb candidate within ±150 chars") measures proximity, not evocation.
  - It can only rise as the list grows.
  - The 20-work trial (unreachable 13/14 → 8/14) showed rows reached through verbs that are merely nearby
    (*Legt* in a fishing poem, *doet* in a verse).
- **The rule as it was written:** ~~re-run T1 with the reviewed list:~~
  - ~~≥ 75% unreachable → the lexicon was not the bottleneck; put the effort into the entry route;~~
  - ~~< 50% → it was the lexicon;~~
  - ~~in between → C3 decides.~~
- **Tools kept:** `scripts/c5_reach.py`, and `triangulate_harvests.py --out` with the `pool_verbs` column.
  They are tools, not a gate.

## 5. Evaluation and gates per step

Rules for every step:
- Write the decision rule down *before* the run.
- Report n and the Wilson 95% CI with every percentage.
- State the baseline. "Better" means better than a named alternative: the current production route, the
  old cue, or "do nothing".
- Keep "did it run" (rows processed, errors) apart from "is it good".
- Look at a handful of cases first. If the alternatives don't differ there, don't run at scale.
- Record the outcome in the evidence `report.md`, with a status: adopted / deferred / stopped /
  retracted.

| Step | What is evaluated | Reference / baseline | Measure | Gate (decided before running) |
|---|---|---|---|---|
| **T1** | Reach of the verb route | Food-first rows as found | % of food-first frames with no uncapped verb hit within ±150 chars; n, CI | **G1:** ≥ 50% unreachable → verb-only is insufficient; T1b is needed to measure what the food route adds. < 20% → verb-only is adequate for reach; T1b only checks label agreement. In between → T1b decides. |
| **T1b** (steps 1–3) | Sample and harvest are sound | Frozen works list | Rows per route per genre; share of passages with both anchors; estimated LLM calls | **G2 (cost):** Rik approves the estimate before any annotation. **G2a (power):** fewer than ~100 passages with both anchors → widen the sample before annotating, or the agreement CI will be too wide to decide. |
| **T1b** (step 4) | Same-passage agreement between the routes | Each route against the other; read disagreements as the arbiter | Agreement with CI; reachability per route; who is right on ≥ 50 read disagreements | **G3:** the verb-anchored label is right in ≥ 2/3 of read disagreements → T5. The food-anchored label is right → no T5; the verb hint misleads. Split → T4c (guidelines) first. |
| **T2** | New heading cue | Old `regime_from_tei_scope_head` | Precision and recall on ~100 read heads (T4a) | **G4:** ship if precision ≥ the old cue's and recall is ≥ 20 points higher. Otherwise keep the old cue and record why. |
| **T3** | Two-level cascade | The same rows without the entry purpose | Sentence-level agreement on T4b/E1 rows; number of frames added at entry level that the sentence route can't reach; entry-level accuracy on T4a | **G5:** adopt only if sentence agreement does not drop (CI overlap is acceptable, a clear drop is not) *and* the entry level adds reachable frames with entry accuracy ≥ 0.8 on T4a. A failure → record as stopped; the unit question stays open. |
| **T4** | Gold of a new unit | n/a (it *is* the reference) | Coverage per genre/work; Rik's own agreement on a re-labelled 10% subsample a week later | **G6:** self-agreement < 0.8 → fix the guidelines (T4c) before using T4 as a reference. |
| **T5** | Verb-aware Step B | The same rows without the verb | Handful: the ~11 explicit E1 misses. Then T1b rows: INGESTION recall/precision with CI | **G7 (handful):** fewer than 6 of 11 flip correctly → stop; it's not the anchor. **G8 (scale):** recall up, precision not clearly down → adopt for food-anchored rows. |
| **T6** | Structure markers for cookbooks/newspapers | Rik's reading of sample pages/articles | Marker precision by sequence/position on ~20 pages/articles per source | **G9:** markers pass the read sample → repeat T1b/T3 for that source type. Otherwise that source type stays sentence-only, labelled as such. |
| **T7** | The headline | E1 (0.48) and the July 75% | Step B agreement with CI per source type and genre, on works never used for prompts | No gate. Replaces the quoted headline; logged in the claims ledger. |
| **T8** | Where frames live, by genre | C3 strata; E1 positions | Evoking kind × genre; entry position × genre; n and CI per cell | Decision rule to be set before the analysis. Not verb reachability (retracted C5 rule, see T8). |

Known threats to validity:
- **Shared judge:** both routes go through the same Step B model.
- **Window proxy:** ±150 characters stands in for "same clause".
- **Sample:** 40 works.
- **Single annotator for T4:** hence G6.
- **Regexes for the cue and `HEAD_FRAME`:** unvalidated until T2.

## 6. Not to do

- Don't overwrite sentence labels with the heading frame.
- Don't add random sentence gold. New gold is targeted (T4).
- Don't stratify the sweep by `text_regime`.
- Don't generalise DBNL TEI results to cookbooks or newspapers.
- No LLM run in T1b or T3 without the cost gate.

## 7. Order of work

1. T1, finish and report.
2. T1b steps 1–3 (no LLM), then the cost gate.
3. T2, in parallel; T4a once T2's head sample exists, since it's the same heads.
4. T1b step 4 + T5, after the gate.
5. T3 prototype on the T1b works.
6. T7 once T4 exists.
7. T6 later, per source type.
8. T8 from existing data (C3, E1) at any time. It feeds the routing in T3.
