import datetime as dt

import pytest

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core import operacje
from kruczek_core.model import BladSprawy, Sprawa
from kruczek_core.operacje import (
    cofnij_zdarzenie,
    dodaj_watek,
    dodaj_zadanie,
    dodaj_zdarzenie,
    dopisz_watek,
    dopisz_zadanie,
    dopisz_zdarzenie,
    nowa_sprawa,
    otworz_sprawe,
    oznacz_zrobione,
    popraw_zdarzenie,
    utworz_sprawe,
    zamknij_sprawe,
)
from kruczek_core.reguly import SpecTerminu
from kruczek_core.repozytorium import wczytaj

D = dt.date
DZIS = D(2026, 10, 20)


@pytest.fixture
def katalog(tmp_path):
    k = tmp_path / "spamer"
    k.mkdir()
    nowa_sprawa(k, "Spamer", "X sp. z o.o.", "opiekun1")
    dodaj_watek(k, "firma", "X sp. z o.o.")
    return k


def test_nowa_sprawa_ma_stale_id_i_opiekuna(katalog):
    # Act
    s = wczytaj(katalog)
    # Assert
    assert len(s.id) == 32
    assert [(u.osoba, u.rola) for u in s.uczestnicy] == [("opiekun1", "opiekun")]


def test_dodaj_zdarzenie_nadanie_zapisuje_i_stosuje_reguly(katalog):
    # Act
    komunikaty = dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS,
                                 watek="firma", termin=SpecTerminu("14d", "art. 7 u.r."))
    # Assert
    s = wczytaj(katalog)
    assert [z.id for z in s.zdarzenia] == ["z1"]
    assert len(s.terminy) == 1 and len(s.zadania) == 2
    assert komunikaty[0] == "zdarzenie z1: nadanie 2026-10-08"
    assert any("szacunek" in k for k in komunikaty)


def test_zdarzenie_z_przyszlosci_odrzucone_i_nic_nie_zapisane(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="w przyszłości"):
        dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 21), Kalendarz(), DZIS)
    assert wczytaj(katalog).zdarzenia == []


def test_nieznany_typ_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="nieznany typ"):
        dodaj_zdarzenie(katalog, "mail", D(2026, 10, 8), Kalendarz(), DZIS)


def test_zdarzenie_korespondencji_wymaga_watku(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="wymaga wątku"):
        dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS)


def test_nieznany_watek_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie ma wątku 'uodo'"):
        dodaj_zdarzenie(katalog, "odpowiedz", D(2026, 10, 8), Kalendarz(), DZIS, watek="uodo")


def test_termin_nie_przy_fakcie(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="przy nadaniu"):
        dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 8), Kalendarz(), DZIS, termin=SpecTerminu("14d", "x"))


def test_wplyw_z_terminem_zapisuje_moj_termin(katalog):
    # Act
    komunikaty = dodaj_zdarzenie(katalog, "wplyw", D(2026, 10, 12), Kalendarz(), DZIS,
                                 watek="firma", termin=SpecTerminu("14d", "pouczenie w decyzji"))
    # Assert
    (t,) = wczytaj(katalog).terminy
    assert (t.czyj, t.data_konca) == ("moj", D(2026, 10, 26))
    assert any("Twój termin" in k for k in komunikaty)


def test_zadanie_reczne_i_zrobione(katalog):
    # Arrange
    zadanie = dodaj_zadanie(katalog, "snapshot Web Archive", D(2026, 11, 3))
    # Act
    zrobione = oznacz_zrobione(katalog, zadanie.id, DZIS)
    # Assert
    assert zrobione.zrobione == DZIS
    assert wczytaj(katalog).znajdz_zadanie(zadanie.id).zrobione == DZIS


def test_oznacz_zrobione_dwa_razy_to_blad(katalog):
    # Arrange
    zadanie = dodaj_zadanie(katalog, "x", D(2026, 10, 1))
    oznacz_zrobione(katalog, zadanie.id, DZIS)
    # Act / Assert
    with pytest.raises(BladSprawy, match="już zrobione"):
        oznacz_zrobione(katalog, zadanie.id, DZIS)


@pytest.mark.parametrize(
    ("pole", "nazwa"),
    [("tytul", "tytuł"), ("strona_przeciwna", "strona przeciwna"), ("wlasciciel", "właściciel")],
)
def test_nowa_sprawa_pusty_pole_odrzucone_i_nic_nie_zapisane(tmp_path, pole, nazwa):
    # Arrange
    k = tmp_path / "pusta"
    k.mkdir()
    dane = {"tytul": "Spamer", "strona_przeciwna": "X sp. z o.o.", "wlasciciel": "opiekun1", pole: "  "}
    # Act / Assert
    with pytest.raises(BladSprawy, match=f"{nazwa} nie może być pusty"):
        nowa_sprawa(k, dane["tytul"], dane["strona_przeciwna"], dane["wlasciciel"])
    assert not (k / "sprawa.json").exists()


def test_dodaj_watek_pusty_id_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="id wątku nie może być pusty"):
        dodaj_watek(katalog, "  ", "X sp. z o.o.")


def test_dodaj_watek_pusty_adresat_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="adresat nie może być pusty"):
        dodaj_watek(katalog, "inny", "")


def test_dodaj_watek_przycina_wartosci(tmp_path):
    # Arrange
    k = tmp_path / "przycinanie"
    k.mkdir()
    nowa_sprawa(k, "Spamer", "X sp. z o.o.", "opiekun1")
    # Act
    dodaj_watek(k, " firma ", " X ")
    # Assert
    (w,) = wczytaj(k).watki
    assert (w.id, w.adresat) == ("firma", "X")


def test_dodaj_zadanie_pusty_opis_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="opis nie może być pusty"):
        dodaj_zadanie(katalog, "", D(2026, 10, 1))
    assert wczytaj(katalog).zadania == []


def test_dodaj_zadanie_termin_wczesniej_niz_aktywne_od_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="wcześniej niż aktywne od"):
        dodaj_zadanie(katalog, "x", D(2026, 10, 10), termin=D(2026, 10, 9))
    assert wczytaj(katalog).zadania == []


def test_dodaj_watek_w_nieistniejacym_katalogu_to_blad_sprawy(tmp_path):
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie istnieje"):
        dodaj_watek(tmp_path / "brak", "firma", "X")


def test_nowa_sprawa_w_nieistniejacym_katalogu_to_blad_sprawy(tmp_path):
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie istnieje"):
        nowa_sprawa(tmp_path / "brak", "Spamer", "X", "opiekun1")


def test_dodaj_watek_drugi_raz_o_tym_samym_id_odrzucony(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy, match="już istnieje"):
        dodaj_watek(katalog, "firma", "X sp. z o.o.")


def test_zdarzenie_bez_watku_nie_wspomina_cli(katalog):
    # Act / Assert
    with pytest.raises(BladSprawy) as e:
        dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS)
    assert "--watek" not in str(e.value)
    assert "wymaga wątku" in str(e.value)


def test_blad_w_zmianie_nic_nie_zapisuje_i_rewizja_bez_zmian(katalog):
    # Arrange
    rewizja = wczytaj(katalog).rewizja
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie ma wątku 'uodo'"):
        dodaj_zdarzenie(katalog, "odpowiedz", D(2026, 10, 8), Kalendarz(), DZIS, watek="uodo")
    s = wczytaj(katalog)
    assert s.zdarzenia == []
    assert s.rewizja == rewizja


def test_wyjatek_po_mutacji_wycofuje_zapis(katalog, monkeypatch):
    # Arrange
    import kruczek_core.operacje as operacje

    rewizja = wczytaj(katalog).rewizja

    def zepsuta_zastosuj(*_args, **_kwargs):
        raise RuntimeError("awaria po dopisaniu zdarzenia")

    monkeypatch.setattr(operacje, "zastosuj", zepsuta_zastosuj)
    # Act / Assert
    with pytest.raises(RuntimeError):
        dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 8), Kalendarz(), DZIS)
    s = wczytaj(katalog)
    assert s.zdarzenia == []
    assert s.rewizja == rewizja


@pytest.mark.parametrize(
    "dlugosc, data, podstawa, fragment",
    [
        ("14 dni", D(2026, 10, 8), "x", "nieznana długość terminu"),
        ("99999r", D(2026, 10, 8), "x", "poza obsługiwanym zakresem"),
        ("14d", D(1999, 12, 1), "x", "poza obsługiwanym zakresem"),
        ("14d", D(2026, 10, 8), "  ", "podstawa"),
    ],
)
def test_zly_termin_to_blad_sprawy_i_nic_nie_zapisane(katalog, kalendarz, dlugosc, data, podstawa, fragment):
    # Arrange
    rewizja = wczytaj(katalog).rewizja
    # Act / Assert
    with pytest.raises(BladSprawy, match=fragment):
        dodaj_zdarzenie(katalog, "nadanie", data, kalendarz, DZIS, watek="firma",
                        termin=SpecTerminu(dlugosc, podstawa))
    s = wczytaj(katalog)
    assert s.rewizja == rewizja and s.zdarzenia == [] and s.terminy == []


def test_niejednoznaczne_doreczenie_nic_nie_zapisuje_a_ze_wskazaniem_przechodzi(katalog):
    # Arrange — dwa pisma czekają naraz
    spec = SpecTerminu("14d", "x")
    dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 1), Kalendarz(), DZIS, watek="firma", termin=spec)
    dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS, watek="firma", termin=spec)
    rewizja = wczytaj(katalog).rewizja
    # Act / Assert
    with pytest.raises(BladSprawy, match="--dotyczy"):
        dodaj_zdarzenie(katalog, "doreczenie", D(2026, 10, 9), Kalendarz(), DZIS, watek="firma")
    assert wczytaj(katalog).rewizja == rewizja
    dodaj_zdarzenie(katalog, "doreczenie", D(2026, 10, 9), Kalendarz(), DZIS, watek="firma", dotyczy=" z2 ")
    assert wczytaj(katalog).terminy[1].od_zdarzenia == "z3"


def _pusta() -> Sprawa:
    return Sprawa(id="s1", tytul="T", wlasciciel="opiekun1", strona_przeciwna="X")


def test_dopisz_w_pamieci_bez_zapisu_na_dysk(monkeypatch):
    # Arrange
    def nie_wolno(*_a, **_k):
        pytest.fail("dopisz_* nie może sięgać do dysku")

    monkeypatch.setattr(operacje, "zmien", nie_wolno)
    monkeypatch.setattr(operacje, "zapisz_nowa", nie_wolno)
    s = _pusta()
    # Act
    dopisz_watek(s, "firma", "X sp. z o.o.")
    komunikaty = dopisz_zdarzenie(s, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS, watek="firma",
                                  termin=SpecTerminu("14d", "wyznaczony w piśmie"))
    zadanie = dopisz_zadanie(s, "snapshot", D(2026, 10, 22))
    # Assert
    assert [z.typ for z in s.zdarzenia] == ["nadanie"]
    assert any("szacunek" in k for k in komunikaty)
    assert zadanie.id in {a.id for a in s.zadania}


def test_dopisz_zdarzenie_waliduje_jak_dodaj_zdarzenie():
    # Arrange
    s = _pusta()
    # Act / Assert
    with pytest.raises(BladSprawy, match="w przyszłości"):
        dopisz_zdarzenie(s, "fakt", D(2026, 10, 21), Kalendarz(), DZIS)
    assert s.zdarzenia == []


def test_dopisz_zdarzenie_z_bledem_regul_wycofuje_zdarzenie():
    # Arrange
    s = _pusta()
    dopisz_watek(s, "firma", "X sp. z o.o.")
    for data in (D(2026, 10, 1), D(2026, 10, 2)):
        dopisz_zdarzenie(s, "nadanie", data, Kalendarz(), DZIS, watek="firma")
    # Act / Assert — dwa czekające nadania, brak dotyczy
    with pytest.raises(BladSprawy):
        dopisz_zdarzenie(s, "doreczenie", D(2026, 10, 5), Kalendarz(), DZIS, watek="firma")
    assert [z.typ for z in s.zdarzenia] == ["nadanie", "nadanie"]


def test_utworz_sprawe_waliduje_i_ustawia_opiekuna():
    # Act
    s = utworz_sprawe(" Spamer ", " X ", "opiekun1")
    # Assert
    assert (s.tytul, s.strona_przeciwna, len(s.id)) == ("Spamer", "X", 32)
    assert [(u.osoba, u.rola) for u in s.uczestnicy] == [("opiekun1", "opiekun")]
    with pytest.raises(BladSprawy, match="właściciel"):
        utworz_sprawe("T", "X", " ")


def test_zamknij_i_otworz_sprawe(katalog):
    # Act
    zamknij_sprawe(katalog, "ugoda")
    zamknieta = wczytaj(katalog)
    otworz_sprawe(katalog)
    otwarta = wczytaj(katalog)
    # Assert
    assert (zamknieta.zamknieta, zamknieta.wynik) == (True, "ugoda")
    assert (otwarta.zamknieta, otwarta.wynik) == (False, None)


@pytest.mark.parametrize("wynik", ["", "wygrałem", "Ugoda"])
def test_zamknij_z_nieznanym_wynikiem_odrzucone(katalog, wynik):
    # Act / Assert
    with pytest.raises(BladSprawy, match="wynik"):
        zamknij_sprawe(katalog, wynik)
    assert wczytaj(katalog).zamknieta is False


def test_zamknij_zamknieta_odrzucone(katalog):
    # Arrange
    zamknij_sprawe(katalog, "wygrana")
    # Act / Assert
    with pytest.raises(BladSprawy, match="już zamknięta"):
        zamknij_sprawe(katalog, "ugoda")


def test_popraw_opis_godzine_i_wyczysc_pewnosc(katalog):
    # Arrange
    dodaj_zdarzenie(katalog, "telefon", D(2026, 10, 8), Kalendarz(), DZIS, opis="x", godzina="10:00",
                    pewnosc="poszlaka")
    # Act
    popraw_zdarzenie(katalog, "z1", Kalendarz(), DZIS, opis="dzwonił dział reklamacji", godzina="10:15", pewnosc="")
    # Assert
    z = wczytaj(katalog).znajdz_zdarzenie("z1")
    assert (z.opis, z.godzina, z.pewnosc) == ("dzwonił dział reklamacji", "10:15", None)


@pytest.mark.parametrize(
    "zmiany, komunikat",
    [({}, "nic do poprawienia"), ({"data": D(2026, 10, 21)}, "w przyszłości"), ({"godzina": "7"}, "GG:MM")],
)
def test_popraw_zle_dane_odrzucone_nic_nie_zapisane(katalog, zmiany, komunikat):
    # Arrange
    dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 8), Kalendarz(), DZIS)
    rewizja = wczytaj(katalog).rewizja
    # Act / Assert
    with pytest.raises(BladSprawy, match=komunikat):
        popraw_zdarzenie(katalog, "z1", Kalendarz(), DZIS, **zmiany)
    assert wczytaj(katalog).rewizja == rewizja


def test_popraw_date_doreczenia_przed_nadaniem_odrzucona_rewizja_bez_zmian(katalog):
    # Arrange
    dodaj_zdarzenie(katalog, "nadanie", D(2026, 10, 8), Kalendarz(), DZIS, watek="firma",
                    termin=SpecTerminu("14d", "wyznaczony w piśmie"))
    dodaj_zdarzenie(katalog, "doreczenie", D(2026, 10, 10), Kalendarz(), DZIS, watek="firma")
    rewizja = wczytaj(katalog).rewizja
    # Act / Assert
    with pytest.raises(BladSprawy, match="z1"):
        popraw_zdarzenie(katalog, "z2", Kalendarz(), DZIS, data=D(2026, 10, 7))
    s = wczytaj(katalog)
    assert s.rewizja == rewizja and s.znajdz_zdarzenie("z2").data == D(2026, 10, 10)


def test_cofnij_tylko_ostatnie(katalog):
    # Arrange
    dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 8), Kalendarz(), DZIS)
    dodaj_zdarzenie(katalog, "fakt", D(2026, 10, 9), Kalendarz(), DZIS)
    # Act / Assert
    with pytest.raises(BladSprawy, match="tylko ostatnie.*z2"):
        cofnij_zdarzenie(katalog, "z1", Kalendarz())
    cofnij_zdarzenie(katalog, "z2", Kalendarz())
    assert [z.id for z in wczytaj(katalog).zdarzenia] == ["z1"]
