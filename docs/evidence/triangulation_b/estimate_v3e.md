# T1b cost estimate (gate G2 / G2a)

Works: 39. Food-anchored occurrences: 26994; verb-selected: 6341 (23.5%). Verb-centred rows: 4980.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       5 |          4157 |            1086 |        0.261 |                 329   |
| RECIPE            |       4 |         16985 |            4614 |        0.272 |                4531.5 |
| drama             |       3 |           226 |              13 |        0.058 |                  97   |
| jeugdliteratuur   |       3 |           188 |              13 |        0.069 |                  49   |
| non-fictie        |       8 |          1671 |             158 |        0.095 |                 220   |
| poëzie            |       6 |           832 |              94 |        0.113 |                 104.5 |
| proza             |       5 |          1032 |             118 |        0.114 |                 100   |
| sec - letterkunde |       2 |          1394 |             192 |        0.138 |                 697   |
| sec - taalkunde   |       3 |           509 |              53 |        0.104 |                 130   |

Largest works (occurrences):

| source_path          |    n |
|:---------------------|-----:|
| _vol002volm01_01.xml | 7340 |
| bate002secr02_01.xml | 6020 |
| magi007kooc02_01.xml | 3043 |
| blan012kart01_01.xml | 2517 |
| herl001besc01_01.xml | 1070 |

Estimated LLM calls (5.28/row; Step A sieve saves ~43% outside RECIPE/MEDICAL, a rough figure since the sieve's saving was measured on verb rows):

- food-anchored: **~129,242**
- verb-centred: **~14,988**

G2a (power): passages with both anchors = 6341 (want ≥ ~100).
