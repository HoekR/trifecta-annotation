# Does the entry heading resolve COOKING_CREATION / PRESERVING / CURE confusion? A handful test

*16 Nov 2026. Read-only, no model run. Source: `docs/evidence/gold_by_position/rows.csv` (gold rows from DBNL TEI works, located in their entry; the head is `scope_head`, and `head_seen` says whether the head text was inside the context the model got). Classification of heads by hand (Claude), one pass; not yet checked by Rik.*

## Question and decision rule (set before reading)

Prediction from the step-back review: if the three-way distinction lives at entry level, the heading should resolve most three-frame confusions.
- **If** most confusions have an informative, findable heading the model did not see → run the T3 prototype (Step B with the heading as context).
- **Otherwise** → the heading is not the missing piece; do not run it, and look at what all attempts shared.

## Cases

All located gold rows with a prediction where gold and prediction are both in {COOKING_CREATION, PRESERVING, CURE} and differ: **18**.

| what the heading does for the case | n | rows (work: head → gold / pred) |
|---|---:|---|
| informative, **already in the context**, model still wrong | **5** | vol002 "Ganzen, hoe men die voor de winter zal inzouten" → PRES / COOK; lee024 "Unguentum odoriserum. Welruikende Salf" → CURE / COOK; pha05 "Syrupus succi Betonicae" → CURE / COOK; chom "Van een gezwollen Tong" → CURE / COOK; chom "Inwendig Bewaarmiddel tegen de Pest" → CURE / COOK |
| informative, not seen, findable | **2** | pha02 "Confituren" → PRES / COOK (regex misses it); chom "Andere hartsterkende Drank, of Julep" → CURE / COOK |
| informative only through genre knowledge (Latin pharmacy name) | **3** | pha05 "Syrupus absinthii Compositus", "Gepraepareerd Staal", "Hiera Diacolocynthidos" → CURE / COOK |
| uninformative or misleading | **4** | pha02 "Trochisci Hedychroi… voor de Theriakel" → PRES / COOK; chom "Destillatie van Rogge…" → PRES / CURE; chom "Geheim tegen de Weegluis" → PRES / COOK; chom "Eigenschap der Vygeboonen" → CURE / COOK |
| would push **toward the wrong** answer | **4** | pha02 "Trochisci Scillitici voor de Theriakel" → COOK / CURE; pha05 "Syrupus aceti" → COOK / CURE; chom "castoreum" → COOK / CURE; vol002 "Peeren in quartieren, om die in de voorzomer… te gebruiken" → COOK / PRES |

**Verdict on the rule:** at most 2–5 of 18 could plausibly be fixed by passing the heading in. That is not most of them, so **don't run the T3 prototype for this question** yet. The 5 "already seen" cases are a weak natural experiment: the heading was inside the text but not marked as a heading, so an explicit "entry heading:" field could still differ. The n is too small to claim anything beyond "not the main piece".

## What the cases have in common instead: gold splits on the same entry type

Inside a single work, entries of the same kind get different gold labels:

| work | entry type | gold labels |
|---|---|---|
| pha001phar05 (pharmacopoeia) | *Syrupus …* | aceti → COOK, Rosarum solutivus → COOK, absinthii Compositus → CURE, succi Betonicae → CURE, quinque Radicum → DROPPED |
| lee024leeu02 | *Oleum …* | Laurinum → CURE, Anisi → CURE, Nucum Moschat → CURE, Terebinthinae → COOK |
| pha001phar02 | *Trochisci … voor de Theriakel* | Scillitici → COOK, Hedychroi → PRES |

Preparing a remedy is cooking *and* cure at once. Neither the sentence nor the heading decides between them, because the gold doesn't decide either. All the attempts so far (few-shots ×2, split classifier, and now the heading) shared one assumption: **one frame per occurrence**. For remedy preparation in pharmacopoeias and household books, that assumption may be what doesn't fit the data. It agrees with the earlier finding that PRESERVING is conceptually a subset of COOKING_CREATION and that CURE overlaps with it.

## Rik's reading (16 Nov): two levels, both frames apply

COOKING_CREATION is the **procedure** (the actual recipe, at sentence level). CURE is the **purpose**, often named by the heading (entry level). The split gold would then be annotators labelling sometimes the procedure and sometimes the purpose, with both correct. This is T3's two-level design applied to the label itself. It is not flat multi-label: each level has one label.

**First check (weak, from record ids only, which encode the verb the harvest matched):** 11 gold-CURE rows have a purpose verb in the sentence (*goed voor, genezen, heelen, remedie voor*). No gold-COOKING_CREATION row has one; those have procedure verbs (*maken, trekken, steenen*). This is consistent with: purpose in the sentence → CURE; procedure only → COOKING_CREATION, even inside cure entries. Under this reading, the 4 "would push toward the wrong answer" cases above are not wrong (heading = purpose, sentence = procedure). **To do:** read the full contexts of the split rows; the ids show only the selecting verb.

**Inheritance (Rik, 16 Nov):** under a single-word ailment heading (e.g. *Hoesten*), all recipes get entry purpose CURE, also without purpose language in the sentence. The sentence frame (e.g. COOKING_CREATION for the procedure) is labelled separately.
- Heading type decides:
  - **ailment** → CURE;
  - **plant/drug** (materia medica: *sphondelium*, *castoreum*, *byvoet*) → mixed; classify per entry;
  - **food/other** → no purpose from the heading.
- Chomel ailment headings in gold: *dolheid* CURE, *onzinnigheid* CURE, *verstopping* DROPPED, *ogen* COOK. So 2 of 4 contradict the rule. These are not gold errors: the gold was labelled under a one-level regime (one frame per sentence). For the two-level question it needs relabelling at entry level, not correcting. Record the labelling regime with any gold reuse.
- **Scoring:** score entry purpose per entry, not per inherited row; otherwise inherited labels inflate accuracy (the header-inheritance trap from PLAN §9e).

## Scope (caveats a–c)

- **(a) Not universal:** all 18 come from works with entry structure (4 works: chom, pha01/02/05, vol002, lee024). Nothing here says anything about recipes in running prose or newspapers.
- **(b) Findability:** 3 of 18 headings are informative only to a reader who knows the genre (Latin pharmacy names). A heading cue would not find them.
- **(c) Structure ≠ cooking:** the pharmacopoeias have a cookbook-like structure. Their headings push toward CURE even where gold says COOK.

## Next (proposed, not decided)

1. Rik checks the split rows above: is the gold inconsistent, or does a real distinction show in the full entry?
2. If the gold is inconsistent or both labels apply: test multi-label (or "COOKING_CREATION + purpose") on these works against single-label. That would be a change to the question, not another fix.
3. Only then, and only if (1) shows a heading-level distinction: the small T3 run on the 7 informative cases.
