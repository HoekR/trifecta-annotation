# T1b: passage-first triangulation (39 works) — v3d

Rows annotated: 4045 of 4045 (0 errors). Yield = share of rows with a real frame (CC/ING/CURE/PRES), Wilson 95% CI.

## 1. Yield per route, and frames the food route adds

| stratum           | verb-selected yield   | food-only yield   |   est. frames via verb route |   est. frames food-only |
|:------------------|:----------------------|:------------------|-----------------------------:|------------------------:|
| MEDICAL           | 54% (49%–60%)         | 48% (42%–55%)     |                          981 |                    2585 |
| RECIPE            | 84% (80%–88%)         | 94% (90%–97%)     |                         3891 |                   11827 |
| drama             | 77% (50%–92%)         | 8% (5%–13%)       |                           10 |                      93 |
| jeugdliteratuur   | 69% (42%–87%)         | 27% (21%–34%)     |                            9 |                     112 |
| non-fictie        | 47% (39%–55%)         | 6% (4%–11%)       |                           74 |                     518 |
| poëzie            | 59% (48%–68%)         | 16% (12%–22%)     |                           55 |                     408 |
| proza             | 73% (64%–80%)         | 18% (13%–23%)     |                           86 |                     582 |
| sec - letterkunde | 70% (64%–76%)         | 42% (36%–49%)     |                          135 |                    1034 |
| sec - taalkunde   | 42% (29%–55%)         | 13% (9%–18%)      |                           22 |                     211 |

Totals: est. frames via verb route ≈ 5263, food-only ≈ 17370 (weighted; precision unverified until `read_food_only_frames.csv` is read).

## 2. Context centring: same occurrence, noun-centred vs verb-centred

Pairs: 1004; same label: 82% (79%–84%).

| label            |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |   PRESERVING |
|:-----------------|-------------------:|-------:|----------:|------------:|-------:|-------------:|
| COOKING_CREATION |                332 |     14 |         3 |          16 |     11 |            7 |
| CURE             |                 25 |     83 |         6 |           2 |      8 |            1 |
| DROPPED          |                  9 |     12 |       226 |           2 |      7 |            0 |
| INGESTION        |                 13 |      3 |         2 |          96 |     10 |            0 |
| NONE             |                  7 |      5 |         6 |           4 |     79 |            2 |
| PRESERVING       |                  5 |      2 |         0 |           0 |      1 |            5 |

## 3. Frame mix per set

| set       |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |   PRESERVING |
|:----------|-------------------:|-------:|----------:|------------:|-------:|-------------:|
| food_only |                319 |     91 |       990 |         123 |    263 |           14 |
| verb_noun |                477 |    167 |       316 |         145 |    118 |           18 |
| verb_verb |                391 |    119 |       243 |         120 |    116 |           15 |

## 4. To read

- `read_food_only_frames.csv`: 100 random food-only frames; fill in `rik_correct` (gate G3 input).
- `read_centring_disagreements.csv`: 183 rows; fill in `rik_which` (noun / verb / neither).
