# Verb lexicon: a reviewed trigger list with measured coverage

**Status:** in progress (13 Nov 2026). V0 probe passed; lemma review lists ready for Rik. Prerequisite for T1b's annotation (TRIANGULATION.md, step T0).
**Owner:** Rik (downloads, review, C3 marking); Claude (generators, tables, measures).
**Evidence:** `docs/evidence/verb_lexicon/`.

## 1. Why

The verb route selects passages by matching a word list (`frame_verbs.py`).
- **Matching:** bare strings in one regex alternation, with `\b` boundaries and case-insensitive. No
  morphology, no spelling normalisation, no fuzzy matching, no embeddings.
- **The list has 357 entries:**
  - **Manual (81):** infinitives only. `_is_verb_like` = `endswith("en")` and excludes `ge-` participles,
    so *eet, at, gegeten, dronk, kookt, gekookt, gebraden* can never be in it.
  - **Mined (247):** mostly nouns, units, containers and function words (*allen, oncen, ponden, steenen,
    vaten, datmen*). The miner writes `keep=yes` automatically (`collocation_lexicon.py:184`), and the
    loader labels that `corpus:review`.
- **Consequences:**
  - 4.2% of food-noun occurrences are verb-selected (T1b), and 91% of food-first frames are unreachable
    by verb (T1).
  - Gold LUs are 12% covered.
  - Silver LUs: 8,002 covered, 11,787 not. The top misses are the inflected forms of the verbs we already
    have.

This is the infinitive-only lexicon from the July POC. It was judged on yield, and its recall was never
measured.

## 2. Goal and result

**Goal:** a list of triggers for *selection* in the harvest. This is not the classifier. Each entry holds:
- `form`, `lemma`, `frame`;
- `pos_check` (the dictionary verdict);
- `generators` (which sources proposed it);
- `dbnl_freq`;
- `rik_decision`: keep / drop / ambiguous / light.

**Result:**
- The reviewed list is committed in the repo (`trifecta_annotation/assets/verb_lexicon.csv` or alongside
  the prompt assets), with provenance per form.
- The loader reads only reviewed entries. Auto-`keep` disappears.
- Light verbs (*geven, nemen, doen, maken, leggen, gebruiken*) get their own decision, based on measured
  precision: out of the list, or in it only with scorer gating.

## 3. Steps

### V0 — Verb check: is this form a verb *here*?

Every candidate passes a verb check before review.

**Primary: a probe on GysBERT in-context token embeddings** (`emanjavacas/GysBERT`, cached locally;
trained on historical Dutch incl. DBNL).
- **Labels without a tagger or dictionary:**
  - negatives: food-vocabulary occurrences (nouns);
  - positives: occurrences of the reviewed manual verbs and their paradigm forms.
- **Model:** logistic regression on the target token's contextual vector (first-subword or mean over its
  subwords).
- **The verdict is per occurrence.** *rook* in "de rook" → noun; in "men rook het" → verb. This replaces
  the ambiguous flag a dictionary would need. A form's score is its share of verb readings over its
  sampled occurrences.
- **Not** embeddings of the bare string: mean-pooled GysBERT on short strings matches junk at cosine ≈
  1.0 (PLAN §9c).
- **Evaluation of the probe:**
  - train/test split *by lemma*, so it must recognise unseen verbs;
  - reported per genre: recipes are imperative-heavy (*neemt, doet, kookt*), narrative is finite/past
    (*at, dronk*);
  - checked against the C3 marks (Rik).
  - **Gate:** held-out-lemma accuracy ≥ 0.9 overall and ≥ 0.85 in each genre; otherwise the probe only
    ranks the review, it does not decide.

**Result (13 Nov 2026): gate passed.** `scripts/verb_probe.py` → `docs/evidence/verb_lexicon/probe_report.md`.
- Held-out-lemma accuracy is 0.908 overall (n=15,022; CI 0.90–0.91): recipe 0.927, medical 0.916,
  other 0.893. Verbs 0.885, non-verbs 0.931.
- The worst "errors" are mostly *seed* errors, i.e. the probe is right:
  - technique-verb stems that are nouns in the text (*suicker, konfijt, peekel, blik, zeef, zeven*);
  - food-vocabulary "nouns" that are verbs (*bezien, prik*).
  - Fix the seeds before the next run.
- Of the candidates: 1,234 verb, 423 ambiguous, 563 not verb, 354 not in the sample.
  - All the mined nouns and function words in the current lexicon come out *not verb*.
  - The top new verbs are the missing inflections (*doet, maakt, kookt, mengt, gekookt, eet, geneest,
    gegeten, gebraden, dronk*).
- The probe judges *verbhood*, not frame relevance: auxiliaries (*worden, werden*) and light verbs come
  out as verbs. That is decided at the lemma review.

**Cross-check, optional: GiGaNT-Molex** (INT, modern spelling, part of speech + paradigms; TSV download
after registration).
- Used to measure the probe on lemmas that Molex knows, and as the paradigm source for generator a.
- GiGaNT-Hilex (historical) needs permission, so it is not used.
- An older open INT/IMPACT historical lexicon would serve here too, if Rik finds it.

**Samples:**
- the T1b works;
- **the cookbooks in the corpus** (6 RECIPE works in the zip): the densest verb register and the imperative
  forms. This is **one stratum, not the sample**: they miss INGESTION in narrative (*at, dronk*), CURE in
  remedy books (*geneest, helpt*) and verbs in general.
- Probe training, evaluation and fill-mask therefore use three source types: recipe, MEDICAL, and
  narrative/other (the T1b strata). Results are reported, and gated, per source type.

### V1 — Candidate generators

| | Generator | Finds | Bias |
|---|---|---|---|
| a | **Paradigms**: Molex paradigms of reviewed lemmas, mapped back to historical spelling by the variant rules. Hand rules only as fallback. | inflected forms (*eet, at, gegeten, kooken*) | only lemmas we already have |
| b | **Silver LUs** (model, ~20.8k Dutch frame rows) | forms and new lemmas, at scale | the model's view; rows the routes selected |
| c | **Gold LUs** (Dutch, human) | human-marked triggers | small, KWIC-shaped |
| d | **English**: FrameNet LUs (Ingestion, Cooking_creation/Apply_heat, Preserving, Cure) + gold English LUs, translated into Dutch lemmas, then through a | missing *concepts* (season, baste, pickle) | modern English inventory |
| e | **Embeddings**: (1) GysBERT fill-mask in the slot next to a food word in the cookbooks and T1b works (\"men moet de boonen [MASK]\"); (2) fastText (character n-grams) on DBNL, neighbours of kept forms | verbs no list has; spelling variants a and b miss | (1) the model's preferences; (2) frequency, neighbours include nouns. Both go through V0. |
| f | **Existing mined list** (238 auto-kept) | the few real verbs | mostly junk |

### Working assumption (Rik, 13 Nov): few lemmas, many forms

The food-related verbs are a small, fairly closed set of **lemmas**. The variety is in inflection and
spelling. So:
- review is at the **lemma** level (about 150 lemmas with frames);
- forms are produced mechanically (paradigm + variants + "occurs in the texts" + the V0 probe);
- only *ambiguous* forms reach Rik;
- generators b–e serve to find **missing lemmas**: their forms are mapped back to known lemmas through the
  paradigms, and only what doesn't map is shown as a possible new lemma;
- C3 tests the assumption: low coverage *because of unknown lemmas* would falsify it.

**Progress (13 Nov 2026).**
- **Spelling side:** `trifecta_annotation/spelling_key.py`, a port of LotA's P1.6 rules (archival-language
  c11f64c) on `formula-detection==0.6.1`, plus our `loose_key`, which squeezes doubled letters.
- **Inflection side:** `trifecta_annotation/verb_forms.py` (tests in `tests/test_verb_forms.py`). The two
  are complementary.
- **`scripts/verb_lexicon.py lemmas`** maps the 1,657 forms the probe calls verb/ambiguous to lemmas:
  - 445 forms map to the **182 known lemmas**. These carry 12,952 silver LU occurrences, vs 5,372
    unmapped, so ~71% of the verb mass is in the known lemmas.
  - The rest falls into 804 stem groups. **122 have ≥ 10 silver occurrences**: 13 proposed `drop-aux`,
    8 `forms-of` a known lemma, 1 prefix, and 100 genuinely open (*distilleren, branden, smeren,
    toebereiden, plukken, weiken, zuiveren, kneden, persen, vullen, verteren* … but also *kopen,
    vangen, krijgen, zien*).
- **Known false merge:** *legen / leggen* (one row; Rik splits it).
- **Review files:**
  - `lemma_review.csv`: one row per lemma, with spelling variants merged, frames, forms found, silver/gold
    counts; Rik fills `rik_decision` / `rik_frame`;
  - `new_lemma_candidates.csv`: Rik fills `rik_lemma` / `rik_frame` / `rik_decision`. Groups under 10
    silver occurrences are the long tail, left out of the review on purpose.

**Variation check (13 Nov 2026, `verb_lexicon.py variation-check` → `variation_check.md`).** Rik: most
variation is soundex-like, and HTR adds visual confusions.
- **A phonetic key works as diagnosis, not expansion (Rik, 13 Nov).** It is never used in matching. Its extra
  matches (`read_phonetic_matches.csv`) are a review aid: a real variant found there points to a gap in the
  paradigms or the rules, and is fixed there as a named rule. As expansion it is too aggressive: It adds 410 types / 29.8k tokens, almost all false (*god → goot,
  zouden → zouten, vast → wast, toen → doen, voet → voedt*): merging d/t and v/w/f destroys the
  distinctions between verb forms and common words. The LotA rules are at the right depth.
- **OCR/HTR confusions are negligible in DBNL text** (re-keyed). The top matches are real words (*het → hel,
  tegen → legen*). Re-check on OCR sources (Delpher, 20th-century cookbooks; T6) with `fuzzy-search`.
- **`loose_key` corrected.** Squeezing vowels merged *naam/nam*, so now only doubled consonants are squeezed
  and the *ge-* prefix doubling is undone. *legen/leggen* are now separate.
- **Remaining homographs** (*was, heel, zout, weg, suiker, smaak, stof, droog*) are the probe's job, per
  occurrence. A form with probe verb_share < 0.8 must not be a bare trigger; V3 decides how (probe at match
  time, or excluded).

**Principle (Rik, 13 Nov 2026): rather too large than too small.** The list feeds collocation, which is
sieved later (scorer, Step A sieve, LLM). A missing verb is lost for good; an extra one costs sieving.
- **Review is "keep unless":** every lemma and candidate group is proposed `keep`, and Rik marks only drops.
- **Homographs stay in**, flagged `ambiguous`.
- **The tail runs down to ≥ 3 silver occurrences.**
- **Exceptions, proposed as drop:** non-verbs (probe verdict *not verb*: they add no recall, only cost) and
  auxiliaries (`drop-aux`: frequent, never frame-evoking).
- **The cost is measured in C5** (extra hits and LLM calls) before T1b goes back to G2.

### V2 — One merged review table

`docs/evidence/verb_lexicon/review.csv`: form, lemma, frame, pos_check, generators, dbnl_freq, 3 KWIC
lines from the DBNL text.
- Sorted by frequency.
- Forms that pass V0 as unambiguous verbs *and* are found by ≥ 2 generators are proposed `keep`, for a
  quick confirm.
- Rik decides the rest.

### V3 — Wire it in

- `build_merged_lexicon` reads the reviewed list.
- `VerbHit` carries the lemma, so `score_snippet_for_frame`'s core-verb bonus and conflict rules work on
  the lemma, not the surface form.
- Tests:
  - paradigm examples;
  - `keep=auto` rows don't load;
  - the reviewed list round-trips.

**Done (16 Nov 2026), not committed:**
- **Export:** `scripts/verb_lexicon.py export` writes `trifecta_annotation/assets/verb_lexicon.csv` from
  `verb_lexicon_review_2.xlsx` + `review_overrides.csv` (overrides win, and are authoritative for the forms
  they list). One row per form: lemma, frame, decision, flags, origin.
- **Forms:** forms Rik saw or added, plus the paradigm restricted to forms attested in the 41 probe works.
  Generated forms the probe calls *not verb* are left out. The paradigm closes the *-t* gap (*haalt*).
- **Result:** 349 lemmas kept, 209 dropped. 1,966 kept forms (1,024 reviewed, 942 paradigm); 1,068 dropped
  forms.
- **Flags:** *ambiguous* (166 forms: homographs or probe verb share < 0.8), *multi-frame*, *aux-ambiguous*,
  *check*.
- **Spelling rules** in `verb_forms._variants`, from the phonetic diagnosis: *vv → w*, final *-c*, *cu/ku*.
- **Loader:** `frame_verbs.load_reviewed_lexicon`. Rik's drops remove forms whatever their source. His
  lemma, frame and flags win. The auto-kept mined corpus list is no longer loaded.
- **Matcher:**
  - word lookup instead of one regex alternation: same hits, 56× faster;
  - enclitic forms (*kooktse, doetmen, doet'er*; stop list *gieter*) match their host;
  - `VerbHit` carries `lemma` and `flags`.
- **Scorer:**
  - `reviewed` passes the guideline gate;
  - core-verb bonus on the lemma (not for *multi-frame*);
  - **−2 for ambiguous forms (provisional, measured in C4/C5)**.
- **Separable verbs (skip-gram, Rik 16 Nov):** after a verb hit, look up to 7 words ahead for a particle that
  *closes the clause*. That means punctuation or a conjunction follows it, not *te* and not a noun phrase. If
  particle + lemma is a known lemma, the hit takes that lemma and frame and is flagged `separable:<base>`.
  - Measured on 4 works: 553 hits. The parse was right in 23 of 25 sampled.
  - Misses: *dampen* as a noun, and *op te leggen*; the latter is fixed.
- **Tests:** `tests/test_reviewed_lexicon.py`, `tests/test_verb_forms.py`. Full suite 338 passed.
- **Open:**
  - 15 lemmas flagged `check`: Rik marked drop, but the note says "stem is …";
  - the form *at*: 2-letter forms are excluded (*eet* is in);
  - lemma names from unfixed proposals (*stooteen, bieen*) are cosmetic, since the forms map correctly;
  - C4/C5.

## 4. Evaluation: how we know coverage is OK

The references are kept independent of each other where possible.

| | Reference | Measures | Gate |
|---|---|---|---|
| C1 | Gold, Dutch *verb* LUs only (baseline computed first) | % of gold verb-LU tokens matched by the list | reported |
| C2 | Leave one generator out: build without silver, measure on silver; build without paradigms, measure on silver; and so on | what each generator adds; silver's bias towards selected rows | reported |
| C3 | **Independent of every list:** ~150 random sentences with a food noun from the 39 T1b works, stratified by genre. Rik marks the frame-evoking word (verb, noun, construction, heading, none). | share evoked by a verb (the route's ceiling); share implicit / without a verb; the list's coverage of the verb share | **≥ 80%** of verb-evoked cases covered |
| C4 | 100 random hits per generator source, read by Rik | precision per source, and for light verbs separately; *hebben* (kept, flag `aux-ambiguous`, see `review_overrides.csv`) on its own | new forms ≥ old hits − 10 points; light verbs and *hebben* decided by their own precision |
| C5 | No LLM: T1 reachability, T1b verb-selected share (4.2%), the funnel; before/after per genre | effect size, with n and CI | reported |

C3 also answers whether "91% unreachable" is an artefact of the lexicon or a fact of the texts. It can
start at once, because it needs no list.

**Decision rule for C5 (set 16 Nov 2026, before the re-run; thresholds are a proposal, Rik to adjust).**
The step-back review (TRIANGULATION.md §2b) predicts a ceiling. If recipes name their goal in the
heading, adding paradigm forms will not reach those frames. Re-run T1 with the reviewed list:
- unreachable share stays **≥ 75%** → the lexicon was not the bottleneck. Stop extending it after V3 and
  put the effort into the entry route (T2/T3).
- unreachable share drops **below 50%** → it was the lexicon. Keep improving it (light verbs, C4).
- in between → C3 decides (the share of frames evoked by a verb at all).

This lexicon work is one fix with a diagnosed cause (infinitive-only list), not a series of failed fixes,
so it is legitimate. The rule records where we would stop.

**Then:** re-run T1b harvest → estimate → select, and go back to gate G2 before any annotation.

## 5. Order

1. C3 sample drawn (252 passages, `docs/evidence/verb_lexicon/c3_sample.csv`; Rik marks it, `is_food`
   first). Candidates b, c, f drawn (`candidates_raw.csv`, 6,392 forms). Optional: Rik downloads Molex.
2. V0 probe: training/test sets from the cookbooks + T1b works, held-out-lemma evaluation, then scoring
   of the candidates.
3. Generators a, b, c, f; then d; then e.
4. V2 review table → Rik reviews.
5. V3 wiring + tests.
6. C1, C2, C4, C5; check C3 against the list.
7. Re-select T1b → G2.

No LLM calls in this plan. No commit or push without asking.

## 6. Not to do

- No historical-Dutch tagger/lemmatiser such as GaLAHaD (decided 13 Nov: not worth it here).
- No embeddings as the *matcher*: they generate candidates only.
- Don't measure coverage against silver alone; that measures resemblance to qwen (hence C2 and C3).
- No auto-`keep`.
