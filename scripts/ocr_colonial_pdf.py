"""Re-OCR a PDF-only colonial book, page by page, with Tesseract.

The Dodoens `Crŭÿde boeck` ships an embedded text layer produced by a
Latin-type engine run over 16th-century blackletter, which makes it unusable
(measured CER 45-48%). Tesseract's Fraktur model `frk` at `--psm 3` cuts that
to roughly 6% after `normalize_hist_dutch` — see docs/CORPUS_ACQUISITION.md for
the engine comparison, including why Kraken's CATMuS models and Calamari were
rejected.

The decisive property of `frk` is that it emits the real long s `ſ`, which
`normalize_hist_dutch` already maps; every non-Fraktur model emits `f` instead,
which cannot be repaired downstream.

Pages are rendered one at a time and the PNG is deleted immediately: at 300 dpi
a page is ~5 MB, so keeping 776 of them would cost ~4 GB for no benefit. The run
is resumable — a page whose text file already exists is skipped — because a full
book takes well over half an hour.

    uv run python scripts/ocr_colonial_pdf.py --book dodoens
    uv run python scripts/ocr_colonial_pdf.py --book dodoens --pages 1-20
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import time
from pathlib import Path

from data_io import resolve

# Books in `colonial_books` that have no usable text, with the language the
# engine comparison selected for each. Only Dodoens is blackletter; the rest of
# the collection already has a usable embedded layer and must not be re-OCRed.
BOOKS: dict[str, dict[str, str]] = {
    "dodoens": {
        "filename": "Crŭÿde boeck_Dodoens_mobot31753000817624.pdf",
        "lang": "frk",
        "psm": "3",
    },
}

_PAGE_RANGE = re.compile(r"^(\d+)(?:-(\d+))?$")


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    match = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if match is None:
        raise SystemExit(f"could not read page count from {pdf}")
    return int(match.group(1))


def ocr_page(pdf: Path, page: int, lang: str, psm: str, out_dir: Path) -> str:
    """Render one page and recognise it. Returns the text."""
    target = out_dir / f"page_{page:04d}.txt"
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        subprocess.run(
            ["pdftoppm", "-r", "300", "-f", str(page), "-l", str(page), "-png",
             str(pdf), str(stem)],
            check=True, capture_output=True,
        )
        rendered = sorted(Path(tmp).glob("page*.png"))
        if not rendered:
            target.write_text("", encoding="utf-8")
            return ""
        subprocess.run(
            ["tesseract", str(rendered[0]), str(target.with_suffix("")),
             "-l", lang, "--psm", psm],
            check=True, capture_output=True,
        )
    return target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", default="dodoens", choices=sorted(BOOKS))
    parser.add_argument("--pages", help="Page range, e.g. 1-20 (default: all)")
    parser.add_argument("--force", action="store_true", help="Redo pages already written")
    args = parser.parse_args()

    spec = BOOKS[args.book]
    pdf = Path(resolve("colonial_books")) / spec["filename"]
    if not pdf.exists():
        raise SystemExit(f"missing source: {pdf}")

    out_dir = Path(resolve("colonial_books_ocr")) / args.book
    out_dir.mkdir(parents=True, exist_ok=True)

    total = page_count(pdf)
    first, last = 1, total
    if args.pages:
        m = _PAGE_RANGE.match(args.pages)
        if not m:
            raise SystemExit(f"bad --pages {args.pages!r}")
        first = int(m.group(1))
        last = int(m.group(2) or m.group(1))
    last = min(last, total)

    print(f"{args.book}: {total} pages, doing {first}-{last} "
          f"with -l {spec['lang']} --psm {spec['psm']}", flush=True)
    started = time.time()
    done = skipped = 0
    for page in range(first, last + 1):
        target = out_dir / f"page_{page:04d}.txt"
        if target.exists() and not args.force:
            skipped += 1
            continue
        try:
            ocr_page(pdf, page, spec["lang"], spec["psm"], out_dir)
        except subprocess.CalledProcessError as exc:
            print(f"  page {page}: FAILED ({exc})", flush=True)
            continue
        done += 1
        if done % 25 == 0:
            rate = done / (time.time() - started)
            left = (last - page) / rate if rate else 0
            print(f"  {page}/{last}  {rate:.2f} pages/s  ~{left/60:.0f} min left", flush=True)

    combined = out_dir.parent / f"{args.book}_frk.txt"
    parts = sorted(out_dir.glob("page_*.txt"))
    with combined.open("w", encoding="utf-8") as fh:
        for part in parts:
            fh.write(f"\n\n=== page {int(part.stem.split('_')[1])} ===\n")
            fh.write(part.read_text(encoding="utf-8", errors="replace"))
    print(f"done: {done} recognised, {skipped} already present, "
          f"{len(parts)} pages -> {combined} ({combined.stat().st_size/1e6:.1f} MB)",
          flush=True)


if __name__ == "__main__":
    main()
