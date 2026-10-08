import datetime as dt

import pytest

from kruczek_core.dni_wolne import DzienJednorazowy, Kalendarz
from kruczek_core.model import BladSprawy, Sprawa, Watek, Zdarzenie
from kruczek_core.reguly import (
    REGULA_ANALIZA,
    REGULA_DORECZENIE,
    REGULA_ODPOWIEDZ,
    SpecTerminu,
    przelicz,
    zastosuj,
)

D = dt.date
SPEC = SpecTerminu("14d", "wyznaczony w piśmie")


def sprawa_z_watkiem() -> Sprawa:
    return Sprawa(id="s1", tytul="T", wlasciciel="w", strona_przeciwna="X", watki=[Watek("firma", "X sp. z o.o.")])


def dodaj(sprawa, id, data, typ, spec=None, kalendarz=Kalendarz()):
    z = Zdarzenie(id, data, typ, watek="firma")
    sprawa.zdarzenia.append(z)
    return zastosuj(sprawa, z, spec, kalendarz)


def test_nadanie_tworzy_szacunkowy_termin_i_dwa_zadania():
    # Arrange
    s = sprawa_z_watkiem()
    # Act
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    # Assert
    (t,) = s.terminy
    assert (t.data_konca, t.szacunek, t.od_zdarzenia, t.watek) == (D(2026, 10, 22), True, "z1", "firma")
    reguly = {a.regula: a for a in s.zadania}
    assert reguly[REGULA_DORECZENIE].aktywne_od == D(2026, 10, 9)
    assert reguly[REGULA_ODPOWIEDZ].aktywne_od == D(2026, 10, 23)
    assert reguly[REGULA_ODPOWIEDZ].termin_id == t.id


def test_nadanie_bez_terminu_tylko_sprawdzenie_doreczenia():
    # Arrange
    s = sprawa_z_watkiem()
    # Act
    komunikaty = dodaj(s, "z1", D(2026, 10, 8), "nadanie")
    # Assert
    assert s.terminy == []
    assert [a.regula for a in s.zadania] == [REGULA_DORECZENIE]
    assert any("bez terminu" in k for k in komunikaty)


def test_doreczenie_przelicza_termin_i_zamyka_sprawdzenie():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z2", D(2026, 10, 12), "doreczenie")
    # Assert
    (t,) = s.terminy
    assert (t.data_konca, t.szacunek, t.od_zdarzenia) == (D(2026, 10, 26), False, "z2")
    reguly = {a.regula: a for a in s.zadania}
    assert reguly[REGULA_DORECZENIE].zrobione == D(2026, 10, 12)
    assert reguly[REGULA_ODPOWIEDZ].aktywne_od == D(2026, 10, 27)


def test_doreczenie_przed_nadaniem_odrzucone():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    # Act / Assert
    with pytest.raises(BladSprawy, match="wcześniej niż nadanie"):
        dodaj(s, "z2", D(2026, 10, 7), "doreczenie")


def test_doreczenie_bez_terminu_nie_wybucha():
    # Arrange
    s = sprawa_z_watkiem()
    # Act
    komunikaty = dodaj(s, "z1", D(2026, 10, 8), "doreczenie")
    # Assert
    assert s.terminy == []
    assert any("nie ma terminu" in k for k in komunikaty)


def test_odpowiedz_zamyka_oczekiwanie_i_tworzy_analize():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z2", D(2026, 10, 15), "odpowiedz")
    # Assert
    reguly = {a.regula: a for a in s.zadania}
    assert reguly[REGULA_ODPOWIEDZ].zrobione == D(2026, 10, 15)
    assert reguly[REGULA_DORECZENIE].zrobione == D(2026, 10, 15)
    assert reguly[REGULA_ANALIZA].aktywne_od == D(2026, 10, 15)
    assert reguly[REGULA_ANALIZA].zrobione is None


def test_odpowiedz_bez_nadania_tworzy_tylko_analize():
    # Arrange
    s = sprawa_z_watkiem()
    # Act
    dodaj(s, "z1", D(2026, 10, 15), "odpowiedz")
    # Assert
    assert [a.regula for a in s.zadania] == [REGULA_ANALIZA]


def test_przelicz_po_dodaniu_dnia_wolnego():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2030, 1, 1), "nadanie", SpecTerminu("1d", "test"))  # koniec 2.01.2030 (środa)
    kal = Kalendarz((DzienJednorazowy(D(2030, 1, 2), "Dz.U. 2029 poz. 1"),))
    # Act
    komunikaty = przelicz(s, kal)
    # Assert
    assert s.terminy[0].data_konca == D(2030, 1, 3)
    assert {a.regula: a for a in s.zadania}[REGULA_ODPOWIEDZ].aktywne_od == D(2030, 1, 4)
    assert komunikaty == ["t1: 2030-01-02 → 2030-01-03"]


def test_wplyw_z_terminem_to_moj_termin_z_data_w_zadaniu():
    # Arrange
    s = sprawa_z_watkiem()
    # Act — decyzja doręczona 12.10, 14 dni na odwołanie
    komunikaty = dodaj(s, "z1", D(2026, 10, 12), "wplyw", SpecTerminu("14d", "pouczenie w decyzji"))
    # Assert
    (t,) = s.terminy
    assert (t.czyj, t.szacunek, t.od_zdarzenia, t.data_konca) == ("moj", False, "z1", D(2026, 10, 26))
    (a,) = s.zadania
    assert (a.regula, a.aktywne_od, a.termin, a.termin_id) == (REGULA_ANALIZA, D(2026, 10, 12), D(2026, 10, 26), t.id)
    assert any("Twój termin" in k for k in komunikaty)


def test_odpowiedz_z_terminem_zamyka_oczekiwanie_i_daje_moj_termin():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z2", D(2026, 10, 15), "odpowiedz", SpecTerminu("7d", "termin z odpowiedzi"))
    # Assert
    moje = [t for t in s.terminy if t.czyj == "moj"]
    assert [t.data_konca for t in moje] == [D(2026, 10, 22)]
    assert {a.regula: a for a in s.zadania}[REGULA_ODPOWIEDZ].zrobione == D(2026, 10, 15)


def test_doreczenie_nie_przelicza_mojego_terminu():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 12), "wplyw", SpecTerminu("14d", "pouczenie"))
    # Act
    komunikaty = dodaj(s, "z2", D(2026, 10, 13), "doreczenie")
    # Assert
    assert s.terminy[0].od_zdarzenia == "z1"
    assert any("nie ma terminu" in k for k in komunikaty)


def test_przelicz_aktualizuje_date_zadania_przy_moim_terminie():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2030, 1, 1), "wplyw", SpecTerminu("1d", "test"))  # koniec 2.01.2030
    kal = Kalendarz((DzienJednorazowy(D(2030, 1, 2), "Dz.U. 2029 poz. 1"),))
    # Act
    przelicz(s, kal)
    # Assert
    assert s.zadania[0].termin == D(2030, 1, 3)
