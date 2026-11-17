# C3: patterns in the first 69 passages, and the enclitic rule

*16 Nov 2026. Rik marked `is_food` (+ `evoking_word`, notes) for 69 of 252 C3 passages in `verb_lexicon_review_2.xlsx`. Patterns read by Claude; agreement table in `c3_prefill.csv`.*

## Decision: C3 stops at 69 (Rik, 16 Nov)

- 52 of 69 targets are not food (75%), so all 252 would yield only about 60 food passages: thin for the ≥ 80% gate.
- Whether a target is food is unequivocal, so marking more of it adds little.
- **Consequence:** the C3 gate in VERB_LEXICON.md §4 cannot be read at the planned precision on this sample. Report C3 as n = 17 food passages with the interval; any coverage claim rests on C5/C1 plus this.

## Patterns

1. **The noun list is the first problem in weak genres.**
   - 52 n's: about 30 body parts (*hart, oog, borst, voet, bloed, hoofd, lever*), in the vocabulary because of offal and cure; about 12 homographs (*zult, noot, Hooft, Louw, voet* as a measure, *Afval, Lam*).
   - RECIPE is 5/6 food, MEDICAL 2/8; the literary and linguistic strata about 10/55.
2. **Evoking kind of the 17 food passages:** about half verb (8), 2 of them verb + fused pronoun (*kooktse, strooid'er*); heading 1–2 (*Niervet, hoe men dat best smelten zal*; *Van de Syropen, Honing en Rob*); construction/noun 3–5; none 2–6.
3. **"Food" depends on use** (Rik's notes):
   - *bier* and *peper* are "always food, except when traded";
   - *Wijn* is "poetic";
   - for *water*, the verb is "not the essence of the cooking".

   **Trade makes food a commodity.** The relation between food and commodity was one of the main ideas behind kg_mockup (VOC commodities export).

## Agreement on evoking kind (Rik pre-filled vs Claude independent): 12 of 17

The 5 disagreements are all about whether there is a frame at all when the food word is real but figurative, an example, or in a heading:

| target | Rik | Claude |
|---|---|---|
| water (*in de karaf*, grammar example) | noun *karaf* | none: metalinguistic example, no event |
| bier (*glaasje bier… aan drank geraken*) | noun *drank* | construction, INGESTION |
| Niervet (*hoe men dat best smelten zal*) | (empty) | heading, COOKING_CREATION |
| olie (*voor het knijpen*) | construction | none: idiom of abundance |
| bier (*scherbier op de tap*) | construction | none: simile |

Note: *Wijn* (poetic) is marked `is_food = n`, but *bier op de tap* (simile) is `y`.

**Rik, 16 Nov:** *Wijn* is food as well. It is used poetically as an object of blame, but it is food nonetheless. So figurative use does not make a word non-food.

**How to record figurative use (careful):** not as an extra `evoking_kind` value but as a separate column, `use` = literal / figurative / metalinguistic. The axes stay apart:
- `is_food`: is the referent food? Unaffected by figurative use.
- `evoking_kind`: what evokes the frame.
- `use`: how the passage uses it.
- `frame`: may still be a real frame in figurative use (wine blamed → drinking is implied), or NONE. Decided per passage, not by the `use` value.

Reason: a `figurative` kind would quietly turn into "no frame" or "not food", and would move cases out of the verb share without a decision.

## Enclitic rule (tested on 4 works: vol002, magi007, chom003, pha001phar05)

**token = known verb form (ending -t/-dt or -en) + enclitic {ze, se, men, er, 'er}**. Match the verb part only. Stop list: *gieter*.

| enclitic | types | tokens | precision (by eye) |
|---|---:|---:|---|
| -ze | 87 | 681 | all correct |
| -se | 43 | 391 | all correct |
| -men | 13 | 35 | all correct |
| -er / -'er | 27 | 180 | 1 false (*gieter*, 19) |

- The check against the reviewed form list is what makes the rule safe. Without it, *bakker, stamper, houder, drankje* and *zacht* match.
- **Side finding, a paradigm gap:** 3rd-person *-t* forms such as *haalt* (364), *brandt, onthoudt, verspreidt* are missing from the form list.
- **Out of scope here:** *vander, salmen, datmen, hoemen* are fused function words. They matter for the heading cue (*hoemen* opens recipe headings) and the noun list, not for verb matching.
