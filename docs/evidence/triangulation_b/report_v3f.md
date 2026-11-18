# T1b: passage-first triangulation (93 works) — v3f

Rows annotated: 5841 of 5841 (0 errors). Yield = share of rows with a real frame (CC/ING/CURE/PRES), Wilson 95% CI.

## 1. Yield per route, and frames the food route adds

| stratum           | verb-selected yield   | food-only yield   |   est. frames via verb route |   est. frames food-only |
|:------------------|:----------------------|:------------------|-----------------------------:|------------------------:|
| MEDICAL           | 87% (82%–90%)         | 64% (57%–70%)     |                         1536 |                    2897 |
| RECIPE            | 84% (80%–88%)         | 91% (86%–94%)     |                         3891 |                   11258 |
| drama             | 48% (40%–55%)         | 32% (25%–38%)     |                           82 |                     407 |
| jeugdliteratuur   | 71% (64%–77%)         | 49% (42%–56%)     |                          135 |                     642 |
| non-fictie        | 53% (49%–58%)         | 44% (38%–51%)     |                          228 |                    1630 |
| poëzie            | 54% (46%–61%)         | 33% (27%–40%)     |                           81 |                     397 |
| proza             | 73% (66%–79%)         | 46% (39%–52%)     |                          137 |                     643 |
| sec - letterkunde | 67% (61%–72%)         | 45% (38%–52%)     |                          182 |                     767 |
| sec - taalkunde   | 37% (30%–43%)         | 30% (24%–36%)     |                           72 |                     382 |

Totals: est. frames via verb route ≈ 6344, food-only ≈ 19023 (weighted; precision unverified until `read_food_only_frames.csv` is read).

## 2. Context centring: same occurrence, noun-centred vs verb-centred

Pairs: 1844; same label: 82% (81%–84%).

| label            |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |   PRESERVING |
|:-----------------|-------------------:|-------:|----------:|------------:|-------:|-------------:|
| COOKING_CREATION |                572 |     24 |         8 |          28 |     33 |            7 |
| CURE             |                 31 |    144 |        11 |           5 |     10 |            2 |
| DROPPED          |                 11 |      9 |       352 |           2 |     22 |            0 |
| INGESTION        |                 25 |      6 |         3 |         228 |     18 |            0 |
| NONE             |                 24 |      8 |        16 |          10 |    215 |            2 |
| PRESERVING       |                  6 |      2 |         0 |           0 |      0 |           10 |

## 3. Frame mix per set

| set       |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |   PRESERVING |
|:----------|-------------------:|-------:|----------:|------------:|-------:|-------------:|
| food_only |                536 |    112 |       522 |         207 |    412 |           11 |
| verb_noun |                833 |    247 |       451 |         324 |    316 |           26 |
| verb_verb |                669 |    193 |       390 |         273 |    298 |           21 |

## 4. To read

- `read_food_only_frames.csv`: 100 random food-only frames; fill in `rik_correct` (gate G3 input).
- `read_centring_disagreements.csv`: 323 rows; fill in `rik_which` (noun / verb / neither).
