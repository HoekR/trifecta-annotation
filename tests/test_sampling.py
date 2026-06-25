"""Stratified sampling tests."""

import pandas as pd

from trifecta_annotation.sampling import stratified_row_indices


def test_stratified_row_indices_spreads_works() -> None:
    rows = []
    for work in ("Work A", "Work B", "Work C"):
        for index in range(5):
            rows.append(
                {
                    "doc_id": f"{work}-{index}",
                    "filename": f"{work}.xml",
                    "title": work,
                    "snippet": f"men gebruikt zout in recept {index}",
                    "original_found_terms": "['zout']",
                },
            )
    frame = pd.DataFrame(rows)
    indices = stratified_row_indices(frame, limit=6, seed=1, max_per_work=2)
    assert len(indices) == 6
    works = {frame.loc[i, "title"] for i in indices}
    assert len(works) == 3


def test_row_has_target_via_indices() -> None:
    frame = pd.DataFrame(
        [
            {
                "doc_id": "1",
                "filename": "a.xml",
                "title": "A",
                "snippet": "geen voedsel hier",
                "original_found_terms": "['zout']",
            },
            {
                "doc_id": "2",
                "filename": "b.xml",
                "title": "B",
                "snippet": "met zout en peper",
                "original_found_terms": "['zout', 'peper']",
            },
        ],
    )
    indices = stratified_row_indices(frame, limit=5, seed=0)
    assert list(indices) == [1]
