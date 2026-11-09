# Indies food names: which name, where, when (1600–1990)

**Status:** in progress (9 Nov 2026). Exploratory; findings are hypotheses on a
small number of books.

**Question:** many ingredients have a Dutch and a Malay name (*koriander* /
*ketoembar*, *Spaansche peper* / *lombok*, *kokosmelk* / *santen*). Which name
does a text use, and when does the Malay name reach Dutch kitchens?

**Scope:** this belongs to the food-harvest stream for colleagues (export +
notebook), **not to kg_mockup**: the material is 1870–1990, "too far after VOC
times" (operator, 9 Nov 2026); kg_mockup stays on the VOC registry and VOC times.

## Done (9 Nov 2026)

1. **Vocabulary blind spot fixed.** `Food_terms.csv` (shared with Preservare) had
   none of the Indies terms. `vocabulary/Food_terms_indies.csv`: 52 entries, own
   `IND###` IDs, appended by `load_food_terms()`. Malay names of things with a
   Dutch name (*djahe, ketoembar, djintan, tjengkeh, pala, kajoe manis, bawang,
   klapper*) are **separate entries with `SIMILAR_TO`**, so the name shift stays
   countable. *Ketjap* has no Dutch rival (soy sauce simply was ketjap; *kecap* in
   modern spelling, English *ketchup*, not Dutch). Homonyms (*lombok* the island,
   *laos* the country) accepted as a risk.
2. **Books.** 10 new works (`GOOGLE_BOOKS_2026_11`), among them three editions of
   the *Oost-Indisch kookboek* (Samarang 1870, 1893; 1913 already in the KB batch),
   the *Indisch kookboek* (Nijmegen 1872) and *De nieuwe in- en buitenlandsche kock*
   (Nijmegen 1790). `PLACE_OF_PRINT` records Samarang vs Nijmegen.
3. **Targeted harvest** (`scripts/run_indies_harvest.py`): 5,086 Indies-term
   mentions in 21 books; 531 annotated (≈94% COOKING_CREATION: the frame adds
   little here, the interest is which word, where, when).
4. **Names over time** (`names_over_time.csv` in the food-harvest export, notebook
   Part D): Malay share per concept, cookbooks 1790–1940 + van Erp et al. newspaper
   recipes 1940s–1990s.
5. **States General / VOC test:** trade spices Dutch everywhere; SG "Malay" hits
   are homonyms (Xanten, *klapperlieden*, Palatinate); the one real local name is
   *klappersolie / calappusolij* in VOC resolutions (1759, 1775).

## Findings so far

- In the Samarang editions the Malay name dominates for coriander, chili, coconut
  (milk), **identically across 1870, 1893, 1913**: a convention, not drift.
- Ginger, cloves, cinnamon, pepper, nutmeg and onion stay Dutch, even there.
- The **Nijmegen-printed** 1872 Indies cookbook writes *Spaansche peper* 99× vs
  *lombok* 3×: place of print / audience effect.
- Around **1938–1940** *ketoembar* and *santen* appear in Dutch cookbooks.
- In the **post-war newspaper recipes** the Dutch names are back (*koriander*,
  *kokosmelk*); *ketoembar* survives mainly as a gloss ("gemalen koriander
  ketoembar").

**Working hypothesis:** trade vocabulary vs market/kitchen vocabulary. Goods with
an established European trade (the VOC spices) kept their Dutch trade name;
ingredients bought locally took the Malay name; the 1940 crossing fits Indies
cuisine moving to the Netherlands, and partly receded after the war.

## Next

| step | what |
|---|---|
| N1 | **Bridge 1800–1870**: targeted Indies-term harvest over DBNL (travel accounts, periodicals, Indies literature; `~/develop/indische_belletrie`) to see whether the cookbook convention predates 1870 |
| N2 | Test 1: Malay/Dutch ratio split by kg_mockup `COMMODITY_REGISTRY` membership (trade good or not) |
| N3 | More Indies cookbooks (Delpher, e.g. Catenius-van der Meijden, *Groot nieuw volledig Oost-Indisch kookboek*, 1902+) |
| N4 | Notebook section on dishes (recipe headings: *sambal goreng*, *nasi goreng*) and how a dish changes between editions |

## Caveats

Small n (3 Samarang editions, 1 Nijmegen, 1 Visser, ~10 Dutch cookbooks); edition
years, not composition dates; newspaper data are extracted ingredient lists; word-
initial matching with known homonyms; Indies cookbooks share a publisher.
