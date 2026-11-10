from trifecta_annotation.catalogue_genre import _from_record


def rec(titel="X", **schemes):
    return {"titel": titel, "genre_assertions": [
        {"scheme": s, "value": v} for s, vals in schemes.items() for v in vals]}


def test_periodical_title_wins():
    assert _from_record(rec("De Gids. Jaargang 34", dbnl_genre=["proza"])) == ("PERIODICAL", "title")


def test_dbnl_childrens_book_beats_fuzzy_ggc():
    r = rec(dbnl_genre=["jeugdliteratuur"], ggc_subject=["Geschiedenis (vorm)"],
            basisclassificatie=["15.70 geschiedenis van Europa"])
    assert _from_record(r) == ("LITERARY", "dbnl_genre")


def test_ggc_basis_beats_dbnl_proza():
    r = rec(dbnl_genre=["proza"], basisclassificatie=["74.26 geografie van Midden- en Zuid-Amerika"])
    assert _from_record(r) == ("TRAVEL", "ggc_basisclassificatie")


def test_food_relevant_code_wins_among_several():
    r = rec(basisclassificatie=["18.11 Nederlandse letterkunde", "44.42 farmacie, farmaceutica"])
    assert _from_record(r)[0] == "MEDICAL"


def test_non_fictie_alone_stays_unknown():
    assert _from_record(rec(dbnl_genre=["non-fictie"])) is None
