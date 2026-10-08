import datetime as dt

import pytest

from kruczek_core.terminy import koniec_nominalny, koniec_terminu, parsuj_dlugosc

D = dt.date


@pytest.mark.parametrize(
    "start, dlugosc, oczekiwany, opis",
    [
        (D(2026, 10, 8), "14d", D(2026, 10, 22), "zwykły czwartek"),
        (D(2026, 10, 3), "14d", D(2026, 10, 19), "koniec w sobotę → poniedziałek"),
        (D(2026, 10, 4), "14d", D(2026, 10, 19), "koniec w niedzielę → poniedziałek"),
        (D(2025, 12, 10), "14d", D(2025, 12, 29), "Wigilia, święta, sobota, niedziela"),
        (D(2024, 12, 10), "14d", D(2024, 12, 24), "Wigilia 2024 nie była wolna"),
        (D(2018, 10, 29), "14d", D(2018, 11, 13), "jednorazowy 12.11.2018"),
        (D(2026, 1, 31), "1m", D(2026, 3, 2), "31.01 + 1m → 28.02 (sobota) → 2.03"),
        (D(2024, 2, 29), "1r", D(2025, 2, 28), "29 lutego + rok → 28 lutego"),
        (D(2005, 3, 25), "14d", D(2005, 4, 8), "dzień tylko dla urzędów nie przesuwa"),
        (D(2026, 3, 23), "14d", D(2026, 4, 7), "Poniedziałek Wielkanocny"),
        (D(2026, 10, 7), "2t", D(2026, 10, 21), "tygodnie: ten sam dzień tygodnia"),
        (D(2026, 10, 8), "30d", D(2026, 11, 9), "30 dni, koniec w sobotę"),
        (D(2026, 10, 22), "10d", D(2026, 11, 2), "Wszystkich Świętych w niedzielę"),
    ],
)
def test_koniec_terminu(start, dlugosc, oczekiwany, opis, kalendarz):
    # Act
    wynik = koniec_terminu(start, dlugosc, kalendarz)
    # Assert
    assert wynik == oczekiwany, opis


def test_dzien_zdarzenia_nie_jest_liczony():
    """Art. 111 § 2 k.c.: 1 dzień od 8.10 kończy się 9.10, nie 8.10."""
    # Act
    wynik = koniec_nominalny(D(2026, 10, 8), "1d")
    # Assert
    assert wynik == D(2026, 10, 9)


@pytest.mark.parametrize("tekst", ["14", "0d", "2 tygodnie", "14D", "", "d14"])
def test_zla_dlugosc(tekst):
    # Act / Assert
    with pytest.raises(ValueError, match="nieznana długość terminu"):
        parsuj_dlugosc(tekst)
