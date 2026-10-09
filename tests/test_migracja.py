import datetime as dt

import pytest

from dane_migracji import STARY_INDEX, propozycja
from kruczek_core import migracja
from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.migracja import kopia_zapasowa, tytul_z_naglowka, wstaw_znaczniki_chronologii, zbuduj_sprawe
from kruczek_core.model import BladSprawy

D = dt.date
DZIS = D(2026, 10, 20)


def test_korespondencja_tam_i_z_powrotem_odtworzona_w_kolejnosci_dat():
    # Arrange — zdarzenia celowo nie po kolei
    p = propozycja()
    p["zdarzenia"].reverse()
    # Act
    wynik = zbuduj_sprawe(p, Kalendarz(), DZIS, "opiekun1")
    # Assert
    s = wynik.sprawa
    assert [z.typ for z in s.zdarzenia] == ["nadanie", "odpowiedz", "nadanie", "doreczenie"]
    assert s.znajdz_zdarzenie("z4").dotyczy == "z3"
    t2 = s.terminy[1]
    assert (t2.od_zdarzenia, t2.szacunek, t2.data_konca) == ("z4", False, D(2026, 9, 29))


@pytest.mark.parametrize(
    "zmiany, komunikat",
    [
        ({"nieznane": 1}, "nieznane"),
        ({"zdarzenia": [{"data": "2026-10-30", "typ": "fakt"}]}, "zdarzenie 1.*w przyszłości"),
        ({"zdarzenia": [{"data": "2026-10-01", "typ": "doreczenie", "watek": "firma", "dotyczy": "brak"}]},
         "dotyczy.*brak"),
        ({"zdarzenia": [{"data": "01.10.2026", "typ": "fakt"}]}, "data"),
        ({"wynik": "remis", "zamknieta": True}, "wynik"),
        ({"tytul": "  "}, "tytuł"),
        ({"zdarzenia": [1]}, "zdarzenie 1.*obiekt"),
        ({"zdarzenia": [{"data": "2026-10-01", "typ": "telefon", "godzina": 9}]}, "zdarzenie 1.*godzina"),
        ({"watki": "firma"}, "wątki.*listy"),
        ({"zdarzenia": [{"data": "2026-10-01", "typ": "nadanie", "watek": "firma", "termin": "14d"}]},
         "zdarzenie 1.*termin.*obiekt"),
        ({"zdarzenia": [{"data": "2026-10-01", "typ": "fakt", "dowody": "plik.pdf"}]}, "zdarzenie 1.*dowody.*listy"),
        ({"zamknieta": "false"}, "zamknieta"),
        ({"wynik": "ugoda"}, "wynik.*zamknieta"),
        ({"zdarzenia": [{"klucz": "a", "data": "2026-10-01", "typ": "fakt"},
                        {"klucz": "a", "data": "2026-10-02", "typ": "fakt"}]}, "klucz 'a'.*dwa razy"),
    ],
    ids=["nieznane-pole", "przyszlosc", "zly-klucz", "zla-data", "zly-wynik", "pusty-tytul",
         "zdarzenie-nie-obiekt", "godzina-liczba", "watki-nie-lista", "termin-napis", "dowody-napis",
         "zamknieta-napis", "wynik-bez-zamkniecia", "klucz-dwa-razy"],
)
def test_zla_propozycja_czytelny_blad(zmiany, komunikat):
    # Act / Assert
    with pytest.raises(BladSprawy, match=komunikat):
        zbuduj_sprawe(propozycja(**zmiany), Kalendarz(), DZIS, "opiekun1")


def test_blad_dotyczy_podaje_klucze_propozycji_zamiast_id():
    # Arrange — dwa pisma czekają w wątku, doręczenie bez wskazania
    p = propozycja(zdarzenia=[
        {"klucz": "pierwsze", "data": "2026-09-01", "typ": "nadanie", "watek": "firma",
         "termin": {"dlugosc": "14d", "podstawa": "x"}},
        {"klucz": "drugie", "data": "2026-09-05", "typ": "nadanie", "watek": "firma",
         "termin": {"dlugosc": "14d", "podstawa": "x"}},
        {"data": "2026-09-08", "typ": "doreczenie", "watek": "firma"},
    ])
    # Act
    with pytest.raises(BladSprawy) as e:
        zbuduj_sprawe(p, Kalendarz(), DZIS, "opiekun1")
    # Assert
    komunikat = str(e.value)
    assert "'pierwsze'" in komunikat and "'drugie'" in komunikat
    assert "z1" not in komunikat and "z2" not in komunikat
    assert 'w propozycji ustaw "dotyczy": "<klucz nadania>"' in komunikat


def test_brak_aktywne_od_w_zadaniu_to_dzis():
    # Act
    wynik = zbuduj_sprawe(propozycja(zadania=[{"opis": "Zebrać paragon"}]), Kalendarz(), DZIS, "opiekun1")
    # Assert
    assert wynik.sprawa.zadania[-1].aktywne_od == DZIS


def test_ostrzega_o_starych_otwartych_zadaniach():
    # Arrange — pismo bez odpowiedzi sprzed 2 miesięcy
    p = propozycja(zdarzenia=[{"data": "2026-08-01", "typ": "nadanie", "watek": "firma",
                               "termin": {"dlugosc": "14d", "podstawa": "x"}}], zadania=[])
    # Act
    wynik = zbuduj_sprawe(p, Kalendarz(), DZIS, "opiekun1")
    # Assert
    assert any(f"ponad {migracja._STARE_ZADANIA_DNI} dni" in o for o in wynik.ostrzezenia)


@pytest.mark.parametrize("naglowek", ["## 1. Chronologia", "## Chronologia", "## 1.Chronologia  ",
                                      "## 1. CHRONOLOGIA"])
def test_znaczniki_wstawione_pod_starym_naglowkiem_a_stara_tabela_zostaje(naglowek):
    # Arrange
    tekst = STARY_INDEX.replace("## 1. Chronologia", naglowek)
    # Act
    nowy, wstawiono = wstaw_znaczniki_chronologii(tekst)
    # Assert
    assert wstawiono
    assert nowy.index("<!-- kruczek:chronologia -->") < nowy.index("### Chronologia sprzed migracji (archiwalna")
    assert nowy.index("### Chronologia sprzed migracji") < nowy.index("| 2026-09-01 | | Reklamacja")
    linie = nowy.splitlines()
    assert all(linia in linie for linia in tekst.splitlines() if linia.strip())


def test_znaczniki_w_pliku_z_crlf_nie_gubia_linii():
    # Arrange
    tekst = STARY_INDEX.replace("\n", "\r\n")
    # Act
    nowy, wstawiono = wstaw_znaczniki_chronologii(tekst)
    # Assert
    assert wstawiono
    linie = [linia.rstrip("\r") for linia in nowy.splitlines()]
    assert all(linia.rstrip("\r") in linie for linia in tekst.splitlines() if linia.strip())


@pytest.mark.parametrize("tekst", ["# SPRAWA: X\n\nnotatki\n", "## Chronologia\n<!-- kruczek:chronologia -->\n",
                                   "##\nChronologia\n"])
def test_bez_naglowka_albo_ze_znacznikami_nic_nie_wstawia(tekst):
    # Act
    nowy, wstawiono = wstaw_znaczniki_chronologii(tekst)
    # Assert
    assert (nowy, wstawiono) == (tekst, False)


@pytest.mark.parametrize("tekst, tytul", [
    ("# SPRAWA: X sp. z o.o.\n", "X sp. z o.o."),
    ("\ufeff\n# Sprawa:  Reklamacja butów \n## 1. Chronologia\n", "Reklamacja butów"),
    ("# Rejestr spraw\n", None),
    ("", None),
])
def test_tytul_z_naglowka_bez_wzgledu_na_wielkosc_liter(tekst, tytul):
    # Act / Assert
    assert tytul_z_naglowka(tekst) == tytul


def test_kopia_zapasowa_bajt_w_bajt_i_nie_nadpisuje(tmp_path):
    # Arrange — BOM, CRLF i bajt spoza UTF-8 muszą przejść bez zmian
    tresc = b"\xef\xbb\xbf# SPRAWA: X\r\n\r\nnotatki \xff\r\n"
    (tmp_path / "index.md").write_bytes(tresc)
    # Act
    pierwsza = kopia_zapasowa(tmp_path, DZIS)
    druga = kopia_zapasowa(tmp_path, DZIS)
    # Assert
    assert pierwsza.name == "index.przed-migracja-2026-10-20.md"
    assert druga.name == "index.przed-migracja-2026-10-20-2.md"
    assert pierwsza.read_bytes() == tresc and druga.read_bytes() == tresc


def test_kopia_zapasowa_bez_index_md(tmp_path):
    # Act / Assert
    assert kopia_zapasowa(tmp_path, DZIS) is None
    assert not (tmp_path / "ROBOCZE").exists()


_NADANIE_10 = {"klucz": "n", "data": "2026-10-01", "godzina": "10:00", "typ": "nadanie", "watek": "firma",
               "termin": {"dlugosc": "14d", "podstawa": "x"}}
_DORECZENIE_TEGO_DNIA = {"data": "2026-10-01", "typ": "doreczenie", "watek": "firma"}


@pytest.mark.parametrize("zdarzenia", [
    [_NADANIE_10, {**_DORECZENIE_TEGO_DNIA, "dotyczy": "n"}],
    [_NADANIE_10, _DORECZENIE_TEGO_DNIA],
    [{**_DORECZENIE_TEGO_DNIA, "dotyczy": "n"}, _NADANIE_10],
], ids=["z-dotyczy", "bez-dotyczy-fifo", "doreczenie-wpisane-przed-nadaniem"])
def test_doreczenie_tego_samego_dnia_bez_godziny_po_nadaniu(zdarzenia):
    # Act
    s = zbuduj_sprawe(propozycja(zdarzenia=zdarzenia), Kalendarz(), DZIS, "opiekun1").sprawa
    # Assert
    nadanie, doreczenie = s.zdarzenia
    assert (nadanie.typ, doreczenie.typ, doreczenie.dotyczy) == ("nadanie", "doreczenie", nadanie.id)
    assert (s.terminy[0].od_zdarzenia, s.terminy[0].szacunek) == (doreczenie.id, False)


def test_w_jednym_dniu_kolejnosc_z_propozycji_a_nie_godzina():
    # Arrange
    zdarzenia = [{"data": "2026-10-01", "godzina": "15:00", "typ": "fakt", "opis": "pierwszy"},
                 {"data": "2026-10-01", "typ": "fakt", "opis": "drugi"}]
    # Act
    s = zbuduj_sprawe(propozycja(zdarzenia=zdarzenia), Kalendarz(), DZIS, "opiekun1").sprawa
    # Assert
    assert [z.opis for z in s.zdarzenia] == ["pierwszy", "drugi"]


def test_dotyczy_zdarzenia_z_pozniejszej_daty_to_blad():
    # Arrange
    zdarzenia = [{**_DORECZENIE_TEGO_DNIA, "dotyczy": "n"}, {**_NADANIE_10, "data": "2026-10-02"}]
    # Act / Assert
    with pytest.raises(BladSprawy, match="dotyczy 'n' — nie ma wcześniejszego"):
        zbuduj_sprawe(propozycja(zdarzenia=zdarzenia), Kalendarz(), DZIS, "opiekun1")


@pytest.mark.parametrize("odpowiedz, ostrzega", [(True, False), (False, True)],
                         ids=["z-odpowiedzia", "bez-odpowiedzi"])
def test_ostrzezenie_o_minionym_szacunku_tylko_dla_pisma_bez_odpowiedzi(odpowiedz, ostrzega):
    # Arrange — nadanie bez daty doręczenia, termin szacunkowy minął
    zdarzenia = [{"data": "2026-09-01", "typ": "nadanie", "watek": "firma",
                  "termin": {"dlugosc": "14d", "podstawa": "x"}}]
    if odpowiedz:
        zdarzenia.append({"data": "2026-09-10", "typ": "odpowiedz", "watek": "firma"})
    # Act
    wynik = zbuduj_sprawe(propozycja(zdarzenia=zdarzenia, zadania=[]), Kalendarz(), DZIS, "opiekun1")
    # Assert
    assert any("liczony od nadania i już minął" in o for o in wynik.ostrzezenia) is ostrzega
