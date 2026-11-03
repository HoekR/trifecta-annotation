"""English reviewer hints for cross-lingual LLM scratch experiments."""

from __future__ import annotations

from pathlib import Path

from trifecta_annotation.glossary import (
    english_hint_for_term,
    glossary_en_lookup,
    read_glossary_csv,
)


def resolve_glossary_path() -> Path | None:
    """Project glossary CSV, then scratch copy."""
    candidates = [
        Path(__file__).resolve().parents[1] / "trifecta_thesaurus_glossary.csv",
    ]
    try:
        from data_io import resolve

        candidates.append(Path(resolve("trifecta_thesaurus_glossary")))
    except Exception:
        pass
    for path in candidates:
        if path.exists():
            return path
    return None


def review_hint_lookup_from_glossary(glossary_path: str | Path) -> dict[str, str]:
    """Map Dutch target tokens to ``English term — gloss`` reviewer hints."""
    frame = read_glossary_csv(glossary_path)
    en_lookup = glossary_en_lookup(frame)
    gloss_by_en: dict[str, str] = {}
    for _, row in frame.iterrows():
        en = str(row.get("pref_label_en") or "").strip()
        gloss = str(row.get("gloss_en") or "").strip()
        if en and gloss:
            gloss_by_en[en.lower()] = gloss

    hints: dict[str, str] = {}
    for term, en in en_lookup.items():
        gloss = gloss_by_en.get(en.lower(), "")
        hints[term] = f"{en} — {gloss}" if gloss else en
    return hints


def default_review_hint_lookup() -> dict[str, str]:
    path = resolve_glossary_path()
    if path is None:
        return {}
    return review_hint_lookup_from_glossary(path)


def review_hint_for_term(term: str, lookup: dict[str, str]) -> str:
    return lookup.get((term or "").strip().lower(), "")


def append_english_hint_block(user_prompt: str, english_hint: str | None) -> str:
    if not english_hint:
        return user_prompt
    return (
        f"{user_prompt}\n\n"
        "English reviewer hint (terminology only; judge the Dutch passage):\n"
        f"{english_hint}"
    )
