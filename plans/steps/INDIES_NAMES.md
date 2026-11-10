# Indies food names: which name, where, when (1600–1990)

**Status:** in progress (9 Nov 2026; N1 done 10 Nov). Exploratory; findings are hypotheses on a
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

6. **N1, DBNL bridge 1750–1889** (`scripts/indies_names_dbnl.py` -> `indies_names_dbnl`,
   `indies_names_dbnl_samples`; DBNL rows in `names_over_time.csv` and notebook Part D).
   2,176 public-domain DBNL works with TEI (the set ends 1889). **Stricter Malay patterns**
   than for cookbooks, after reading every sample of a first run: *santen* = "saints"
   (63/63), *santan* = Santander, *tauge* = German *taugen*, *bawang* = river Toelang
   Bawang; so lowercase *lombok*, *klapper* only in compounds, *santan*/*tauge* whole
   words, *santen* not counted. 80 Malay hits remain, nearly all genuine.

7. **Acquisition routes for 1889–1949** (10 Nov 2026; nothing downloaded yet):
   - **KB cookbooks (N3).** The list is the KB culinary bibliography we already had
     (`kb_titles_parsed`, 7,545 catalogue records of the KB cookbook collection).
     `scripts/kb_cookbook_candidates.py` ->
     `acquisitions/kb_cookbook_candidates_1889_1949.xlsx`: 471 titles, 27 with Indies
     title words, 248 with a digital-copy link (KB resolver `MMKB…` = Delpher book, or
     Google Books), `decision` / `note` columns for Rik. Gotcha: the catalogue scrape
     is messy (records run into each other) and a digitised copy is a *separate*
     record dated by its digitisation year, so links are matched by **title only**
     and may point to another edition. Our KB files are named by MMKB id, which marks
     what we already have. Download target: `acquisitions/delpher_2026_11/` (+ year);
     register like the 9 Nov Google batch (`build_colonial_kwic.py` +
     `run_indies_harvest.sources()`).
   - **DBNL prose after 1889.** The PD zip ends in 1889 (*copyright verlopen* set);
     later works can be downloaded one by one on dbnl.org. Intake:
     `acquisitions/dbnl_manual_2026_11/` (files + `registry.csv`: file,title,year,note)
     and `scripts/indies_names_dbnl.py --extra-dir <folder>` (txt/pdf/epub; rows
     `manual: true`; only counts + short samples are stored, so in-copyright texts stay
     internal). Candidates: Daum (*Goena-goena* 1889, *Ups en downs* 1890, *Indische
     mensen in Holland* 1890), Van Maurik *Indrukken van een Tòtòk* (1897, on DBNL),
     Couperus *De stille kracht* (1900), A. de Wit (1902–05), Kartini (1911), Székely-
     Lulofs (1931–32), Du Perron (1935), Vuyk (1939); availability to check.
   - **Leiden *Indische bellettrie*** (`~/develop/indische_belletrie/leidenuniv_scrape.py`):
     does **not** work (see below). Rik had already downloaded 5 KITLV microfilms by hand
     (`~/Downloads/kb_indische_letteren/`); text + `registry.csv` in
     `acquisitions/leiden_kitlv_2026_11/` (KITLV condition: no reproduction, so counts and
     samples only). Ritter, *Indische herinneringen* (1843): no Malay names. Daum, *Ups en
     downs* (1890, text of a later druk): Malay only in *klapper*-compounds, *Spaansche
     peper* not *lombok*. Three films (Isoline, Ten Brink 6e druk, Westerlinck) lack a
     year and are skipped until Rik fills it in. KIT (Amsterdam) colonial material is
     also in Leiden Digital Collections ("Colonial Sources (KIT)"), same access problem.
     Also found: Wannée, *Kookboek van de Amsterdamsche Huishoudschool* 1911 and 1920
     PDFs in `~/develop/trifecta/amsterdams_kookboek/` (with text layer) that never went
     into `ldk2025_cookbooks` (1910/1912/1925/1940 did). The Leiden scraper itself The site resets connections to its `/search` path for automated
     clients (Playwright and plain curl, honest UA); homepage fine, `/oai2` 404. Not
     worked around. Routes: ask Leiden UB for a bulk export / OAI-PMH endpoint, or
     download by hand.

## Findings so far

- **Before 1866 the Malay kitchen names are absent from Dutch print** (DBNL): no
  *ketoembar*, *santan*, *lombok*, *djahe*. The exception is coconut: *klapper*-compounds
  (*klapperboom*, *klapperolie*) from 1805, Malay share 3–7% to 1860, ~20% 1860–1889;
  a plantation/trade word (VOC *klappersolie*). *Lombok* / *tjabé* appear 1866–1877 in
  Indies-themed periodicals (*De Gids*, *Los en vast*) and colonial novels, **with a
  gloss** ("lombok, Spaansche peper"). So the Samarang 1870 convention is Indies print;
  the metropolitan press of the same years translates.

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
| ~~N1~~ | **done 10 Nov** (see Done 6). Was: **Bridge 1800–1870**: targeted Indies-term harvest over DBNL (travel accounts, periodicals, Indies literature; `~/develop/indische_belletrie`) to see whether the cookbook convention predates 1870 |
| N2 | Test 1: Malay/Dutch ratio split by kg_mockup `COMMODITY_REGISTRY` membership (trade good or not) |
| N3 | More Indies cookbooks: candidate list ready (Done 7); waiting on Rik's picks/downloads, then register + harvest + Part D. Pairs to test the audience effect: *Makanlah nasi… voor Holland* (1928), *Het geheim van de rijsttafel: bewerking voor Nederland* (1934), *Indisch eten in Nederland* (1936) vs *De Hollandsche tafel in Indië* (1913), *Calvé-Delft's Hollandsche recepten voor Indië* (1938). *Kokki Bitja* (1895) is in Malay: Malay share meaningless, dish names useful |
| N4 | Notebook section on dishes (recipe headings: *sambal goreng*, *nasi goreng*) and how a dish changes between editions |

## Caveats

Small n (3 Samarang editions, 1 Nijmegen, 1 Visser, ~10 Dutch cookbooks); edition
years, not composition dates; newspaper data are extracted ingredient lists; word-
initial matching with known homonyms; Indies cookbooks share a publisher.
