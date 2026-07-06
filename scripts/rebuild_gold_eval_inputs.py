#!/usr/bin/env python3
"""Build gold_eval_inputs.jsonl from imported gold.parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gold_io import load_gold_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    args = parser.parse_args()

    gold_path = args.gold_path or Path(resolve("trifecta_gold"))
    out = args.output_path or Path(resolve("trifecta_gold")).parent / "gold_eval_inputs.jsonl"
    records = load_gold_records(gold_path=gold_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            provenance = record["provenance"]
            handle.write(
                json.dumps(
                    {
                        "record_id": provenance["record_id"],
                        "corpus": provenance.get("corpus"),
                        "target_word": provenance.get("target_word"),
                        "context_text": provenance.get("context_text"),
                        "date": provenance.get("date"),
                        "source_path": provenance.get("source_path"),
                        "text_regime": provenance.get("text_regime"),
                        "title": provenance.get("title"),
                    },
                    ensure_ascii=False,
                )
                + "\n",
            )
    print(f"Wrote {len(records)} eval inputs → {out}")


if __name__ == "__main__":
    main()
