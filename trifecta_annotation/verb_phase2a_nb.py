"""Interactive notebook editor for verb Phase 2a human review."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd

from trifecta_annotation.gold_nb import snippet_to_html


REVIEW_COLUMNS = (
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
)

_FRAMES = ("COOKING_CREATION", "CURE", "INGESTION", "PRESERVING", "NONE")


class VerbPhase2aLabeller:
    """Row editor that preserves source predictions and autosaves human review."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
        for column in REVIEW_COLUMNS:
            if column not in self.df.columns:
                self.df[column] = ""
        self._pos = 0
        self._widgets: dict[str, Any] = {}

    def summary(self) -> dict[str, int | str]:
        reviewed = self.df["reviewed"].str.lower().eq("true")
        return {"path": str(self.path), "rows": len(self.df), "reviewed": int(reviewed.sum())}

    def save(self) -> Path:
        self.df.to_csv(self.path, index=False)
        return self.path

    def _row(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.df.iloc[self._pos].to_dict().items()}

    def _set_status(self, message: str) -> None:
        reviewed = int(self.df["reviewed"].str.lower().eq("true").sum())
        self._widgets["status"].value = (
            f"<b>{html.escape(message)}</b> · row {self._pos + 1}/{len(self.df)} · "
            f"reviewed {reviewed}/{len(self.df)}"
        )

    def _load(self) -> None:
        row = self._row()
        widgets = self._widgets
        widgets["context"].value = snippet_to_html(row)
        widgets["metadata"].value = (
            f"<p><b>target:</b> {html.escape(row.get('target_word', ''))} · "
            f"<b>source frame:</b> {html.escape(row.get('source_step_b', ''))} · "
            f"<b>source verb:</b> {html.escape(row.get('frame_verb', ''))} · "
            f"<b>regime:</b> {html.escape(row.get('text_regime', 'UNKNOWN'))}</p>"
        )
        widgets["frame"].value = row.get("reviewed_frame", "")
        widgets["verb"].value = row.get("reviewed_lexical_unit", "")
        for column in REVIEW_COLUMNS[2:-1]:
            widgets[column].value = row.get(column, "")
        widgets["reviewed"].value = row.get("reviewed", "").lower() == "true"
        self._set_status("Editing")

    def _save_current(self) -> None:
        widgets = self._widgets
        self.df.loc[self.df.index[self._pos], "reviewed_frame"] = widgets["frame"].value
        self.df.loc[self.df.index[self._pos], "reviewed_lexical_unit"] = widgets["verb"].value
        for column in REVIEW_COLUMNS[2:-1]:
            self.df.loc[self.df.index[self._pos], column] = widgets[column].value
        self.df.loc[self.df.index[self._pos], "reviewed"] = "true" if widgets["reviewed"].value else "false"
        self.save()

    def display(self) -> Any:
        from IPython.display import display
        from ipywidgets import Button, Checkbox, Dropdown, HTML, HBox, Layout, Text, VBox

        wide = Layout(width="98%")
        self._widgets = {
            "status": HTML(),
            "context": HTML(),
            "metadata": HTML(),
            "frame": Dropdown(options=[("-- choose --", ""), *((frame, frame) for frame in _FRAMES)], description="human frame"),
            "verb": Text(description="human verb", layout=wide),
            "reviewed": Checkbox(description="reviewed"),
        }
        labels = {
            "COOKING_CREATION_Method": "Cooking method",
            "COOKING_CREATION_Process": "Cooking process",
            "COOKING_CREATION_Food_Product": "Cooking product",
            "PR_Technique": "Preserving technique",
            "PR_Medium": "Preserving medium",
            "PR_Food_Patient": "Preserved food",
            "INGESTION_Context": "Ingestion context",
            "INGESTION_Ingestor": "Ingestor",
            "INGESTION_Manner": "Ingestion manner",
            "CURE_Affliction": "Affliction",
            "CURE_Food_Treatment": "Treatment",
            "uncertainty_note": "Uncertainty",
        }
        for column, label in labels.items():
            self._widgets[column] = Text(description=label, layout=wide)

        previous = Button(description="Prev")
        next_row = Button(description="Next")
        save = Button(description="Save", button_style="primary")
        save_next = Button(description="Save & next", button_style="success")

        def go_previous(_button: Any) -> None:
            self._save_current()
            self._pos = max(0, self._pos - 1)
            self._load()

        def go_next(_button: Any) -> None:
            self._save_current()
            self._pos = min(len(self.df) - 1, self._pos + 1)
            self._load()

        def save_row(_button: Any) -> None:
            self._save_current()
            self._set_status("Saved")

        def save_and_next(_button: Any) -> None:
            go_next(_button)

        previous.on_click(go_previous)
        next_row.on_click(go_next)
        save.on_click(save_row)
        save_next.on_click(save_and_next)
        self._load()
        panel = VBox(
            [
                HTML("<h3>Verb Phase 2a human review</h3>"),
                self._widgets["status"],
                HBox([previous, next_row, save, save_next]),
                self._widgets["metadata"],
                self._widgets["context"],
                self._widgets["frame"],
                self._widgets["verb"],
                *[self._widgets[column] for column in REVIEW_COLUMNS[2:-1]],
                self._widgets["reviewed"],
            ],
            layout=Layout(width="100%"),
        )
        display(panel)
        return panel