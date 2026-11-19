"""Timed progress report for a long annotation run (Rik, 18 Nov 2026: "not fond of messageless scripts").

Every `--every` minutes: one line on stdout (rows done, rate, finish time, error rows) and a macOS
notification. Waits while the run has not started yet; sends a final notification when the run's process
is gone (finished or stopped), then exits.

    uv run python scripts/run_progress.py --inputs triangulation_b_routed_run_kwic_inputs \\
        --output triangulation_b_routed_annotations --process "triangulation_sample[.]py annotate" --every 60

`--process` is a `pgrep -f` pattern; write one character as a class (`[.]`) so the pattern does not match
this reporter's own command line.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

from data_io import resolve


def count(path: Path) -> tuple[int, int]:
    """(rows, error rows) in a JSONL annotation file."""
    if not path.exists():
        return 0, 0
    n = err = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
                if json.loads(line).get("error"):
                    err += 1
    return n, err


def running(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def machine_state(ollama_url: str) -> str:
    """What the model server has loaded and how much memory is free: the routed run slowed from 5 to 33 s/row
    overnight on identical passages (18-19 Nov 2026), so each report records the machine side too."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{ollama_url}/api/ps", timeout=5) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
        loaded = "ollama: " + (", ".join(models) or "nothing loaded")
    except Exception as e:  # report, never stop the reporter
        loaded = f"ollama: unreachable ({type(e).__name__})"
    try:
        out = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=10).stdout
        free = next((l.split(":")[-1].strip() for l in out.splitlines() if "free percentage" in l), "?")
    except Exception:
        free = "?"
    return f"{loaded}; memory free {free}"


def notify(title: str, msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M} {msg}", flush=True)
    subprocess.run(["osascript", "-e", f"display notification {json.dumps(msg)} with title {json.dumps(title)}"],
                   capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True, help="logical name of the run's input JSONL (for the total)")
    ap.add_argument("--output", required=True, help="logical name of the annotation JSONL being written")
    ap.add_argument("--process", required=True, help="pgrep -f pattern of the run")
    ap.add_argument("--every", type=float, default=60, help="minutes between reports")
    ap.add_argument("--title", default="Annotation run")
    ap.add_argument("--ollama-url", default="http://localhost:11434",
                    help="log what this model server has loaded with each report; '' to switch off")
    a = ap.parse_args()

    total, _ = count(Path(resolve(a.inputs)))
    out = Path(resolve(a.output))
    start_rows, _ = count(out)
    notify(a.title, f"reporter on: {start_rows} of {total} rows present, report every {a.every:g} min")
    t0, n0 = None, start_rows
    if out.exists() and time.time() - out.stat().st_mtime < 120:   # run already writing: clock starts now
        t0 = time.monotonic()
    while running(a.process):
        time.sleep(a.every * 60)
        n, err = count(out)
        if n == n0 and t0 is None:          # scheduled but not started yet
            continue
        if t0 is None:                      # first rows seen: start the clock now (the run may have begun
            t0, n0 = time.monotonic(), n    # anywhere in the last interval, so no rate from this tick)
            notify(a.title, f"run started: {n} of {total} rows; speed and finish time from the next report")
            continue
        rate = (n - n0) / max(time.monotonic() - t0, 1)
        left = total - n
        eta = dt.datetime.now() + dt.timedelta(seconds=left / rate) if rate > 0 else None
        msg = (f"{n} of {total} rows ({n / total:.0%}), {1 / rate:.1f} s/row, done ~{eta:%a %H:%M}" if eta
               else f"{n} of {total} rows, no progress yet")
        notify(a.title, msg + (f", {err} error rows" if err else ""))
        if a.ollama_url:
            print(f"{dt.datetime.now():%H:%M}   machine: {machine_state(a.ollama_url)}", flush=True)
    n, err = count(out)
    notify(a.title, f"run ended: {n} of {total} rows" + (f", {err} error rows" if err else "")
           + ("" if n >= total else " — NOT complete, check the log"))


if __name__ == "__main__":
    main()
