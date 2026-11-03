"""Lineage overview + staleness surfacing for DVC-tracked dataset mirrors.

A dataset can declare, in ``data_manifest.toml``, a ``mirror_of`` field
pointing at another logical name it is a (typically local, DVC-tracked)
snapshot of::

    [datasets.kwic_inputs_mirror]
    tier = "local"
    path = "kwic_inputs.jsonl"
    mirror_of = "kwic_inputs"

This module answers two questions plain ``resolve()`` never could: "what
produced this dataset" (``overview``, walking the manifest's ``parent``
chain) and "has the thing I'm about to use drifted since it was last
mirrored" (``check_staleness``, surfaced inline from ``DataManager.resolve``,
not via a separate command someone has to remember to run).

Context: ``kwic_inputs.jsonl`` was silently overwritten on 2026-10-14,
destroying the only record of the version that had fed the July 2026
GijsBERT training export. Reconstructing what happened took manual
cross-referencing of a ``.meta.toml`` timestamp, row counts, and git commit
dates. See ``docs/DATA_LINEAGE.md``.

Nothing here requires DVC to be installed at import time — DVC is only
needed to actually run ``dvc add``/``dvc push``; reading a ``.dvc`` sidecar
is just YAML. Projects that never declare a ``mirror_of`` entry pay for
none of this: every function below is a no-op when there's nothing to
check. This module originates in ``republic_ner_matching/data_io`` and is
vendored here via ``dighum_template``'s sync mechanism — see
``docs/DATA_LINEAGE.md`` before editing it directly, since local changes
won't survive the next ``--data-io`` sync.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from data_io.manifest import DataManager, DatasetNotFoundError

_LINEAGE_LOG_NAME = "_lineage_log.jsonl"
_checked_this_process: set[str] = set()


def mirror_map(manager: DataManager) -> dict[str, str]:
    """canonical logical name -> its mirror's logical name, from the manifest."""
    return {
        dataset.mirror_of: name
        for name, dataset in manager.datasets.items()
        if dataset.mirror_of
    }


def _repo_root() -> Path:
    """Best-effort project root: walk up from this file until a .git dir shows up."""
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return here.parent


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
    import yaml

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


def lineage_chain(manager: DataManager, logical_name: str) -> list[ChainNode]:
    """Walk *logical_name*'s ``parent`` chain (child first), noting any mirror's DVC hash."""
    mirrors = mirror_map(manager)
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
        mirror_name = mirrors.get(name)
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
        f"repo @ {git_head() or 'unknown commit'}",
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
    """Compare a mirrored dataset's DVC hash to the live source file's current hash.

    Returns a warning string if they differ (the mirror is stale relative to
    its source), else None. Only runs for datasets that have a `mirror_of`
    sibling declared in the manifest; otherwise this is a no-op.
    """
    manager = manager or DataManager()
    mirror_name = mirror_map(manager).get(logical_name)
    if mirror_name is None or mirror_name not in manager.datasets:
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
        f"{logical_name!r} has changed since its mirror ({mirror_name!r}) was last "
        f"synced (live md5 {live_hash[:10]} != mirror md5 {tracked_hash[:10]}). "
        f"Re-sync the mirror (e.g. `python -m data_io sync-mirrors`), and check "
        f"whether anything built from the old version needs to know."
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
    entirely (e.g. an interactive labelling tool saving against a live input).
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


def sync_mirrors(manager: DataManager | None = None, *, push: bool = False) -> list[str]:
    """Refresh every mirror declared via `mirror_of` from its live source.

    Copies each changed source into its mirror's path, returns the list of
    logical mirror names that changed (ready for `dvc add`). Does not shell
    out to `dvc` itself for the add step — callers (e.g. the `data_io`
    CLI) own that so this stays testable without DVC installed.
    """
    manager = manager or DataManager()
    changed: list[str] = []
    for canonical, mirror_name in mirror_map(manager).items():
        try:
            live_path = manager.resolve(canonical)
            mirror_path = manager.resolve(mirror_name)
        except Exception:  # noqa: BLE001
            continue
        if not live_path.exists():
            continue
        old_hash = dvc_hash_for(mirror_path)
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        mirror_path.write_bytes(live_path.read_bytes())
        new_hash = live_hash_for(mirror_path)
        if old_hash != new_hash:
            changed.append(mirror_name)
    return changed
