# Step A sieve: shadow run on held-out rows

4638 rows annotated after training (entry-scope run, selection v1/v2), minus texts in the training split. `work_seen` = the work was in the training split (split is by work).
Production applies the sieve only to ROUTED rows (weak regimes); RECIPE/MEDICAL go straight to the LLM.

| stratum | threshold | n | calls saved | Step A keeps lost | real frames lost | of real frames |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 0.90 | 4638 | 28% (1297) | 161 | 117 | 4.2% of 2768 |
| ALL | 0.95 | 4638 | 27% (1234) | 138 | 99 | 3.6% of 2768 |
| ALL | 0.98 | 4638 | 24% (1103) | 92 | 63 | 2.3% of 2768 |
| ALL | 0.99 | 4638 | 21% (993) | 69 | 47 | 1.7% of 2768 |
| ROUTED (production) | 0.90 | 1160 | 48% (556) | 35 | 11 | 3.3% of 329 |
| ROUTED (production) | 0.95 | 1160 | 47% (542) | 30 | 9 | 2.7% of 329 |
| ROUTED (production) | 0.98 | 1160 | 43% (503) | 18 | 5 | 1.5% of 329 |
| ROUTED (production) | 0.99 | 1160 | 42% (486) | 14 | 4 | 1.2% of 329 |
| ROUTED regime=LITERARY | 0.90 | 561 | 50% (280) | 14 | 4 | 2.3% of 173 |
| ROUTED regime=LITERARY | 0.95 | 561 | 49% (276) | 12 | 3 | 1.7% of 173 |
| ROUTED regime=LITERARY | 0.98 | 561 | 46% (260) | 8 | 1 | 0.6% of 173 |
| ROUTED regime=LITERARY | 0.99 | 561 | 44% (248) | 6 | 1 | 0.6% of 173 |
| ROUTED regime=UNKNOWN | 0.90 | 599 | 46% (276) | 21 | 7 | 4.5% of 156 |
| ROUTED regime=UNKNOWN | 0.95 | 599 | 44% (266) | 18 | 6 | 3.8% of 156 |
| ROUTED regime=UNKNOWN | 0.98 | 599 | 41% (243) | 10 | 4 | 2.6% of 156 |
| ROUTED regime=UNKNOWN | 0.99 | 599 | 40% (238) | 8 | 3 | 1.9% of 156 |
| regime=LITERARY | 0.90 | 561 | 50% (280) | 14 | 4 | 2.3% of 173 |
| regime=LITERARY | 0.95 | 561 | 49% (276) | 12 | 3 | 1.7% of 173 |
| regime=LITERARY | 0.98 | 561 | 46% (260) | 8 | 1 | 0.6% of 173 |
| regime=LITERARY | 0.99 | 561 | 44% (248) | 6 | 1 | 0.6% of 173 |
| regime=MEDICAL | 0.90 | 1548 | 33% (505) | 76 | 61 | 7.3% of 840 |
| regime=MEDICAL | 0.95 | 1548 | 31% (477) | 70 | 57 | 6.8% of 840 |
| regime=MEDICAL | 0.98 | 1548 | 27% (418) | 52 | 40 | 4.8% of 840 |
| regime=MEDICAL | 0.99 | 1548 | 23% (353) | 40 | 30 | 3.6% of 840 |
| regime=RECIPE_PRACTICE | 0.90 | 1921 | 12% (234) | 50 | 45 | 2.8% of 1596 |
| regime=RECIPE_PRACTICE | 0.95 | 1921 | 11% (213) | 38 | 33 | 2.1% of 1596 |
| regime=RECIPE_PRACTICE | 0.98 | 1921 | 9% (180) | 22 | 18 | 1.1% of 1596 |
| regime=RECIPE_PRACTICE | 0.99 | 1921 | 8% (152) | 15 | 13 | 0.8% of 1596 |
| regime=UNKNOWN | 0.90 | 608 | 46% (278) | 21 | 7 | 4.4% of 159 |
| regime=UNKNOWN | 0.95 | 608 | 44% (268) | 18 | 6 | 3.8% of 159 |
| regime=UNKNOWN | 0.98 | 608 | 40% (245) | 10 | 4 | 2.5% of 159 |
| regime=UNKNOWN | 0.99 | 608 | 39% (240) | 8 | 3 | 1.9% of 159 |
| work_seen=False | 0.90 | 1115 | 21% (229) | 46 | 35 | 4.6% of 767 |
| work_seen=False | 0.95 | 1115 | 19% (207) | 35 | 26 | 3.4% of 767 |
| work_seen=False | 0.98 | 1115 | 16% (177) | 24 | 17 | 2.2% of 767 |
| work_seen=False | 0.99 | 1115 | 14% (154) | 16 | 11 | 1.4% of 767 |
| work_seen=True | 0.90 | 3523 | 30% (1068) | 115 | 82 | 4.1% of 2001 |
| work_seen=True | 0.95 | 3523 | 29% (1027) | 103 | 73 | 3.6% of 2001 |
| work_seen=True | 0.98 | 3523 | 26% (926) | 68 | 46 | 2.3% of 2001 |
| work_seen=True | 0.99 | 3523 | 24% (839) | 53 | 36 | 1.8% of 2001 |
