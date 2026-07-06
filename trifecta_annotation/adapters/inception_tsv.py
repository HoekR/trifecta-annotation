"""Adapter for INCEpTION / WebAnno TSV 3.3 exports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from trifecta_annotation.schemas import (
    AnnotationProvenance,
    CookingCreationQualia,
    CureQualia,
    EntityValidation,
    FormalDimension,
    FrameClassification,
    FrameQualia,
    IngestionQualia,
    KwicInput,
    PreservingQualia,
    TrifectaAnnotation,
    TrifectaFrame,
)
from trifecta_annotation.snippet_lookup import lookup_snippet_metadata
from trifecta_annotation.text_regime import TextRegime, infer_text_regime

_LAYER_SPLIT = re.compile(r"\|")
_LAYER_SUFFIX = re.compile(r"\[\d+\]$")
_UNESCAPE = str.maketrans({"\\": ""})

_FRAME_LU_MARKERS: list[tuple[TrifectaFrame, tuple[str, ...]]] = [
    (TrifectaFrame.COOKING_CREATION, ("COOKING_CREATION_LU",)),
    (TrifectaFrame.CURE, ("CURE_LU",)),
    (TrifectaFrame.INGESTION, ("INGESTION_LU", "INGR_Material_LU")),
    (TrifectaFrame.PRESERVING, ("PR_LU",)),
]

_FORMAL_LAYER_MAP = {
    "FOOD_Unit": FormalDimension.FOOD_UNIT,
    "FOOD_Constituent_Part": FormalDimension.FOOD_CONSTITUENT_PART,
    "FOOD_Descriptor": FormalDimension.FOOD_DESCRIPTOR,
    "FOOD_Whole": FormalDimension.FOOD_WHOLE,
}

_STEP_C_FIELDS: dict[TrifectaFrame, dict[str, str]] = {
    TrifectaFrame.COOKING_CREATION: {
        "COOKING_CREATION_Method": "COOKING_CREATION_Method",
        "COOKING_CREATION_Process": "COOKING_CREATION_Process",
        "COOKING_CREATION_Food_Product": "COOKING_CREATION_Food_Product",
        "COOKING_CREATION_Food_Material": "COOKING_CREATION_Food_Material",
        "COOKING_CREATION_Cook": "COOKING_CREATION_Method",
    },
    TrifectaFrame.CURE: {
        "CURE_Affliction": "CURE_Affliction",
        "CURE_Food_Treatment": "CURE_Food_Treatment",
        "CURE_Patient": "CURE_Food_Treatment",
        "CURE_Healer": "CURE_Healer",
    },
    TrifectaFrame.INGESTION: {
        "INGESTION_Context": "INGESTION_Context",
        "INGESTION_Ingestor": "INGESTION_Ingestor",
        "INGESTION_Manner": "INGESTION_Manner",
        "INGR_Food_Product": "INGESTION_Context",
        "INGESTION_Food_Ingestible": "INGESTION_Context",
    },
    TrifectaFrame.PRESERVING: {
        "PR_Technique": "PR_Technique",
        "PR_Medium": "PR_Medium",
        "PR_Food_Patient": "PR_Food_Patient",
        "PR_Agent": "PR_Medium",
    },
}


@dataclass
class AnnotatedToken:
    token_id: str
    begin: int
    end: int
    surface: str
    layers: list[str] = field(default_factory=list)


@dataclass
class AnnotatedSentence:
    sentence_id: int
    text: str
    tokens: list[AnnotatedToken] = field(default_factory=list)


def _clean_layer(raw: str) -> str:
    text = raw.strip().translate(_UNESCAPE)
    text = _LAYER_SUFFIX.sub("", text)
    if text in {"_", "*"}:
        return ""
    return text


def _split_layers(cell: str) -> list[str]:
    if not cell or cell.strip() in {"_", "*"}:
        return []
    return [layer for layer in (_clean_layer(part) for part in _LAYER_SPLIT.split(cell)) if layer]


def _is_food_target(layers: list[str]) -> bool:
    return any(layer == "FOOD_LU" or layer.startswith("FOOD_LU") for layer in layers)


def _is_metaphor(layers: list[str]) -> bool:
    return any(layer.startswith("MET_") for layer in layers)


def _formal_dimension(layers: list[str]) -> FormalDimension | None:
    for layer in layers:
        if layer in _FORMAL_LAYER_MAP:
            return _FORMAL_LAYER_MAP[layer]
    return None


def _frame_from_layers(layers: list[str]) -> TrifectaFrame | None:
    for frame, markers in _FRAME_LU_MARKERS:
        if any(any(layer == marker or layer.startswith(f"{marker}[") for layer in layers) for marker in markers):
            return frame
    return None


def _frame_lu_surface(sentence: AnnotatedSentence, frame: TrifectaFrame) -> str | None:
    if frame == TrifectaFrame.NONE:
        return None
    markers = dict(_FRAME_LU_MARKERS)[frame]
    for token in sentence.tokens:
        if _frame_from_layers(token.layers) == frame:
            return token.surface
    for token in sentence.tokens:
        if any(marker.replace("_LU", "") in layer for layer in token.layers for marker in markers):
            continue
        if _frame_from_layers(token.layers) is not None:
            continue
    for token in sentence.tokens:
        for layer in token.layers:
            if any(marker in layer for marker in markers):
                return token.surface
    return None


def _infer_frame(sentence: AnnotatedSentence, food_token: AnnotatedToken) -> TrifectaFrame:
    on_target = _frame_from_layers(food_token.layers)
    if on_target is not None:
        return on_target
    frames = {_frame_from_layers(token.layers) for token in sentence.tokens}
    frames.discard(None)
    if len(frames) == 1:
        return next(iter(frames))
    priority = (
        TrifectaFrame.PRESERVING,
        TrifectaFrame.COOKING_CREATION,
        TrifectaFrame.CURE,
        TrifectaFrame.INGESTION,
    )
    for frame in priority:
        if frame in frames:
            return frame
    return TrifectaFrame.NONE


def _collect_step_c(sentence: AnnotatedSentence, frame: TrifectaFrame) -> dict[str, str]:
    field_map = _STEP_C_FIELDS.get(frame, {})
    collected: dict[str, str] = {}
    for token in sentence.tokens:
        for layer in token.layers:
            target_field = field_map.get(layer)
            if target_field and target_field not in collected:
                collected[target_field] = token.surface
    return collected


def _build_step_c(frame: TrifectaFrame, qualia: dict[str, str], lexical_unit: str) -> FrameQualia | None:
    if frame == TrifectaFrame.NONE:
        return None
    if frame == TrifectaFrame.COOKING_CREATION:
        return CookingCreationQualia(
            COOKING_CREATION_Method=qualia.get("COOKING_CREATION_Method", ""),
            COOKING_CREATION_Process=qualia.get("COOKING_CREATION_Process", ""),
            COOKING_CREATION_Food_Product=qualia.get("COOKING_CREATION_Food_Product", ""),
            lexical_unit=lexical_unit,
        )
    if frame == TrifectaFrame.CURE:
        return CureQualia(
            CURE_Affliction=qualia.get("CURE_Affliction", ""),
            CURE_Food_Treatment=qualia.get("CURE_Food_Treatment", ""),
            lexical_unit=lexical_unit,
        )
    if frame == TrifectaFrame.INGESTION:
        return IngestionQualia(
            INGESTION_Context=qualia.get("INGESTION_Context", ""),
            INGESTION_Ingestor=qualia.get("INGESTION_Ingestor", ""),
            INGESTION_Manner=qualia.get("INGESTION_Manner", ""),
            lexical_unit=lexical_unit,
        )
    if frame == TrifectaFrame.PRESERVING:
        return PreservingQualia(
            PR_Technique=qualia.get("PR_Technique", lexical_unit),
            PR_Medium=qualia.get("PR_Medium", ""),
            PR_Food_Patient=qualia.get("PR_Food_Patient", ""),
            lexical_unit=lexical_unit,
        )
    return None


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "doc"


def _corpus_from_doc(doc_name: str) -> str:
    """INCEpTION export doc id (batch file); annotations are snippet-line views."""
    return "inception_snippets"


def _enrich_from_snippets(
    *,
    context_text: str,
    doc_name: str,
) -> dict[str, object]:
    """Attach cort_voc snippet lineage when the line matches food_snippets."""
    match = lookup_snippet_metadata(context_text)
    if match is None:
        return {
            "corpus": _corpus_from_doc(doc_name),
            "title": doc_name,
            "text_regime": TextRegime.UNKNOWN,
            "source_path": None,
            "snippet_doc_id": None,
        }
    return {
        "corpus": "cort_voc_db",
        "title": match.title or doc_name,
        "text_regime": match.text_regime,
        "source_path": match.filename or None,
        "snippet_doc_id": match.doc_id or None,
    }


def parse_webanno_tsv(path: str | Path) -> list[AnnotatedSentence]:
    """Parse a WebAnno TSV 3.3 file into annotated sentences."""
    sentences: list[AnnotatedSentence] = []
    current: AnnotatedSentence | None = None

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#Text="):
            if current is not None:
                sentences.append(current)
            text = line[len("#Text=") :]
            sent_id = len(sentences) + 1
            current = AnnotatedSentence(sentence_id=sent_id, text=text)
            continue
        if line.startswith("#") or current is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        token_id, offsets, surface = parts[0], parts[1], parts[2]
        layer_cell = parts[3] if len(parts) > 3 else ""
        begin_s, _, end_s = offsets.partition("-")
        try:
            begin = int(begin_s)
            end = int(end_s)
        except ValueError:
            continue
        current.tokens.append(
            AnnotatedToken(
                token_id=token_id,
                begin=begin,
                end=end,
                surface=surface,
                layers=_split_layers(layer_cell),
            ),
        )

    if current is not None:
        sentences.append(current)
    return sentences


def _record_id(doc_name: str, annotator: str, sentence: AnnotatedSentence, token: AnnotatedToken) -> str:
    return (
        f"inception_nl__{_slug(doc_name)}__{_slug(annotator)}__"
        f"s{sentence.sentence_id}__{token.begin}__{_slug(token.surface)}"
    )


def sentence_food_targets(sentence: AnnotatedSentence) -> list[AnnotatedToken]:
    return [token for token in sentence.tokens if _is_food_target(token.layers)]


def sentence_to_kwic_input(
    sentence: AnnotatedSentence,
    food_token: AnnotatedToken,
    *,
    doc_name: str,
    annotator: str,
    export_root: str | Path | None = None,
    text_regime: TextRegime | None = None,
) -> KwicInput:
    corpus = _corpus_from_doc(doc_name)
    meta = _enrich_from_snippets(context_text=sentence.text, doc_name=doc_name)
    regime = text_regime or meta["text_regime"]  # type: ignore[assignment]
    source_path = meta.get("source_path")
    if source_path is None and export_root is not None:
        source_path = str(Path(export_root) / "source" / doc_name)
    return KwicInput(
        record_id=_record_id(doc_name, annotator, sentence, food_token),
        corpus=str(meta["corpus"]),
        target_word=food_token.surface,
        context_text=sentence.text,
        source_path=source_path,
        title=str(meta.get("title") or doc_name),
        text_regime=regime,
        kwic_mode="food",
    )


def sentence_to_annotation(
    sentence: AnnotatedSentence,
    food_token: AnnotatedToken,
    *,
    doc_name: str,
    annotator: str,
    export_root: str | Path | None = None,
    text_regime: TextRegime | None = None,
) -> TrifectaAnnotation:
    kwic = sentence_to_kwic_input(
        sentence,
        food_token,
        doc_name=doc_name,
        annotator=annotator,
        export_root=export_root,
        text_regime=text_regime,
    )
    metaphor = _is_metaphor(food_token.layers)
    is_food = _is_food_target(food_token.layers) and not metaphor
    frame = _infer_frame(sentence, food_token)
    lexical_unit = _frame_lu_surface(sentence, frame) or ""
    qualia = _collect_step_c(sentence, frame)

    step_a = EntityValidation(
        is_food_entity=is_food,
        is_metaphor=metaphor,
        formal_dimension=_formal_dimension(food_token.layers),
        reasoning=f"Imported from INCEpTION ({annotator})",
    )
    step_b: FrameClassification | None = None
    step_c: FrameQualia | None = None
    dropped = metaphor or not is_food
    drop_reason = None
    if metaphor:
        drop_reason = "metaphor"
    elif not is_food:
        drop_reason = "not_food_entity"

    if not dropped and frame != TrifectaFrame.NONE:
        step_b = FrameClassification(
            selected_frame=frame,
            lexical_unit=lexical_unit or food_token.surface,
            reasoning=f"Imported from INCEpTION ({annotator})",
        )
        step_c = _build_step_c(frame, qualia, lexical_unit or food_token.surface)

    return TrifectaAnnotation(
        provenance=AnnotationProvenance(
            corpus=kwic.corpus,
            target_word=kwic.target_word,
            context_text=kwic.context_text,
            source_path=kwic.source_path,
            record_id=kwic.record_id,
            date=kwic.date,
            text_regime=kwic.text_regime,
            title=kwic.title,
            kwic_mode=kwic.kwic_mode,
        ),
        step_a=step_a,
        step_b=step_b,
        step_c=step_c,
        dropped=dropped,
        drop_reason=drop_reason,
        model=f"inception:{annotator}",
    )


def iter_inception_tsv_files(
    export_root: str | Path,
    *,
    layer: str = "annotation",
    annotators: set[str] | None = None,
) -> list[tuple[str, str, Path]]:
    """Return ``(doc_name, annotator, tsv_path)`` under an INCEpTION export."""
    root = Path(export_root)
    layer_dir = root / layer
    if not layer_dir.is_dir():
        raise FileNotFoundError(f"Missing INCEpTION layer directory: {layer_dir}")

    out: list[tuple[str, str, Path]] = []
    for doc_dir in sorted(layer_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        doc_name = doc_dir.name
        for tsv_path in sorted(doc_dir.glob("*.tsv")):
            if tsv_path.name == "INITIAL_CAS.tsv":
                continue
            annotator = tsv_path.stem
            if annotators is not None and annotator not in annotators:
                continue
            out.append((doc_name, annotator, tsv_path))
    return out


def load_inception_kwic_inputs(
    export_root: str | Path,
    *,
    layer: str = "annotation",
    annotators: set[str] | None = None,
    require_food_lu: bool = True,
) -> tuple[list[KwicInput], list[dict[str, object]]]:
    """Build KwicInput records from INCEpTION WebAnno exports."""
    records: list[KwicInput] = []
    skipped: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for doc_name, annotator, tsv_path in iter_inception_tsv_files(
        export_root,
        layer=layer,
        annotators=annotators,
    ):
        for sentence in parse_webanno_tsv(tsv_path):
            targets = sentence_food_targets(sentence)
            if not targets:
                if not require_food_lu:
                    continue
                skipped.append(
                    {
                        "doc": doc_name,
                        "annotator": annotator,
                        "sentence_id": sentence.sentence_id,
                        "reason": "no_food_lu",
                    },
                )
                continue
            for food_token in targets:
                kwic = sentence_to_kwic_input(
                    sentence,
                    food_token,
                    doc_name=doc_name,
                    annotator=annotator,
                    export_root=export_root,
                )
                if kwic.record_id in seen_ids:
                    continue
                seen_ids.add(kwic.record_id)
                records.append(kwic)
    return records, skipped


def load_inception_annotations(
    export_root: str | Path,
    *,
    layer: str = "annotation",
    annotators: set[str] | None = None,
) -> tuple[list[TrifectaAnnotation], list[dict[str, object]]]:
    """Build silver TrifectaAnnotation records from INCEpTION exports."""
    records: list[TrifectaAnnotation] = []
    skipped: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for doc_name, annotator, tsv_path in iter_inception_tsv_files(
        export_root,
        layer=layer,
        annotators=annotators,
    ):
        for sentence in parse_webanno_tsv(tsv_path):
            targets = sentence_food_targets(sentence)
            if not targets:
                skipped.append(
                    {
                        "doc": doc_name,
                        "annotator": annotator,
                        "sentence_id": sentence.sentence_id,
                        "reason": "no_food_lu",
                    },
                )
                continue
            for food_token in targets:
                ann = sentence_to_annotation(
                    sentence,
                    food_token,
                    doc_name=doc_name,
                    annotator=annotator,
                    export_root=export_root,
                )
                rid = ann.provenance.record_id or ""
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                records.append(ann)
    return records, skipped
