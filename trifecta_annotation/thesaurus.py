"""Build and query the merged TRIFECTA food thesaurus (vectorized pandas)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trifecta_annotation.normalize import normalize_series

THESAURUS_COLUMNS = [
    "pref_label",
    "alias",
    "alias_norm",
    "alias_type",
    "semantic_type",
    "foodon_type",
    "era",
    "source",
    "preservation_tags",
    "snippet_freq",
    "keep_for_trifecta",
    "drop_reason",
]

# High-frequency false positives in embedding/regex snippet matching (not food targets).
DEFAULT_DENYLIST = frozenset(
    {
        "mede",
        "dier",
        "engeland",
        "nederland",
        "frankrijk",
        "spanje",
        "duitschland",
        "italië",
        "italie",
        "zon",
        "boom",
        "plant",
        "broeder",
        "goud",
        "ras",
        "e",
        "geel",
        "wit",
    },
)

_TYPES_SKIP = frozenset({"disagree", "needs_review", "nan", ""})

# Dutch lexicalized compounds — do not split even when a suffix matches a head noun.
LEXICALIZED_COMPOUNDS = frozenset(
    {
        "aardappel",
        "aardappelen",
        "aardbei",
        "aardbeien",
        "aalbes",
        "aalbessen",
        "bloemkool",
        "boterham",
        "brandewijn",
        "haring",
        "kaneel",
        "moeskruid",
        "moeskruiden",
        "pannekoek",
        "pannekoeken",
        "roomboter",
        "spruitjes",
        "zuurkool",
    },
)

# Modifier stems in Dutch modifier+head compounds (incl. historic spellings).
COMPOUND_MODIFIERS = frozenset(
    {
        "arabische",
        "armenische",
        "bloem",
        "bruine",
        "bruin",
        "cadix",
        "cageliary",
        "cleyn",
        "droge",
        "fijn",
        "frans",
        "franse",
        "gekookte",
        "gele",
        "gesneden",
        "goed",
        "goud",
        "graauw",
        "graauwen",
        "groene",
        "groen",
        "hollandsche",
        "hollandse",
        "italiaans",
        "italiaanse",
        "jong",
        "klein",
        "nederlandsche",
        "oud",
        "portugals",
        "rauw",
        "rode",
        "rood",
        "sauoysche",
        "savoij",
        "savooi",
        "spaans",
        "spaanse",
        "verse",
        "vers",
        "witte",
        "wit",
        "zoete",
        "zoute",
        "gezouten",
        "zee",
        "gesoden",
        "bruin",
        "geel",
        "zwart",
        "zwarte",
    },
) | DEFAULT_DENYLIST


def _explode_food_terms(food_terms: pd.DataFrame) -> pd.DataFrame:
    base = food_terms.rename(columns={"Pref_label": "pref_label", "Type": "foodon_type"})
    base["pref_label"] = base["pref_label"].astype(str).str.strip()
    base = base[base["pref_label"].ne("") & base["pref_label"].ne("nan")]

    pref = base[["pref_label", "foodon_type"]].drop_duplicates().assign(
        alias=base["pref_label"],
        alias_type="pref",
        source="food_terms",
        era="early",
    )

    alt_src = base.dropna(subset=["Alt_label"]).copy()
    alt_src["alias"] = alt_src["Alt_label"].astype(str).str.split(",")
    alt = alt_src.explode("alias", ignore_index=True)
    alt["alias"] = alt["alias"].str.strip()
    alt = alt[alt["alias"].ne("")].assign(
        alias_type="alt",
        source="food_terms",
        era="early",
    )

    return pd.concat(
        [pref[["pref_label", "alias", "alias_type", "foodon_type", "source", "era"]],
         alt[["pref_label", "alias", "alias_type", "foodon_type", "source", "era"]]],
        ignore_index=True,
    )


def _explode_categories(categories: pd.DataFrame) -> pd.DataFrame:
    frame = categories.rename(columns={"category": "pref_label", "term": "alias"})
    frame["pref_label"] = frame["pref_label"].astype(str).str.strip()
    frame["alias"] = frame["alias"].astype(str).str.strip()

    # Space-bundled variant lists in categories.term
    bundled = frame[frame["alias"].str.contains(r"\s", regex=True, na=False)].copy()
    bundled["alias"] = bundled["alias"].str.split()
    bundled = bundled.explode("alias", ignore_index=True)
    bundled["alias"] = bundled["alias"].str.strip()

    single = frame[~frame["alias"].str.contains(r"\s", regex=True, na=False)]
    out = pd.concat([single, bundled], ignore_index=True)
    return out[out["alias"].ne("")].assign(
        alias_type="category_variant",
        source="categories",
        era="early",
        foodon_type=pd.NA,
    )


def _explode_modern_curated(path: Path, *, category_col: str, era: str = "modern") -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["pref_label", "alias", "alias_type", "source", "era"])
    frame = pd.read_csv(path)
    if category_col not in frame.columns or "ingredient" not in frame.columns:
        return pd.DataFrame(columns=["pref_label", "alias", "alias_type", "source", "era"])
    kept = frame[frame[category_col].astype(int).eq(1)].copy()
    kept["alias"] = kept["ingredient"].astype(str).str.strip()
    kept["pref_label"] = kept.get("matched_stem", kept["alias"]).astype(str).str.strip()
    kept.loc[kept["pref_label"].eq("") | kept["pref_label"].eq("nan"), "pref_label"] = kept["alias"]
    return kept[["pref_label", "alias"]].assign(
        alias_type="modern",
        source=path.stem,
        era=era,
        foodon_type=pd.NA,
    )


def _attach_semantic_types(frame: pd.DataFrame, types_merged: pd.DataFrame | None) -> pd.DataFrame:
    if types_merged is None or types_merged.empty:
        return frame.assign(semantic_type=pd.NA)
    types = types_merged.rename(columns={"Pref_label": "pref_label", "final_type": "semantic_type"})
    types["pref_label"] = types["pref_label"].astype(str).str.strip()
    types["semantic_type"] = types["semantic_type"].astype(str).str.strip()
    types = types[~types["semantic_type"].isin(_TYPES_SKIP)]
    return frame.merge(types[["pref_label", "semantic_type"]].drop_duplicates(), on="pref_label", how="left")


def _attach_preservation_tags(frame: pd.DataFrame, technique_assoc: pd.DataFrame | None) -> pd.DataFrame:
    if technique_assoc is None or technique_assoc.empty:
        return frame.assign(preservation_tags=pd.NA)

    assoc = technique_assoc.copy()
    assoc["term_norm"] = normalize_series(assoc["term"])
    tags_by_term = (
        assoc.groupby("term_norm", sort=False)["technique"]
        .apply(lambda values: ",".join(sorted(set(values.astype(str)))))
        .rename("preservation_tags")
    )
    out = frame.merge(tags_by_term, left_on="alias_norm", right_index=True, how="left")

    pref_tags = (
        out.dropna(subset=["preservation_tags"])
        .groupby("pref_label", sort=False)["preservation_tags"]
        .apply(lambda values: ",".join(sorted(set(",".join(values).split(",")))))
    )
    out["preservation_tags"] = out["preservation_tags"].fillna(out["pref_label"].map(pref_tags))
    return out


def _compound_parts(
    alias_norm: str,
    *,
    heads: frozenset[str],
    atomic_aliases: frozenset[str],
) -> list[str] | None:
    """Split a compound alias into tokens, or None if atomic/lexicalized."""
    term = str(alias_norm).strip()
    if not term or term in LEXICALIZED_COMPOUNDS:
        return None
    if " " in term:
        return [part for part in term.split() if part]
    if "-" in term:
        parts = [part for part in term.split("-") if part]
        if len(parts) == 2:
            left, right = parts
            if left in COMPOUND_MODIFIERS or (
                right in heads and (left in atomic_aliases or left in heads)
            ):
                return parts
        return None
    for head in sorted(heads, key=len, reverse=True):
        if len(head) < 3 or not term.endswith(head) or term == head:
            continue
        stem = term[: -len(head)]
        if len(stem) < 2:
            continue
        if stem in COMPOUND_MODIFIERS or stem in heads or stem in atomic_aliases:
            return [stem, head]
    return None


def _compound_head(parts: list[str]) -> str | None:
    for token in reversed(parts):
        if len(token) >= 3 and token not in COMPOUND_MODIFIERS:
            return token
    return parts[-1] if parts else None


def _is_decomposable_row(
    alias_norm: str,
    *,
    heads: frozenset[str],
    atomic_aliases: frozenset[str],
) -> bool:
    return _compound_parts(alias_norm, heads=heads, atomic_aliases=atomic_aliases) is not None


def _decompose_compounds(frame: pd.DataFrame) -> pd.DataFrame:
    """Collapse modifier+head compounds onto head nouns; demote compound surface forms."""
    if frame.empty:
        return frame

    single_pref = (
        frame["pref_label"]
        .astype(str)
        .str.strip()
        .loc[lambda s: ~s.str.contains(" ", na=False)]
    )
    atomic_aliases = frozenset(
        frame.loc[
            ~frame["alias_norm"].astype(str).str.contains(r"[\s-]", regex=True, na=False),
            "alias_norm",
        ]
        .astype(str)
        .unique()
    )
    heads = frozenset(
        token
        for token in pd.concat([single_pref, pd.Series(sorted(atomic_aliases))]).astype(str).unique()
        if len(token) >= 3 and token not in {"nan", ""}
    )

    parts_by_alias: dict[str, list[str] | None] = {
        str(alias_norm): _compound_parts(str(alias_norm), heads=heads, atomic_aliases=atomic_aliases)
        for alias_norm in frame["alias_norm"].unique()
    }

    out = frame.copy()
    decompose_mask = out["alias_norm"].map(
        lambda alias_norm: _is_decomposable_row(
            str(alias_norm),
            heads=heads,
            atomic_aliases=atomic_aliases,
        ),
    )
    out.loc[decompose_mask, "keep_for_trifecta"] = "no"
    out.loc[decompose_mask, "drop_reason"] = "compound_decomposed"

    head_tokens: dict[str, dict[str, object]] = {}
    for alias_norm, parts in parts_by_alias.items():
        if not parts:
            continue
        head = _compound_head(parts)
        if not head or len(head) < 3 or head in COMPOUND_MODIFIERS or head in DEFAULT_DENYLIST:
            continue
        if head in head_tokens:
            continue
        source_rows = out[out["alias_norm"].eq(alias_norm)]
        semantic = source_rows["semantic_type"].dropna()
        foodon = source_rows["foodon_type"].dropna()
        pref_match = out[out["pref_label"].astype(str).str.strip().eq(head)]
        pref_label = head
        if not pref_match.empty:
            pref_label = str(pref_match.iloc[0]["pref_label"])
        head_tokens[head] = {
            "pref_label": pref_label,
            "semantic_type": semantic.iloc[0] if not semantic.empty else (
                pref_match["semantic_type"].dropna().iloc[0] if not pref_match.empty and not pref_match["semantic_type"].dropna().empty else pd.NA
            ),
            "foodon_type": foodon.iloc[0] if not foodon.empty else (
                pref_match["foodon_type"].dropna().iloc[0] if not pref_match.empty and not pref_match["foodon_type"].dropna().empty else pd.NA
            ),
            "era": source_rows["era"].iloc[0] if not source_rows.empty else "early",
            "preservation_tags": source_rows["preservation_tags"].dropna().iloc[0]
            if not source_rows.empty and not source_rows["preservation_tags"].dropna().empty
            else pd.NA,
        }

    existing = set(zip(out["pref_label"].astype(str), out["alias_norm"].astype(str)))
    existing_alias_norms = set(out["alias_norm"].astype(str))
    new_rows: list[dict[str, object]] = []
    for head, meta in sorted(head_tokens.items()):
        if head in existing_alias_norms:
            continue
        key = (str(meta["pref_label"]), head)
        if key in existing:
            continue
        new_rows.append(
            {
                "pref_label": meta["pref_label"],
                "alias": head,
                "alias_norm": head,
                "alias_type": "compound_head",
                "semantic_type": meta["semantic_type"],
                "foodon_type": meta["foodon_type"],
                "era": meta["era"],
                "source": "compound_split",
                "keep_for_trifecta": pd.NA,
                "drop_reason": pd.NA,
                "preservation_tags": meta["preservation_tags"],
            },
        )

    if new_rows:
        out = pd.concat([out, pd.DataFrame(new_rows)], ignore_index=True)

    return out


def _assign_keep_flags(
    frame: pd.DataFrame,
    *,
    denylist: frozenset[str] = DEFAULT_DENYLIST,
) -> pd.DataFrame:
    out = frame.copy()
    if "drop_reason" not in out.columns:
        out["drop_reason"] = pd.NA

    on_denylist = out["alias_norm"].isin(denylist)
    out.loc[on_denylist, "keep_for_trifecta"] = "no"
    out.loc[on_denylist, "drop_reason"] = "denylist"

    missing_pref = out["pref_label"].isna() | out["pref_label"].astype(str).str.strip().eq("")
    out.loc[missing_pref, "keep_for_trifecta"] = "no"
    out.loc[missing_pref, "drop_reason"] = "missing_pref_label"

    short_alias = out["alias_norm"].str.len().lt(3)
    out.loc[short_alias & out["keep_for_trifecta"].isna(), "keep_for_trifecta"] = "no"
    out.loc[short_alias & out["drop_reason"].isna(), "drop_reason"] = "too_short"

    conflict_labels = (
        out.groupby("alias_norm", sort=False)["pref_label"]
        .transform("nunique")
        .gt(1)
    )
    out.loc[conflict_labels, "keep_for_trifecta"] = "review"
    out.loc[conflict_labels & out["drop_reason"].isna(), "drop_reason"] = "alias_conflict"

    modern_unlinked = out["era"].eq("modern") & out["alias_type"].eq("modern")
    out.loc[modern_unlinked & out["keep_for_trifecta"].isna(), "keep_for_trifecta"] = "review"
    out.loc[modern_unlinked & out["drop_reason"].isna(), "drop_reason"] = "modern_surface"

    no_semantic = out["semantic_type"].isna() & out["source"].eq("categories")
    out.loc[no_semantic & out["keep_for_trifecta"].isna(), "keep_for_trifecta"] = "review"
    out.loc[no_semantic & out["drop_reason"].isna(), "drop_reason"] = "category_only"

    compound_head = out["alias_type"].eq("compound_head")
    out.loc[compound_head & out["keep_for_trifecta"].isna(), "keep_for_trifecta"] = "yes"

    default_yes = out["keep_for_trifecta"].isna() & out["source"].eq("food_terms")
    out.loc[default_yes, "keep_for_trifecta"] = "yes"

    out["keep_for_trifecta"] = out["keep_for_trifecta"].fillna("review")

    decomposed = out["drop_reason"].eq("compound_decomposed")
    out.loc[decomposed, "keep_for_trifecta"] = "no"
    out.loc[decomposed, "drop_reason"] = "compound_decomposed"

    return out


def _resolve_alias_conflicts(out: pd.DataFrame) -> pd.DataFrame:
    """Pick one canonical kept row per alias_norm when multiple pref_labels compete."""
    conflict_aliases = (
        out.groupby("alias_norm", sort=False)["pref_label"]
        .transform("nunique")
        .gt(1)
    )
    if not conflict_aliases.any():
        return out

    type_rank = {"pref": 0, "alt": 1, "compound_head": 2, "modern": 3, "category_variant": 4}
    frame = out.copy()
    winners: list[int] = []
    for _, group in frame.groupby("alias_norm", sort=False):
        if group["pref_label"].nunique() <= 1:
            continue
        scored = group.copy()
        scored["_canonical"] = scored["alias_norm"].eq(
            scored["pref_label"].astype(str).str.strip(),
        )
        scored["_type_rank"] = scored["alias_type"].map(type_rank).fillna(9)
        scored["_food_terms"] = scored["source"].eq("food_terms")
        winner_idx = scored.sort_values(
            ["_canonical", "_type_rank", "_food_terms"],
            ascending=[False, True, False],
        ).index[0]
        winners.append(winner_idx)

    frame.loc[conflict_aliases, "keep_for_trifecta"] = "review"
    frame.loc[conflict_aliases, "drop_reason"] = "alias_conflict"
    frame.loc[winners, "keep_for_trifecta"] = "yes"
    frame.loc[winners, "drop_reason"] = pd.NA

    decomposed = frame["drop_reason"].eq("compound_decomposed")
    frame.loc[decomposed, "keep_for_trifecta"] = "no"
    return frame


def snippet_term_frequencies(
    snippets: pd.DataFrame | None,
    *,
    term_column: str = "matched_term",
) -> pd.Series:
    """Normalized matched_term → row count in food_snippets_long."""
    if snippets is None or snippets.empty or term_column not in snippets.columns:
        return pd.Series(dtype=int)
    return normalize_series(snippets[term_column]).value_counts()


def _attach_snippet_frequencies(
    frame: pd.DataFrame,
    freq: pd.Series,
) -> pd.DataFrame:
    out = frame.copy()
    if freq.empty:
        out["snippet_freq"] = 0
    else:
        out["snippet_freq"] = out["alias_norm"].map(freq).fillna(0).astype(int)
    return out


def _apply_snippet_freq_filter(
    frame: pd.DataFrame,
    *,
    min_snippet_freq: int,
) -> pd.DataFrame:
    """Drop kept/review aliases that never (or rarely) appear as snippet matched_term."""
    if min_snippet_freq <= 0:
        return frame

    out = frame.copy()
    low = out["snippet_freq"].lt(min_snippet_freq) & out["keep_for_trifecta"].isin(["yes", "review"])
    out.loc[low, "keep_for_trifecta"] = "no"
    out.loc[low & out["drop_reason"].isna(), "drop_reason"] = "low_snippet_freq"
    return out


def build_thesaurus(
    *,
    food_terms: pd.DataFrame,
    categories: pd.DataFrame | None = None,
    types_merged: pd.DataFrame | None = None,
    technique_assoc: pd.DataFrame | None = None,
    modern_curated: list[Path] | None = None,
    denylist: frozenset[str] = DEFAULT_DENYLIST,
    decompose_compounds: bool = True,
    snippets: pd.DataFrame | None = None,
    min_snippet_freq: int = 0,
) -> pd.DataFrame:
    """Merge ontology sources into one alias table (vectorized explode + merge)."""
    parts = [_explode_food_terms(food_terms)]
    if categories is not None and not categories.empty:
        parts.append(_explode_categories(categories))

    for path in modern_curated or []:
        col = {
            "vegetables_curated": "is_vegetable",
            "vlees": "is_vlees",
            "vis": "is_vis",
            "koolhydraten": "is_koolhydraat",
        }.get(path.stem, "is_food")
        part = _explode_modern_curated(path, category_col=col)
        if not part.empty:
            parts.append(part)

    frame = pd.concat(parts, ignore_index=True)
    frame["alias"] = frame["alias"].astype(str).str.strip()
    frame["pref_label"] = frame["pref_label"].astype(str).str.strip()
    frame["alias_norm"] = normalize_series(frame["alias"])

    frame = frame[frame["alias_norm"].ne("")].drop_duplicates(
        subset=["pref_label", "alias_norm", "alias_type"],
        keep="first",
    )

    frame = _attach_semantic_types(frame, types_merged)
    frame = _attach_preservation_tags(frame, technique_assoc)
    if decompose_compounds:
        frame = _decompose_compounds(frame)
    frame = _assign_keep_flags(frame, denylist=denylist)
    frame = _resolve_alias_conflicts(frame)
    frame = _attach_snippet_frequencies(frame, snippet_term_frequencies(snippets))
    frame = _apply_snippet_freq_filter(frame, min_snippet_freq=min_snippet_freq)

    return frame[THESAURUS_COLUMNS].sort_values(
        ["snippet_freq", "keep_for_trifecta", "pref_label", "alias_norm"],
        ascending=[False, True, True, True],
        kind="stable",
    ).reset_index(drop=True)


def filter_long_snippets_frame(
    frame: pd.DataFrame,
    lookup: dict[str, str],
    *,
    term_column: str = "matched_term",
) -> pd.DataFrame:
    """Keep rows whose normalized matched term is in the thesaurus lookup."""
    if not lookup or term_column not in frame.columns:
        return frame
    norms = normalize_series(frame[term_column])
    return frame.loc[norms.isin(lookup)].copy()


def canonical_pref_for_term(term: str, lookup: dict[str, str]) -> str | None:
    if not lookup:
        return None
    from trifecta_annotation.normalize import normalize_hist_dutch

    return lookup.get(normalize_hist_dutch(term))


def alt_label_index(
    thesaurus: pd.DataFrame,
    *,
    kept_only: bool = True,
) -> dict[str, str]:
    """Map normalized alias → pref_label for snippet matching."""
    frame = thesaurus
    if kept_only:
        frame = frame[frame["keep_for_trifecta"].eq("yes")]
    index: dict[str, str] = {}
    for alias_norm, pref in zip(frame["alias_norm"], frame["pref_label"], strict=True):
        if alias_norm and pref and alias_norm not in index:
            index[str(alias_norm)] = str(pref)
    return index


def thesaurus_summary(thesaurus: pd.DataFrame) -> dict[str, int]:
    """Counts for logging."""
    kept = thesaurus[thesaurus["keep_for_trifecta"].eq("yes")]
    summary = {
        "rows": len(thesaurus),
        "pref_labels": int(thesaurus["pref_label"].nunique()),
        "aliases": int(thesaurus["alias_norm"].nunique()),
        **thesaurus["keep_for_trifecta"].value_counts().astype(int).to_dict(),
    }
    if "snippet_freq" in thesaurus.columns:
        summary["kept_with_snippet_hits"] = int((kept["snippet_freq"] > 0).sum())
        summary["snippet_rows_covered"] = int(kept["snippet_freq"].sum())
    return summary
