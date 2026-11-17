# T1b cost estimate (gate G2 / G2a)

Works: 95. Food-anchored occurrences: 36764; verb-selected: 7983 (21.7%). Verb-centred rows: 6412.

| stratum           |   works |   occurrences |   verb_selected |   verb_share |   occ_per_work_median |
|:------------------|--------:|--------------:|----------------:|-------------:|----------------------:|
| MEDICAL           |       9 |          6299 |            1772 |        0.281 |                 356   |
| RECIPE            |       4 |         16985 |            4614 |        0.272 |                4531.5 |
| drama             |      20 |          1465 |             172 |        0.117 |                  33.5 |
| jeugdliteratuur   |      20 |          1501 |             190 |        0.127 |                  52.5 |
| non-fictie        |      10 |          4090 |             428 |        0.105 |                 264   |
| poëzie            |      10 |          1354 |             151 |        0.112 |                 121.5 |
| proza             |       8 |          1601 |             188 |        0.117 |                 110   |
| sec - letterkunde |       6 |          1976 |             271 |        0.137 |                 238   |
| sec - taalkunde   |       8 |          1493 |             197 |        0.132 |                 141.5 |

Largest works (occurrences):

| source_path          |    n |
|:---------------------|-----:|
| _vol002volm01_01.xml | 7340 |
| bate002secr02_01.xml | 6020 |
| magi007kooc02_01.xml | 3043 |
| blan012kart01_01.xml | 2517 |
| zorg003bloe01_01.xml | 1984 |

Estimated LLM calls (5.28/row; Step A sieve saves ~43% outside RECIPE/MEDICAL, a rough figure since the sieve's saving was measured on verb rows):

- food-anchored: **~163,509**
- verb-centred: **~19,298**

G2a (power): passages with both anchors = 7983 (want ≥ ~100).
