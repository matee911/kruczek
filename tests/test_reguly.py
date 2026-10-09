import datetime as dt

import pytest

from kruczek_core.dni_wolne import DzienJednorazowy, Kalendarz
from kruczek_core.model import BladSprawy, Sprawa, Watek, Zdarzenie
from kruczek_core.widok import stan_watku
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


def dodaj(sprawa, id, data, typ, spec=None, kalendarz=Kalendarz(), dotyczy=None):
    z = Zdarzenie(id, data, typ, watek="firma")
    sprawa.zdarzenia.append(z)
    return zastosuj(sprawa, z, spec, kalendarz, dotyczy=dotyczy)


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
    (t,) = s.terminy
    assert (t.data_konca, t.szacunek, t.od_zdarzenia) == (D(2026, 10, 22), True, "z1")


def test_nadanie_bez_terminu_domykane_doreczeniem():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie")
    # Act
    dodaj(s, "z2", D(2026, 10, 12), "doreczenie")
    # Assert
    (a,) = s.zadania
    assert (a.regula, a.zrobione) == (REGULA_DORECZENIE, D(2026, 10, 12))


def test_dwa_czekajace_nadania_doreczenie_bez_wskazania_odrzucone():
    # Arrange — dwa pisma czekają naraz; kod nie zgaduje, którego dotyczy doręczenie
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SPEC)
    # Act / Assert
    with pytest.raises(BladSprawy, match=r"z1.*z2.*--dotyczy"):
        dodaj(s, "z3", D(2026, 10, 9), "doreczenie")
    assert all(t.szacunek for t in s.terminy)


def test_dwa_nadania_doreczenie_ze_wskazaniem_potem_jedyne_czekajace():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z3", D(2026, 10, 9), "doreczenie", dotyczy="z1")
    # Assert
    t1, t2 = s.terminy
    assert (t1.data_konca, t1.szacunek, t1.od_zdarzenia) == (D(2026, 10, 23), False, "z3")
    assert (t2.data_konca, t2.szacunek, t2.od_zdarzenia) == (D(2026, 10, 22), True, "z2")
    # Act
    dodaj(s, "z4", D(2026, 10, 12), "doreczenie")
    # Assert
    assert (t2.data_konca, t2.szacunek, t2.od_zdarzenia) == (D(2026, 10, 26), False, "z4")
    assert (t1.data_konca, t1.szacunek, t1.od_zdarzenia) == (D(2026, 10, 23), False, "z3")


def test_doreczenie_przed_drugim_nadaniem_pasuje_do_pierwszego():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z3", D(2026, 10, 5), "doreczenie")
    # Assert
    t1, t2 = s.terminy
    assert (t1.data_konca, t1.szacunek, t1.od_zdarzenia) == (D(2026, 10, 19), False, "z3")
    assert (t2.data_konca, t2.szacunek) == (D(2026, 10, 22), True)


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


def test_jedna_odpowiedz_zamyka_tylko_najstarsze_nadanie_w_watku():
    # Arrange — reklamacja 14d (z1), potem wezwanie 30d (z2) w tym samym wątku
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SpecTerminu("30d", "wezwanie"))
    # Act
    komunikaty = dodaj(s, "z3", D(2026, 10, 15), "odpowiedz")
    # Assert
    otwarte = [a for a in s.zadania if a.zrobione is None and a.regula in (REGULA_ODPOWIEDZ, REGULA_DORECZENIE)]
    assert {(a.regula, a.zdarzenie_id) for a in otwarte} == {(REGULA_ODPOWIEDZ, "z2"), (REGULA_DORECZENIE, "z2")}
    zamkniete = [a for a in s.zadania if a.zrobione == D(2026, 10, 15)]
    assert {a.zdarzenie_id for a in zamkniete if a.regula != REGULA_ANALIZA} == {"z1"}
    assert any("nadal otwarte" in k and "z2, 2026-10-08" in k for k in komunikaty)
    assert stan_watku(s, "firma").pilka == "adresata"


def test_odpowiedz_nie_zamyka_nadania_pozniejszego_niz_odpowiedz():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 15), "nadanie", SPEC)
    # Act
    dodaj(s, "z3", D(2026, 10, 10), "odpowiedz")
    # Assert
    otwarte = {a.zdarzenie_id for a in s.zadania if a.zrobione is None and a.regula == REGULA_ODPOWIEDZ}
    assert otwarte == {"z2"}


def _dwa_nadania_i_odpowiedz(s):
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SpecTerminu("30d", "wezwanie"))
    dodaj(s, "z3", D(2026, 10, 15), "odpowiedz")


def test_spoznione_doreczenie_po_odpowiedzi_trafia_do_nadania_zamknietego_odpowiedzia():
    # Arrange — odpowiedź zamknęła oczekiwania z1; potwierdzenie EPO dla z1 wpisane później
    s = sprawa_z_watkiem()
    _dwa_nadania_i_odpowiedz(s)
    # Act
    dodaj(s, "z4", D(2026, 10, 3), "doreczenie")
    # Assert
    t1, t2 = s.terminy
    assert (t1.od_zdarzenia, t1.szacunek) == ("z4", False)
    assert (t2.od_zdarzenia, t2.szacunek) == ("z2", True)


def test_po_odpowiedzi_doreczenie_niejednoznaczne_wymaga_wskazania():
    # Arrange — z1 i z2 czekały naraz, odpowiedź zamknęła z1; doręczenie 10-09 pasuje do obu
    s = sprawa_z_watkiem()
    _dwa_nadania_i_odpowiedz(s)
    # Act / Assert
    with pytest.raises(BladSprawy, match="--dotyczy"):
        dodaj(s, "z4", D(2026, 10, 9), "doreczenie")


def test_doreczenie_pierwszego_nadania_ze_wskazaniem_nie_przelicza_drugiego():
    # Arrange
    s = sprawa_z_watkiem()
    _dwa_nadania_i_odpowiedz(s)
    # Act
    dodaj(s, "z4", D(2026, 10, 9), "doreczenie", dotyczy="z1")
    # Assert
    t1, t2 = s.terminy
    assert t1.od_zdarzenia == "z4"
    assert (t2.od_zdarzenia, t2.szacunek, t2.data_konca) == ("z2", True, D(2026, 11, 9))
    otwarte = {a.zdarzenie_id for a in s.zadania if a.zrobione is None and a.regula == REGULA_DORECZENIE}
    assert otwarte == {"z2"}


def test_nadania_tego_samego_dnia_zamykane_w_kolejnosci_wpisania():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 8), "nadanie")
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    komunikaty = dodaj(s, "z3", D(2026, 10, 15), "odpowiedz")
    # Assert
    otwarte = {a.zdarzenie_id for a in s.zadania if a.zrobione is None and a.regula != REGULA_ANALIZA}
    assert otwarte == {"z2"}
    assert any("z2" in k and "nadal" in k for k in komunikaty)


def test_korespondencja_tam_i_z_powrotem_doreczenie_trafia_do_biezacego_pisma():
    # Arrange — pismo, odpowiedź, kontra; doręczenia pierwszego pisma nikt nie wpisał
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 10), "odpowiedz")
    dodaj(s, "z3", D(2026, 10, 12), "nadanie", SPEC)
    # Act
    dodaj(s, "z4", D(2026, 10, 14), "doreczenie")
    # Assert
    t1, t2 = s.terminy
    assert (t2.od_zdarzenia, t2.szacunek, t2.data_konca) == ("z4", False, D(2026, 10, 28))
    assert t1.od_zdarzenia == "z1"


def test_odpowiedz_ze_wskazaniem_zamyka_wskazane_nadanie():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 8), "nadanie", SPEC)
    # Act
    dodaj(s, "z3", D(2026, 10, 15), "odpowiedz", dotyczy="z2")
    # Assert
    otwarte = {a.zdarzenie_id for a in s.zadania if a.zrobione is None and a.regula == REGULA_ODPOWIEDZ}
    assert otwarte == {"z1"}


@pytest.mark.parametrize(
    "dotyczy, komunikat",
    [("z9", "z9"), ("z0", "nie jest nadaniem"), ("z2", "późniejsze")],
    ids=["nieznane", "nie-nadanie", "pozniejsze-niz-zdarzenie"],
)
def test_wskazanie_nadania_walidowane(dotyczy, komunikat):
    # Arrange
    s = sprawa_z_watkiem()
    s.zdarzenia.append(Zdarzenie("z0", D(2026, 9, 30), "fakt", watek="firma"))
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 20), "nadanie", SPEC)
    # Act / Assert
    with pytest.raises(BladSprawy, match=komunikat):
        dodaj(s, "z3", D(2026, 10, 9), "doreczenie", dotyczy=dotyczy)


def test_doreczenie_i_odpowiedz_zapamietuja_ktorego_nadania_dotycza():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    # Act
    dodaj(s, "z2", D(2026, 10, 3), "doreczenie")
    dodaj(s, "z3", D(2026, 10, 10), "odpowiedz")
    # Assert
    assert (s.znajdz_zdarzenie("z2").dotyczy, s.znajdz_zdarzenie("z3").dotyczy) == ("z1", "z1")


def test_drugie_doreczenie_tego_samego_pisma_po_odpowiedzi_nie_pasuje():
    # Arrange — z1 doręczone i z odpowiedzią; z4 wysłane po odpowiedzi
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 3), "doreczenie")
    dodaj(s, "z3", D(2026, 10, 10), "odpowiedz")
    dodaj(s, "z4", D(2026, 10, 12), "nadanie", SPEC)
    # Act
    dodaj(s, "z5", D(2026, 10, 14), "doreczenie")
    # Assert
    assert s.znajdz_zdarzenie("z5").dotyczy == "z4"


def test_wskazane_nadanie_z_doreczeniem_po_odpowiedzi_odrzucone():
    # Arrange
    s = sprawa_z_watkiem()
    dodaj(s, "z1", D(2026, 10, 1), "nadanie", SPEC)
    dodaj(s, "z2", D(2026, 10, 3), "doreczenie")
    dodaj(s, "z3", D(2026, 10, 10), "odpowiedz")
    # Act / Assert
    with pytest.raises(BladSprawy, match="ma już wpisane doręczenie z2"):
        dodaj(s, "z4", D(2026, 10, 11), "doreczenie", dotyczy="z1")
