# Selection-mode experiment

Pool 1500 mentions/work, top 40/mode, seed 0. Errors excluded: 0.

Works: RECIPE_PRACTICE: Huishoudelyk woordboek (chom003huis01_01.xml); LITERARY: De Tijdspiegel. Jaargang 33 (_tij008187601_01.xml); UNKNOWN: Biblia, dat is: De gantsche H. Schrifture, vervattende alle de canonijcke Boecken des Ouden en des Nieuwen Testaments (_sta001stat02_01.xml)

| regime | mode | n | survive Step A | real frame |
|---|---|---:|---:|---:|
| ALL | embedding | 120 | 75% (90) | 62% (74) |
| ALL | noun | 120 | 55% (66) | 33% (40) |
| ALL | verb_food | 120 | 79% (95) | 76% (91) |
| LITERARY | embedding | 40 | 85% (34) | 62% (25) |
| LITERARY | noun | 40 | 50% (20) | 15% (6) |
| LITERARY | verb_food | 40 | 78% (31) | 75% (30) |
| RECIPE_PRACTICE | embedding | 40 | 82% (33) | 82% (33) |
| RECIPE_PRACTICE | noun | 40 | 82% (33) | 65% (26) |
| RECIPE_PRACTICE | verb_food | 40 | 75% (30) | 75% (30) |
| UNKNOWN | embedding | 40 | 57% (23) | 40% (16) |
| UNKNOWN | noun | 40 | 32% (13) | 20% (8) |
| UNKNOWN | verb_food | 40 | 85% (34) | 78% (31) |
