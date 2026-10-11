"""Dane ekranów (bez serwera): dobór słów, znaczników i akcji z wyników kruczek_core."""

import datetime as dt

import pytest
from kruczek_core.dni_wolne import DzienJednorazowy, Kalendarz
from kruczek_core.model import Sprawa, Uczestnik, Watek, Zadanie, Zdarzenie
from kruczek_core.reguly import SpecTerminu, zastosuj
from kruczek_core.widok import co_robic, sekcje
from kruczek_strona.ekrany import ekran_sprawy, sekcje_ekranu
from kruczek_strona.format import data_doreczenia

D = dt.date
DZIS = D(2026, 10, 20)
PUSTY_KALENDARZ = Kalendarz()


def sprawa(*zadania, klientka=None):
    s = Sprawa(id="s1", tytul="Sprawa testowa", wlasciciel="opiekun1", strona_przeciwna="Firma X sp. z o.o.",
               watki=[Watek("firma", "Firma X sp. z o.o.")], zadania=list(zadania))
    if klientka:
        s.uczestnicy.append(Uczestnik(klientka, "klientka"))
    return s


def ekran(s, kal=PUSTY_KALENDARZ):
    return sekcje_ekranu(sekcje(co_robic([("sprawa-a", s)], DZIS), {"sprawa-a": s}, DZIS), {"sprawa-a": s},
                         {"sprawa-a": kal}, DZIS)


def z_nadaniem(data):
    s = sprawa(klientka="Osoba Testowa")
    z = Zdarzenie("z1", data, "nadanie", watek="firma")
    s.zdarzenia.append(z)
    zastosuj(s, z, SpecTerminu("14d", "art. 7 testowej ustawy"), Kalendarz())
    return s


def test_karta_wlasnego_terminu_nasz_termin_i_ile_zostalo():
    # Arrange
    s = sprawa(Zadanie("a1", "Wyślij odwołanie", D(2026, 10, 1), termin=D(2026, 10, 24)))
    # Act
    k = ekran(s).teraz[0]
    # Assert
    assert (k.status, k.kiedy, k.akcja) == ("ours", "do 24.10.2026 · zostały 4 dni", "zrobione")


def test_karta_po_terminie_minal_i_ile_dni_temu():
    # Arrange
    s = sprawa(Zadanie("a1", "Wyślij odwołanie", D(2026, 10, 1), termin=D(2026, 10, 13)))
    # Act
    k = ekran(s).po_terminie[0]
    # Assert
    assert (k.status, k.kiedy) == ("overdue", "minął 13.10.2026 · 7 dni temu")


def test_karta_sprawdzenia_doreczenia_szacunek_kto_ma_termin_i_formularz():
    # Arrange — nadanie 08.10, termin firmy szacunkowo do 22.10
    s = z_nadaniem(D(2026, 10, 8))
    # Act
    k = ekran(s).teraz[0]
    # Assert
    assert (k.status, k.akcja) == ("estimate", "doreczenie")
    assert k.kiedy == "Firma X sp. z o.o.: ok. 22.10.2026"
    assert k.dlaczego == ("Firma X sp. z o.o.: 14 dni — art. 7 testowej ustawy · termin szacunkowy — "
                          "wpisz datę doręczenia")


def test_odpowiedz_po_terminie_firmy_polecenie_eskalacji():
    # Arrange — termin firmy minął 15.10
    s = z_nadaniem(D(2026, 10, 1))
    # Act
    e = ekran(s)
    # Assert
    k = e.po_terminie[0]
    assert (k.status, k.akcja, k.polecenie) == ("overdue", "polecenie", "/kruczek:eskalacja sprawa-a")
    assert e.czekam == []


def test_dzien_wolny_dla_urzedow_jako_uwaga_na_karcie():
    # Arrange
    s = sprawa(Zadanie("a1", "Złóż wniosek", D(2026, 10, 1), termin=D(2026, 10, 23)))
    kal = Kalendarz((DzienJednorazowy(D(2026, 10, 23), "test", True),))
    # Act
    k = ekran(s, kal).teraz[0]
    # Assert
    assert any("urzędy zamknięte" in u for u in k.uwagi)


def test_nic_na_dzis_podaje_najblizszy_termin_czekania():
    # Arrange — po doręczeniu nic do zrobienia, czekamy na firmę
    s = z_nadaniem(D(2026, 10, 15))
    s.znajdz_zadanie("a1").zrobione = D(2026, 10, 16)
    # Act
    e = ekran(s)
    # Assert
    assert e.teraz == [] and e.po_terminie == [] and e.najblizszy == D(2026, 10, 29)
    assert (e.czekam[0].data, e.czekam[0].pod_data) == ("ok. 29.10.2026", "szacunek · zostało 9 dni")


def test_ekran_sprawy_termin_strony_i_chronologia_z_dowodami():
    # Arrange
    s = z_nadaniem(D(2026, 10, 8))
    s.zdarzenia.append(Zdarzenie("z2", D(2026, 10, 9), "fakt", "Rozmowa", dowody=["ARCHIWUM/notatka.md"],
                                 pewnosc="poszlaka"))
    # Act
    e = ekran_sprawy("sprawa-a", s, Kalendarz(), DZIS)
    # Assert
    assert e.strona == "Osoba Testowa"
    assert (e.terminy[0].data, e.terminy[0].co, e.terminy[0].status) == (
        "ok. 22.10.2026", "Firma X sp. z o.o.: 14 dni", "estimate")
    assert "art. 7 testowej ustawy" in e.terminy[0].meta and "szacunek" in e.terminy[0].meta
    assert [(w.co, w.status, w.dowody) for w in e.chronologia] == [
        ("Nadanie pisma", "", []), ("Fakt: Rozmowa", "clue", ["ARCHIWUM/notatka.md"])]


@pytest.mark.parametrize("wpis, komunikat", [
    ("", "Wpisz datę doręczenia."),
    ("2026-10-09", "Wpisz datę jako dd.mm.rrrr"),
    ("10.13.2026", "Miesiąc to liczba od 01 do 12"),
    ("29.02.2027", "Luty 2027 ma 28 dni."),
    ("21.10.2026", "Data jest z przyszłości. Wpisz dzień, w którym pismo odebrano — najpóźniej 20.10.2026."),
])
def test_data_doreczenia_bledy_mowia_jak_poprawic(wpis, komunikat):
    # Act / Assert
    with pytest.raises(ValueError, match=komunikat.replace(".", r"\.")):
        data_doreczenia(wpis, DZIS)
