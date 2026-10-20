"""Lineage overview + staleness surfacing for the local DVC-tracked mirrors.

Context: a scratch-tier dataset (``kwic_inputs.jsonl``) was silently
overwritten in October 2026, destroying the only record of the version that
had fed an earlier GijsBERT training export. There was no system record of
this happening. This module answers two questions `data_io.check` never
could: "what produced this dataset" (lineage overview, walking the
manifest's ``parent`` chain) and "has the thing I'm about to use drifted
since it was last mirrored" (staleness check, surfaced inline from
``resolve()``, not via a separate command someone has to remember to run).

Scope is deliberately narrow: only the datasets with a ``<name>_mirror``
entry in the manifest (the small, critical-path ones DVC-tracks locally via
``data_local/``) participate. Everything else keeps behaving exactly as
before.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from data_io.manifest import DataManager, DatasetNotFoundError

# Canonical logical name -> its local DVC-tracked mirror's logical name.
MIRROR_OF: dict[str, str] = {
    "kwic_inputs": "kwic_inputs_mirror",
    "trifecta_gold_csv": "trifecta_gold_csv_mirror",
    "trifecta_annotations": "trifecta_annotations_mirror",
    "inception_nl_v2_iaa_agreed_gold": "inception_nl_v2_iaa_agreed_gold_mirror",
}

_LINEAGE_LOG_NAME = "_lineage_log.jsonl"
_checked_this_process: set[str] = set()


def _repo_root() -> Path:
    """The trifecta-annotation repo root (data_io always lives inside it)."""
    return Path(__file__).resolve().parent.parent


def git_head(repo_root: Path | None = None) -> str | None:
    root = repo_root or _repo_root()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def dvc_hash_for(data_path: Path) -> str | None:
    """Read the md5 hash DVC recorded for *data_path* from its ``.dvc`` sidecar."""
    dvc_file = data_path.with_name(data_path.name + ".dvc")
    if not dvc_file.is_file():
        return None
    try:
        doc = yaml.safe_load(dvc_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    outs = (doc or {}).get("outs") or []
    if not outs:
        return None
    return outs[0].get("md5")


def live_hash_for(path: Path, *, chunk_size: int = 1 << 20) -> str | None:
    """MD5 of *path*'s current bytes on disk (same algorithm DVC uses), or None if missing."""
    if not path.is_file():
        return None
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ChainNode:
    name: str
    tier: str
    phase: str
    description: str
    path: Path
    exists: bool
    dvc_hash: str | None
    mirror_of: str | None  # set when this node IS a mirror, naming what it mirrors


def lineage_chain(manager: DataManager, logical_name: str) -> list[ChainNode]:
    """Walk *logical_name*'s ``parent`` chain (child first), including its mirror if any."""
    chain: list[ChainNode] = []
    seen: set[str] = set()
    name: str | None = logical_name
    while name and name not in seen:
        seen.add(name)
        try:
            dataset = manager.dataset(name)
            resolved = manager.resolve(name)
        except (DatasetNotFoundError, Exception):  # noqa: BLE001 - tier may be unmounted
            break
        mirror_name = MIRROR_OF.get(name)
        mirror_hash = None
        if mirror_name and mirror_name in manager.datasets:
            try:
                mirror_hash = dvc_hash_for(manager.resolve(mirror_name))
            except Exception:  # noqa: BLE001
                mirror_hash = None
        chain.append(
            ChainNode(
                name=name,
                tier=dataset.tier,
                phase=dataset.phase,
                description=dataset.description,
                path=resolved,
                exists=resolved.exists(),
                dvc_hash=mirror_hash,
                mirror_of=None,
            )
        )
        name = dataset.parent or None
    return chain


def overview(logical_name: str, manager: DataManager | None = None) -> str:
    """Human-readable "what produced this, and what state is it in" report."""
    manager = manager or DataManager()
    chain = lineage_chain(manager, logical_name)
    if not chain:
        return f"No lineage found for {logical_name!r} (unknown dataset or tier unavailable)."

    lines = [
        f"trifecta-annotation @ {git_head() or 'unknown commit'}",
        f"Lineage for {logical_name!r}:",
    ]
    for depth, node in enumerate(chain):
        indent = "  " * depth
        arrow = "-> " if depth else ""
        hash_note = f" [dvc:{node.dvc_hash[:10]}]" if node.dvc_hash else ""
        exists_note = "" if node.exists else " (MISSING)"
        lines.append(
            f"{indent}{arrow}{node.name} ({node.tier}/{node.phase}){hash_note}{exists_note}"
            f" — {node.description}"
        )
    stale = check_staleness(logical_name, manager)
    if stale:
        lines.append(f"\n⚠ {stale}")
    return "\n".join(lines)


def check_staleness(logical_name: str, manager: DataManager | None = None) -> str | None:
    """Compare a mirrored dataset's DVC hash to the live scratch file's current hash.

    Returns a warning string if they differ (the mirror is stale relative to
    the scratch original), else None. Cheap: only runs for datasets listed in
    MIRROR_OF, and only hashes files once per process.
    """
    mirror_name = MIRROR_OF.get(logical_name)
    if mirror_name is None:
        return None
    manager = manager or DataManager()
    if mirror_name not in manager.datasets:
        return None
    try:
        live_path = manager.resolve(logical_name)
        mirror_path = manager.resolve(mirror_name)
    except Exception:  # noqa: BLE001 - tier unavailable, nothing to check
        return None

    tracked_hash = dvc_hash_for(mirror_path)
    if tracked_hash is None:
        return None
    live_hash = live_hash_for(live_path)
    if live_hash is None or live_hash == tracked_hash:
        return None
    return (
        f"{logical_name!r} has changed since its local mirror was last synced "
        f"(live md5 {live_hash[:10]} != mirror md5 {tracked_hash[:10]}). "
        f"Re-run scripts/sync_dvc_mirrors.py, and check whether anything built "
        f"from the old version needs to know."
    )


def warn_if_stale(logical_name: str, manager: DataManager | None = None) -> None:
    """Called from DataManager.resolve(); warns at most once per dataset per process."""
    if logical_name in _checked_this_process:
        return
    _checked_this_process.add(logical_name)
    message = check_staleness(logical_name, manager)
    if message:
        warnings.warn(message, stacklevel=3)


def append_lineage_log(
    child_logical: str,
    *,
    parent_logical: str,
    parent_hash: str | None,
    manager: DataManager | None = None,
) -> None:
    """Append-only record: *child_logical* was written against *parent_logical*
    at the recorded hash. Intended for call sites that bypass the DVC mirrors
    entirely (e.g. gold_labeller/store.py saving against a live kwic_inputs).
    """
    manager = manager or DataManager()
    try:
        local_tier_root = manager.tiers["local"].root
    except KeyError:
        return
    local_tier_root.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "child": child_logical,
        "parent": parent_logical,
        "parent_hash": parent_hash,
        "git_commit": git_head(),
    }
    log_path = local_tier_root / _LINEAGE_LOG_NAME
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
