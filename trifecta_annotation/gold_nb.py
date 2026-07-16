"""Notebook helpers for interactive gold CSV labelling (overview + row editor)."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import resolve

from gold_labeller.store import choice_options, highlight_target, is_labelled
from trifecta_annotation.fewshot_export import strip_tgt_markup
from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS
from trifecta_annotation.review_columns import HOMONYM_CHECK_VALUES, HOMONYM_REVIEW_COLUMNS

COOKING_STEP_C_COLUMNS = [
    "COOKING_CREATION_Method",
    "COOKING_CREATION_Process",
    "COOKING_CREATION_Food_Product",
]

STEP_C_FIELD_HINTS = {
    "method": "Heat, tools, manner (e.g. braden, in de oven) — empty if not stated",
    "process": "Cooking action (e.g. smoren, kloppen) — empty if not stated",
    "food_product": "Result dish or ingredient — empty if not stated",
}

_TGT_PATTERN = re.compile(r"\[TGT\](.*?)\[/TGT\]", re.DOTALL)
_EXPORT_NOTE_MARKERS = ("discovery_verb=", "frame_hint=", "kwic_mode=", "candidate_terms:")

# Asymmetric window: less lead-in, target appears in the upper third of the box.
EDITOR_SNIPPET_BEFORE = 90
EDITOR_SNIPPET_AFTER = 220
OVERVIEW_SNIPPET_RADIUS = 150

_SNIPPET_BOX_STYLE = (
    "font-family:Georgia,'Iowan Old Style',serif;font-size:1.28em;line-height:1.75;"
    "white-space:pre-wrap;padding:18px 20px;min-height:9em;"
    "border:1px solid #c9b458;border-radius:8px;background:#fffef5;"
    "box-shadow:inset 0 0 0 1px #fff8dc;"
)
_TARGET_MARK_STYLE = (
    "background:#ffd24d;padding:1px 5px;font-weight:700;border-radius:4px;"
    "box-shadow:0 0 0 1px #d4a90a;text-decoration:none;"
)


def default_cooking_batch_path() -> Path:
    return Path(resolve("trifecta_gold")).parent / "eval" / "cooking_stepc_batch.csv"


def focused_snippet_markup(row: dict[str, str]) -> str:
    """Re-center snippet on target from full context (reliable [TGT] focus)."""
    from trifecta_annotation.clear_frame_examples import target_centered_snippet

    context = str(row.get("context_text", "")).strip()
    target = str(row.get("target_word", "")).strip()
    if context and target:
        verb = str(row.get("lexical_unit", "")).strip() or None
        return target_centered_snippet(
            context,
            target,
            before_radius=EDITOR_SNIPPET_BEFORE,
            after_radius=EDITOR_SNIPPET_AFTER,
            near_verb=verb,
        )
    return str(row.get("review_snippet", "")).strip()


def snippet_preview(row: dict[str, str], *, max_len: int = 120) -> str:
    """Plain-text snippet for the overview table."""
    text = strip_tgt_markup(
        focused_snippet_markup(row)
        if str(row.get("context_text", "")).strip()
        else str(row.get("review_snippet", ""))
    )
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def is_export_note(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _EXPORT_NOTE_MARKERS)


def markup_to_html_body(markup: str) -> str:
    """Convert [TGT]…[/TGT] markup to HTML with a prominent target highlight."""
    parts: list[str] = []
    last = 0
    for match in _TGT_PATTERN.finditer(markup):
        parts.append(html.escape(markup[last : match.start()]))
        parts.append(
            f'<mark style="{_TARGET_MARK_STYLE}">{html.escape(match.group(1))}</mark>',
        )
        last = match.end()
    parts.append(html.escape(markup[last:]))
    return "".join(parts)


def target_callout_html(row: dict[str, str]) -> str:
    """Banner: the word to find, plus the target sentence extracted from markup."""
    target = html.escape(str(row.get("target_word", "")).strip())
    markup = focused_snippet_markup(row)
    sentence = strip_tgt_markup(markup).replace("…", " ").strip()
    if _TGT_PATTERN.search(markup):
        inner = _TGT_PATTERN.search(markup)
        assert inner is not None
        # Show ~short window around target in plain text for IDE search fallback.
        plain = strip_tgt_markup(markup)
        idx = plain.lower().find(inner.group(1).lower())
        if idx >= 0:
            lo = max(0, idx - 60)
            hi = min(len(plain), idx + len(inner.group(1)) + 80)
            sentence = plain[lo:hi]
            if lo > 0:
                sentence = "…" + sentence
            if hi < len(plain):
                sentence = sentence + "…"
    return (
        '<div style="margin:8px 0 10px;padding:10px 14px;border:2px solid #d4a90a;'
        'border-radius:8px;background:#fff9e6;">'
        f'<div style="font-size:0.95em;color:#666;margin-bottom:6px;">'
        "Target word (highlighted in yellow in snippet below, or use Cmd+F):"
        "</div>"
        f'<div style="font-size:1.45em;font-weight:700;letter-spacing:0.02em;">{target}</div>'
        f'<div style="margin-top:8px;font-family:Georgia,serif;font-size:1.05em;line-height:1.5;">'
        f"{html.escape(sentence)}</div></div>"
    )


def snippet_to_html(row: dict[str, str]) -> str:
    """Large, target-centered snippet for the row editor."""
    markup = focused_snippet_markup(row)
    if markup and _TGT_PATTERN.search(markup):
        body = markup_to_html_body(markup)
    else:
        context = str(row.get("context_text", ""))
        target = str(row.get("target_word", ""))
        body = highlight_target(context, target)
    return f'<div style="{_SNIPPET_BOX_STYLE}">{body}</div>'


def export_info_html(row: dict[str, str]) -> str:
    """Read-only miner / export metadata (not annotator input)."""
    miner = html.escape(str(row.get("step_b_reasoning", "")).strip())
    notes = str(row.get("notes", "")).strip()
    export_note = html.escape(notes) if notes and is_export_note(notes) else ""
    parts: list[str] = []
    if miner:
        parts.append(f"<p style='margin:0 0 4px;color:#666;font-size:90%;'><b>miner</b> {miner}</p>")
    if export_note:
        parts.append(
            f"<p style='margin:0;color:#888;font-size:85%;'><b>export</b> {export_note}</p>",
        )
    if not parts:
        return ""
    return (
        '<div style="margin:6px 0 10px;padding:8px;border-left:3px solid #ddd;background:#f8f8f8;">'
        + "".join(parts)
        + "</div>"
    )


def _tri_state_options() -> list[tuple[str, str]]:
    # ipywidgets Dropdown tuples are (label, value).
    return [("—", "__unset__"), ("yes", "true"), ("no", "false")]


def _normalize_bool_csv(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return ""


def _tri_state_from_csv(value: str) -> str:
    normalized = _normalize_bool_csv(value)
    return normalized if normalized else "__unset__"


def _tri_state_to_csv(value: str) -> str:
    return "" if str(value) == "__unset__" else str(value)


def _dropdown_options(values: list[str], *, include_blank: bool = True) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    if include_blank:
        options.append(("—", ""))
    options.extend((value, value) for value in values)
    return options


def _set_dropdown(widget: Any, value: str) -> None:
    text = str(value or "")
    allowed = {opt[1] for opt in widget.options}
    widget.value = text if text in allowed else ""


class GoldBatchEditor:
    """Load a gold candidate CSV, overview with itables, edit rows in memory, save."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser().resolve() if path else default_cooking_batch_path()
        self.df = self.load()

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Batch CSV not found: {self.path}")
        frame = pd.read_csv(self.path, dtype=str, keep_default_na=False)
        for col in GOLD_CSV_COLUMNS:
            if col not in frame.columns:
                frame[col] = ""
        extra = [
            c
            for c in [*HOMONYM_REVIEW_COLUMNS, "review_snippet", "homonym_hint"]
            if c in frame.columns
        ]
        return frame.reindex(columns=[*GOLD_CSV_COLUMNS, *extra], fill_value="")

    def save(self, path: str | Path | None = None) -> Path:
        out = Path(path).expanduser().resolve() if path else self.path
        out.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(out, index=False)
        self.path = out
        return out

    def summary(self) -> dict[str, Any]:
        labelled = self.df["labelled"].astype(str).str.lower().eq("true")
        cooking = self.df["selected_frame"].astype(str).eq("COOKING_CREATION")
        step_c_filled = cooking & labelled & self.df[COOKING_STEP_C_COLUMNS].astype(str).ne("").any(axis=1)
        return {
            "path": str(self.path),
            "rows": len(self.df),
            "labelled": int(labelled.sum()),
            "cooking_creation": int(cooking.sum()),
            "cooking_labelled_with_step_c": int(step_c_filled.sum()),
        }

    def filtered_frame(
        self,
        *,
        frame: str | None = "COOKING_CREATION",
        pending_only: bool = False,
    ) -> pd.DataFrame:
        view = self.df.copy()
        if frame:
            view = view[view["selected_frame"].astype(str) == frame]
        if pending_only:
            rows = view.to_dict(orient="records")
            pending_ids = {str(row["record_id"]) for row in rows if not is_labelled(row)}
            view = view[view["record_id"].astype(str).isin(pending_ids)]
        return view.reset_index(drop=True)

    def overview_frame(
        self,
        *,
        frame: str | None = "COOKING_CREATION",
        pending_only: bool = False,
    ) -> pd.DataFrame:
        """Human-readable overview for itables (snippet-first, short qualia headers)."""
        view = self.filtered_frame(frame=frame, pending_only=pending_only)
        rows: list[dict[str, str]] = []
        for raw in view.to_dict(orient="records"):
            row = {k: str(v) for k, v in raw.items()}
            rows.append(
                {
                    "snippet": snippet_preview(row),
                    "target": row.get("target_word", ""),
                    "regime": row.get("text_regime", ""),
                    "homonym": row.get("homonym_check", ""),
                    "verb": row.get("lexical_unit", ""),
                    "Method": row.get("COOKING_CREATION_Method", ""),
                    "Process": row.get("COOKING_CREATION_Process", ""),
                    "Product": row.get("COOKING_CREATION_Food_Product", ""),
                    "done": "✓" if is_labelled(row) else "",
                },
            )
        return pd.DataFrame(rows)

    def show_overview(self, **kwargs: Any) -> pd.DataFrame:
        """Spreadsheet-style browse/filter table. Requires: uv sync (dev deps)."""
        from itables import init_notebook_mode, show

        init_notebook_mode(all_interactive=True)
        view = self.overview_frame(**kwargs)
        show(
            view,
            column_filters="header",
            maxBytes=0,
            classes="display compact",
            columnDefs=[
                {"targets": 0, "width": "40%"},
            ],
        )
        return view

    def row_dict(self, record_id: str) -> dict[str, str]:
        match = self.df[self.df["record_id"].astype(str) == str(record_id)]
        if match.empty:
            raise KeyError(f"record_id not found: {record_id}")
        return {k: str(v) for k, v in match.iloc[0].to_dict().items()}

    def update(self, record_id: str, **fields: str) -> None:
        mask = self.df["record_id"].astype(str) == str(record_id)
        if not mask.any():
            raise KeyError(f"record_id not found: {record_id}")
        for key, value in fields.items():
            if key not in self.df.columns:
                raise KeyError(f"Unknown column: {key}")
            self.df.loc[mask, key] = str(value)

    def mark_labelled(self, record_id: str, *, labelled: bool = True) -> None:
        self.update(record_id, labelled="true" if labelled else "false")


class RowLabeller:
    """
    Hybrid labeller: itables overview for browsing + ipywidgets form for context-rich edits.

    Hand gold only — no LLM qualia proposals.
    """

    def __init__(
        self,
        editor: GoldBatchEditor | None = None,
        *,
        path: str | Path | None = None,
        frame_filter: str | None = "COOKING_CREATION",
        pending_only: bool = True,
        autosave: bool = True,
    ) -> None:
        self.editor = editor or GoldBatchEditor(path)
        self.frame_filter = frame_filter
        self.pending_only = pending_only
        self.autosave = autosave
        self._pos = 0
        self._record_ids = self._filtered_record_ids()
        self._widgets: dict[str, Any] = {}
        self._built = False

    def refresh(self) -> None:
        """Reload pending row list (e.g. after external CSV edits)."""
        self._record_ids = self._filtered_record_ids()
        if self._record_ids:
            self._pos = min(self._pos, len(self._record_ids) - 1)
        else:
            self._pos = 0
        if self._built:
            self._sync_picker_options()
            self._sync_picker()
            self._load_row_into_form()

    def _filtered_record_ids(self) -> list[str]:
        view = self.editor.filtered_frame(frame=self.frame_filter, pending_only=self.pending_only)
        return view["record_id"].astype(str).tolist()

    def _current_record_id(self) -> str | None:
        if not self._record_ids:
            return None
        self._pos = max(0, min(self._pos, len(self._record_ids) - 1))
        return self._record_ids[self._pos]

    def _picker_label(self, record_id: str) -> str:
        row = self.editor.row_dict(record_id)
        done = "✓" if is_labelled(row) else "·"
        target = row.get("target_word", "")[:18]
        verb = row.get("lexical_unit", "")[:14]
        preview = snippet_preview(row, max_len=36)
        return f"{done} {target} · {verb} · {preview}"

    def _build_widgets(self) -> None:
        from ipywidgets import (
            Accordion,
            Box,
            Button,
            Checkbox,
            Dropdown,
            HTML,
            HBox,
            Text,
            VBox,
            Layout,
        )

        options = choice_options()
        wide = Layout(width="98%")
        self._widgets = {
            "status": HTML(value=""),
            "target_callout": HTML(value=""),
            "context": HTML(value=""),
            "meta": HTML(value=""),
            "export_info": HTML(value=""),
            "homonym_check": Dropdown(
                options=_dropdown_options(sorted(HOMONYM_CHECK_VALUES - {""})),
                description="homonym",
            ),
            "homonym_note": Text(description="note", placeholder="e.g. bloem=flower", layout=wide),
            "text_regime": Dropdown(options=_dropdown_options(options["text_regimes"]), description="regime"),
            "is_food_entity": Dropdown(options=_tri_state_options(), description="food?"),
            "is_metaphor": Dropdown(options=_tri_state_options(), description="metaphor?"),
            "dropped": Dropdown(options=_tri_state_options(), description="dropped"),
            "drop_reason": Dropdown(options=_dropdown_options(options["drop_reasons"]), description="drop_reason"),
            "formal_dimension": Dropdown(
                options=_dropdown_options(options["formal_dimensions"]),
                description="formal_dim",
            ),
            "selected_frame": Dropdown(options=_dropdown_options(options["frames"]), description="frame"),
            "lexical_unit": Text(
                description="frame verb",
                placeholder="miner hint — verify in snippet",
                layout=wide,
            ),
            "method": Text(description="Method", placeholder=STEP_C_FIELD_HINTS["method"], layout=wide),
            "process": Text(description="Process", placeholder=STEP_C_FIELD_HINTS["process"], layout=wide),
            "food_product": Text(
                description="Product",
                placeholder=STEP_C_FIELD_HINTS["food_product"],
                layout=wide,
            ),
            "labelled": Checkbox(description="labelled", value=False),
            "record_picker": Dropdown(description="row", layout=Layout(width="98%")),
            "prev_btn": Button(description="◀ Prev", button_style=""),
            "next_btn": Button(description="Next ▶", button_style=""),
            "save_btn": Button(description="Save", button_style="primary"),
            "save_next_btn": Button(description="Save & next", button_style="success"),
            "refresh_overview_btn": Button(description="Refresh overview"),
        }

        advanced = Accordion(
            children=[
                VBox(
                    [
                        self._widgets["dropped"],
                        self._widgets["drop_reason"],
                        self._widgets["formal_dimension"],
                        self._widgets["selected_frame"],
                    ],
                ),
            ],
            selected_index=None,
            layout=wide,
        )
        advanced.set_title(0, "Advanced (dropout / formal dim / frame override)")
        self._widgets["advanced"] = advanced

        picker = self._widgets["record_picker"]
        self._sync_picker_options()
        if self._record_ids:
            picker.value = self._record_ids[0]

        for name in ("prev_btn", "next_btn", "save_btn", "save_next_btn", "refresh_overview_btn"):
            self._widgets[name].on_click(getattr(self, f"_on_{name}"))

        picker.observe(self._on_picker_change, names="value")
        self._built = True
        self._load_row_into_form()

    def _on_prev_btn(self, _btn: Any) -> None:
        if self._pos > 0:
            self._pos -= 1
            self._sync_picker()
            self._load_row_into_form()

    def _on_next_btn(self, _btn: Any) -> None:
        if self._pos < len(self._record_ids) - 1:
            self._pos += 1
            self._sync_picker()
            self._load_row_into_form()

    def _on_save_btn(self, _btn: Any) -> None:
        self._save_form_to_df()
        if self.pending_only:
            self.refresh()
        self._set_status(self._save_message())

    def _on_save_next_btn(self, _btn: Any) -> None:
        was_pending_only = self.pending_only
        self._save_form_to_df()
        if was_pending_only:
            self.refresh()
        elif self._pos < len(self._record_ids) - 1:
            self._pos += 1
            self._sync_picker()
            self._load_row_into_form()
        self._set_status(self._save_message(moved_next=True))

    def _save_message(self, *, moved_next: bool = False) -> str:
        if self.autosave:
            base = f"Saved to {self.editor.path.name}"
        else:
            base = "Saved in memory (run editor.save() to write CSV)"
        if moved_next:
            suffix = "next pending row." if self.pending_only else "next row."
            return f"{base}; {suffix}"
        return base

    def _on_refresh_overview_btn(self, _btn: Any) -> None:
        self.refresh()
        self.editor.show_overview(frame=self.frame_filter, pending_only=False)
        self._set_status("Queue refreshed; overview shows all rows.")

    def _on_picker_change(self, change: dict[str, Any]) -> None:
        if change.get("name") != "value" or not change.get("new"):
            return
        rid = str(change["new"])
        if rid in self._record_ids:
            self._pos = self._record_ids.index(rid)
            self._load_row_into_form()

    def _sync_picker_options(self) -> None:
        picker = self._widgets["record_picker"]
        picker.options = [(self._picker_label(rid), rid) for rid in self._record_ids] or [
            ("(no pending rows)", ""),
        ]

    def _sync_picker(self) -> None:
        rid = self._current_record_id()
        if rid is not None:
            self._widgets["record_picker"].value = rid

    def _set_status(self, message: str) -> None:
        summary = self.editor.summary()
        rid = self._current_record_id() or "—"
        if self._record_ids:
            pos = f"{self._pos + 1}/{len(self._record_ids)}"
        else:
            pos = "0/0"
        mode = "pending only" if self.pending_only else "all rows"
        self._widgets["status"].value = (
            f"<p><b>{html.escape(message)}</b> · {mode} · queue {pos} · "
            f"<code>{html.escape(rid)}</code> · "
            f"labelled {summary['labelled']}/{summary['rows']}</p>"
        )

    def _set_tri_state(self, widget: Any, value: str) -> None:
        widget.value = _tri_state_from_csv(value)

    def _load_row_into_form(self) -> None:
        rid = self._current_record_id()
        if rid is None:
            self._widgets["context"].value = (
                "<p><i>No pending rows — all labelled in this filter. "
                "Set <code>pending_only=False</code> to review finished rows.</i></p>"
            )
            self._set_status("Queue empty.")
            return
        row = self.editor.row_dict(rid)
        w = self._widgets
        w["target_callout"].value = target_callout_html(row)
        w["context"].value = snippet_to_html(row)
        hint = html.escape(str(row.get("homonym_hint", "")).strip())
        w["meta"].value = (
            "<p style='margin:0 0 6px;font-size:1.05em;'>"
            f"<b>target:</b> {html.escape(row.get('target_word', ''))} · "
            f"<b>regime:</b> {html.escape(row.get('text_regime', '') or 'UNKNOWN')} · "
            f"<b>corpus:</b> {html.escape(row.get('corpus', ''))}"
            f"{f' · <b>homonym risk:</b> <code>{hint}</code>' if hint else ''}"
            "</p>"
        )
        w["export_info"].value = export_info_html(row)
        _set_dropdown(w["homonym_check"], row.get("homonym_check", ""))
        w["homonym_note"].value = row.get("homonym_note", "")
        _set_dropdown(w["text_regime"], row.get("text_regime", ""))
        self._set_tri_state(w["is_food_entity"], row.get("is_food_entity", ""))
        self._set_tri_state(w["is_metaphor"], row.get("is_metaphor", ""))
        self._set_tri_state(w["dropped"], row.get("dropped", ""))
        _set_dropdown(w["drop_reason"], row.get("drop_reason", ""))
        _set_dropdown(w["formal_dimension"], row.get("formal_dimension", ""))
        _set_dropdown(w["selected_frame"], row.get("selected_frame", ""))
        w["lexical_unit"].value = row.get("lexical_unit", "")
        w["method"].value = row.get("COOKING_CREATION_Method", "")
        w["process"].value = row.get("COOKING_CREATION_Process", "")
        w["food_product"].value = row.get("COOKING_CREATION_Food_Product", "")
        w["labelled"].value = str(row.get("labelled", "")).lower() == "true"
        self._set_status("Editing.")

    def _save_form_to_df(self) -> None:
        rid = self._current_record_id()
        if rid is None:
            return
        w = self._widgets
        self.editor.update(
            rid,
            homonym_check=str(w["homonym_check"].value),
            homonym_note=str(w["homonym_note"].value),
            text_regime=str(w["text_regime"].value),
            is_food_entity=_tri_state_to_csv(str(w["is_food_entity"].value)),
            is_metaphor=_tri_state_to_csv(str(w["is_metaphor"].value)),
            dropped=_tri_state_to_csv(str(w["dropped"].value)),
            drop_reason=str(w["drop_reason"].value),
            formal_dimension=str(w["formal_dimension"].value),
            selected_frame=str(w["selected_frame"].value),
            lexical_unit=str(w["lexical_unit"].value),
            COOKING_CREATION_Method=str(w["method"].value),
            COOKING_CREATION_Process=str(w["process"].value),
            COOKING_CREATION_Food_Product=str(w["food_product"].value),
            labelled="true" if w["labelled"].value else "false",
        )
        if self.autosave:
            self.editor.save()
        if not self.pending_only:
            self._sync_picker_options()
            self._widgets["record_picker"].value = rid

    def display(self) -> Any:
        """Show overview + row editor. Call in a notebook cell."""
        from ipywidgets import Box, HBox, HTML, VBox, Layout
        from IPython.display import display

        if not self._built:
            self._build_widgets()

        w = self._widgets
        nav = HBox(
            [w["prev_btn"], w["record_picker"], w["next_btn"], w["save_btn"], w["save_next_btn"]],
            layout=Layout(flex_wrap="wrap"),
        )
        homonym_box = Box(
            layout=Layout(border="1px solid #eee", padding="8px", margin="4px 0"),
            children=[
                HTML("<b>1. Homonym screen</b>"),
                w["homonym_check"],
                w["homonym_note"],
                w["text_regime"],
            ],
        )
        step_a = Box(
            layout=Layout(border="1px solid #eee", padding="8px", margin="4px 0"),
            children=[
                HTML("<b>2. Step A — entity</b>"),
                w["is_food_entity"],
                w["is_metaphor"],
            ],
        )
        step_b = Box(
            layout=Layout(border="1px solid #eee", padding="8px", margin="4px 0"),
            children=[
                HTML("<b>3. Step B — frame verb</b> (miner pre-fill is a hint only)"),
                w["lexical_unit"],
            ],
        )
        step_c = Box(
            layout=Layout(border="1px solid #eee", padding="8px", margin="4px 0"),
            children=[
                HTML(
                    "<b>4. Step C — qualia</b> "
                    "<span style='color:#666;font-weight:normal;'>"
                    "(fill only what the snippet states; leave blank otherwise)"
                    "</span>",
                ),
                w["method"],
                w["process"],
                w["food_product"],
            ],
        )
        panel = VBox(
            [
                HTML("<h3>Gold row editor — hand labels from snippet</h3>"),
                w["status"],
                nav,
                HTML("<h4 style='margin-top:14px;'>Snippet</h4>"),
                w["target_callout"],
                w["context"],
                w["meta"],
                w["export_info"],
                homonym_box,
                step_a,
                w["advanced"],
                step_b,
                step_c,
                w["labelled"],
                HTML(
                    "<h4>Overview — all rows (filter/sort; jump via dropdown above)</h4>",
                ),
                w["refresh_overview_btn"],
            ],
        )
        display(panel)
        self.editor.show_overview(frame=self.frame_filter, pending_only=False)
        return panel
