import datetime as dt

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.model import Sprawa, Termin, Watek, Zadanie, Zdarzenie
from kruczek_core.render import renderuj

D = dt.date


def sprawa() -> Sprawa:
    return Sprawa(
        id="s1", tytul="T", wlasciciel="w", strona_przeciwna="X",
        watki=[Watek("firma", "X")],
        zdarzenia=[Zdarzenie("z1", D(2026, 10, 8), "nadanie", "wezwanie", "firma", ["ARCHIWUM/a.pdf"])],
        terminy=[Termin("t1", "art. 7 u.r.", "z1", "14d", D(2026, 10, 22), "firma", True)],
        zadania=[Zadanie("a1", "sprawdź odpowiedź", D(2026, 10, 23), watek="firma"),
                 Zadanie("a2", "stare", D(2026, 10, 1), zrobione=D(2026, 10, 2))],
    )


def test_dokleja_brakujace_bloki_i_zostawia_wolny_tekst():
    # Arrange
    tekst = "# SPRAWA: T\n\n## Strategia\n\nMoje notatki.\n"
    # Act
    wynik = renderuj(tekst, sprawa(), Kalendarz())
    # Assert
    assert wynik.startswith(tekst)
    assert "<!-- kruczek:chronologia -->" in wynik
    assert "| 2026-10-08 | nadanie | firma | wezwanie | ARCHIWUM/a.pdf |" in wynik
    assert "| t1 | adresata | firma | art. 7 u.r. | 14d | 2026-10-22 | szacunek |" in wynik
    assert "- [ ] a1 — sprawdź odpowiedź (aktywne od 2026-10-23)" in wynik
    assert "stare" not in wynik  # zrobione zadania nie są wypisywane


def test_ponowne_renderowanie_podmienia_zamiast_dublowac():
    # Arrange
    raz = renderuj("# SPRAWA: T\n", sprawa(), Kalendarz())
    # Act
    dwa = renderuj(raz, sprawa(), Kalendarz())
    # Assert
    assert dwa == raz
    assert dwa.count("<!-- kruczek:terminy -->") == 1


def test_opis_z_pionowa_kreska_i_nowa_linia_nie_psuje_tabeli():
    # Arrange
    s = Sprawa(
        id="s2", tytul="T", wlasciciel="w", strona_przeciwna="X",
        zdarzenia=[Zdarzenie("z1", D(2026, 10, 8), "nadanie", "a | b\nc")],
    )
    # Act
    wynik = renderuj("# T\n", s, Kalendarz())
    # Assert
    wiersz = next(l for l in wynik.splitlines() if l.startswith("| 2026-10-08 |"))
    assert "a \\| b c" in wiersz
    assert wiersz.replace("\\|", "").count("|") == 6  # 5 kolumn
