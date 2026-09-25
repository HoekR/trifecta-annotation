The draft and your work share the same scientific story; the fit is **Dutch staged A→B→C + stage-wise eval** as the counterpart (or extension) to the paper’s English single-pass BIO + harmonization story.

## What the draft already claims

1. Food’s **non-nutritional uses** (CURE, PRESERVING) are the hard long-tail problem
2. **LLM silver → human gold** with correction rates by frame
3. CURE/PRESERVING need more correction than FOOD/COOKING
4. Then fine-tune sequence labelers for scale

Your numbers already echo (3): Step B F1 CURE **0.52** vs COOKING **0.84** / PRESERVING **0.86**; Step C soft micro CURE **20.8** vs INGESTION **45.5**. The draft’s Table 2 is the English twin of that finding.

## Where you plug in (especially “comparing stages”)

The draft treats annotation as one BIO pass. You have an explicit **cascade**. That is the natural ACL angle:


| Paper section        | Your material                                                                                    | Stage-comparison story                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| §3 Schema            | Same frames + roles (FOOD → COOKING / PRESERVING / CURE; you add **INGESTION**; paper has DESCR) | Same guideline family; Dutch as the Limitations “cross-lingual” case                                       |
| §4 LLM silver        | A→B→C with instructor/Pydantic; model compare (`compare_llm_models`)                             | Don’t only compare **models** — compare **stages**: A easy (91.7%), B mid (69%), C hard (30.3% soft micro) |
| §5 Harmonization     | Gold UIs + silver→gold correction                                                                | Correction rate **by stage and by frame** (not only by BIO layer)                                          |
| §6 Fine-tune / scale | GijsBERT Step B (~67%); Step C stays LLM; KWIC batch ~9k                                         | Staged specialization: classifier for B, LLM for C — vs one multitask tagger                               |
| Limitations          | Explicitly flags historical Dutch                                                                | You *are* that experiment                                                                                  |


**Comparing stages** = show error concentrates downstream:

- **A** filters ~1/3 of KWIC noise (dropout 32.7%) → cheap precision for "is this food?"  
- **B** gets macro-frame mostly right except long-tail CURE/INGESTION/NONE  
- **C** is where silver→gold pain lives (qualia boundaries, missing afflictions, etc.)

That reframes the paper’s headline (“LLMs struggle on CURE/PRESERVING”) as: **entity/frame detection is mostly solvable; use/role extraction is not** — which justifies both staging and fine-tuning.

## Concrete ACL packaging

1. **Shared claim** — Alternative food uses in historical text; CURE/PRESERVING hardest.
2. **Your contribution block** — Dutch KWIC corpus + **staged** silver pipeline + stage-wise gold metrics (308 gold / 93 with Step C).
3. **Table to add next to paper Table 1–2** — per-stage P/R/F1 (or accuracy) + correction rate by frame × stage.
4. **Optional contrast** — single-prompt BIO (paper) vs staged A→B→C (you): same guideline layers, different annotation protocol cost/error profile.
5. **Don’t force-fit yet** — MaChAmp Table 3 / lexicon baseline is their English track; your GijsBERT is the Dutch Step B analogue, not a full §6 replacement unless you train BIO on Dutch gold.



## Honest mismatch (keep as scope, not friction)

- **Language:** paper EN; you NL (good Limitations fill-in).  
- **Representation:** token BIO vs structured frame/qualia JSON.  
- **INGESTION** is yours; paper’s DESCR/FOOD_ATTRIBUTES are thinner in your pipeline (Step A formal layer only).  
- Paper still has empty LLM/F1 tables — your frozen eval can populate a **Dutch** column or a parallel “staged pipeline” subsection without waiting for their EN numbers.

**Bottom line:** Fit as *the staged, cross-lingual operationalization of the same schema*, with **stage comparison** as the main empirical contribution: show that the paper’s hard frames are hard *because Step C (uses/roles) fails*, not because food mention detection fails. That turns A→B→C from engineering into the result.