"""The paradigm generator proposes the forms the infinitive-only lexicon missed (VERB_LEXICON.md, generator a)."""

from trifecta_annotation.verb_forms import forms_for


def test_strong_eten_includes_past_and_participle() -> None:
    f = forms_for("eten")
    assert {"eet", "at", "aten", "gegeten", "eeten"} <= set(f)


def test_historical_drincken_maps_to_strong_paradigm() -> None:
    assert {"drinkt", "dronk", "gedronken", "ghedronken"} <= set(forms_for("drincken"))


def test_weak_koken_open_syllable_and_old_spelling() -> None:
    assert {"kook", "kookt", "kookte", "gekookt", "kooken", "koockt"} <= set(forms_for("koken"))


def test_weak_bakken_degeminates() -> None:
    assert {"bakt", "bakte", "gebakken", "backt"} <= set(forms_for("bakken"))


def test_eren_verb_keeps_unstressed_syllable() -> None:
    f = forms_for("roosteren")
    assert "rooster" in f and "roostert" in f and "geroosterd" in f
    assert "roosteer" not in f


def test_separable_verb_does_not_claim_base_verb_forms() -> None:
    f = forms_for("inmaken")
    assert "ingemaakt" in f and "inmaakt" in f
    assert "maakt" not in f and "maak" not in f


def test_no_doubled_vowel_in_prefix() -> None:
    assert not any(x.startswith(("gee", "ghee", "bee")) and x != "geeten" and x != "gheeten"
                   for x in forms_for("eten"))


def test_vv_for_w_and_final_c() -> None:
    assert "brouvven" in forms_for("brouwen") and "bevvaar" in forms_for("bewaren")
    assert "brac" in forms_for("breken") and "stac" in forms_for("steken")
    assert "kurert" in forms_for("cureren")


def test_s_z_swap_only_before_vowel() -> None:
    assert "zieden" in forms_for("sieden")
    assert not any(x.startswith("zm") for x in forms_for("smaken"))
