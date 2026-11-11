"""Trifecta and EU logos for the notebooks (embedded as data URIs, so the .ipynb and its HTML render stand alone).

Logos from https://trifecta.dhlab.nl/ (assets/logos/). Used by the notebook generators: `cells=[logo_cell()] + CELLS + [eu_cell()]`.
"""

from __future__ import annotations

import base64
from pathlib import Path

import nbformat as nbf

LOGOS = Path(__file__).resolve().parents[1] / "assets" / "logos"


def _img(name: str, alt: str, height: int) -> str:
    data = base64.b64encode((LOGOS / name).read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{alt}" style="height:{height}px; margin-right:24px">'


def logo_cell():
    """Top of the notebook: the Trifecta logo."""
    return nbf.v4.new_markdown_cell(_img("trifecta.png", "Trifecta logo: three palm trees", 90))


def eu_cell():
    """Bottom of the notebook: the EU funding emblem."""
    return nbf.v4.new_markdown_cell(_img("funded_by_eu.png", "Funded by the European Union", 80))
