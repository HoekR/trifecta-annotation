# TRIFECTA Annotatie Pipeline: Tussentijdse Analyse KWIC Batch

**Datum:** 28 augustus 2026  
**Model:** `qwen2.5-coder:latest` (Ollama, Apple Silicon M4)  
**Corpus:** `food_snippets_long_kwic.csv` (~107k regels)

---

## 1. Overzicht & Status

Deze tussenrapportage vat de voortgang en tussenresultaten samen van de grootschalige annotatierun op het historische KWIC-snippetcorpus.

- **Totaal verwerkte records op peilmoment:** 9.148 records
- **Executie-architectuur:** 3-traps LLM-pipeline (Stap A $\rightarrow$ Stap B $\rightarrow$ Stap C) met gestructureerde Pydantic/instructor schema's via Ollama (100% GPU Metal-offload op Apple Silicon M4).
- **Vroegtijdige uitval (Dropout):** 2.995 records (32,7%) zijn direct bij Stap A afgevallen, waardoor duizenden zware Stap B/C aanroepen zijn bespaard.

---

## 2. Stap A: Entiteit- & Metafoorfilter (Dropout)

Stap A valideert of de doelterm in de historische context daadwerkelijk naar een voedingsentiteit verwijst en sluit metaforisch of oneigenlijk taalgebruik direct uit.

| Stap A Oordeel | Aantal | Percentage | Toelichting |
|:---|---:|---:|:---|
| `FOOD` (Bevestigd) | 6.153 | 67,3% | Voedselcontext bevestigd; doorgestroomd naar Stap B & C. |
| `DROPOUT` (Uitval) | 2.995 | 32,7\% | Geen voedselcontext, homoniem of metaforisch gebruik; vroege exit. |
| **Totaal** | **9.148** | **100,0%** | |

---

## 3. Stap B: Macro-Frame Distributie

Records die Stap A passeren worden in Stap B geclassificeerd in macro-frames:

| Macro-Frame | Aantal | Aandeel | Karakteristiek / Typische Context |
|:---|---:|---:|:---|
| `COOKING_CREATION` | 3.092 | 33,8% | Recepten, kookbereidingen, culinaire handelingen |
| `NONE` / `DROPOUT` | 2.995 | 32,7% | Uitval via Stap A of niet-culinair domein |
| `UNSPECIFIED` | 1.217 | 13,3% | Voedselentiteit aanwezig zonder expliciete culinaire actie |
| `CURE` | 852 | 9,3% | Dieet- en medicinale receptuur, huismiddelen, remedies |
| `INGESTION` | 787 | 8,6% | Consumptie, eten, drinken, maaltijdsituaties |
| `PRESERVING` | 205 | 2,2% | Inmaken, pekelen, drogen, conserveren |
| **Totaal** | **9.148** | **100,0%** | |

---

## 4. Stap C: Qualia Slot-Invulling

Voor de doelframes worden in Stap C frame-specifieke Qualia-rollen geëxtraheerd:

| Frame | Qualia Slot | Ingevulde Instanties |
|:---|:---|---:|
| **COOKING_CREATION** | `Method` (kookmethode / techniek) | 1.972 |
| | `Food_Product` (bereid eindproduct) | 1.788 |
| | `Process` (procesverloop) | 1.360 |
| **CURE** | `Food_Treatment` (behandeling / toediening) | 784 |
| | `Affliction` (kwaal, aandoening, doel) | 671 |
| **INGESTION** | `Manner` (wijze van consumptie) | 652 |
| | `Context` (maaltijd/setting) | 556 |
| | `Ingestor` (consument/persoon) | 489 |
| | `Food_Patient` (geconsumeerd item) | 384 |
| | `Purpose` (doel van consumptie) | 249 |
| **PRESERVING** | `PR_Food_Patient` (te conserveren waar) | 190 |
| | `PR_Technique` (conserveringstechniek) | 152 |
| | `PR_Medium` (inmaakmedium: azijn, pekel, suiker) | 72 |

---

## 5. Belangrijkste Inzichten & Aanbevelingen

1. **Hoge densiteit in `COOKING_CREATION` en `CURE`:** Zowel culinaire methoden als medicinale kwalen (`Affliction`) vertonen een zeer hoge slot-extractiegraad. Dit maakt de dataset direct bruikbaar voor diachrone analyses naar vroegmoderne geneeskundige voedingsrecepten vs. culinaire bereidingen.
2. **Doeltreffendheid van de Dropout-architectuur:** Met een uitvalpercentage van 32,7% bewijst de tweetraps filtering zijn waarde; 1 op de 3 records hoeft niet door de zware Qualia-prompting.
3. **Schaalstrategie:**
   - *Ontkoppelde Stap A filtering:* Voor nieuwe tranches eerst een bulk Stap A run draaien (`make step-a-bulk`).
   - *GijsBERT pre-filter:* Inzet van GijsBERT voor lokale high-throughput screening van `NONE`-gevallen.
   - *HPC Scaling (SURF):* Voor de volledige corpusverwerking ($>$100k snippets) opschalen naar dual NVIDIA A10 GPU's via `vLLM`.
