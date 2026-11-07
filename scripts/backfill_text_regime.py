"""Backfill provenance.text_regime on already-annotated rows where scan_text's
noun-fallback path never wrote it (PLAN.md §9i bug, fixed going forward in
scan_text itself as of the `c7be555` commit — this backfills rows annotated
before that fix).

infer_text_regime(corpus, title, source_path) is a pure function of fields
already stored on every row, so this needs no re-harvest and no LLM call.
Dry-run by default; pass --apply to write. Backs up each file before writing
and removes the backup only after the caller has verified the diff (this
script does not delete its own backups).

    uv run python scripts/backfill_text_regime.py           # dry run
    uv run python scripts/backfill_text_regime.py --apply   # write + sidecar
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from data_io import resolve
from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar
from trifecta_annotation.text_regime import infer_text_regime

FILES = ["trifecta_annotations", "dbnl_sweep_annotations", "colonial_annotations", "handdownload_annotations"]


def backfill_one(logical: str, *, apply: bool) -> None:
    path = Path(resolve(logical))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    changed = 0
    for row in rows:
        if row.get("error"):
            continue
        prov = row.get("provenance") or {}
        if prov.get("text_regime"):
            continue
        regime = infer_text_regime(
            corpus=prov.get("corpus"),
            title=prov.get("title"),
            source_path=prov.get("source_path"),
        )
        prov["text_regime"] = regime.value
        changed += 1

    print(f"{logical}: {changed} of {len(rows)} rows backfilled")
    if not apply or changed == 0:
        return

    backup = path.with_suffix(path.suffix + ".bak_regime_backfill")
    shutil.copy2(path, backup)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_sidecar(
        path,
        ProvenanceRecord(
            logical_name=logical,
            phase="semi",
            parent_sources=[],
            description=f"text_regime backfilled on {changed} rows (PLAN.md §9i scan_text bug), no re-annotation",
            created_by_script="scripts/backfill_text_regime.py",
            record_count=len(rows),
            git_commit=git_commit_hash(path.parent),
        ),
    )
    print(f"  wrote {path}  (backup: {backup.name} — verify the diff, then delete it)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for logical in FILES:
        backfill_one(logical, apply=args.apply)
    if not args.apply:
        print("\n(dry run -- pass --apply to write)")


if __name__ == "__main__":
    main()
