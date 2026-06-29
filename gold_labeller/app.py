"""Flask app for hand-labelling TRIFECTA gold CSV rows."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from gold_labeller.store import (
    choice_options,
    csv_path,
    get_row,
    highlight_target,
    is_labelled,
    load_frame,
    next_unlabelled_id,
    record_index,
    rows_as_dicts,
    save_frame,
    stats,
    update_row,
)
from trifecta_annotation.gold_io import annotation_to_labelling_row
from trifecta_annotation.glossary import english_hint_for_term, glossary_en_lookup, read_glossary_csv
from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import KwicInput

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    *,
    csv_logical: str = "trifecta_gold_csv",
    csv_file: str | Path | None = None,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )
    app.config["CSV_LOGICAL"] = csv_logical
    app.config["CSV_FILE"] = str(csv_file) if csv_file else None

    def _path() -> Path:
        return csv_path(app.config["CSV_LOGICAL"], app.config["CSV_FILE"])

    def _glossary_lookup() -> dict[str, str]:
        cached = app.config.get("_GLOSSARY_LOOKUP")
        if cached is not None:
            return cached
        candidates = []
        try:
            from data_io import resolve

            candidates.append(resolve("trifecta_thesaurus_glossary"))
        except Exception:
            pass
        candidates.append(Path(__file__).resolve().parents[1] / "trifecta_thesaurus_glossary.csv")
        lookup: dict[str, str] = {}
        for path in candidates:
            path = Path(path)
            if path.exists():
                lookup = glossary_en_lookup(read_glossary_csv(path))
                break
        app.config["_GLOSSARY_LOOKUP"] = lookup
        return lookup

    def _load():
        return load_frame(_path())

    @app.get("/")
    def index():
        frame = _load()
        record_id = next_unlabelled_id(frame) or rows_as_dicts(frame)[0]["record_id"]
        return redirect(url_for("label_record", record_id=record_id))

    @app.get("/label/<record_id>")
    def label_record(record_id: str):
        frame = _load()
        try:
            idx = record_index(frame, record_id)
        except KeyError:
            abort(404)
        row = get_row(frame, record_id)
        rows = rows_as_dicts(frame)
        prev_id = rows[idx - 1]["record_id"] if idx > 0 else None
        next_id = rows[idx + 1]["record_id"] if idx + 1 < len(rows) else None
        st = stats(frame)
        options = choice_options()
        english_hint = english_hint_for_term(row["target_word"], _glossary_lookup())
        return render_template(
            "label.html",
            row=row,
            index=idx,
            prev_id=prev_id,
            next_id=next_id,
            stats=st,
            options=options,
            highlighted=highlight_target(row["context_text"], row["target_word"]),
            is_done=is_labelled(row),
            english_hint=english_hint,
        )

    @app.get("/api/stats")
    def api_stats():
        return jsonify(stats(_load()))

    @app.get("/api/records")
    def api_records():
        frame = _load()
        items = []
        for idx, row in enumerate(rows_as_dicts(frame)):
            items.append(
                {
                    "index": idx,
                    "record_id": row["record_id"],
                    "target_word": row["target_word"],
                    "labelled": is_labelled(row),
                    "selected_frame": row.get("selected_frame", ""),
                },
            )
        return jsonify(items)

    @app.post("/api/save/<record_id>")
    def api_save(record_id: str):
        frame = _load()
        payload = request.get_json(silent=True) or {}
        try:
            updated = update_row(frame, record_id, payload)
        except KeyError:
            abort(404)
        path = save_frame(updated, _path())
        row = get_row(updated, record_id)
        return jsonify({"ok": True, "path": str(path), "row": row, "stats": stats(updated)})

    @app.post("/api/suggest/<record_id>")
    def api_suggest(record_id: str):
        """Optional LLM draft — user must still review and save."""
        from data_io import resolve

        kwic_records = {
            str(r["record_id"]): r
            for r in __import__("data_io").load_jsonl(resolve("kwic_inputs"))
        }
        raw = kwic_records.get(record_id)
        if raw is None:
            abort(404, description="record not in kwic_inputs")
        ann = annotate_record(KwicInput.model_validate(raw))
        row = annotation_to_labelling_row(
            ann,
            notes="llm_suggest_ui",
            labelled=False,
        )
        return jsonify({"ok": True, "suggestion": row})

    return app


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="TRIFECTA gold labelling web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--csv-logical", default="trifecta_gold_csv")
    parser.add_argument("--csv-path", default=None, help="Override path to gold_labelling.csv")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app(csv_logical=args.csv_logical, csv_file=args.csv_path)
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug or bool(os.environ.get("FLASK_DEBUG")),
    )


if __name__ == "__main__":
    main()
