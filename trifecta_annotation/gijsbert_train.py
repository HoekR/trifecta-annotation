"""Fine-tune GijsBERT for TRIFECTA macro-frame classification."""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trifecta_annotation.eval import _per_class_f1
from trifecta_annotation.gijsbert_export import FRAME_LABELS, load_gijsbert_jsonl

NONE_LABEL = "NONE"


@dataclass
class GijsbertEvalResult:
    total: int
    accuracy: float
    per_frame_f1: dict[str, float]
    predictions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "accuracy": self.accuracy,
            "per_frame_f1": self.per_frame_f1,
        }


def load_label_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def classification_metrics(
    gold_labels: list[str],
    pred_labels: list[str],
) -> GijsbertEvalResult:
    total = len(gold_labels)
    accuracy = sum(g == p for g, p in zip(gold_labels, pred_labels, strict=True)) / total if total else 0.0
    predictions = [
        {"gold": gold, "pred": pred}
        for gold, pred in zip(gold_labels, pred_labels, strict=True)
    ]
    return GijsbertEvalResult(
        total=total,
        accuracy=accuracy,
        per_frame_f1=_per_class_f1(gold_labels, pred_labels),
        predictions=predictions,
    )


def _resolve_device(requested: str | None) -> str:
    import torch

    if requested:
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def oversample_none_rows(
    rows: list[dict[str, Any]],
    *,
    factor: int = 1,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Duplicate NONE-labelled rows to balance train signal."""
    if factor <= 1:
        return rows
    none_rows = [row for row in rows if str(row.get("label")) == NONE_LABEL]
    if not none_rows:
        return rows
    rng = random.Random(seed)
    extra = [dict(row) for row in rng.choices(none_rows, k=len(none_rows) * (factor - 1))]
    return rows + extra


def filter_frames_only(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop NONE rows for frames-only training."""
    return [row for row in rows if str(row.get("label")) != NONE_LABEL]


def build_label_maps(
    *,
    frames_only: bool,
    manifest_label2id: dict[str, int],
    manifest_id2label: dict[int, str],
) -> tuple[dict[str, int], dict[int, str]]:
    if not frames_only:
        label2id = {str(k): int(v) for k, v in manifest_label2id.items()}
        id2label = {int(k): str(v) for k, v in manifest_id2label.items()}
        return label2id, id2label

    frame_labels = [label for label in FRAME_LABELS if label != NONE_LABEL]
    label2id = {label: idx for idx, label in enumerate(frame_labels)}
    id2label = {idx: label for label, idx in label2id.items()}
    return label2id, id2label


def remap_rows_for_frames_only(
    rows: list[dict[str, Any]],
    label2id: dict[str, int],
) -> list[dict[str, Any]]:
    remapped: list[dict[str, Any]] = []
    for row in rows:
        label = str(row.get("label"))
        if label == NONE_LABEL:
            continue
        out = dict(row)
        out["label"] = label
        out["label_id"] = label2id[label]
        remapped.append(out)
    return remapped


def compute_class_weights(
    label_ids: list[int],
    *,
    num_labels: int,
    none_label_id: int | None,
    none_boost: float = 1.0,
) -> list[float]:
    """Inverse-frequency class weights; optional extra boost for NONE."""
    counts = Counter(label_ids)
    total = len(label_ids)
    weights: list[float] = []
    for label_id in range(num_labels):
        count = counts.get(label_id, 0)
        weight = total / (num_labels * count) if count else 1.0
        if none_label_id is not None and label_id == none_label_id:
            weight *= none_boost
        weights.append(weight)
    return weights


def train_gijsbert(
    *,
    data_dir: str | Path,
    output_dir: str | Path,
    model_name: str | None = None,
    epochs: float = 3.0,
    batch_size: int = 8,
    learning_rate: float = 2e-5,
    max_length: int = 256,
    seed: int = 42,
    device: str | None = None,
    oversample_none: int = 1,
    class_weight_balance: bool = False,
    none_weight_boost: float = 2.0,
    frames_only: bool = False,
) -> dict[str, Path]:
    """Fine-tune GijsBERT and evaluate on dev split."""
    from trifecta_annotation.hf_cache import configure_hf_hub_cache

    configure_hf_hub_cache()
    import torch
    from datasets import Dataset
    from torch import nn
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    data_path = Path(data_dir).expanduser().resolve()
    out_path = Path(output_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    manifest = load_label_manifest(data_path / "label_manifest.json")
    label2id, id2label = build_label_maps(
        frames_only=frames_only,
        manifest_label2id=manifest["label2id"],
        manifest_id2label=manifest["id2label"],
    )
    model_base = model_name or str(manifest.get("model_base") or "emanjavacas/gysbert")

    train_rows = load_gijsbert_jsonl(data_path / "train.jsonl")
    dev_rows_full = load_gijsbert_jsonl(data_path / "dev.jsonl")
    train_rows = oversample_none_rows(train_rows, factor=oversample_none, seed=seed)
    dev_rows = dev_rows_full
    if frames_only:
        train_rows = remap_rows_for_frames_only(train_rows, label2id)
        dev_rows = remap_rows_for_frames_only(dev_rows, label2id)

    set_seed(seed)
    resolved_device = _resolve_device(device)
    hf_cache = configure_hf_hub_cache()

    tokenizer = AutoTokenizer.from_pretrained(model_base, cache_dir=str(hf_cache))
    model = AutoModelForSequenceClassification.from_pretrained(
        model_base,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
        cache_dir=str(hf_cache),
    )

    def _to_dataset(rows: list[dict[str, Any]]) -> Dataset:
        return Dataset.from_dict(
            {
                "text": [row["text"] for row in rows],
                "label": [int(row["label_id"]) for row in rows],
            }
        )

    train_ds = _to_dataset(train_rows)
    dev_ds = _to_dataset(dev_rows)

    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding="max_length",
        )

    train_ds = train_ds.map(_tokenize, batched=True)
    dev_ds = dev_ds.map(_tokenize, batched=True)

    use_fp16 = resolved_device == "cuda"
    args = TrainingArguments(
        output_dir=str(out_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=2,
        seed=seed,
        fp16=use_fp16,
        report_to=[],
    )

    def _compute_metrics(eval_pred) -> dict[str, float]:
        import numpy as np

        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        accuracy = float((preds == labels).mean())
        return {"accuracy": accuracy}

    class_weights_tensor: torch.Tensor | None = None
    if class_weight_balance:
        train_label_ids = [int(row["label_id"]) for row in train_rows]
        none_id = label2id.get(NONE_LABEL)
        weights = compute_class_weights(
            train_label_ids,
            num_labels=len(label2id),
            none_label_id=none_id,
            none_boost=none_weight_boost,
        )
        class_weights_tensor = torch.tensor(weights, dtype=torch.float32)

    trainer_cls: type[Trainer] = Trainer
    if class_weights_tensor is not None:

        class WeightedTrainer(Trainer):
            def __init__(self, *args, class_weights: torch.Tensor, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.class_weights = class_weights

            def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
                labels = inputs.pop("labels")
                outputs = model(**inputs)
                loss_fn = nn.CrossEntropyLoss(weight=self.class_weights.to(model.device))
                loss = loss_fn(
                    outputs.logits.view(-1, model.config.num_labels),
                    labels.view(-1),
                )
                return (loss, outputs) if return_outputs else loss

        trainer_cls = WeightedTrainer

    trainer_kwargs: dict[str, Any] = {
        "model": model,
        "args": args,
        "train_dataset": train_ds,
        "eval_dataset": dev_ds,
        "processing_class": tokenizer,
        "compute_metrics": _compute_metrics,
    }
    if class_weights_tensor is not None:
        trainer_kwargs["class_weights"] = class_weights_tensor

    trainer = trainer_cls(**trainer_kwargs)

    train_result = trainer.train()
    trainer.save_model(str(out_path / "model"))
    tokenizer.save_pretrained(str(out_path / "model"))

    pred_output = trainer.predict(dev_ds)
    import numpy as np

    pred_ids = np.argmax(pred_output.predictions, axis=-1).tolist()
    gold_labels = [str(row["label"]) for row in dev_rows]
    pred_labels = [id2label[int(pid)] for pid in pred_ids]
    metrics = classification_metrics(gold_labels, pred_labels)

    if frames_only:
        frame_metrics = metrics
    else:
        gold_labels_full = [str(row["label"]) for row in dev_rows_full]
        full_pred_labels = list(pred_labels)
        if len(full_pred_labels) < len(gold_labels_full):
            none_pad = len(gold_labels_full) - len(full_pred_labels)
            full_pred_labels.extend(["COOKING_CREATION"] * none_pad)
        frame_pairs = [
            (g, p)
            for g, p in zip(gold_labels_full, full_pred_labels, strict=True)
            if g != NONE_LABEL
        ]
        frame_gold = [g for g, _ in frame_pairs]
        frame_pred = [p for _, p in frame_pairs]
        frame_metrics = (
            classification_metrics(frame_gold, frame_pred)
            if frame_gold
            else None
        )

    run_meta = {
        "model_base": model_base,
        "hf_hub_cache": str(hf_cache),
        "data_dir": str(data_path),
        "output_dir": str(out_path),
        "device": resolved_device,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "train_rows": len(train_rows),
        "dev_rows": len(dev_rows),
        "oversample_none": oversample_none,
        "class_weight_balance": class_weight_balance,
        "none_weight_boost": none_weight_boost,
        "frames_only": frames_only,
        "train_loss": float(train_result.training_loss),
        "finished_at": datetime.now(UTC).isoformat(),
        "dev_metrics": metrics.to_dict(),
        "dev_metrics_frame_only": frame_metrics.to_dict() if frame_metrics else None,
        "baseline_qwen_step_b_accuracy": 0.75,
    }

    metrics_path = out_path / "dev_metrics.json"
    metrics_path.write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    report_lines = [
        "# GijsBERT fine-tune report",
        "",
        f"- Model: `{model_base}`",
        f"- Train rows: {len(train_rows)}",
        f"- Dev rows: {len(dev_rows)}",
        f"- Oversample NONE: {oversample_none}x",
        f"- Class weights: {class_weight_balance} (NONE boost {none_weight_boost})",
        f"- Frames-only train: {frames_only}",
        f"- Device: {resolved_device}",
        f"- Dev accuracy (all): **{metrics.accuracy:.3f}**",
        f"- Dev accuracy (frames only, n={len(frame_gold)}): **{frame_metrics.accuracy:.3f}**"
        if frame_metrics
        else "- Dev accuracy (frames only): n/a",
        f"- qwen Step B baseline: 0.750",
        "",
        "## Per-frame F1 (dev, all)",
    ]
    for label, score in sorted(metrics.per_frame_f1.items()):
        report_lines.append(f"- {label}: {score:.3f}")
    if frame_metrics:
        report_lines.extend(["", "## Per-frame F1 (dev, frames only — excl. NONE)"])
        for label, score in sorted(frame_metrics.per_frame_f1.items()):
            report_lines.append(f"- {label}: {score:.3f}")
    report_path = out_path / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "model": out_path / "model",
        "metrics": metrics_path,
        "report": report_path,
    }
