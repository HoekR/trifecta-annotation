# Spelling variation check: phonetic key and OCR/HTR confusions

Vocabulary of the 41 probe works: 179,910 types (≥ 3 letters), 4,690,549 tokens. Known verb paradigms: 146 lemmas, 1,866 generated forms.

| matched by | types | tokens |
|---|---|---|
| loose_key (LotA rules + squeezed doubles) | 1,081 | 155,571 |
| phonetic key, *additionally* | 410 | 29,796 |
| OCR/HTR confusion of a matched form, *additionally* | 238 | 112,156 |

Precision is unknown until read: `read_phonetic_matches.csv` (40 random) and `read_ocr_matches.csv` (40 most frequent). Confusions in the OCR sample:

|        |   types |
|:-------|--------:|
| l->t   |      46 |
| t->l   |      41 |
| i->l   |      36 |
| b->h   |      27 |
| c->e   |      17 |
| f->s   |      15 |
| n->u   |      14 |
| u->n   |      12 |
| h->b   |      10 |
| s->f   |       8 |
| cl->d  |       4 |
| ij->ii |       3 |

Most frequent phonetic additions:

god (2444) → goot, godt (2437) → goot, zouden (2031) → zouten, zoude (2013) → zoutte, vast (1873) → wast, toen (1680) → doen, hout (1633) → houdt, ziet (1580) → ziedt, voet (1564) → voedt, soude (1069) → zoutte, voeten (1007) → voeden, vallen (868) → wallen, siet (815) → ziedt, valt (626) → walt, lieden (611) → lieten, souden (590) → zouten, lid (544) → liet, zitten (395) → zieden, stoffen (375) → stoven, vvas (290) → was, zit (274) → ziedt, val (212) → wal, soud (210) → sout, houten (175) → houden, visch (166) → wiesch, zeden (161) → zetten, goden (154) → goten, zoudt (152) → sout, eed (151) → eet, lied (130) → liet

Most frequent OCR additions:

het (86766) → hel [t->l], wat (10742) → wal [t->l], tegen (4375) → legen [t->l], geest (1603) → geeft [s->f], heet (1088) → heel [t->l], etc (592) → ete [c->e], genen (588) → geuen [n->u], geel (528) → geet [l->t], maat (421) → maal [t->l], doel (392) → doet [l->t], haat (300) → haal [t->l], beelden (251) → heelden [b->h], maten (232) → malen [t->l], honden (228) → houden [n->u], hond (218) → houd [n->u], teghen (168) → leghen [t->l], haet (146) → hael [t->l], verbeeld (142) → verheeld [b->h], heeten (138) → heelen [t->l], gift (136) → gist [f->s], heil (136) → hell [i->l], haten (125) → halen [t->l], haak (101) → baak [h->b], gesond (92) → gesoud [n->u], fout (88) → sout [f->s], fouten (85) → souten [f->s], verbeelden (84) → verheelden [b->h], beelt (84) → heelt [b->h], heide (71) → helde [i->l], lijck (70) → liick [ij->ii]
