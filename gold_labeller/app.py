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


def create_verb_phase2a_app(*, csv_file: str | Path | None = None) -> Flask:
    """Create the verb Phase 2a review UI, preserving model-source columns."""
    from data_io import resolve

    app = Flask(
        "verb_phase2a_labeller",
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )
    app.config["CSV_FILE"] = str(csv_file) if csv_file else str(resolve("verb_phase2a_gold"))

    def _path() -> Path:
        return Path(app.config["CSV_FILE"]).expanduser().resolve()

    def _load():
        path = _path()
        if not path.exists():
            raise FileNotFoundError(f"Phase 2a CSV not found: {path}")
        frame = __import__("pandas").read_csv(path, dtype=str, keep_default_na=False)
        for column in (
            "reviewed_frame",
            "reviewed_lexical_unit",
            "COOKING_CREATION_Method",
            "COOKING_CREATION_Process",
            "COOKING_CREATION_Food_Product",
            "PR_Technique",
            "PR_Medium",
            "PR_Food_Patient",
            "INGESTION_Context",
            "INGESTION_Ingestor",
            "INGESTION_Manner",
            "CURE_Affliction",
            "CURE_Food_Treatment",
            "uncertainty_note",
            "reviewed",
        ):
            if column not in frame.columns:
                frame[column] = ""
        return frame

    def _rows(frame):
        return [{key: str(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]

    def _stats(frame):
        reviewed = frame["reviewed"].astype(str).str.lower().eq("true")
        return {"total": len(frame), "reviewed": int(reviewed.sum()), "pending": int((~reviewed).sum())}

    @app.get("/")
    def phase2a_index():
        frame = _load()
        rows = _rows(frame)
        row = next((item for item in rows if item.get("reviewed", "").lower() != "true"), rows[0])
        return redirect(url_for("phase2a_label", record_id=row["record_id"]))

    @app.get("/label/<record_id>")
    def phase2a_label(record_id: str):
        frame = _load()
        rows = _rows(frame)
        try:
            index = next(i for i, row in enumerate(rows) if row["record_id"] == record_id)
        except StopIteration:
            abort(404)
        row = rows[index]
        return render_template(
            "verb_phase2a_label.html",
            row=row,
            index=index,
            prev_id=rows[index - 1]["record_id"] if index else None,
            next_id=rows[index + 1]["record_id"] if index + 1 < len(rows) else None,
            stats=_stats(frame),
            highlighted=highlight_target(row["context_text"], row["target_word"]),
            frames=["COOKING_CREATION", "CURE", "INGESTION", "PRESERVING", "NONE"],
        )

    @app.post("/save/<record_id>")
    def phase2a_save(record_id: str):
        frame = _load()
        matches = frame.index[frame["record_id"].astype(str) == record_id]
        if len(matches) != 1:
            abort(404)
        allowed = {
            "reviewed_frame",
            "reviewed_lexical_unit",
            "COOKING_CREATION_Method",
            "COOKING_CREATION_Process",
            "COOKING_CREATION_Food_Product",
            "PR_Technique",
            "PR_Medium",
            "PR_Food_Patient",
            "INGESTION_Context",
            "INGESTION_Ingestor",
            "INGESTION_Manner",
            "CURE_Affliction",
            "CURE_Food_Treatment",
            "uncertainty_note",
        }
        index = matches[0]
        for column in allowed:
            frame.at[index, column] = request.form.get(column, "").strip()
        frame.at[index, "reviewed"] = "true" if request.form.get("reviewed") else "false"
        frame.to_csv(_path(), index=False)
        destination = request.form.get("next_record_id") or record_id
        return redirect(url_for("phase2a_label", record_id=destination))

    return app


def create_stepc_app(*, csv_file: str | Path | None = None) -> Flask:
    """Create a Step C qualia review UI for candidate batches or gold CSVs."""
    from data_io import resolve

    app = Flask(
        "stepc_labeller",
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )
    default_csv = Path(resolve("trifecta_gold")).parent / "eval" / "preservare_gold_candidates.csv"
    app.config["CSV_FILE"] = str(csv_file) if csv_file else str(default_csv)

    def _path() -> Path:
        return Path(app.config["CSV_FILE"]).expanduser().resolve()

    def _load():
        path = _path()
        if not path.exists():
            raise FileNotFoundError(f"Step C batch CSV not found: {path}")
        frame = __import__("pandas").read_csv(path, dtype=str, keep_default_na=False)
        for column in (
            "selected_frame",
            "lexical_unit",
            "is_food_entity",
            "dropped",
            "labelled",
            "COOKING_CREATION_Method",
            "COOKING_CREATION_Process",
            "COOKING_CREATION_Food_Product",
            "PR_Technique",
            "PR_Medium",
            "PR_Food_Patient",
            "INGESTION_Context",
            "INGESTION_Ingestor",
            "INGESTION_Manner",
            "INGESTION_Food_Patient",
            "INGESTION_Purpose",
            "CURE_Affliction",
            "CURE_Food_Treatment",
            "notes",
        ):
            if column not in frame.columns:
                frame[column] = ""
        return frame

    def _rows(frame):
        return [{key: str(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]

    def _stats(frame):
        labelled = frame["labelled"].astype(str).str.lower().isin(["true", "1"])
        return {"total": len(frame), "labelled": int(labelled.sum()), "pending": int((~labelled).sum())}

    @app.get("/")
    def stepc_index():
        frame = _load()
        rows = _rows(frame)
        row = next((item for item in rows if item.get("labelled", "").lower() not in ["true", "1"]), rows[0])
        return redirect(url_for("stepc_label", record_id=row["record_id"]))

    @app.get("/label/<record_id>")
    def stepc_label(record_id: str):
        frame = _load()
        rows = _rows(frame)
        try:
            index = next(i for i, row in enumerate(rows) if row["record_id"] == record_id)
        except StopIteration:
            abort(404)
        row = rows[index]
        return render_template(
            "stepc_label.html",
            row=row,
            index=index,
            prev_id=rows[index - 1]["record_id"] if index else None,
            next_id=rows[index + 1]["record_id"] if index + 1 < len(rows) else None,
            stats=_stats(frame),
            highlighted=highlight_target(row["context_text"], row["target_word"]),
            frames=["COOKING_CREATION", "CURE", "INGESTION", "PRESERVING", "NONE"],
        )

    @app.post("/save/<record_id>")
    def stepc_save(record_id: str):
        frame = _load()
        matches = frame.index[frame["record_id"].astype(str) == record_id]
        if len(matches) != 1:
            abort(404)
        allowed = {
            "selected_frame",
            "lexical_unit",
            "is_food_entity",
            "dropped",
            "COOKING_CREATION_Method",
            "COOKING_CREATION_Process",
            "COOKING_CREATION_Food_Product",
            "PR_Technique",
            "PR_Medium",
            "PR_Food_Patient",
            "INGESTION_Context",
            "INGESTION_Ingestor",
            "INGESTION_Manner",
            "INGESTION_Food_Patient",
            "INGESTION_Purpose",
            "CURE_Affliction",
            "CURE_Food_Treatment",
            "notes",
        }
        index = matches[0]
        for column in allowed:
            frame.at[index, column] = request.form.get(column, "").strip()
        frame.at[index, "labelled"] = "True" if request.form.get("labelled") else "False"
        frame.to_csv(_path(), index=False)
        destination = request.form.get("next_record_id") or record_id
        return redirect(url_for("stepc_label", record_id=destination))

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


def main_verb_phase2a() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Verb Phase 2a human-review web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5051)
    parser.add_argument("--csv-path", default=None, help="Override the managed Phase 2a worksheet")
    args = parser.parse_args()

    create_verb_phase2a_app(csv_file=args.csv_path).run(host=args.host, port=args.port)


def main_step_c() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Step C Qualia human-labelling web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5051)
    parser.add_argument("--csv-path", default=None, help="Path to batch CSV to label")
    args = parser.parse_args()

    create_stepc_app(csv_file=args.csv_path).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
