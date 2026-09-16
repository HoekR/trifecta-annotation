# Decision Log

Record durable methodological and architectural decisions here. Keep entries short enough to scan.

## Template

### YYYY-MM-DD: Decision title

- **Context:** What changed or what result forced a choice?
- **Decision:** What did we decide?
- **Reason:** Why is this the right tradeoff now?

---

### 2026-09-16: Embedding hybrid candidates (not pure KWIC, not LU-free)

- **Context:** KWIC thesaurus matching feeds the batch pool but yields ~33% Step A dropout (homographs, travel/catalog, false hits). Dissatisfaction with lexical-only discovery.
- **Decision:** Pilot **embedding retrieval + thesaurus LU anchor** → still emit `KwicInput` with `target_word`. Keep A→B→C LLM path; do not replace Step C with embeddings; do not drop the lexical unit for FrameNet/qualia claims. Embedder for pilot: mean-pooled `emanjavacas/gysbert`. Gate on 500 vs 500 comparison before scaling index or rewiring batch.
- **Reason:** Research object remains lemma-in-frame; embeddings fix *candidate quality/recall*, not annotation schemas. Reuse GysBERT already in the stack before adding a dedicated retrieval model.
- **Guide:** [plans/steps/EMBEDDING_CANDIDATES.md](../plans/steps/EMBEDDING_CANDIDATES.md)
