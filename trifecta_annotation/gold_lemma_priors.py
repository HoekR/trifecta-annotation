"""Build lemma-level priors from labelled gold (G2).

Aggregates drop / food-pass / homonym rates per normalized ``target_word``
and applies gated thresholds for hard-blocked lemmas consumed by
``gold_target_filter``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from trifecta_annotation.gold_target_filter import normalize_target
from trifecta_annotation.review_columns import HOMONYM_CHECK_VALUES

PRIORS_VERSION = 1

# Conservative defaults (CLI / G4 can loosen). Prefer under-blocking rare food.
DEFAULT_MIN_N = 3
DEFAULT_MAX_FOOD_PASS_RATE = 0.2
DEFAULT_MIN_DROP_RATE = 0.75
DEFAULT_MIN_OTHER_SENSE_RATE = 0.5
DEFAULT_SOFT_FOOD_PASS_CAP = 5
DEFAULT_DISAMBIG_MIN_N = 3
DEFAULT_DISAMBIG_MIN_MIX_RATE = 0.25


def _parse_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _is_labelled(row: Mapping[str, Any]) -> bool:
    labelled = _parse_bool(row.get("labelled"))
    if labelled is True:
        return True
    if labelled is False:
        return False
    # Imported gold rows without explicit labelled flag still count if Step A filled.
    if _parse_bool(row.get("dropped")) is not None:
        return True
    if _parse_bool(row.get("is_food_entity")) is not None:
        return True
    return bool(str(row.get("selected_frame") or "").strip())


def _homonym_check(row: Mapping[str, Any]) -> str:
    raw = str(row.get("homonym_check") or "").strip().lower()
    return raw if raw in HOMONYM_CHECK_VALUES else ""


def _frame_label(row: Mapping[str, Any]) -> str:
    if _parse_bool(row.get("dropped")) is True:
        return "NONE"
    frame = str(row.get("selected_frame") or "").strip()
    if frame in {"USING_CURE", "CURE"}:
        return "CURE"
    if frame in {"USING_INGESTION", "INGESTION"}:
        return "INGESTION"
    return frame or "UNKNOWN"


def _regime_label(row: Mapping[str, Any]) -> str:
    return str(row.get("text_regime") or "").strip() or "UNKNOWN"


@dataclass(frozen=True)
class PriorThresholds:
    """Gated cutoffs for hard-block / soft signals."""

    min_n: int = DEFAULT_MIN_N
    max_food_pass_rate: float = DEFAULT_MAX_FOOD_PASS_RATE
    min_drop_rate: float = DEFAULT_MIN_DROP_RATE
    min_other_sense_rate: float = DEFAULT_MIN_OTHER_SENSE_RATE
    soft_food_pass_cap: int = DEFAULT_SOFT_FOOD_PASS_CAP
    disambig_min_n: int = DEFAULT_DISAMBIG_MIN_N
    disambig_min_mix_rate: float = DEFAULT_DISAMBIG_MIN_MIX_RATE


@dataclass
class LemmaAgg:
    """Mutable per-lemma counters while scanning labelled rows."""

    n: int = 0
    food_pass: int = 0
    dropped: int = 0
    other_sense: int = 0
    metaphor: int = 0
    frames: Counter[str] | None = None
    regimes: Counter[str] | None = None

    def __post_init__(self) -> None:
        if self.frames is None:
            self.frames = Counter()
        if self.regimes is None:
            self.regimes = Counter()


def accumulate_row(agg: LemmaAgg, row: Mapping[str, Any]) -> None:
    """Update one lemma aggregate from a labelled gold / labelling CSV row."""
    dropped = _parse_bool(row.get("dropped")) is True
    food = _parse_bool(row.get("is_food_entity"))
    food_pass = (not dropped) and food is True
    homonym = _homonym_check(row)
    metaphor = (_parse_bool(row.get("is_metaphor")) is True) or (homonym == "metaphor")
    other_sense = homonym == "other_sense"

    agg.n += 1
    if food_pass:
        agg.food_pass += 1
    if dropped:
        agg.dropped += 1
    if other_sense:
        agg.other_sense += 1
    if metaphor:
        agg.metaphor += 1
    assert agg.frames is not None
    assert agg.regimes is not None
    agg.frames[_frame_label(row)] += 1
    agg.regimes[_regime_label(row)] += 1


def aggregate_labelled_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, LemmaAgg]:
    """Group labelled rows by normalized target; skip empty targets."""
    by_lemma: dict[str, LemmaAgg] = {}
    for row in rows:
        if not _is_labelled(row):
            continue
        target_norm = normalize_target(str(row.get("target_word") or ""))
        if not target_norm:
            continue
        agg = by_lemma.get(target_norm)
        if agg is None:
            agg = LemmaAgg()
            by_lemma[target_norm] = agg
        accumulate_row(agg, row)
    return by_lemma


def _rate(num: int, den: int) -> float:
    return (num / den) if den else 0.0


def lemma_stats_dict(target_norm: str, agg: LemmaAgg) -> dict[str, Any]:
    """Serialize one lemma aggregate to a JSON-friendly stats dict."""
    n = agg.n
    assert agg.frames is not None and agg.regimes is not None
    return {
        "target_norm": target_norm,
        "n": n,
        "food_pass": agg.food_pass,
        "dropped": agg.dropped,
        "other_sense": agg.other_sense,
        "metaphor": agg.metaphor,
        "food_pass_rate": round(_rate(agg.food_pass, n), 4),
        "drop_rate": round(_rate(agg.dropped, n), 4),
        "other_sense_rate": round(_rate(agg.other_sense, n), 4),
        "metaphor_rate": round(_rate(agg.metaphor, n), 4),
        "frames": dict(sorted(agg.frames.items())),
        "regimes": dict(sorted(agg.regimes.items())),
    }


def should_hard_block(stats: Mapping[str, Any], thresholds: PriorThresholds) -> bool:
    """True when lemma should be hard-skipped by exporters (G3)."""
    n = int(stats.get("n") or 0)
    if n < thresholds.min_n:
        return False
    other_sense_rate = float(stats.get("other_sense_rate") or 0.0)
    if other_sense_rate >= thresholds.min_other_sense_rate:
        return True
    food_pass_rate = float(stats.get("food_pass_rate") or 0.0)
    drop_rate = float(stats.get("drop_rate") or 0.0)
    return (
        food_pass_rate <= thresholds.max_food_pass_rate
        and drop_rate >= thresholds.min_drop_rate
    )


def should_require_disambiguation(
    stats: Mapping[str, Any],
    thresholds: PriorThresholds,
    *,
    hard_skip: bool,
) -> bool:
    """Polysemous-but-sometimes-food lemmas (soft signal for G3)."""
    if hard_skip:
        return False
    n = int(stats.get("n") or 0)
    if n < thresholds.disambig_min_n:
        return False
    food_pass_rate = float(stats.get("food_pass_rate") or 0.0)
    if food_pass_rate <= 0.0 or food_pass_rate >= 1.0:
        return False
    mix = max(
        float(stats.get("drop_rate") or 0.0),
        float(stats.get("metaphor_rate") or 0.0),
        float(stats.get("other_sense_rate") or 0.0),
        1.0 - food_pass_rate,
    )
    return mix >= thresholds.disambig_min_mix_rate


def should_soft_deprioritize(
    stats: Mapping[str, Any],
    thresholds: PriorThresholds,
    *,
    hard_skip: bool,
) -> bool:
    """Saturated food-pass lemmas (soft signal for G3)."""
    if hard_skip:
        return False
    return int(stats.get("food_pass") or 0) >= thresholds.soft_food_pass_cap


def build_priors_payload(
    rows: Iterable[Mapping[str, Any]],
    *,
    thresholds: PriorThresholds | None = None,
    source: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the G2 priors JSON object (compatible with ``prior_blocked_lemmas``)."""
    thr = thresholds or PriorThresholds()
    aggs = aggregate_labelled_rows(rows)
    lemmas: dict[str, Any] = {}
    blocked: list[str] = []
    require_disambiguation: list[str] = []
    soft_deprioritize: list[str] = []

    for target_norm in sorted(aggs):
        stats = lemma_stats_dict(target_norm, aggs[target_norm])
        hard_skip = should_hard_block(stats, thr)
        disambig = should_require_disambiguation(stats, thr, hard_skip=hard_skip)
        soft = should_soft_deprioritize(stats, thr, hard_skip=hard_skip)
        stats["hard_skip"] = hard_skip
        stats["require_disambiguation"] = disambig
        stats["soft_deprioritize"] = soft
        lemmas[target_norm] = stats
        if hard_skip:
            blocked.append(target_norm)
        if disambig:
            require_disambiguation.append(target_norm)
        if soft:
            soft_deprioritize.append(target_norm)

    n_labelled = sum(int(s["n"]) for s in lemmas.values())
    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "version": PRIORS_VERSION,
        "generated_at": stamp,
        "meta": {
            "source": source,
            "n_labelled": n_labelled,
            "n_lemmas": len(lemmas),
            "n_blocked": len(blocked),
            "n_require_disambiguation": len(require_disambiguation),
            "n_soft_deprioritize": len(soft_deprioritize),
            "thresholds": {
                "min_n": thr.min_n,
                "max_food_pass_rate": thr.max_food_pass_rate,
                "min_drop_rate": thr.min_drop_rate,
                "min_other_sense_rate": thr.min_other_sense_rate,
                "soft_food_pass_cap": thr.soft_food_pass_cap,
                "disambig_min_n": thr.disambig_min_n,
                "disambig_min_mix_rate": thr.disambig_min_mix_rate,
            },
        },
        "blocked": blocked,
        "require_disambiguation": require_disambiguation,
        "soft_deprioritize": soft_deprioritize,
        "lemmas": lemmas,
    }


def top_offenders(
    payload: Mapping[str, Any],
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Lemmas sorted by drop volume then low food-pass (for CLI summary)."""
    lemmas = payload.get("lemmas")
    if not isinstance(lemmas, Mapping):
        return []
    rows = list(lemmas.values())
    rows.sort(
        key=lambda s: (
            -int(s.get("dropped") or 0),
            float(s.get("food_pass_rate") or 0.0),
            -int(s.get("n") or 0),
            str(s.get("target_norm") or ""),
        )
    )
    return rows[:limit]


def offenders_summary_lines(
    payload: Mapping[str, Any],
    *,
    limit: int = 15,
) -> list[str]:
    """Human-readable offender lines for stderr / notebook."""
    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
    lines = [
        (
            f"priors: labelled={meta.get('n_labelled', '?')} "
            f"lemmas={meta.get('n_lemmas', '?')} "
            f"blocked={meta.get('n_blocked', '?')} "
            f"disambig={meta.get('n_require_disambiguation', '?')} "
            f"soft={meta.get('n_soft_deprioritize', '?')}"
        )
    ]
    blocked = payload.get("blocked")
    if isinstance(blocked, Sequence) and not isinstance(blocked, (str, bytes)):
        lines.append(f"blocked: {', '.join(str(x) for x in blocked) or '(none)'}")
    lines.append("top offenders (by dropped count):")
    for stats in top_offenders(payload, limit=limit):
        flag = " BLOCK" if stats.get("hard_skip") else ""
        lines.append(
            f"  {stats.get('target_norm')}: n={stats.get('n')} "
            f"food_pass={stats.get('food_pass_rate')} "
            f"drop={stats.get('drop_rate')} "
            f"other_sense={stats.get('other_sense_rate')} "
            f"metaphor={stats.get('metaphor_rate')}{flag}"
        )
    return lines
