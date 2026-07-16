# Trifecta Food History & Framenet — research strategy summary

*Coordination brief for colleagues on the **English** INCEpTION / WebAnno track, with enough Dutch context to align procedures and next steps. Canonical policy: [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md). Engineering status: [PLAN.md](../PLAN.md).*

---

## 1. What we are building

TRIFECTA annotates historic food-related text in **three steps** (same semantics in Dutch and English):


| Step  | Question                                                                 | Typical output                                                                   |
| ----- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| **A** | Is the target a **food entity** in context (or metaphor / out of scope)? | Keep or drop early                                                               |
| **B** | Which **macro-frame** surrounds the target?                              | `COOKING_CREATION` | `CURE` | `INGESTION` | `PRESERVING` | `NONE`                |
| **C** | Which **qualia roles** fill that frame?                                  | e.g. Method / Process / Food_Product; Technique / Medium; Affliction / Treatment |


Above the steps sits **Layer 0 —** `text_regime` (genre / discourse type): `RECIPE_PRACTICE`, `MEDICAL`, `TRAVEL`, `LITERARY`, `ADMIN_TRADE`, `SCIENTIFIC`, `UNKNOWN`. Regime is **not** the same as the Step B frame (a recipe snippet can still be CURE; a medical book can still be COOKING_CREATION). See [ANNOTATION_STRATEGY.md §2](ANNOTATION_STRATEGY.md#2-layered-annotation-model).

Field / WebAnno mapping: [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md).

---



## 2. How English differs from Dutch


|               | English track                           | Dutch track                                                                    |
| ------------- | --------------------------------------- | ------------------------------------------------------------------------------ |
| Tool          | INCEpTION / WebAnno                     | CSV + notebook gold lab                                                        |
| Unit          | Token spans on snippet lines            | KWIC + `target_word` + `record_id`                                             |
| Hand gold     | Parallel `en_gold` (**TBD**)            | `gold.parquet` (~**187** rows; ~**27** with Step C)                            |
| Silver        | WebAnno exports → `inception_*`         | LLM `trifecta-batch` + INCEpTION import (~2.7k Step C silver, **unvalidated**) |
| Current focus | Align schema, sampling, eval with Dutch | **Step 5 / m10** — COOKING_CREATION qualia for analysis                        |


**Do not merge** EN and NL gold by snippet text — there is **no shared** `record_id`. Dutch INCEpTION imports are a **silver** view (snippet lines + cort_voc metadata), not hand gold.

---



## 3. Procedure (Dutch track — what “doing TRIFECTA” looks like)

English tooling differs, but the **logical procedure** is what we want to keep parallel.

### 3.1 Annotate a slice (A → B → C)

1. **Build inputs** — KWIC / snippet records with provenance (`corpus`, `date`, `target_word`, `context_text`, ideally `text_regime`).
2. **Run or label Step A** — food entity? metaphor? early dropout when out of scope.
3. **Run or label Step B** — pick one macro-frame + a short lexical trigger (`lexical_unit`).
4. **Run or label Step C** — fill **only** the roles for that frame; leave empty when not stated in the snippet.
5. **Keep provenance** on every row — era/corpus are fields, not separate pipelines.

Automated Dutch path: `trifecta-batch` (LLM + structured Pydantic outputs). Hand path: gold CSV / notebook lab.

### 3.2 Grow hand gold (quota batches)

Dutch Step 5 runbook ([GOLD_LABELLING.md](GOLD_LABELLING.md#step-5-runbook--cooking_creation-qualia-m10)):

1. **Export a bounded batch** — e.g. clear-frame miner → ~30 `COOKING_CREATION` candidates (`export_clear_frame_examples.py`).
2. **Hand-label** in the notebook lab (`cooking_stepc_gold_lab`) — snippet-first; Step A/B + COOKING Step C fields; mark `labelled=true`.
3. **Merge → import** → `gold_labelling_all.csv` → `gold.parquet` / `gold.jsonl`.
4. **Sampling discipline** (policy): cap per lemma; sample by regime × phenomenon; no new core gold with `UNKNOWN` regime; disagreement CSVs for adjudication only (not auto-relabel).



### 3.3 Evaluate and calibrate

1. Rebuild gold eval inputs → `trifecta-batch` on the gold slice → `gold_predictions.jsonl`.
2. `trifecta-eval` — Step A/B (report **per** `text_regime` first) + Step C:
  - **Exact** normalized string match (strict).
  - **Soft** containment (pred may be longer than gold if one string contains the other).
3. **Review** gold vs pred (`step_c_review` notebook / CSV) → pick few-shot exemplars → wire into Step C prompts → re-batch gold only.
4. **Analysis export** — flatten batch JSONL → parquet (`trifecta_analysis`) with an explicit **uncertainty** note: Step C is an LLM hypothesis unless the row is hand gold.



### 3.4 What English can mirror without sharing IDs


| Dutch artefact              | English analogue                                                               |
| --------------------------- | ------------------------------------------------------------------------------ |
| KWIC `record_id`            | Stable WebAnno / document+span id                                              |
| Gold CSV columns            | Same Step A/B/C semantics via [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) |
| Quota batch (~30 per frame) | Genre × frame pilot export from INCEpTION                                      |
| `trifecta-eval` per regime  | Same reporting rule once `en_gold` exists                                      |
| Soft Step C metric          | Useful for free-text qualia in both languages                                  |


---



## 4. State of affairs (16 Jul 2026)



### 4.1 Settled (Dutch)


| Item                                | Status                                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| Full LLM pipeline A→B→C             | Production-ready (`trifecta-annotate` / `trifecta-batch`)                                         |
| Step B frozen baseline              | **75%** on curated **157**-row gold (qwen2.5-coder:latest)                                        |
| Expanded gold (after COOKING pilot) | **~187** rows; Step B on this mix ~**59%** (not comparable to the frozen 157)                     |
| Hand Step C (COOKING pilot)         | **~27** rows with qualia in gold                                                                  |
| Step C metrics                      | Exact + soft in `eval/report.md`                                                                  |
| COOKING Step C few-shots            | Wired; gold re-batched                                                                            |
| Analysis parquet                    | `resolve("trifecta_analysis")` — exploratory use only                                             |
| GijsBERT (Step B classifier)        | Trained (~62% pooled dev; strong NONE); **not** replacing qwen for Step C; hybrid wiring deferred |




### 4.2 Step C numbers (honest)

On ~27 gold Step C rows after COOKING few-shots (soft / exact):


| Metric               | Exact | Soft (containment) |
| -------------------- | ----- | ------------------ |
| Joint (all fields)   | ~4%   | ~11%               |
| Micro (field tokens) | ~18%  | ~22%               |
| COOKING micro        | ~10%  | ~15%               |


Interpretation: longer LLM predictions often feel right to annotators but fail exact match; soft helps only a little. **Do not** treat Step C aggregates as analytic claims yet.

### 4.3 Usable vs not


| Use                                                                | OK?                                                        |
| ------------------------------------------------------------------ | ---------------------------------------------------------- |
| Exploratory qualia on a KWIC / WebAnno slice (spot-check by frame) | **Yes** — label as LLM / silver hypotheses                 |
| Cheap NONE pre-filter (Dutch GijsBERT)                             | Ready offline; not wired into batch CLI                    |
| Counts, trends, cross-era claims from Step C                       | **Not yet** — need more hand gold + better field agreement |
| Merging EN↔NL gold rows                                            | **No** — no shared ids                                     |




### 4.4 English track

Parallel `en_gold`, shared eval loop, and a first quota batch are still **open** (see §6). Schema and frames are already shared.

---



## 5. Future actions



### 5.1 Dutch (near term)

1. **More Step C hand gold** — extend beyond COOKING (PRESERVING / INGESTION / CURE quotas) with the same export → lab → merge loop.
2. **Prompt calibration** — more frame-specific few-shots; optional softer gold style (allow longer spans) or further soft metrics if review shows systematic pred⊃gold.
3. **Analysis notebooks** — consume `trifecta_analysis` with regime filters; always surface `uncertainty_note`.
4. **Keep deferred** unless blocking: more NONE silver, GijsBERT hybrid batch wiring, collocation→GijsBERT export (blocked — see [COLLOCATION.md](COLLOCATION.md)).



### 5.2 English (proposed parallel)

1. **Confirm regime list** for English corpora (keep six-way or adapt).
2. **Decide first pilot** — Step B–only gold vs a COOKING-like Step C quota (~30) mirroring Dutch Step 5.
3. **Export priority** — which genres / frames from WebAnno first.
4. **Stable ids + mapping** — document EN id scheme; keep [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) current.
5. **Eval reporting** — commit to **per-regime** Step B (then Step C); pooled F1 secondary; consider soft match for qualia.
6. **Uncertainty convention** — silver / LLM Step C = hypothesis until `en_gold` exists.



### 5.3 Joint

- Adjudicate **COOKING vs CURE** with the same snippet-level rule (preparation vs treatment) — see [ANNOTATION_STRATEGY.md §2.1](ANNOTATION_STRATEGY.md#21-cooking_creation-vs-cure-recipe--cure-frame).
- Coarse frames first? See ANNOTATION_STRATEGY §7 — optional staging before full qualia.

---



## 6. Questions for joint discussion

1. **Regime taxonomy** — Is the six-way `text_regime` list right for English corpora?
2. **Coarse frames first?** — Stage EN annotation before full Step C?
3. **English gold size & order** — Match Dutch stratification (regime × frame × phenomenon)? Start Step B–only or Step C pilot?
4. **WebAnno export priority** — Which genres / frames first?
5. **Evaluation** — Per regime primary; soft containment for free-text qualia?
6. **Uncertainty** — Shared wording that LLM / silver Step C is hypothesis-only until hand gold exists in that language?

---



## 7. References


| Document                                         | Content                                              |
| ------------------------------------------------ | ---------------------------------------------------- |
| [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) | **Canonical** gold, sampling, eval, track boundaries |
| [GOLD_LABELLING.md](GOLD_LABELLING.md)           | Dutch CSV / notebook lab + Step 5 runbook            |
| [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) | WebAnno ↔ TRIFECTA field mapping                     |
| [TRIFECTA.md](TRIFECTA.md)                       | Pipeline overview                                    |
| [PLAN.md](../PLAN.md)                            | Dutch engineering milestones / status                |
| [COLLOCATION.md](COLLOCATION.md)                 | Frame-verb / collocation track (separate)            |


---

*16 July 2026 — English coordination brief with Dutch procedure, status, and next actions for alignment.*