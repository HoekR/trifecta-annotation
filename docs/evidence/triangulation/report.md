# Triangulation: food-first vs verb-first harvests

Works with both: 1438. Window: ±150 chars around the food-first target. food row located: 7803, verb row not located: 77, food row not located: 970.

## 1. Reachability: would the verb route have found the food-first row?

Verb route uncapped (full candidate pool). Rows by food-first label:

| food_label       |   False |   True |   All |
|:-----------------|--------:|-------:|------:|
| COOKING_CREATION |     547 |     45 |   592 |
| CURE             |     147 |     12 |   159 |
| DROPPED          |    5145 |     66 |  5211 |
| INGESTION        |     347 |     48 |   395 |
| NONE             |    1406 |     20 |  1426 |
| PRESERVING       |      19 |      1 |    20 |
| All              |    7611 |    192 |  7803 |

Food-first real frames unreachable by verb: **1060 of 1166** (91%, 95% CI 89%–92%).

## 2. Cross-check: food-first rows with an annotated verb-first neighbour

Paired rows: 209. Same label: 139 (67%, 95% CI 60%–73%).

Frame vs no frame:

| food_kind   |   frame |   no frame |   All |
|:------------|--------:|-----------:|------:|
| frame       |      90 |         22 |   112 |
| no frame    |      20 |         77 |    97 |
| All         |     110 |         99 |   209 |

Full labels (rows = food-first, columns = verb-first):

| food_label       |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |
|:-----------------|-------------------:|-------:|----------:|------------:|-------:|
| COOKING_CREATION |                 35 |      1 |         3 |           3 |      3 |
| CURE             |                  1 |      8 |         2 |           1 |      0 |
| DROPPED          |                  4 |      3 |        52 |           6 |      9 |
| INGESTION        |                  4 |      0 |         7 |          36 |      7 |
| NONE             |                  4 |      0 |         8 |           3 |      8 |
| PRESERVING       |                  0 |      0 |         0 |           1 |      0 |

## 3. The disagreement to read: food-first no frame, verb-first neighbour has a frame

20 rows; sample (first 25):

- `_eer002eers01_01.xml` [oog] food=DROPPED, verb=INGESTION (eten): "; 't Goede minnen, 't kwade haten, 't Echte ziften van den schijn: Want wat wij ook onderwinden, Schoon geen mensch het merkt of ziet, Denkt er altijd aan, mijn vrinden: 's Heeren oog ontgaat het niet"
- `_eer002eers01_01.xml` [maag] food=DROPPED, verb=INGESTION (eten): "onderwinden, Schoon geen mensch het merkt of ziet, Denkt er altijd aan, mijn vrinden: 's Heeren oog ontgaat het niet. Smullebroer. Altijd eten, altijd smullen, Altijd denken om de maag Met wat lekkers"
- `_fie002fiel01_01.xml` [water] food=DROPPED, verb=COOKING_CREATION (braden): 'cleederen Dallinger ee n hangman Diftel oft cluseme n t die kercke Dille een meysken Deystere eene n teerlinc. E Rlat een meester Erlatinne een meestersse. F Oncke vier Flossaert water Flosselic visch'
- `_haa007haag01_01.xml` [harte] food=DROPPED, verb=INGESTION (drinken): "dagen, het streeld onze zinnen, De liefde geeft vreugde aan onze Vrindinnen, Dan kent men geen zorgen, dan voelt men geen smarte, Want de vreugd van 't minne neemd de zorg van 't harte. 6. Kom laat on"
- `_hul004hulp01_01.xml` [Aal] food=NONE, verb=COOKING_CREATION (Eten): 'landsch en russisch naar de hollandsche uitspraak gesteld. &nbsp; Prijs 5½ Stuiver. &nbsp; Te AMSTERDAM , B ij E. MAASKAMP, Dam en Kalverstraat, No. 1. I. Van het Eten en Drinken. Aal Uhgor Baars Ohku'
- `_hul004hulp01_01.xml` [Baars] food=NONE, verb=COOKING_CREATION (Eten): 'russisch naar de hollandsche uitspraak gesteld. &nbsp; Prijs 5½ Stuiver. &nbsp; Te AMSTERDAM , B ij E. MAASKAMP, Dam en Kalverstraat, No. 1. I. Van het Eten en Drinken. Aal Uhgor Baars Ohkun Aardappel'
- `_hul004hulp01_01.xml` [Aardappelen] food=NONE, verb=COOKING_CREATION (Eten): 'ar de hollandsche uitspraak gesteld. &nbsp; Prijs 5½ Stuiver. &nbsp; Te AMSTERDAM , B ij E. MAASKAMP, Dam en Kalverstraat, No. 1. I. Van het Eten en Drinken. Aal Uhgor Baars Ohkun Aardappelen Simijack'
- `_hul004hulp01_01.xml` [Appel] food=NONE, verb=COOKING_CREATION (Eten): 'nbsp; Prijs 5½ Stuiver. &nbsp; Te AMSTERDAM , B ij E. MAASKAMP, Dam en Kalverstraat, No. 1. I. Van het Eten en Drinken. Aal Uhgor Baars Ohkun Aardappelen Simijacke Bessen Gruhscha Appel Jäbloko Blaauw'
- `_vro023vrol01_01.xml` [hart] food=DROPPED, verb=INGESTION (eeten): "21. Jaap, die ook vreugd wil raapen, Ryt mede fluks naar steê, Om 't Kermis feest te vieren En neemt zyn Kniertje meê. 22. Hoe vrolyk lacht dit paartje Nu het de Kermis ziet! Het hart springt op van v"
- `_zaa002zaan01_01.xml` [lysters] food=NONE, verb=INGESTION (eeten): "deren, &amp;c. 6. Vraag het aan het jonge Volkje, Vraag het zelfs den Drukker T..kje. 't Woord is, Kinderen &amp;c. 7 Heere voegje naast uw Vrysters, Drinkt en klinkt en zingt als lysters Waare Kinder"
- `_zee004zeeu01_01.xml` [bloed] food=DROPPED, verb=CURE (legen): '2009-11-24 AS colofon toegevoegd De wijn. Eene bekende Wijs. O! wat is de wijn toch goed, Want hij zuiverd, want hij zuiverd, O! wat is de wijn toch goed, Want hij zuiverd ons het bloed. Wie zou dan g'
- `ampz001hoog01_01.xml` [herten] food=DROPPED, verb=CURE (maken): 'ewijsen: waerom ik ook niet en hebbe willen nalaten dese onse goede vriendschap, van uwer E dele sijde met gemelde weldaed (onverdiend) besegeld, met dit gering getuygenisze mijns herten, aen mijner s'
- `ampz001hoog01_01.xml` [lendenen] food=DROPPED, verb=CURE (maken): 'lde weldaed (onverdiend) besegeld, met dit gering getuygenisze mijns herten, aen mijner sijde desgelijkx te bevestigen, ende uwer E dele nu Peter van den sone mijns lichaems, ende lendenen, van dese v'
- `ampz001nasz01_01.xml` [bloed] food=DROPPED, verb=COOKING_CREATION (maken): 'jn swaerd sal vleesch eten over den bloede der verslagenen, ende over gevangenisze, ende over den ontblooten hoofde des vijands. Iuycht alle gy die sijn volk sijt: want hy sal het bloed sijner knechte'
- `blan049juff01_01.xml` [borst] food=DROPPED, verb=INGESTION (drinken): 'essen Gedronken, voor den dorst... Ferdinand . Daar is Krispyn. Krispyn , zingt . Ik heb omtrent twee vlessen Gedronken, voor den dorst. En om de smart te lessen Van myn benaauwde borst, Zo ga ik zomt'
- `goev001oomw01_01.xml` [voeten] food=DROPPED, verb=COOKING_CREATION (stoven): 'fden te gaan, dan zochten zij oom willem vaak onder den appelboom op, en de oude man was dan recht in zijn schik, als zijne kleine vriendjes zich naast hem op de bank of aan zijne voeten in het gras n'
- `hoff049wild01_01.xml` [haas] food=NONE, verb=INGESTION (drinken): "door 't groene gras, Totdat hij bij zijn woning was; - Daar sprong de man, met pak en zak, Voorover in den regenbak. 't Was juist bijtijds, want eensklaps: - ‘Paf!’ Daar schoot de haas zijn snaphaan a"
- `hoff049wild01_01.xml` [haas] food=NONE, verb=INGESTION (drinken): "ken zou; Maar toen de haas had losgebrand, Schoot hij haar 't kopje uit de hand; En ziet! - vlak bij den regenbak, Daar zat in 't gras, op zijn gemak, Het zoontjen van den grooten haas; - Dien armen, "
- `lang020arle01_01.xml` [zult] food=DROPPED, verb=COOKING_CREATION (bakken): "an Kapitano geeven. Mezetyn . Daar is uw schat, myn Heer, 'k wil zeggen uw papier, Het a la modes geld, zo kostlyk en zo dier. Kapitano . Nu, Arlequyn, laat zien wat je in de kist zult pakken. Arlequy"
- `sche039geze02_01.xml` [schouder] food=DROPPED, verb=INGESTION (eten): "k mijn Kanarie meê Een stukje suiker uit de thee. Het makke beest schijnt dit te weten; Want nauwlijks zijn wij aangezeten, Of 't fladdert stadig heen en weêr, Zet zich op moeders schouder neêr, En sc"
