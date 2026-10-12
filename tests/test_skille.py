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


PYTA_USERA = re.compile(r"zapytaj|dopytaj|zapytać|AskUserQuestion|pytaj użytkownika|pytaj usera", re.IGNORECASE)
SKILLE_Z_MODELEM = sorted(k.name for k in SKILLE.iterdir() if (k / "SKILL.md").exists() and "model" in _skill(k.name)[0])


@pytest.mark.parametrize("nazwa", SKILLE_Z_MODELEM)
def test_skill_z_modelem_pyta_usera_przez_askuserquestion(nazwa):
    # Arrange — model komendy obowiązuje w pierwszej turze; odpowiedź w prozie zaczyna nową turę modelem sesji
    pola, tresc = _skill(nazwa)
    if not PYTA_USERA.search(tresc):
        pytest.skip("komenda nie pyta użytkownika")
    # Act
    narzedzia = pola.get("allowed-tools", "").split()
    # Assert
    assert "AskUserQuestion" in narzedzia


def test_pismo_deleguje_redakcje_do_napisz_pismo_przez_pliki():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    napisz, zloz = _sekcja(tresc, 5), _sekcja(tresc, 6)
    # Assert
    assert "napisz-pismo" in napisz and "zawsze" in napisz and "BRIEF.md" in napisz
    assert "Przy złożonej subsumpcji" not in napisz
    assert "--tresc" in zloz and "tresc.html" in zloz


def test_pismo_ogranicza_rundy_poprawek():
    # Arrange
    _, tresc = _skill("pismo")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "najwyżej jedna runda" in krok and "AskUserQuestion" in krok


def test_pismo_sklada_raport_wedlug_skilla_recenzja_i_definiuje_przejscie():
    # Arrange
    _, tresc = _skill("pismo")
    recenzja = (SKILLE / "recenzja" / "SKILL.md").read_text(encoding="utf-8")
    # Act
    krok = _sekcja(tresc, 8)
    # Assert
    assert "skills/recenzja/SKILL.md" in krok and "sekcji Raport" in krok
    assert re.search(r"^## Raport$", recenzja, re.MULTILINE)
    assert "przechodzi, gdy nie ma 🔴" in krok


def test_napisz_pismo_ma_staly_model_opus_i_pisze_plik():
    # Arrange
    tekst = (AGENCI / "napisz-pismo.md").read_text(encoding="utf-8")
    # Assert
    assert _frontmatter(tekst).get("model") == "opus"
    assert "tresc.html" in tekst and "Twierdzenia spoza briefu" in tekst


def test_recenzuj_porownuje_pismo_z_briefem():
    # Arrange
    tekst = (AGENCI / "recenzuj.md").read_text(encoding="utf-8")
    # Assert
    assert "BRIEF.md" in tekst
    assert "weryfikatorem-cytatow" not in tekst


def test_fakt_nie_odsyla_do_samego_siebie():
    # Arrange — model jest już wewnątrz /kruczek:fakt; podpowiedź ma wskazywać następny krok
    _, tresc = _skill("fakt")
    # Assert
    assert "/kruczek:fakt" not in tresc


PLIKI_Z_MANIFESTEM = [SKILLE / "dowod" / "SKILL.md", SKILLE / "pismo" / "SKILL.md", AGENCI / "archiwizuj.md"]


@pytest.mark.parametrize("plik", PLIKI_Z_MANIFESTEM, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_blad_manifestu_pokazuje_sie_userowi_a_index_md_nie_jest_edytowany(plik):
    # Arrange — index.md zawiera notatki użytkownika, więc naprawa „na szybko” przez model je zniszczy
    tresc = plik.read_text(encoding="utf-8")
    # Act
    zdanie = re.search(r"uszkodzone znaczniki.{0,80}popraw\s+ręcznie.{0,300}", tresc, re.DOTALL)
    # Assert
    assert zdanie, "brak reguły: błąd manifestu → pokaż komunikat"
    assert re.search(r"pokaż komunikat\s+użytkownikowi", zdanie.group(0))
    assert re.search(r"nie edytuj\s+`index\.md`", zdanie.group(0))
