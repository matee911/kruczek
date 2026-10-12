"""Testy strukturalne skilli i agentów: rzeczy, których nie złapie żaden test kodu, a które psują
zachowanie komend (np. krok, którego model nie może wykonać)."""

import re
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parent.parent
SKILLE = KORZEN / "skills"
AGENCI = KORZEN / "agents"
WZMIANKA = re.compile(r"/kruczek:([a-z-]+)")
# Komenda z disable-model-invocation jest niewidoczna dla modelu — wolno ją tylko podpowiedzieć użytkownikowi.
PODPOWIEDZ_DLA_USERA = re.compile(r"zaproponuj|podpowiedz|użytkownikowi|podpowiedź dla użytkownika", re.IGNORECASE)


def _frontmatter(tekst: str) -> dict[str, str]:
    _, naglowek, _ = tekst.split("---", 2)
    pola = {}
    for linia in naglowek.splitlines():
        if ":" in linia and not linia.startswith((" ", "\t")):
            klucz, wartosc = linia.split(":", 1)
            pola[klucz.strip()] = wartosc.strip()
    return pola


def _skill(nazwa: str) -> tuple[dict[str, str], str]:
    tekst = (SKILLE / nazwa / "SKILL.md").read_text(encoding="utf-8")
    return _frontmatter(tekst), tekst.split("---", 2)[2]


def _sekcja(tresc: str, numer: int) -> str:
    """Treść sekcji „## <numer>. …” do następnego nagłówka „## ”."""
    m = re.search(rf"^## {numer}\..*?(?=^## |\Z)", tresc, re.MULTILINE | re.DOTALL)
    assert m, f"brak sekcji {numer}"
    return m.group(0)


def _niewidoczne_dla_modelu() -> set[str]:
    return {k.name for k in SKILLE.iterdir()
            if (k / "SKILL.md").exists() and _skill(k.name)[0].get("disable-model-invocation") == "true"}


def martwe_wzmianki(tresc: str, niewidoczne: set[str], wlasna: str = "") -> list[str]:
    """Linie, które wymieniają komendę niewidoczną dla modelu bez znacznika podpowiedzi dla usera.

    >>> martwe_wzmianki("```\\n/kruczek:kontrola  # mechanicznie\\n/kruczek:recenzja  # merytorycznie\\n```", {"recenzja"})
    ['/kruczek:recenzja  # merytorycznie']
    >>> martwe_wzmianki("zaproponuj `/kruczek:recenzja`\\n| `/kruczek:recenzja` | spis |", {"recenzja"})
    []
    """
    zle = []
    for linia in tresc.splitlines():
        if linia.lstrip().startswith("|") or PODPOWIEDZ_DLA_USERA.search(linia):
            continue
        if any(m.group(1) in niewidoczne and m.group(1) != wlasna for m in WZMIANKA.finditer(linia)):
            zle.append(linia.strip())
    return zle


PLIKI_Z_INSTRUKCJAMI = sorted([*SKILLE.glob("*/SKILL.md"), *AGENCI.glob("*.md")])


@pytest.mark.parametrize("plik", PLIKI_Z_INSTRUKCJAMI, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_instrukcje_nie_wymieniaja_komendy_niewidocznej_bez_podpowiedzi_dla_usera(plik):
    # Arrange
    tresc = plik.read_text(encoding="utf-8").split("---", 2)[2]
    wlasna = plik.parent.name if plik.name == "SKILL.md" else plik.stem
    # Act
    martwe = martwe_wzmianki(tresc, _niewidoczne_dla_modelu(), wlasna)
    # Assert
    assert martwe == []


def test_dawny_krok_recenzji_w_pismie_jest_wykrywany():
    # Arrange — krok 8 /kruczek:pismo w wersji 0.10.0: blok kodu z komendami, bez czasownika
    dawny = "```\n/kruczek:kontrola     # mechanicznie: numeracja\n/kruczek:recenzja     # merytorycznie: fakty\n```"
    # Act
    martwe = martwe_wzmianki(dawny, _niewidoczne_dla_modelu(), "pismo")
    # Assert
    assert martwe == ["/kruczek:recenzja     # merytorycznie: fakty"]


def test_pismo_recenzuje_przez_agentow_a_nie_komende_usera():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "weryfikuj-cytaty" in krok and "recenzuj" in krok
    assert martwe_wzmianki(krok, {"recenzja"}) == []
