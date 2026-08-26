# TRIFECTA label mapping (English WebAnno ↔ Dutch pipeline)

Shared vocabulary between INCEpTION/WebAnno exports (English colleagues) and the
`trifecta-annotation` JSON/CSV schema (Dutch KWIC pipeline).

## Macro-frames (Step B)

| Canonical JSON | WebAnno prefix | Legacy Dutch name |
|----------------|----------------|-------------------|
| `COOKING_CREATION` | `COOKING_CREATION_*` | (unchanged) |
| `CURE` | `CURE_*` | `USING_CURE` |
| `INGESTION` | `INGESTION_*` / `INGR_*` | `USING_INGESTION` |
| `PRESERVING` | `PR_*` | (unchanged) |
| `NONE` | (no frame LU) | (unchanged) |

`lexical_unit` in JSON ↔ `*_LU` span on the trigger token in WebAnno.

## Step A — entity / formal layer

| JSON field | WebAnno span | Notes |
|------------|--------------|-------|
| `is_food_entity=true` | `FOOD_LU` on target | |
| `formal_dimension=FOOD_Unit` | `FOOD_Unit` | |
| `formal_dimension=FOOD_Constituent_Part` | `FOOD_Constituent_Part` | |
| `formal_dimension=FOOD_Descriptor` | `FOOD_Descriptor` | |
| `formal_dimension=FOOD_Whole` | — | NL extension; map to nearest EN label in export |
| `is_metaphor=true` | `MET_expression` / `MET_Food_LU` | |
| `canonical_pref_label` | — | Dutch thesaurus only |

## Step C — qualia roles

### CURE

| JSON field | WebAnno |
|------------|---------|
| `CURE_Affliction` | `CURE_Affliction` |
| `CURE_Food_Treatment` | `CURE_Food_Treatment` |
| `lexical_unit` | `CURE_LU` |

### COOKING_CREATION

| JSON field | WebAnno |
|------------|---------|
| `COOKING_CREATION_Method` | (extension; related to recipe steps) |
| `COOKING_CREATION_Process` | (extension) |
| `COOKING_CREATION_Food_Product` | `COOKING_CREATION_Food_Product` / `Produced_Food` |
| `lexical_unit` | `COOKING_CREATION_LU` |

Also in WebAnno: `COOKING_CREATION_Food_Material`, `COOKING_CREATION_Cook`.

### INGESTION

| JSON field | WebAnno |
|------------|---------|
| `INGESTION_Context` | (extension) |
| `INGESTION_Ingestor` | `INGESTION_Ingestor` |
| `INGESTION_Manner` | (extension) |
| `INGESTION_Food_Patient` | `INGR_Food_Product` / `INGR_Material_LU` |
| `INGESTION_Purpose` | (extension: occasion, toast, intent) |
| `lexical_unit` | `INGESTION_LU` |

Also in WebAnno: `INGR_Material_LU`, `INGR_Food_Product`.

### PRESERVING

| JSON field | WebAnno |
|------------|---------|
| `PR_Technique` | technique implied by `PR_LU` context |
| `PR_Medium` | `PR_Medium` |
| `PR_Food_Patient` | `PR_Food_Patient` |
| `lexical_unit` | `PR_LU` |

Also in WebAnno: `PR_Agent`.

## Representation difference (not merged)

| | English | Dutch |
|---|---------|-------|
| Tool | INCEpTION / WebAnno TSV | CSV + `trifecta-gold-ui` |
| Unit | Full document, token spans | KWIC snippet + `target_word` |
| Step C | Inline token roles | JSON `step_c` object (optional in gold CSV) |

Legacy JSON and CSV values (`USING_CURE`, `cure_affliction`, …) are still accepted on import.
