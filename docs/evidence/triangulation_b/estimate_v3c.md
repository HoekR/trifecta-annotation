# T1b cost estimate (gate G2 / G2a)

Works: 39. Food-anchored occurrences: 44372; verb-selected: 7163 (16.1%). Verb-centred rows: 5618.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       5 |          7134 |            1885 |        0.264 |                 575   |
| RECIPE            |       4 |         17196 |            4580 |        0.266 |                4598   |
| drama             |       3 |          1111 |              13 |        0.012 |                 177   |
| jeugdliteratuur   |       3 |           427 |              15 |        0.035 |                 124   |
| non-fictie        |       8 |          8122 |             177 |        0.022 |                 714   |
| poëzie            |       6 |          2642 |              96 |        0.036 |                 364.5 |
| proza             |       5 |          3442 |             125 |        0.036 |                 653   |
| sec - letterkunde |       2 |          2624 |             211 |        0.08  |                1312   |
| sec - taalkunde   |       3 |          1674 |              61 |        0.036 |                 472   |

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
- verb-centred: **~16,908**

G2a (power): passages with both anchors = 7163 (want ≥ ~100).
