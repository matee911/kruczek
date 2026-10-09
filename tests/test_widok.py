import datetime as dt

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.model import Sprawa, Watek, Zadanie, Zdarzenie
from kruczek_core.reguly import SpecTerminu, zastosuj
from kruczek_core.widok import co_robic, stan_watku

D = dt.date
DZIS = D(2026, 10, 20)


def sprawa(tytul, zadania=(), zamknieta=False) -> Sprawa:
    return Sprawa(id=tytul, tytul=tytul, wlasciciel="w", strona_przeciwna="X",
                  watki=[Watek("firma", "X")], zadania=list(zadania), zamknieta=zamknieta)


def test_teraz_tylko_aktywne_i_niezrobione_wkrotce_w_horyzoncie():
    # Arrange
    a = sprawa("A", [Zadanie("a1", "aktywne", D(2026, 10, 19)),
                     Zadanie("a2", "zrobione", D(2026, 10, 1), zrobione=D(2026, 10, 2))])
    b = sprawa("B", [Zadanie("a1", "za tydzień", D(2026, 10, 27)),
                     Zadanie("a2", "za miesiąc", D(2026, 11, 30))])
    # Act
    p = co_robic([a, b], DZIS)
    # Assert
    assert [(x.sprawa, x.zadanie.opis) for x in p.teraz] == [("A", "aktywne")]
    assert [(x.sprawa, x.zadanie.opis) for x in p.wkrotce] == [("B", "za tydzień")]


def test_teraz_sortowane_po_terminie():
    # Arrange
    s = sprawa("A", [Zadanie("a1", "bez terminu", D(2026, 10, 1)),
                     Zadanie("a2", "pilne", D(2026, 10, 10), termin=D(2026, 10, 21))])
    # Act
    p = co_robic([s], DZIS)
    # Assert
    assert [x.zadanie.opis for x in p.teraz] == ["pilne", "bez terminu"]


def test_zamknieta_sprawa_pomijana():
    # Arrange
    s = sprawa("A", [Zadanie("a1", "x", D(2026, 10, 1))], zamknieta=True)
    # Act
    p = co_robic([s], DZIS)
    # Assert
    assert p.teraz == [] and p.czekam == []


def test_pilka_po_nadaniu_u_adresata_po_odpowiedzi_moja():
    # Arrange
    s = sprawa("A")
    z1 = Zdarzenie("z1", D(2026, 10, 8), "nadanie", watek="firma")
    s.zdarzenia.append(z1)
    zastosuj(s, z1, SpecTerminu("14d", "test"), Kalendarz())
    # Act
    po_nadaniu = stan_watku(s, "firma")
    z2 = Zdarzenie("z2", D(2026, 10, 15), "odpowiedz", watek="firma")
    s.zdarzenia.append(z2)
    zastosuj(s, z2, None, Kalendarz())
    po_odpowiedzi = stan_watku(s, "firma")
    # Assert
    assert (po_nadaniu.pilka, po_nadaniu.czekam_do, po_nadaniu.szacunek) == ("adresata", D(2026, 10, 22), True)
    assert (po_odpowiedzi.pilka, po_odpowiedzi.czekam_do) == ("moja", None)


def test_moj_termin_na_gorze_teraz_i_nie_w_czekam():
    # Arrange
    s = sprawa("A", [Zadanie("a9", "stare bez terminu", D(2026, 10, 1))])
    z = Zdarzenie("z1", D(2026, 10, 12), "wplyw", watek="firma")
    s.zdarzenia.append(z)
    zastosuj(s, z, SpecTerminu("14d", "pouczenie"), Kalendarz())
    # Act
    p = co_robic([s], DZIS)
    # Assert
    assert p.teraz[0].zadanie.termin == D(2026, 10, 26)
    assert p.czekam == []


def test_czekam_zawiera_watki_z_pilka_u_adresata():
    # Arrange
    s = sprawa("A")
    z1 = Zdarzenie("z1", D(2026, 10, 8), "nadanie", watek="firma")
    s.zdarzenia.append(z1)
    zastosuj(s, z1, SpecTerminu("14d", "test"), Kalendarz())
    # Act
    p = co_robic([s], DZIS)
    # Assert
    assert [(c.sprawa, c.watek.id, c.czekam_do) for c in p.czekam] == [("A", "firma", D(2026, 10, 22))]


def test_stary_termin_nie_wraca_po_nowym_nadaniu_bez_terminu():
    # Arrange
    s = sprawa("A")
    z1 = Zdarzenie("z1", D(2026, 10, 1), "nadanie", watek="firma")
    s.zdarzenia.append(z1)
    zastosuj(s, z1, SpecTerminu("14d", "test"), Kalendarz())
    z2 = Zdarzenie("z2", D(2026, 10, 10), "odpowiedz", watek="firma")
    s.zdarzenia.append(z2)
    zastosuj(s, z2, None, Kalendarz())
    z3 = Zdarzenie("z3", D(2026, 10, 12), "nadanie", watek="firma")
    s.zdarzenia.append(z3)
    zastosuj(s, z3, None, Kalendarz())
    # Act
    st = stan_watku(s, "firma")
    # Assert
    assert (st.pilka, st.czekam_do, st.szacunek) == ("adresata", None, False)


def test_dwa_pisma_czekaja_czekam_do_najwczesniejszego_terminu():
    # Arrange
    s = sprawa("A")
    z1 = Zdarzenie("z1", D(2026, 10, 1), "nadanie", watek="firma")
    s.zdarzenia.append(z1)
    zastosuj(s, z1, SpecTerminu("14d", "test"), Kalendarz())
    z2 = Zdarzenie("z2", D(2026, 10, 8), "nadanie", watek="firma")
    s.zdarzenia.append(z2)
    zastosuj(s, z2, SpecTerminu("14d", "test"), Kalendarz())
    # Act
    st = stan_watku(s, "firma")
    # Assert
    assert (st.pilka, st.czekam_do, st.szacunek) == ("adresata", D(2026, 10, 15), True)


def test_doreczenie_jako_ostatnie_zdarzenie_przelicza_termin_od_doreczenia():
    # Arrange
    s = sprawa("A")
    z1 = Zdarzenie("z1", D(2026, 10, 8), "nadanie", watek="firma")
    s.zdarzenia.append(z1)
    zastosuj(s, z1, SpecTerminu("14d", "test"), Kalendarz())
    z2 = Zdarzenie("z2", D(2026, 10, 12), "doreczenie", watek="firma")
    s.zdarzenia.append(z2)
    zastosuj(s, z2, None, Kalendarz())
    # Act
    st = stan_watku(s, "firma")
    # Assert
    assert (st.pilka, st.czekam_do, st.szacunek) == ("adresata", D(2026, 10, 26), False)


def test_watek_bez_korespondencji_ma_pilke_u_mnie():
    # Arrange
    s = sprawa("A")
    # Act
    st = stan_watku(s, "firma")
    # Assert
    assert (st.pilka, st.czekam_do, st.szacunek) == ("moja", None, False)


def test_granica_horyzontu_wlacza_dzien_14_i_wyklucza_dzien_15():
    # Arrange
    a = sprawa("A", [Zadanie("a1", "w granicy", D(2026, 11, 3)),
                     Zadanie("a2", "za daleko", D(2026, 11, 4))])
    # Act
    p = co_robic([a], DZIS)
    # Assert
    assert p.teraz == []
    assert [x.zadanie.opis for x in p.wkrotce] == ["w granicy"]


def test_teraz_przeterminowany_termin_na_gorze_potem_nadchodzacy_potem_bez_terminu():
    # Arrange
    s = sprawa("A", [Zadanie("a1", "termin 25", D(2026, 10, 1), termin=D(2026, 10, 25)),
                     Zadanie("a2", "przeterminowany", D(2026, 10, 10), termin=D(2026, 10, 18)),
                     Zadanie("a3", "bez terminu", D(2026, 9, 1))])
    # Act
    p = co_robic([s], DZIS)
    # Assert
    assert [x.zadanie.opis for x in p.teraz] == ["przeterminowany", "termin 25", "bez terminu"]


def test_sprawa_bez_ruchu_ponad_30_dni():
    # Arrange
    stara = Sprawa(id="s1", tytul="Stara", wlasciciel="w", strona_przeciwna="X",
                   zdarzenia=[Zdarzenie("z1", D(2026, 9, 1), "fakt")])
    zywa = Sprawa(id="s2", tytul="Żywa", wlasciciel="w", strona_przeciwna="X",
                  zdarzenia=[Zdarzenie("z1", D(2026, 10, 15), "fakt")])
    # Act
    p = co_robic([stara, zywa], D(2026, 10, 20))
    # Assert
    assert [(b.sprawa, b.sprawa_id, b.ostatni_ruch) for b in p.bez_ruchu] == [("Stara", "s1", D(2026, 9, 1))]


def test_bez_ruchu_pomija_zamknieta_otwarte_zadanie_i_sprawe_bez_zdarzen_wypisuje_pierwsza():
    # Arrange
    stare = [Zdarzenie("z1", D(2026, 8, 1), "fakt")]
    zamknieta = Sprawa(id="a", tytul="A", wlasciciel="w", strona_przeciwna="X", zdarzenia=stare, zamknieta=True)
    z_zadaniem = Sprawa(id="b", tytul="B", wlasciciel="w", strona_przeciwna="X", zdarzenia=stare,
                        zadania=[Zadanie("a1", "x", D(2026, 12, 1))])
    pusta = Sprawa(id="c", tytul="C", wlasciciel="w", strona_przeciwna="X")
    stara = Sprawa(id="d", tytul="D", wlasciciel="w", strona_przeciwna="X", zdarzenia=stare)
    # Act
    p = co_robic([zamknieta, z_zadaniem, stara, pusta], D(2026, 10, 20))
    # Assert
    assert [(b.sprawa_id, b.ostatni_ruch) for b in p.bez_ruchu] == [("c", None), ("d", D(2026, 8, 1))]


def test_pozycje_niosa_id_sprawy():
    # Arrange
    s = Sprawa(id="abc", tytul="T", wlasciciel="w", strona_przeciwna="X",
               zadania=[Zadanie("a1", "x", D(2026, 10, 1))])
    # Act
    p = co_robic([s], D(2026, 10, 20))
    # Assert
    assert p.teraz[0].sprawa_id == "abc"
