# Trifecta Food History & Framenet — English track brief

*For colleagues on the English INCEpTION / WebAnno track. **All gold policy, sampling, and eval rules:** [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md).*

---

## Shared schema

| Step | Question |
|------|----------|
| **A** | Food entity in context (or metaphor / out of scope)? |
| **B** | Macro-frame: COOKING_CREATION, CURE, INGESTION, PRESERVING, NONE? |
| **C** | Qualia roles (technique, patient, affliction, …)? |

Same frame vocabulary and Step semantics as Dutch. Field mapping: [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md).

---

## How English differs from Dutch

| | English track | Dutch track |
|---|---------------|-------------|
| Tool | INCEpTION / WebAnno | CSV + gold UI |
| Unit | Token spans on snippet lines | KWIC + `target_word` |
| Gold | Parallel `en_gold` (TBD) | `gold.parquet` (~123 rows, growing) |
| Silver today | WebAnno exports → `inception_*` on scratch | LLM batch + INCEpTION import |

**Do not merge** EN and NL gold by snippet — no shared `record_id`. Dutch INCEpTION import is a **snippet-line silver view** linked to cort_voc metadata, not hand gold.

---

## Questions for joint discussion

1. **Regime taxonomy** — Is the six-way `text_regime` list right for English corpora?
2. **Coarse frames first?** — See ANNOTATION_STRATEGY §7.
3. **English gold size** — Match Dutch stratification (regime × frame × phenomenon)?
4. **WebAnno export priority** — Which genres / frames first?
5. **Evaluation** — Report per regime; pooled F1 secondary only.

---

## References

| Document | Content |
|----------|---------|
| [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) | **Canonical** gold & eval guide |
| [GOLD_LABELLING.md](GOLD_LABELLING.md) | CSV / UI columns |
| [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) | WebAnno mapping |

---

*July 2026 — English coordination brief only.*
