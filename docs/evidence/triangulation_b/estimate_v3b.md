# T1b cost estimate (gate G2 / G2a)

Works: 39. Food-anchored occurrences: 44372; verb-selected: 8632 (19.5%). Verb-centred rows: 6936.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       5 |          7134 |            2036 |        0.285 |                 575   |
| RECIPE            |       4 |         17196 |            4694 |        0.273 |                4598   |
| drama             |       3 |          1111 |             105 |        0.095 |                 177   |
| jeugdliteratuur   |       3 |           427 |              52 |        0.122 |                 124   |
| non-fictie        |       8 |          8122 |             598 |        0.074 |                 714   |
| poëzie            |       6 |          2642 |             321 |        0.121 |                 364.5 |
| proza             |       5 |          3442 |             325 |        0.094 |                 653   |
| sec - letterkunde |       2 |          2624 |             321 |        0.122 |                1312   |
| sec - taalkunde   |       3 |          1674 |             180 |        0.108 |                 472   |

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
- verb-centred: **~20,875**

G2a (power): passages with both anchors = 8632 (want ≥ ~100).
