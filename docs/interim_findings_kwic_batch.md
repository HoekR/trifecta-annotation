# TRIFECTA Annotation Pipeline: Interim KWIC Batch Analysis

**Date:** 28 August 2026  
**Model:** `qwen2.5-coder:latest` (Ollama, Apple Silicon M4)  
**Corpus:** `food_snippets_long_kwic.csv` (~107k candidate rows)

---

## 1. Overview & Status

This interim report summarizes progress and preliminary results from the large-scale batch annotation run on the historical Dutch KWIC snippet corpus.

- **Total records processed at benchmark:** 9,148 records
- **Execution Architecture:** 3-stage LLM pipeline (Step A $\rightarrow$ Step B $\rightarrow$ Step C) using structured Pydantic / instructor schemas via Ollama (100% GPU Metal-offload on Apple Silicon M4).
- **Early Dropout (Filtering):** 2,995 records (32.7%) dropped out at Step A, saving thousands of computationally heavy Step B and Step C inferences.

---

## 2. Step A: Entity & Metaphor Filtering (Dropout)

Step A validates whether the target term in its historical context refers to an actual culinary/food entity and filters out metaphorical or homonymous usages before deeper frame parsing.

| Step A Verdict | Count | Share | Description |
|:---|---:|---:|:---|
| `FOOD` (Confirmed) | 6,153 | 67.3% | Food context confirmed; forwarded to Step B & C parsing. |
| `DROPOUT` (Excluded) | 2,995 | 32.7% | Non-food context, homonym, or metaphor; early exit. |
| **Total** | **9,148** | **100.0%** | |

---

## 3. Step B: Macro-Frame Distribution

Records that pass Step A are classified into macro-frames in Step B:

| Macro-Frame | Count | Share | Typical Context & Characteristics |
|:---|---:|---:|:---|
| `COOKING_CREATION` | 3,092 | 33.8% | Recipes, culinary preparations, cooking actions |
| `NONE` / `DROPOUT` | 2,995 | 32.7% | Step A dropout or out-of-scope non-food domains |
| `UNSPECIFIED` | 1,217 | 13.3% | Food entity present without a specific action/frame |
| `CURE` | 852 | 9.3% | Dietary & medicinal remedies, herbal cures, health treatments |
| `INGESTION` | 787 | 8.6% | Consumption, eating, drinking, meal contexts |
| `PRESERVING` | 205 | 2.2% | Pickling, salting, drying, preserving foods |
| **Total** | **9,148** | **100.0%** | |

---

## 4. Step C: Qualia Slot Extraction

For the target frames, Step C extracts frame-specific qualia roles:

| Frame | Qualia Slot | Populated Instances |
|:---|:---|---:|
| **COOKING_CREATION** | `Method` (cooking technique/method) | 1,972 |
| | `Food_Product` (resulting food product) | 1,788 |
| | `Process` (ongoing process/state) | 1,360 |
| **CURE** | `Food_Treatment` (application/preparation) | 784 |
| | `Affliction` (disease, symptom, target ailment) | 671 |
| **INGESTION** | `Manner` (manner of consumption) | 652 |
| | `Context` (social/meal setting) | 556 |
| | `Ingestor` (consumer/person) | 489 |
| | `Food_Patient` (item consumed) | 384 |
| | `Purpose` (purpose of eating/drinking) | 249 |
| **PRESERVING** | `PR_Food_Patient` (preserved commodity) | 190 |
| | `PR_Technique` (preservation method) | 152 |
| | `PR_Medium` (medium: vinegar, brine, sugar) | 72 |

---

## 5. Key Insights & Scaling Recommendations

1. **High Slot Density in `COOKING_CREATION` and `CURE`:** Both culinary methods and medicinal ailments (`Affliction`) show very high extraction rates. This enables direct diachronic comparisons between early modern medical food remedies and culinary practices.
2. **Effectiveness of Early Dropout:** The 32.7% dropout rate validates the staged pipeline design; 1 in 3 records is filtered early without invoking heavy Step C qualia prompts.
3. **Scaling Roadmap:**
   - *Decoupled Step A Filtering:* Run lightweight Step A in bulk across new tranches (`make step-a-bulk`).
   - *Local SLM / GijsBERT Pre-filter:* Use fine-tuned GijsBERT locally for high-throughput `NONE` classification.
   - *HPC Scaling (SURF):* Scale the full corpus (>100k snippets) to dual NVIDIA A10 GPUs via `vLLM` with tensor parallelism and continuous batching.
