# T1b cost estimate (gate G2 / G2a)

Works: 39. Food-anchored occurrences: 44372; verb-selected: 1870 (4.2%). Verb-centred rows: 1567.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       5 |          7134 |             347 |        0.049 |                 575   |
| RECIPE            |       4 |         17196 |            1035 |        0.06  |                4598   |
| drama             |       3 |          1111 |              28 |        0.025 |                 177   |
| jeugdliteratuur   |       3 |           427 |              17 |        0.04  |                 124   |
| non-fictie        |       8 |          8122 |             141 |        0.017 |                 714   |
| poëzie            |       6 |          2642 |              61 |        0.023 |                 364.5 |
| proza             |       5 |          3442 |              79 |        0.023 |                 653   |
| sec - letterkunde |       2 |          2624 |             117 |        0.045 |                1312   |
| sec - taalkunde   |       3 |          1674 |              45 |        0.027 |                 472   |

Largest works (occurrences):

| source_path          |    n |
|:---------------------|-----:|
| _vol002volm01_01.xml | 7382 |
| bate002secr02_01.xml | 6125 |
| blan012kart01_01.xml | 4819 |
| quac001soci06_01.xml | 3635 |
| magi007kooc02_01.xml | 3071 |

Estimated LLM calls (5.28/row; Step A sieve saves ~43% outside RECIPE/MEDICAL, a rough figure since the sieve's saving was measured on verb rows):

- food-anchored: **~188,781**
- verb-centred: **~4,716**

G2a (power): passages with both anchors = 1870 (want ≥ ~100).
