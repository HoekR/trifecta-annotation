# Selection-mode experiment v2

Pool 1500 mentions/work, top 60/mode, seed 0. Errors excluded: 0.

## Works

| regime | work | mentions | verb-selectable | scope-selectable | TEI entries |
|---|---|---:|---:|---:|---:|
| RECIPE_PRACTICE | Huishoudelyk woordboek (`chom003huis01_01.xml`) | 52353 | 494/1500 | 191/1500 | 7120 |
| RECIPE_PRACTICE | Het secreet-boek vol heerlijke konsten (`bate002secr02_01.xml`) | 6125 | 359/1500 | 134/1500 | 1386 |
| RECIPE_PRACTICE | De volmaakte Hollandsche keuken-meid (`_vol002volm01_01.xml`) | 7382 | 439/1500 | 39/1500 | 691 |
| MEDICAL | Pharmacopoea Amstelredamensis (`_pha001phar05_01.xml`) | 1010 | 163/1010 | 18/1010 | 238 |
| LITERARY | De Tijdspiegel. Jaargang 33 (`_tij008187601_01.xml`) | 3990 | 93/1500 | 0/1500 | 144 |
| LITERARY | Vaderlandsche letteroefeningen. Jaargang 1866 (`_vad003186601_01.xml`) | 3201 | 34/1500 | 11/1500 | 140 |
| LITERARY | Proeve eener geschiedenis der Nederduitsche dichtk (`vrie032proe01_01.xml`) | 1222 | 20/1222 | 0/1222 | 25 |
| UNKNOWN | Biblia, dat is: De gantsche H. Schrifture, vervatt (`_sta001stat02_01.xml`) | 16036 | 96/1500 | 0/1500 | 0 |
| UNKNOWN | De levens en werken der Hollandsche en Vlaamsche k (`kram011leve01_01.xml`) | 4462 | 23/1500 | 5/1500 | 7013 |
| UNKNOWN | Nieuw woordenboek der Nederlandsche taal (`cali003nieu01_01.xml`) | 10044 | 100/1500 | 4/1500 | 15541 |

## Results

`unreachable by verb` = real frames on mentions with no qualifying verb, which `verb_food` can never select.

| regime | mode | n | survive Step A | real frame | unreachable by verb |
|---|---|---:|---:|---:|---:|
| ALL | verb_food | 497 | 79% (391) | 67% (334) | 0 |
| ALL | embedding | 600 | 62% (375) | 52% (314) | 227 |
| ALL | noun | 600 | 56% (338) | 38% (225) | 164 |
| ALL | entry_scope | 197 | 84% (165) | 78% (154) | 107 |
| ALL | entry_scope_head | 197 | 84% (165) | 80% (158) | 110 |
| LITERARY | verb_food | 114 | 67% (76) | 55% (63) | 0 |
| LITERARY | embedding | 180 | 52% (94) | 35% (63) | 48 |
| LITERARY | noun | 180 | 27% (48) | 10% (18) | 15 |
| LITERARY | entry_scope | 11 | 27% (3) | 9% (1) | 1 |
| LITERARY | entry_scope_head | 11 | 18% (2) | 0% (0) | 0 |
| MEDICAL | verb_food | 60 | 85% (51) | 85% (51) | 0 |
| MEDICAL | embedding | 60 | 90% (54) | 90% (54) | 42 |
| MEDICAL | noun | 60 | 87% (52) | 72% (43) | 32 |
| MEDICAL | entry_scope | 18 | 89% (16) | 89% (16) | 12 |
| MEDICAL | entry_scope_head | 18 | 83% (15) | 83% (15) | 11 |
| RECIPE_PRACTICE | verb_food | 180 | 91% (163) | 90% (162) | 0 |
| RECIPE_PRACTICE | embedding | 180 | 91% (163) | 91% (163) | 110 |
| RECIPE_PRACTICE | noun | 180 | 87% (156) | 80% (144) | 98 |
| RECIPE_PRACTICE | entry_scope | 159 | 87% (139) | 86% (136) | 93 |
| RECIPE_PRACTICE | entry_scope_head | 159 | 89% (141) | 88% (140) | 96 |
| UNKNOWN | verb_food | 143 | 71% (101) | 41% (58) | 0 |
| UNKNOWN | embedding | 180 | 36% (64) | 19% (34) | 27 |
| UNKNOWN | noun | 180 | 46% (82) | 11% (20) | 19 |
| UNKNOWN | entry_scope | 9 | 78% (7) | 11% (1) | 1 |
| UNKNOWN | entry_scope_head | 9 | 78% (7) | 33% (3) | 3 |

Note: entry-scope selection uses production's `regime_from_tei_scope_head` cues, which have their own false positives (`manier om` matches 'Andere manier om Aal te vangen').
