"""Shared target filter for gold candidate exports (denylist + lemma priors).

Used by clear-frame / preservare / regime exporters. Pure helpers only —
optional priors load via ``load_filter_for_export``.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.thesaurus import DEFAULT_DENYLIST

REASON_DENYLIST = "denylist"
REASON_LEMMA_PRIOR = "lemma_prior"
DEFAULT_PRIORS_LOGICAL = "gold_lemma_priors"


def normalize_target(target: str | None) -> str:
    """Normalize a KWIC / gold ``target_word`` for denylist and prior lookup."""
    if target is None:
        return ""
    return normalize_hist_dutch(str(target))


@dataclass(frozen=True)
class TargetFilterDecision:
    """Outcome of a single target check.

    ``hard_skip`` means exporters must drop the candidate before labelling.
    Soft flags guide sampling / homonym gating without hard-dropping.
    """

    target_norm: str
    hard_skip: bool
    reason: str | None = None
    require_disambiguation: bool = False
    soft_deprioritize: bool = False


def _lemma_list(priors: Mapping[str, Any], *keys: str) -> frozenset[str]:
    for key in keys:
        raw = priors.get(key)
        if isinstance(raw, (list, tuple, set, frozenset)):
            return frozenset(
                norm for item in raw if (norm := normalize_target(str(item)))
            )
    return frozenset()


def prior_blocked_lemmas(
    priors: Mapping[str, Any] | Iterable[str] | None,
) -> frozenset[str]:
    """Extract hard-blocked lemma norms from a G2 priors payload or plain iterable.

    Accepted shapes:
    - ``None`` → empty
    - iterable of lemma strings
    - mapping with ``blocked`` / ``hard_blocked`` list (or set) of lemmas
    - mapping of ``lemma → True`` / ``lemma → {"hard_skip": true}``
    """
    if priors is None:
        return frozenset()

    if isinstance(priors, Mapping):
        blocked = _lemma_list(priors, "blocked", "hard_blocked")
        if blocked:
            return blocked

        out: set[str] = set()
        for key, value in priors.items():
            if key in {
                "blocked",
                "hard_blocked",
                "meta",
                "generated_at",
                "version",
                "lemmas",
                "require_disambiguation",
                "soft_deprioritize",
            }:
                continue
            norm = normalize_target(str(key))
            if not norm:
                continue
            if value is True:
                out.add(norm)
            elif isinstance(value, Mapping) and (
                value.get("hard_skip") is True or value.get("blocked") is True
            ):
                out.add(norm)
        return frozenset(out)

    return frozenset(norm for item in priors if (norm := normalize_target(str(item))))


def prior_require_disambiguation(
    priors: Mapping[str, Any] | None,
) -> frozenset[str]:
    if not isinstance(priors, Mapping):
        return frozenset()
    return _lemma_list(priors, "require_disambiguation")


def prior_soft_deprioritize(
    priors: Mapping[str, Any] | None,
) -> frozenset[str]:
    if not isinstance(priors, Mapping):
        return frozenset()
    return _lemma_list(priors, "soft_deprioritize")


def load_priors_payload(path: str | Path) -> Mapping[str, Any] | list[Any]:
    """Load priors JSON (object or list)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, (Mapping, list)):
        raise ValueError(f"Priors JSON must be object or list, got {type(payload).__name__}")
    return payload


def load_prior_blocked(path: str | Path) -> frozenset[str]:
    """Load hard-blocked lemmas from a JSON priors file (G2 artifact)."""
    return prior_blocked_lemmas(load_priors_payload(path))


@dataclass
class FilterStats:
    """Mutable counters for a mine/sample pass (batch report)."""

    considered: int = 0
    kept: int = 0
    hard_skip_denylist: int = 0
    hard_skip_lemma_prior: int = 0
    require_disambiguation: int = 0
    soft_deprioritize: int = 0
    skipped_disambiguation: int = 0
    blocked_targets: Counter[str] = field(default_factory=Counter)

    def record_decision(self, decision: TargetFilterDecision) -> None:
        self.considered += 1
        if decision.hard_skip:
            if decision.reason == REASON_DENYLIST:
                self.hard_skip_denylist += 1
            elif decision.reason == REASON_LEMMA_PRIOR:
                self.hard_skip_lemma_prior += 1
            if decision.target_norm:
                self.blocked_targets[decision.target_norm] += 1
            return
        if decision.require_disambiguation:
            self.require_disambiguation += 1
        if decision.soft_deprioritize:
            self.soft_deprioritize += 1
        self.kept += 1

    @property
    def hard_skipped(self) -> int:
        return self.hard_skip_denylist + self.hard_skip_lemma_prior

    def as_dict(self) -> dict[str, Any]:
        top_blocked = sorted(
            self.blocked_targets.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )[:15]
        return {
            "considered": self.considered,
            "kept": self.kept,
            "hard_skipped": self.hard_skipped,
            "hard_skip_denylist": self.hard_skip_denylist,
            "hard_skip_lemma_prior": self.hard_skip_lemma_prior,
            "require_disambiguation": self.require_disambiguation,
            "soft_deprioritize": self.soft_deprioritize,
            "skipped_disambiguation": self.skipped_disambiguation,
            "top_blocked": top_blocked,
        }


def format_filter_report(
    stats: FilterStats,
    *,
    selected: Sequence[Any] | None = None,
    target_attr: str = "target_word",
    frame_attr: str | None = None,
    label: str = "lemma_filter",
) -> dict[str, Any]:
    """Build a stderr-friendly batch report dict."""
    report: dict[str, Any] = {"label": label, "filter": stats.as_dict()}
    if selected is None:
        return report

    by_frame: Counter[str] = Counter()
    by_lemma: Counter[str] = Counter()
    for item in selected:
        target = _extract_target(item, target_attr)
        if target:
            by_lemma[normalize_target(target)] += 1
        if frame_attr:
            frame = _extract_attr(item, frame_attr)
            if frame:
                by_frame[str(frame)] += 1

    report["selected"] = {
        "n": len(selected),
        "by_frame": dict(sorted(by_frame.items())) if by_frame else {},
        "top_lemmas": sorted(by_lemma.items(), key=lambda p: (-p[1], p[0]))[:15],
    }
    return report


def _extract_attr(item: Any, attr: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(attr)
    if "." in attr:
        cur: Any = item
        for part in attr.split("."):
            cur = getattr(cur, part, None)
            if cur is None:
                return None
        return cur
    return getattr(item, attr, None)


def _extract_target(item: Any, target_attr: str) -> str:
    value = _extract_attr(item, target_attr)
    return str(value or "")


@dataclass(frozen=True)
class GoldTargetFilter:
    """Hard-skip denylist targets; optionally apply gold lemma priors."""

    denylist: frozenset[str] = DEFAULT_DENYLIST
    prior_blocked: frozenset[str] = frozenset()
    require_disambiguation_lemmas: frozenset[str] = frozenset()
    soft_deprioritize_lemmas: frozenset[str] = frozenset()
    apply_lemma_priors: bool = True

    @classmethod
    def from_priors(
        cls,
        priors: Mapping[str, Any] | Iterable[str] | None = None,
        *,
        denylist: frozenset[str] = DEFAULT_DENYLIST,
        priors_path: str | Path | None = None,
        apply_lemma_priors: bool = True,
    ) -> GoldTargetFilter:
        payload: Mapping[str, Any] | Iterable[str] | None = priors
        if priors_path is not None:
            loaded = load_priors_payload(priors_path)
            if payload is None:
                payload = loaded
            elif isinstance(payload, Mapping) and isinstance(loaded, Mapping):
                merged = dict(loaded)
                merged.update(payload)
                payload = merged
            elif isinstance(loaded, list) and not isinstance(payload, Mapping):
                payload = list(payload) + list(loaded)

        blocked = set(prior_blocked_lemmas(payload))
        require: set[str] = set()
        soft: set[str] = set()
        if isinstance(payload, Mapping):
            require |= set(prior_require_disambiguation(payload))
            soft |= set(prior_soft_deprioritize(payload))
        return cls(
            denylist=denylist,
            prior_blocked=frozenset(blocked),
            require_disambiguation_lemmas=frozenset(require),
            soft_deprioritize_lemmas=frozenset(soft),
            apply_lemma_priors=apply_lemma_priors,
        )

    def decide(self, target: str | None) -> TargetFilterDecision:
        target_norm = normalize_target(target)
        if not target_norm:
            return TargetFilterDecision(target_norm="", hard_skip=True, reason=None)
        if target_norm in self.denylist:
            return TargetFilterDecision(
                target_norm=target_norm,
                hard_skip=True,
                reason=REASON_DENYLIST,
            )
        if self.apply_lemma_priors and target_norm in self.prior_blocked:
            return TargetFilterDecision(
                target_norm=target_norm,
                hard_skip=True,
                reason=REASON_LEMMA_PRIOR,
            )
        require = (
            self.apply_lemma_priors and target_norm in self.require_disambiguation_lemmas
        )
        soft = self.apply_lemma_priors and target_norm in self.soft_deprioritize_lemmas
        return TargetFilterDecision(
            target_norm=target_norm,
            hard_skip=False,
            reason=None,
            require_disambiguation=require,
            soft_deprioritize=soft,
        )

    def should_hard_skip(self, target: str | None) -> bool:
        return self.decide(target).hard_skip


def resolve_priors_path(
    *,
    priors_logical: str = DEFAULT_PRIORS_LOGICAL,
    priors_path: str | Path | None = None,
) -> Path | None:
    """Resolve priors file path; ``None`` if unavailable."""
    if priors_path is not None:
        path = Path(priors_path).expanduser()
        return path if path.exists() else None
    try:
        from data_io import resolve

        path = Path(resolve(priors_logical))
    except Exception:
        return None
    return path if path.exists() else None


def load_filter_for_export(
    *,
    apply_lemma_priors: bool = True,
    priors_logical: str = DEFAULT_PRIORS_LOGICAL,
    priors_path: str | Path | None = None,
) -> GoldTargetFilter:
    """Load exporter filter: denylist always; priors when enabled and file exists."""
    if not apply_lemma_priors:
        return GoldTargetFilter(apply_lemma_priors=False)
    path = resolve_priors_path(priors_logical=priors_logical, priors_path=priors_path)
    if path is None:
        return GoldTargetFilter(apply_lemma_priors=True)
    return GoldTargetFilter.from_priors(priors_path=path, apply_lemma_priors=True)


def add_lemma_prior_cli_args(parser: Any) -> None:
    """Shared CLI flags for gold exporters (mutates ``parser``)."""
    parser.add_argument(
        "--no-lemma-priors",
        action="store_true",
        help=(
            "Escape hatch: do not apply gold lemma prior hard/soft lists. "
            "Denylist hard-skip still applies. "
            "Priors default ON (hard-block: min_n=3 & food_pass≤0.2 & drop≥0.75, "
            "or other_sense≥0.5; soft: require_disambiguation / soft_deprioritize)."
        ),
    )
    parser.add_argument(
        "--priors-logical",
        default=DEFAULT_PRIORS_LOGICAL,
        help=f"Manifest logical name for priors JSON (default: {DEFAULT_PRIORS_LOGICAL})",
    )
    parser.add_argument(
        "--priors-path",
        type=Path,
        default=None,
        help="Priors JSON path (overrides --priors-logical)",
    )


def filter_from_cli_args(args: Any) -> GoldTargetFilter:
    """Build filter from argparse namespace produced by ``add_lemma_prior_cli_args``."""
    return load_filter_for_export(
        apply_lemma_priors=not bool(getattr(args, "no_lemma_priors", False)),
        priors_logical=str(getattr(args, "priors_logical", DEFAULT_PRIORS_LOGICAL)),
        priors_path=getattr(args, "priors_path", None),
    )
