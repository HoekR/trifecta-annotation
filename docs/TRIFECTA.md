# TRIFECTA architecture (summary)

The **full project plan** with milestones and data tables lives in [PLAN.md](../PLAN.md).

## Official guidelines

| Document | Path |
|----------|------|
| English | `docs/Annotation_Guidelines_final.pdf` (local copy; not in git) |
| Dutch | `docs/Annotation_Guidelines_NL.pdf` (local copy) |

See the full [documentation map](README.md).

## Snippet sources

Manual annotation uses **cort_voc_db** food snippets, not preservare KWIC. See [SNIPPETS.md](SNIPPETS.md).

## Pipeline

```text
KWIC window + target_word
        │
        ▼
  Step A — Entity validation + formal layer (FOOD_Unit, …)
        │  early exit: metaphor / non-food
        ▼
  Step B — Macro-frame enum
        │  COOKING_CREATION | CURE | INGESTION | PRESERVING | NONE
        ▼
  Step C — Frame-specific qualia roles
        ▼
  JSONL / parquet + provenance sidecar (data_io)
```

## Macro-frames

| Frame | Description |
|-------|-------------|
| `COOKING_CREATION` | Thermal / mechanical preparation |
| `CURE` | Medicinal treatment |
| `INGESTION` | Direct consumption |
| `PRESERVING` | Smoking, salting, pickling, drying |
| `NONE` | Metaphorical or irrelevant |

## Infrastructure

| | Local | HPC |
|---|-------|-----|
| Engine | Ollama | vLLM |
| Model | `qwen2.5-coder:32b-instruct` | FP16 |
| Structured output | instructor | instructor / outlines |

Env: `OLLAMA_BASE_URL`, `TRIFECTA_MODEL`.

## Corpus provenance

Every output record includes `corpus`, `date` (when known), `target_word`, `context_text`.  
17th–20th century sources share one schema; era stratification is for evaluation, not separate pipelines.

See also [DATA.md](DATA.md) and [GOLD_LABELLING.md](GOLD_LABELLING.md).
