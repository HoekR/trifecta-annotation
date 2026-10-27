# Semantic Scoping — Summary for English Track

## Core finding: frame boundaries track discourse structure, not just semantics

### 1. Frame overlap is real, not a classifier bug

PRESERVING is conceptually a subset of COOKING_CREATION; CURE genuinely overlaps
with COOKING_CREATION in household books. Three independent fix attempts (flat
few-shots, balanced few-shots, 2-stage hierarchical router) all failed on the
same confusion pair.

Corroborated independently: English INCEpTION annotators hit the same
PRESERVING/CURE → COOKING_CREATION entanglement by hand.

Caveat: COOKING_CREATION was never given positive annotation criteria (CURE/
PRESERVING were) — so this may be partly a scheme artifact, not pure
real-world overlap. The two explanations are not mutually exclusive.

### 2. Intention is often structural, not lexical — confirmed at scale

- **71.0%** of 3,326 Dutch recipes (`voc_recipes`) name their goal only in the
  title; the head word never recurs in the body (**74.4%** on the
  harder-to-parse half — not a coverage artifact).
- English: **45.9%** for recipe books (n=135 goals), **17.9%** for medical
  texts (n=39) — same gap, genre-driven, roughly half as severe as Dutch.
- Dutch: **69.1%** (`voc_recipes`) / **61.5%** (long-KWIC) — amplified by
  opaque Dutch culinary vocabulary (e.g. `blancmengier` names only the dish,
  never reappears) vs English (`CUCUMBER SOOP` recurs via "cucumber").
- Purest case: `Een ander.` ("another one for the same thing") — **218**
  instances, zero lexical content, intention inherited purely by position.

### 3. "Unit structure" isn't one thing — there are organizing axes

The axis decides which frame element is structurally free vs. local:

| Genre | What's free (header-governed) | What stays local |
|---|---|---|
| Recipe collections | goal/outcome | affliction is *not* local |
| Formulary | preparation | affliction (indication beside it; ±180-char window recovers it **58–73%** of the time) |
| Dictionary | nothing frame-relevant | — |

Consequence: the same frame (CURE) is tractable in one genre and not in
another, for reasons unrelated to language.

### 4. Genre labeling was broken and fixed

Title-keyword `text_regime` inference silently mis-tagged historical Dutch
(spelling variants, "chirurgijn" in a travel account → MEDICAL). Fixed with
explicit per-work overrides for all **61** corpus works. DBNL genre metadata
too coarse (cookbook = remedy book = "non-fictie"). Unit-structure density
tried as a classifier and rejected — dictionary scored highest density,
formulary scored 0.0.

## Open decision point

How to handle the COOKING_CREATION/PRESERVING/CURE overlap at Step B:

- **(a) Merge** the three into one coarse label.
- **(b) Defer the split** — classify coarse at Step B, derive the fine frame
  downstream from which Step C field actually grounds a span.
- **(c) Force a hard taxonomy split** — already tried 3x, likely to fail
  again given the overlap is in the source material, not just the model.

Leaning toward (b), not yet decided.
