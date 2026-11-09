"""Grow the GGC subject cache, politely.

Rik's standing instruction is not to hammer the catalogue, so this is the only
place that talks to it, and it:

- never re-requests a title already in the cache (one request per title, ever);
- spaces live requests by at least `--interval` seconds and at least twice the
  recent response time, single-threaded, backing off exponentially on errors;
- stops after `--limit` live requests so a run is always bounded.

Pick the titles to fetch with `--select`. Catalogue traffic is the scarce
resource here, not CPU, so the default is the narrowest useful set.

    uv run python scripts/fetch_ggc_subjects.py --select corpus
    uv run python scripts/fetch_ggc_subjects.py --select screened --limit 50
    uv run python scripts/fetch_ggc_subjects.py --select unknown --limit 5000
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
UA = "trifecta-annotation/1.0 (mailto:rik.hoekstra@di.huc.knaw.nl)"
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
    if mode == "unknown":
        # Works with annotated rows whose text_regime is UNKNOWN: half of all
        # frames sit there (PLAN §9i), so GGC genre is what makes them usable.
        keys = unknown_regime_work_keys()
        return [r for r in rows if r["ti_id"].lstrip("_")[:12] in keys]
    raise SystemExit(f"unknown --select {mode!r}")


def unknown_regime_work_keys() -> set[str]:
    import json

    keys: set[str] = set()
    for logical in ("trifecta_annotations", "colonial_annotations", "dbnl_sweep_annotations"):
        path = Path(resolve(logical))
        if not path.exists():
            continue
        for line in path.open(encoding="utf-8"):
            if '"UNKNOWN"' not in line:
                continue
            pv = json.loads(line)["provenance"]
            if pv.get("text_regime") == "UNKNOWN" and pv.get("source_path"):
                keys.add(Path(pv["source_path"]).stem.removesuffix("_01").lstrip("_")[:12])
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", default="screened", choices=["corpus", "screened", "unknown"])
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

    # Adaptive pacing: the gap before each request is at least --interval and at
    # least 2x the (smoothed) recent response time, so a catalogue that slows
    # down gets proportionally more breathing room. Errors double a backoff
    # (capped at 5 min) that only decays on success; 10 errors in a row stop the run.
    latency = None          # exponentially smoothed seconds per response
    backoff = 0.0
    errors_in_row = 0
    t_start = time.monotonic()
    for i, row in enumerate(pending, 1):
        if i > 1:
            gap = max(args.interval, 2 * (latency or 0), backoff)
            time.sleep(gap)
        q = urllib.parse.quote(f'dc.title="{short_title(row["titel"])}"')
        req = urllib.request.Request(SRU.format(q=q), headers={"User-Agent": UA})
        t0 = time.monotonic()
        try:
            body = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        except Exception as exc:
            errors_in_row += 1
            backoff = min(300.0, max(backoff * 2, 10.0))
            print(f"  {i:4d} ERR {short_title(row['titel'])[:44]}: {exc} -> backoff {backoff:.0f}s", flush=True)
            if errors_in_row >= 10:
                print("10 errors in a row: stopping; rerun later (cache resumes)", flush=True)
                break
            continue
        dt = time.monotonic() - t0
        latency = dt if latency is None else 0.8 * latency + 0.2 * dt
        errors_in_row = 0
        backoff = backoff / 2 if backoff > 1 else 0.0
        cache_path(cache_dir, row["titel"]).write_text(body, encoding="utf-8")
        n = re.search(r"numberOfRecords>(\d+)", body)
        eta = (len(pending) - i) * (time.monotonic() - t_start) / i / 60
        print(f"  {i:4d} n={(n.group(1) if n else '?'):>4} {dt:4.1f}s (avg {latency:4.1f}s, ~{eta:.0f} min left) "
              f"{short_title(row['titel'])[:50]}", flush=True)
    print("\nnow rebuild the sidecar: uv run python scripts/build_dbnl_genre.py --summary")


if __name__ == "__main__":
    main()
