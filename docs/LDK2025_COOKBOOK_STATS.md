# 20th-Century Cookbook Corpus Statistics (1910–1940)

- **Total annotated recipes:** 3,663
- **Corpus source:** `ldk2025_cookbooks` (`cookbook_1910.txt`, `1912`, `1925`, `1940`)
- **Analysis table:** `ldk2025_analysis` (parquet)

---

## 1. Timeline & Volume Breakdown

| Year / Date | Recipes | Unique Targets | COOKING_CREATION | PRESERVING | CURE | NONE | Unassigned / Dropped |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1910 | 875 | 144 | 861 (98.4%) | 2 | 1 | 0 | 11 |
| 1912 | 890 | 145 | 871 (97.9%) | 2 | 2 | 2 | 13 |
| 1925 | 868 | 145 | 851 (98.0%) | 3 | 3 | 0 | 11 |
| 1940 | 1,030 | 153 | 1,018 (98.8%) | 3 | 1 | 0 | 8 |
| **Total** | **3,663** | **168** | **3,601 (98.3%)** | **10** | **7** | **2** | **43** |

---

## 2. Top 25 Food Ingredients & Dominant Preparation Triggers

| Ingredient (`target_word`) | Count | Dominant Governing Verbs (`lexical_unit`) | Top Methods (`COOKING_CREATION_Method`) |
|---|---:|---|---|
| melk | 331 | aan de kook, kook, bereid | gaar koken, bereid |
| boter | 292 | bereiding, bereid op de gewone wijze, roer | feuilletée, roer de boter tot room |
| eieren | 246 | klop, bereid, roer | gereid, klop |
| water | 230 | kook, bereid, kokend water | giet, gaar koken |
| suiker | 193 | bereid, inkoken, bereiding | inkoken, meng in |
| zout | 161 | zout, kook ze, bereid ze als bruine boonen | zout, roerende |
| bouillon | 122 | bouillon, bereid, kook | bereid de saus op de gewone wijze, trek op de gewone wijze bouillon |
| bloem | 103 | kneed, bereid, roer | rijzen, kneed alle ingrediënten tot een stevigen bal |
| aardappelen | 75 | koken, bakken, gebakken | zet ze op, oude aardappelen koken |
| brood | 74 | week, bak, wrijf | bak, wrijven |
| tarwemeel | 74 | meng, kneed, bak | meng, meng het tarwemeel met zooveel lauwe melk aan |
| rijst | 68 | aan de kook, rijstebrij, bak | gaar, rijstebrij |
| appelen | 53 | appelmoes, kook, zet ze op | appelmoes, weeken |
| room | 53 | , kook, breng | langzaam aan de kook, gaar |
| vleesch | 46 | bak, bereid, gekookte | gekookte, snijd het vleesch in dunne plakjes, leg deze op een schotel en bedek ze met de saus, die op de gewone wijze bereid is |
| abrikozen | 43 | kook, gaar koken, gaargekookt | gaar koken, gaargekookt |
| sap | 43 | kloppende, trekken, sap | kloppende, ontdoe de kersen van de stelen, wasch ze, haal er de pitten uit, maar zorg, dat al het sap opgevangen wordt |
| kalfsgehakt | 41 | meng het gehakt op de gewone wijze aan, koken, kook | meng het gehakt op de gewone wijze aan, meng |
| tong | 37 | kooktongen, behandel, gaar koken | behandel de tong evenals kalfstong, kook ze in het kokende water met het zout |
| azijn | 35 | bereid, azijn, kookroom | roer er het laatst de gewasschen en zeer fijngehakte kruiden door, wasch het vleesch, snijd zoo noodig een deel van het vet af en zet het 24 uur in half azijn, half water met het zout en de kruiden. keer het vleesch in dien tijd eenige keeren om en braad |
| garnalen | 34 | bereid, behandel, koken | bereid, bereid de saus op de gewone wijze |
| boonen | 34 | koken, gaar koken, bereid ze als bruine boonen | fijn koken, gaar koken |
| ham | 33 | kook, bereid, kook ze | kook de pijpen in hun geheel gaar in kokend water met zout, roereieren met ham |
| jus | 29 | kook, bereid, gaar koken | kook het lof gaar, bereid de saus, zooals in recept 319 beschreven is |
| saus | 29 | bereid, saus van, trekken | bereid de saus op de gewone wijze en voeg er wat suiker en nootmuskaat bij, roer er voorzichtig de gaargekookte asperges door, trekken |

---

## 3. Step C Qualia Role Fill Rates

| Qualia Role Field | Frame | Filled Count | Coverage |
|---|---|---:|---:|
| `COOKING_CREATION_Method` | COOKING_CREATION | 3,349 | 91.4% |
| `COOKING_CREATION_Process` | COOKING_CREATION | 2,073 | 56.6% |
| `COOKING_CREATION_Food_Product` | COOKING_CREATION | 2,783 | 76.0% |
| `PR_Technique` | PRESERVING | 10 | 0.3% |
| `PR_Medium` | PRESERVING | 6 | 0.2% |
| `PR_Food_Patient` | PRESERVING | 10 | 0.3% |
| `CURE_Affliction` | CURE | 6 | 0.2% |
| `CURE_Food_Treatment` | CURE | 7 | 0.2% |
| `INGESTION_Context` | INGESTION | 0 | 0.0% |
| `INGESTION_Ingestor` | INGESTION | 0 | 0.0% |
| `INGESTION_Manner` | INGESTION | 0 | 0.0% |
| `INGESTION_Food_Patient` | INGESTION | 0 | 0.0% |
| `INGESTION_Purpose` | INGESTION | 0 | 0.0% |

---

## 4. Top 20 Extracted Food Products (`COOKING_CREATION_Food_Product`)

| Resulting Dish / Food Product | Count |
|---|---:|
| bouillon | 49 |
| eieren | 36 |
| rijst | 31 |
| saus | 28 |
| soep | 27 |
| bruine boonen | 26 |
| taart | 24 |
| deeg | 22 |
| visch | 22 |
| pudding | 22 |
| aardappelen | 18 |
| vleesch | 17 |
| peren | 15 |
| marmelade | 15 |
| brood | 14 |
| melk | 14 |
| garnalen | 12 |
| snoek | 12 |
| appelmoes | 11 |
| gedroogde abrikozen | 11 |

---

## 5. Preservation Practices (`PRESERVING`)

| Technique (`PR_Technique`) | Medium (`PR_Medium`) | Preserved Food (`PR_Food_Patient`) | Trigger Verb | Date |
|---|---|---|---|---|
| droog worden |  | peterselie | droog worden | 1910 |
| pickling | mosterdzuur | Groenten | meng | 1910 |
| droog worden |  | peterselie | droog worden | 1912 |
| pickling | mosterdzuur | Groenten | meng | 1912 |
| droog worden |  | peterselie | droog worden | 1925 |
| pickling | mosterdzuur | groenten | meng | 1925 |
| bewaren met zout, salpeter en suiker | zout, salpeter en suiker | vleesch | wrijf | 1925 |
| droog worden |  | peterselie | droog worden | 1940 |
| pickling | mosterdzuur | groenten | inmaakazijn | 1940 |
| bewaren in alcohol | alcohol, brandewijn | vleesch | bewaar | 1940 |
