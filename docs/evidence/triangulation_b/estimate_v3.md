# T1b cost estimate (gate G2 / G2a)

Works: 39. Food-anchored occurrences: 44372; verb-selected: 12249 (27.6%). Verb-centred rows: 10317.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       5 |          7134 |            2083 |        0.292 |                 575   |
| RECIPE            |       4 |         17196 |            4700 |        0.273 |                4598   |
| drama             |       3 |          1111 |             398 |        0.358 |                 177   |
| jeugdliteratuur   |       3 |           427 |             146 |        0.342 |                 124   |
| non-fictie        |       8 |          8122 |            1643 |        0.202 |                 714   |
| poëzie            |       6 |          2642 |             936 |        0.354 |                 364.5 |
| proza             |       5 |          3442 |            1114 |        0.324 |                 653   |
| sec - letterkunde |       2 |          2624 |             678 |        0.258 |                1312   |
| sec - taalkunde   |       3 |          1674 |             551 |        0.329 |                 472   |

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
- verb-centred: **~31,050**

G2a (power): passages with both anchors = 12249 (want ≥ ~100).
