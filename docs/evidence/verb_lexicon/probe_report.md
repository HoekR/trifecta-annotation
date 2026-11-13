# V0 verb probe (GysBERT, in-context token embeddings)

Texts: 41 works (39 T1b + cookbooks). Seeds: 577 verb forms, 1167 non-verb forms (`probe_seeds.csv`). Training occurrences: 7511 verb, 7511 non-verb.

## Held-out evaluation (5-fold, grouped by lemma: the probe never saw the test verbs)

| subset         |     n |   accuracy | 95% CI    |
|:---------------|------:|-----------:|:----------|
| all            | 15022 |      0.908 | 0.90–0.91 |
| recipe         |  5377 |      0.927 | 0.92–0.93 |
| medical        |  1647 |      0.916 | 0.90–0.93 |
| other          |  7998 |      0.893 | 0.89–0.90 |
| verbs only     |  7511 |      0.885 | 0.88–0.89 |
| non-verbs only |  7511 |      0.931 | 0.92–0.94 |
| verbs, recipe  |  2229 |      0.893 | 0.88–0.90 |
| verbs, medical |   689 |      0.882 | 0.86–0.90 |
| verbs, other   |  4593 |      0.881 | 0.87–0.89 |

Gate (VERB_LEXICON.md V0): ≥ 0.9 overall and ≥ 0.85 per source type.

## Forms the held-out probe gets most wrong

| form      |   label |    p |   err |
|:----------|--------:|-----:|------:|
| bruynen   |       1 | 0    |  1    |
| peekel    |       1 | 0    |  1    |
| inmaakt   |       1 | 0    |  1    |
| zuyker    |       1 | 0    |  1    |
| suicker   |       1 | 0    |  1    |
| konfijt   |       1 | 0    |  1    |
| bruyn     |       1 | 0    |  1    |
| tempe     |       0 | 1    |  1    |
| bezien    |       0 | 1    |  1    |
| seef      |       1 | 0.01 |  0.99 |
| schyven   |       0 | 0.99 |  0.99 |
| zuikeren  |       1 | 0.01 |  0.99 |
| blik      |       1 | 0.02 |  0.98 |
| ghenooten |       1 | 0.02 |  0.98 |
| suur      |       1 | 0.02 |  0.98 |
| zeef      |       1 | 0.04 |  0.96 |
| seven     |       1 | 0.06 |  0.94 |
| prik      |       0 | 0.94 |  0.94 |
| verw      |       1 | 0.07 |  0.93 |
| zeven     |       1 | 0.08 |  0.92 |
| wallen    |       1 | 0.1  |  0.9  |
| spyzen    |       1 | 0.1  |  0.9  |
| zwel      |       1 | 0.1  |  0.9  |
| fruiten   |       0 | 0.89 |  0.89 |
| blick     |       1 | 0.12 |  0.88 |

## Candidate verdicts (`candidates_scored.csv`)

Verdict per form from its sampled occurrences: verb (≥ 80% verb readings), ambiguous (20–80%), not verb (< 20%).

| verdict                  |   forms |
|:-------------------------|--------:|
| verb                     |    1234 |
| not verb                 |     563 |
| ambiguous                |     423 |
| no occurrences in sample |     354 |

Not in the current lexicon, verdict verb, by silver frequency (top 40):

| form      | frame            |   silver_n |   gold_n |   n_occ |   verb_share |
|:----------|:-----------------|-----------:|---------:|--------:|-------------:|
| doet      | COOKING_CREATION |        280 |        7 |      24 |     0.958333 |
| maakt     | COOKING_CREATION |        167 |        1 |      24 |     0.958333 |
| doen      | COOKING_CREATION |        163 |        2 |      24 |     0.833333 |
| worden    | COOKING_CREATION |        150 |        0 |      24 |     0.833333 |
| geven     | COOKING_CREATION |        140 |       18 |      24 |     1        |
| kookt     | COOKING_CREATION |        138 |        0 |      24 |     1        |
| mengt     | COOKING_CREATION |        130 |        0 |      24 |     1        |
| gekookt   | COOKING_CREATION |        129 |       12 |      24 |     1        |
| eet       | INGESTION        |        105 |        0 |      24 |     0.958333 |
| geeft     | CURE             |         94 |        9 |      24 |     1        |
| geneest   | CURE             |         89 |        1 |      24 |     1        |
| mengen    | COOKING_CREATION |         86 |        2 |      24 |     0.958333 |
| gegeten   | INGESTION        |         80 |        0 |      24 |     1        |
| maaken    | COOKING_CREATION |         79 |        0 |      24 |     1        |
| gebraden  | COOKING_CREATION |         72 |        0 |      24 |     1        |
| gebruiken | CURE             |         65 |        1 |      24 |     1        |
| wordt     | COOKING_CREATION |         64 |        0 |      24 |     0.875    |
| gebakken  | COOKING_CREATION |         63 |        1 |      24 |     1        |
| gereed    | COOKING_CREATION |         57 |        0 |      24 |     0.916667 |
| gedronken | INGESTION        |         55 |        0 |      24 |     1        |
| kooken    | COOKING_CREATION |         55 |        0 |      24 |     1        |
| giet      | COOKING_CREATION |         54 |        1 |      24 |     1        |
| gemaakt   | COOKING_CREATION |         54 |        0 |      24 |     1        |
| nemen     | INGESTION        |         53 |        2 |      24 |     0.916667 |
| gesmolten | COOKING_CREATION |         53 |        0 |      24 |     1        |
| gemengt   | COOKING_CREATION |         52 |        0 |      24 |     1        |
| leggen    | COOKING_CREATION |         51 |        3 |      24 |     1        |
| bereid    | COOKING_CREATION |         50 |        1 |      24 |     1        |
| gemengd   | COOKING_CREATION |         49 |        0 |      24 |     0.958333 |
| dronk     | INGESTION        |         48 |        0 |      24 |     1        |
| drinkt    | INGESTION        |         48 |        0 |      24 |     1        |
| gebruikt  | CURE             |         46 |        4 |      24 |     1        |
| zetten    | COOKING_CREATION |         46 |        0 |      24 |     0.958333 |
| maak      | COOKING_CREATION |         44 |        0 |      24 |     0.875    |
| neemt     | COOKING_CREATION |         40 |       14 |      24 |     0.875    |
| legt      | COOKING_CREATION |         40 |        2 |      24 |     1        |
| gedaan    | COOKING_CREATION |         40 |        0 |      24 |     0.958333 |
| weeken    | COOKING_CREATION |         39 |        0 |      24 |     0.875    |
| brengen   | INGESTION        |         39 |        0 |      24 |     1        |
| werden    | COOKING_CREATION |         34 |        0 |      24 |     0.958333 |

In the current lexicon, verdict not verb:

| form          | frame            | generators                 |   n_occ |   verb_share |
|:--------------|:-----------------|:---------------------------|--------:|-------------:|
| groen         | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0.0416667 |
| stukken       | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0.125     |
| pillen        | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0.0416667 |
| glazen        | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0         |
| pinten        | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0.0416667 |
| eigen         | INGESTION        | lexicon_mined;mined;silver |      24 |    0         |
| oncen         | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0.0833333 |
| linzen        | INGESTION        | lexicon_mined;mined;silver |       6 |    0         |
| koeijen       | COOKING_CREATION | lexicon_mined;mined;silver |      21 |    0         |
| bollen        | INGESTION        | lexicon_mined;mined;silver |      17 |    0.117647  |
| conserven     | PRESERVING       | lexicon_mined;mined;silver |      21 |    0.0952381 |
| jeneverbeijen | COOKING_CREATION | lexicon_mined;mined;silver |       6 |    0         |
| beesten       | COOKING_CREATION | lexicon_mined;mined;silver |      24 |    0         |
| koejen        | INGESTION        | lexicon_mined;mined;silver |       6 |    0         |
| flesken       | COOKING_CREATION | lexicon_mined;mined;silver |       3 |    0         |
| allen         | CURE             | lexicon_mined;mined        |      24 |    0.166667  |
| overeen       | COOKING_CREATION | lexicon_mined;mined        |      24 |    0.125     |
| ponden        | COOKING_CREATION | lexicon_mined;mined        |      24 |    0.0833333 |
| hoemen        | COOKING_CREATION | lexicon_mined;mined        |      17 |    0         |
| datmen        | COOKING_CREATION | lexicon_mined;mined        |      24 |    0         |
| alsmen        | COOKING_CREATION | lexicon_mined;mined        |      24 |    0.0833333 |
| machmen       | PRESERVING       | lexicon_mined;mined        |      15 |    0         |
| frambozen     | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| cappoen       | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| moetmen       | COOKING_CREATION | lexicon_mined;mined        |      20 |    0         |
| pasteijen     | INGESTION        | lexicon_mined;mined        |       7 |    0.142857  |
| peulvruchten  | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| flesschen     | PRESERVING       | lexicon_mined;mined        |       7 |    0         |
| kannen        | INGESTION        | lexicon_mined;mined        |      24 |    0.0416667 |
| dobbelsteenen | COOKING_CREATION | lexicon_mined;mined        |       3 |    0         |
| granaten      | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| houtsnippen   | INGESTION        | lexicon_mined;mined        |       4 |    0         |
| kalfstongen   | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| okkerneuten   | INGESTION        | lexicon_mined;mined        |       4 |    0         |
| oraignen      | PRESERVING       | lexicon_mined;mined        |       4 |    0         |
| ouwbakken     | COOKING_CREATION | lexicon_mined;mined        |       6 |    0.166667  |
| razijnen      | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| sausyzen      | COOKING_CREATION | lexicon_mined;mined        |       5 |    0         |
| watermeloenen | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| wijbesien     | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| vaten         | COOKING_CREATION | lexicon_mined;mined        |      24 |    0.125     |
| bananen       | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| neuten        | COOKING_CREATION | lexicon_mined;mined        |       7 |    0         |
| vleesnatten   | COOKING_CREATION | lexicon_mined;mined        |       6 |    0.166667  |
| zwynen        | INGESTION        | lexicon_mined;mined        |       9 |    0         |
| aardbeijen    | COOKING_CREATION | lexicon_mined;mined        |       7 |    0         |
| aardbessen    | COOKING_CREATION | lexicon_mined;mined        |       3 |    0         |
| aelbessen     | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| afrikozen     | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| ananassen     | PRESERVING       | lexicon_mined;mined        |       4 |    0         |
| aragnien      | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| bargamotten   | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| boomvruchten  | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| castagnen     | COOKING_CREATION | lexicon_mined;mined        |       4 |    0         |
| drogeryen     | COOKING_CREATION | lexicon_mined;mined        |       6 |    0.166667  |
| erwetten      | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| eyerdoiren    | COOKING_CREATION | lexicon_mined;mined        |       4 |    0         |
| eyerkoeken    | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| faizanten     | PRESERVING       | lexicon_mined;mined        |       6 |    0         |
| galnoten      | PRESERVING       | lexicon_mined;mined        |      15 |    0         |
| granen        | COOKING_CREATION | lexicon_mined;mined        |      11 |    0.181818  |
| hespen        | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| jopen         | INGESTION        | lexicon_mined;mined        |       2 |    0         |
| kalfsnatten   | INGESTION        | lexicon_mined;mined        |       1 |    0         |
| ketelken      | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| kruijsbeijen  | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| kweepitten    | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| lapken        | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| leeuwerken    | INGESTION        | lexicon_mined;mined        |       7 |    0         |
| letterkoeken  | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| lijsbetten    | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| lupynen       | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| moscaten      | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| passourellen  | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| pasteikorsten | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| pruimellen    | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| saliebladen   | COOKING_CREATION | lexicon_mined;mined        |       1 |    0         |
| sapgroen      | COOKING_CREATION | lexicon_mined;mined        |       2 |    0         |
| slakken       | COOKING_CREATION | lexicon_mined;mined        |       7 |    0         |
| soesen        | COOKING_CREATION | lexicon_mined;mined        |       3 |    0         |
| venesoen      | COOKING_CREATION | lexicon_mined;mined        |       7 |    0         |
| violetten     | COOKING_CREATION | lexicon_mined;mined        |      12 |    0.166667  |
| visdagen      | COOKING_CREATION | lexicon_mined;mined        |       7 |    0         |
| wegsmelten    | PRESERVING       | lexicon_mined;mined        |       1 |    0         |
| kóólen        | COOKING_CREATION | lexicon_mined;mined        |       6 |    0         |
| zurigheden    | COOKING_CREATION | lexicon_mined;mined        |       5 |    0         |
| doornbessen   | PRESERVING       | lexicon_mined;mined        |       6 |    0         |
| moerbesien    | PRESERVING       | lexicon_mined;mined        |      12 |    0         |
| pastelingen   | CURE             | lexicon_mined;mined        |       6 |    0         |
