# Gold accuracy by position in the document

Gold rows from DBNL TEI works: 505. work not in zip: 55, located: 360, before first entry: 25, not located: 65. With a prediction (`gold_predictions`): 280.

Step B agreement = gold label == predicted label (frame, NONE or DROPPED). Wilson 95% intervals.

## By position of the target word

| position   |   n |   agree |   accuracy | 95% CI    |
|:-----------|----:|--------:|-----------:|:----------|
| body       | 232 |     117 |       0.5  | 0.44–0.57 |
| head       |   8 |       6 |       0.75 | 0.41–0.93 |
| near_head  |  40 |      13 |       0.33 | 0.20–0.48 |

## By whether the entry's head names a purpose (recipe/remedy cue)

| purpose_head    |   n |   agree |   accuracy | 95% CI    |
|:----------------|----:|--------:|-----------:|:----------|
|                 | 265 |     128 |       0.48 | 0.42–0.54 |
| MEDICAL         |  12 |       6 |       0.5  | 0.25–0.75 |
| RECIPE_PRACTICE |   3 |       2 |       0.67 | 0.21–0.94 |

## Purpose head × could the model see the head (head text inside the context)?

| purpose         | head_seen   |   n |   accuracy | 95% CI    |
|:----------------|:------------|----:|-----------:|:----------|
| no purpose head | False       | 191 |       0.51 | 0.44–0.58 |
| no purpose head | True        |  74 |       0.42 | 0.31–0.53 |
| purpose head    | False       |   8 |       0.5  | 0.22–0.78 |
| purpose head    | True        |   7 |       0.57 | 0.25–0.84 |

## Gold vs predicted labels where the head names a purpose and the model could not see it

| gold             |   COOKING_CREATION |   CURE |   DROPPED |
|:-----------------|-------------------:|-------:|----------:|
| COOKING_CREATION |                  1 |      0 |         0 |
| CURE             |                  0 |      2 |         1 |
| DROPPED          |                  0 |      2 |         1 |
| PRESERVING       |                  1 |      0 |         0 |

## Broader head reading: the frame the head implies (`HEAD_FRAME`)

Does the production cue (`regime_from_tei_scope_head`) see these heads? Rows per implied frame, and how many of them the production cue flags:

| head_frame       |   n |   flagged by production cue |
|:-----------------|----:|----------------------------:|
| (none)           | 223 |                           1 |
| COOKING_CREATION |  33 |                           0 |
| CURE             |  16 |                          12 |
| PRESERVING       |   8 |                           2 |

Agreement by implied head frame × head visible to the model:

| head_frame       | head_seen   |   n |   agree |   accuracy | 95% CI    |
|:-----------------|:------------|----:|--------:|-----------:|:----------|
|                  | False       | 170 |      84 |       0.49 | 0.42–0.57 |
|                  | True        |  53 |      17 |       0.32 | 0.21–0.45 |
| COOKING_CREATION | False       |  15 |      10 |       0.67 | 0.42–0.85 |
| COOKING_CREATION | True        |  18 |      11 |       0.61 | 0.39–0.80 |
| CURE             | False       |  10 |       4 |       0.4  | 0.17–0.69 |
| CURE             | True        |   6 |       4 |       0.67 | 0.30–0.90 |
| PRESERVING       | False       |   4 |       3 |       0.75 | 0.30–0.95 |
| PRESERVING       | True        |   4 |       3 |       0.75 | 0.30–0.95 |

## Where the head implies a frame: is gold that frame, and does the model get it?

|   n |   gold = head frame |   pred = head frame | pred = head frame, head NOT visible   | pred = head frame, head visible   |
|----:|--------------------:|--------------------:|:--------------------------------------|:----------------------------------|
|  31 |                  31 |                  26 | 11 of 13                              | 15 of 18                          |

(Only rows whose gold equals the head's implied frame, i.e. where the head was right.)

## Rows where gold has a real frame (not NONE / DROPPED)

|   rows |   accuracy | 95% CI    |
|-------:|-----------:|:----------|
|    165 |       0.53 | 0.46–0.61 |

## Confusion (all rows with a prediction)

| gold             |   COOKING_CREATION |   CURE |   DROPPED |   INGESTION |   NONE |   PRESERVING |
|:-----------------|-------------------:|-------:|----------:|------------:|-------:|-------------:|
| COOKING_CREATION |                 36 |      3 |         4 |           1 |      9 |            1 |
| CURE             |                  9 |     24 |         3 |           1 |      7 |            0 |
| DROPPED          |                 18 |      6 |        35 |           7 |     24 |            0 |
| INGESTION        |                  6 |      1 |         1 |          23 |     22 |            0 |
| NONE             |                  4 |      3 |         1 |           3 |     13 |            1 |
| PRESERVING       |                  4 |      1 |         0 |           0 |      4 |            5 |

## By work

| work                 |   n |   agree |   accuracy | 95% CI    |
|:---------------------|----:|--------:|-----------:|:----------|
| _den001denk09_01.xml |   2 |       1 |       0.5  | 0.09–0.91 |
| _jaa002187401_01.xml |   1 |       1 |       1    | 0.21–1.00 |
| _jaa033187301_01.xml |   2 |       2 |       1    | 0.34–1.00 |
| _kod003kodd02_01.xml |   3 |       1 |       0.33 | 0.06–0.79 |
| _lee024leeu02_01.xml |   6 |       4 |       0.67 | 0.30–0.90 |
| _nie148nieu01_01.xml |   5 |       3 |       0.6  | 0.23–0.88 |
| _pha001phar02_01.xml |   6 |       0 |       0    | 0.00–0.39 |
| _pha001phar05_01.xml |  12 |       6 |       0.5  | 0.25–0.75 |
| _tij008186501_01.xml |   8 |       4 |       0.5  | 0.22–0.78 |
| _vad003180901_01.xml |   5 |       5 |       1    | 0.57–1.00 |
| _vad003182101_01.xml |   3 |       2 |       0.67 | 0.21–0.94 |
| _vad003182701_01.xml |   2 |       2 |       1    | 0.34–1.00 |
| _vad003183301_01.xml |   3 |       2 |       0.67 | 0.21–0.94 |
| _vad003183401_01.xml |   6 |       3 |       0.5  | 0.19–0.81 |
| _vad003183901_01.xml |   2 |       0 |       0    | 0.00–0.66 |
| _vad003184101_01.xml |   4 |       2 |       0.5  | 0.15–0.85 |
| _vad003185501_01.xml |   1 |       0 |       0    | 0.00–0.79 |
| _vad003185901_01.xml |   4 |       1 |       0.25 | 0.05–0.70 |
| _vol002volm01_01.xml |  21 |      13 |       0.62 | 0.41–0.79 |
| alke003nede01_01.xml |   1 |       0 |       0    | 0.00–0.79 |
| bate002secr02_01.xml |   7 |       3 |       0.43 | 0.16–0.75 |
| bont009gebr01_01.xml |   3 |       0 |       0    | 0.00–0.56 |
| bure003magd01_01.xml |   2 |       2 |       1    | 0.34–1.00 |
| cats001houw01_01.xml |   4 |       3 |       0.75 | 0.30–0.95 |
| chom003huis01_01.xml |  77 |      34 |       0.44 | 0.34–0.55 |
| eman001lang01_01.xml |   4 |       1 |       0.25 | 0.05–0.70 |
| fric007drie01_01.xml |   4 |       1 |       0.25 | 0.05–0.70 |
| gram004madj01_01.xml |   1 |       0 |       0    | 0.00–0.79 |
| hein008denv01_01.xml |   7 |       2 |       0.29 | 0.08–0.64 |
| hond001dape02_01.xml |   4 |       0 |       0    | 0.00–0.49 |
| joos025kley01_01.xml |   4 |       2 |       0.5  | 0.15–0.85 |
| kapp006zesj01_01.xml |   7 |       2 |       0.29 | 0.08–0.64 |
| koer001bloe01_01.xml |   2 |       2 |       1    | 0.34–1.00 |
| magi007kooc02_01.xml |   7 |       7 |       1    | 0.65–1.00 |
| meer017tone02_01.xml |   5 |       3 |       0.6  | 0.23–0.88 |
| pica002naau05_01.xml |   4 |       3 |       0.75 | 0.30–0.95 |
| poir001dens01_01.xml |   1 |       1 |       1    | 0.21–1.00 |
| roch007natu01_01.xml |   8 |       3 |       0.38 | 0.14–0.69 |
| sche471verm01_01.xml |   2 |       1 |       0.5  | 0.09–0.91 |
| teen002nege01_01.xml |   4 |       2 |       0.5  | 0.15–0.85 |
| weye002ontl01_01.xml |   5 |       3 |       0.6  | 0.23–0.88 |
| wicq003jour01_01.xml |   3 |       0 |       0    | 0.00–0.56 |
| wits008noor02_01.xml |  14 |       7 |       0.5  | 0.27–0.73 |
| wolf016hist01_01.xml |   4 |       2 |       0.5  | 0.15–0.85 |
