"""Grow the GGC subject cache, politely.

Rik's standing instruction is not to hammer the catalogue, so this is the only
place that talks to it, and it:

- never re-requests a title already in the cache (one request per title, ever);
- spaces live requests by `--interval` seconds, single-threaded;
- stops after `--limit` live requests so a run is always bounded.

Pick the titles to fetch with `--select`. Catalogue traffic is the scarce
resource here, not CPU, so the default is the narrowest useful set.

    uv run python scripts/fetch_ggc_subjects.py --select corpus
    uv run python scripts/fetch_ggc_subjects.py --select screened --limit 50
"""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from data_io import resolve

from trifecta_annotation.dbnl_genre import read_titels, title_screen, xml_stems
from trifecta_annotation.text_regime import _WORK_REGIME

SRU = ("https://jsru.kb.nl/sru/sru?operation=searchRetrieve&x-collection=GGC"
       "&query={q}&maximumRecords=5&recordSchema=dcx")
UA = "trifecta-annotation/1.0 (mailto:rik.hoekstra@gmail.com)"
_SPLIT = re.compile(r"[,.]| of | ofte | Deel | Jaargang ")
_YEAR = re.compile(r"1[0-9]{3}")


def short_title(titel: str) -> str:
    return _SPLIT.split(titel or "")[0].strip()


def cache_path(cache_dir: Path, titel: str) -> Path:
    return cache_dir / (hashlib.sha1((titel or "").encode("utf-8")).hexdigest()[:16] + ".xml")


def year(row: dict) -> int | None:
    m = _YEAR.search((row.get("_jaar") or "") + " " + (row.get("jaar") or ""))
    return int(m.group(0)) if m else None


def select(rows: list[dict], mode: str, have_xml: set[str]) -> list[dict]:
    if mode == "corpus":
        # Works the project has already annotated: the per-work regime table is
        # the record of those, so GGC acts as an independent second opinion.
        keys = {k.lstrip("_").rstrip("_01")[:12] for k in _WORK_REGIME}
        return [r for r in rows if r["ti_id"].lstrip("_")[:12] in keys]
    if mode == "screened":
        # Title-screen hits that have text and fall in range — the step-1 pool.
        return [r for r in rows
                if title_screen(r.get("titel", ""))
                and (y := year(r)) and 1500 <= y < 1900
                and r["ti_id"].lstrip("_")[:12] in have_xml]
    raise SystemExit(f"unknown --select {mode!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", default="screened", choices=["corpus", "screened"])
    parser.add_argument("--limit", type=int, default=40, help="Max live requests this run")
    parser.add_argument("--interval", type=float, default=1.5, help="Seconds between requests")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_titels(resolve("dbnl_titels"))
    have_xml = xml_stems(resolve("dbnl_xml"))
    cache_dir = Path(resolve("ggc_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Dedupe by queried title: reprints share a short title and would otherwise
    # each cost a request for the same answer.
    todo: dict[str, dict] = {}
    for row in select(rows, args.select, have_xml):
        if cache_path(cache_dir, row.get("titel", "")).exists():
            continue
        todo.setdefault(short_title(row.get("titel", "")), row)

    pending = list(todo.values())[: args.limit]
    print(f"{len(todo)} uncached titles in --select {args.select}; "
          f"fetching {len(pending)} this run")
    if args.dry_run:
        for row in pending:
            print(f"  would fetch: {short_title(row['titel'])[:60]}")
        return

    for i, row in enumerate(pending, 1):
        if i > 1:
            time.sleep(args.interval)
        q = urllib.parse.quote(f'dc.title="{short_title(row["titel"])}"')
        req = urllib.request.Request(SRU.format(q=q), headers={"User-Agent": UA})
        try:
            body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except Exception as exc:
            print(f"  {i:3d} ERR {short_title(row['titel'])[:44]}: {exc}")
            continue
        cache_path(cache_dir, row["titel"]).write_text(body, encoding="utf-8")
        n = re.search(r"numberOfRecords>(\d+)", body)
        print(f"  {i:3d} n={(n.group(1) if n else '?'):>4} {short_title(row['titel'])[:56]}")
    print("\nnow rebuild the sidecar: uv run python scripts/build_dbnl_genre.py --summary")


if __name__ == "__main__":
    main()
