import datetime as dt

import holidays
import pytest

from kruczek_core.dni_wolne import (
    PIERWSZY_ROK,
    DzienJednorazowy,
    dni_ustawowo_wolne,
    wczytaj_jednorazowe,
    wczytaj_kalendarz,
    wielkanoc,
    zapisz_jednorazowy,
)

D = dt.date


@pytest.mark.parametrize(
    "rok, oczekiwana",
    [
        (2000, D(2000, 4, 23)),
        (2018, D(2018, 4, 1)),
        (2024, D(2024, 3, 31)),
        (2025, D(2025, 4, 20)),
        (2026, D(2026, 4, 5)),
        (2038, D(2038, 4, 25)),
    ],
)
def test_wielkanoc(rok, oczekiwana):
    # Act
    wynik = wielkanoc(rok)
    # Assert
    assert wynik == oczekiwana


@pytest.mark.parametrize("rok", range(PIERWSZY_ROK, 2041))
def test_zgodnosc_z_pakietem_holidays(rok, kalendarz):
    """Niezależny sprawdzian: nasze reguły z ustawy vs kalendarz PL z pakietu holidays.

    Przy rozbieżności NIE dopasowuj kodu do holidays — sprawdź w ELI, kto ma rację.
    """
    # Arrange
    wzorzec = set(holidays.Poland(years=rok))
    jednorazowe = {j.data for j in kalendarz.jednorazowe if j.data.year == rok and not j.tylko_urzedy}
    # Act
    nasze = set(dni_ustawowo_wolne(rok)) | jednorazowe
    # Assert
    assert nasze == wzorzec


@pytest.mark.parametrize(
    "dzien, wolny",
    [
        (D(2010, 1, 6), False),  # przed wprowadzeniem Trzech Króli
        (D(2011, 1, 6), True),
        (D(2024, 12, 24), False),  # Wigilia wolna dopiero od 1.02.2025
        (D(2025, 12, 24), True),
        (D(2018, 11, 12), True),  # jednorazowy, ustawa z 7.11.2018
        (D(2005, 4, 8), False),  # tylko urzędy — nie „ustawowo wolny”
        (D(2026, 10, 11), True),  # niedziela
        (D(2026, 10, 10), False),  # sobota nie jest dniem wolnym
        (D(2026, 4, 6), True),  # Poniedziałek Wielkanocny
        (D(2026, 6, 4), True),  # Boże Ciało (Wielkanoc 5.04 + 60)
    ],
)
def test_czy_wolny(dzien, wolny, kalendarz):
    # Act
    wynik = kalendarz.czy_wolny(dzien)
    # Assert
    assert wynik is wolny


def test_sobota_przesuwa_termin(kalendarz):
    # Act / Assert
    assert kalendarz.czy_przesuwa(D(2026, 10, 10)) is True
    assert kalendarz.czy_przesuwa(D(2026, 10, 9)) is False


def test_dzien_tylko_dla_urzedow_daje_ostrzezenie_bez_przesuniecia(kalendarz):
    # Act
    przesuwa = kalendarz.czy_przesuwa(D(2005, 4, 8))
    ostrzezenia = kalendarz.ostrzezenia(D(2005, 4, 8))
    # Assert
    assert przesuwa is False
    assert len(ostrzezenia) == 1
    assert "urzędy zamknięte" in ostrzezenia[0]


def test_lata_przed_2000_odrzucone():
    # Act / Assert
    with pytest.raises(ValueError, match="1999"):
        dni_ustawowo_wolne(1999)


def test_zapis_jednorazowego_bez_duplikatow(tmp_path):
    # Arrange
    plik = tmp_path / ".kruczek" / "dni-wolne.json"
    dzien = DzienJednorazowy(D(2030, 1, 2), "Dz.U. 2029 poz. 1")
    # Act
    zapisz_jednorazowy(plik, dzien)
    zapisz_jednorazowy(plik, dzien)
    # Assert
    assert wczytaj_jednorazowe(plik) == [dzien]


def test_kalendarz_projektu_dokleja_dni_z_pliku_projektu(tmp_path):
    # Arrange
    zapisz_jednorazowy(tmp_path / ".kruczek" / "dni-wolne.json", DzienJednorazowy(D(2030, 1, 2), "test"))
    # Act
    kal = wczytaj_kalendarz(tmp_path)
    # Assert
    assert kal.czy_wolny(D(2030, 1, 2)) is True
    assert kal.czy_wolny(D(2018, 11, 12)) is True  # z pliku pluginu nadal działa
