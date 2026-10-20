#!/usr/bin/env python3
"""Refresh the local DVC-tracked mirrors of the critical-path scratch datasets.

Copies each dataset in ``data_io.lineage.MIRROR_OF`` from its live scratch
location into ``data_local/``, runs ``dvc add``, and pushes to the
configured DVC remote. Run this after re-running an ingest script
(``build_kwic_inputs.py``, a gold export, a full batch run) so the local
mirror — and therefore ``python -m data_io overview`` and the inline
staleness check in ``resolve()`` — reflects the current scratch content
instead of silently going stale.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from data_io import get_manager
from data_io.lineage import MIRROR_OF, dvc_hash_for, live_hash_for


def sync_one(canonical: str, mirror: str, *, manager) -> tuple[bool, str]:
    live_path = manager.resolve(canonical)
    mirror_path = manager.resolve(mirror)
    if not live_path.exists():
        return False, f"{canonical}: live file missing at {live_path}, skipped"

    old_hash = dvc_hash_for(mirror_path)
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    mirror_path.write_bytes(live_path.read_bytes())
    new_hash = live_hash_for(mirror_path)

    if old_hash == new_hash:
        return False, f"{canonical}: unchanged ({new_hash[:10]})"
    return True, f"{canonical}: {old_hash[:10] if old_hash else '(none)'} -> {new_hash[:10]}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--push",
        action="store_true",
        help="Also run `dvc push` after re-adding changed mirrors.",
    )
    args = parser.parse_args(argv)

    manager = get_manager(reload=True)
    repo_root = Path(__file__).resolve().parents[1]

    changed: list[str] = []
    for canonical, mirror in MIRROR_OF.items():
        try:
            did_change, message = sync_one(canonical, mirror, manager=manager)
        except Exception as exc:  # noqa: BLE001
            print(f"{canonical}: ERROR — {exc}", file=sys.stderr)
            continue
        print(message)
        if did_change:
            changed.append(manager.resolve(mirror).relative_to(manager.tiers["local"].root).as_posix())

    if not changed:
        print("\nNo mirrors changed.")
        return

    print(f"\nRe-adding {len(changed)} changed mirror(s) to DVC...")
    subprocess.run(
        ["dvc", "add", *[str(Path("data_local") / c) for c in changed]],
        cwd=repo_root,
        check=True,
    )

    if args.push:
        subprocess.run(["dvc", "push"], cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
