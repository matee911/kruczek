import datetime as dt
import json
import multiprocessing
from pathlib import Path

import pytest
from kruczek_core.model import SCHEMA_VERSION, BladSprawy, Sprawa, Zadanie, kolejne_id
from kruczek_core.repozytorium import (
    PLIK_SPRAWY,
    KonfliktRewizji,
    czy_folder_sprawy,
    lista_spraw,
    wczytaj,
    zapisz,
    zapisz_nowa,
    zmien,
)


def nowa(tmp_path, nazwa="sprawa") -> "Path":
    katalog = tmp_path / nazwa
    katalog.mkdir()
    zapisz_nowa(katalog, Sprawa(id="s1", tytul="T", wlasciciel="w", strona_przeciwna="X"))
    return katalog


def test_zapis_i_odczyt(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    # Act
    sprawa = wczytaj(katalog)
    # Assert
    assert sprawa.tytul == "T"
    assert sprawa.rewizja == 0


def test_zapisz_nowa_nie_nadpisuje(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    # Act / Assert
    with pytest.raises(BladSprawy, match="już istnieje"):
        zapisz_nowa(katalog, Sprawa(id="s2", tytul="T2", wlasciciel="w", strona_przeciwna="X"))


def test_brak_pliku(tmp_path):
    # Act / Assert
    with pytest.raises(BladSprawy, match="brak sprawa.json"):
        wczytaj(tmp_path)


def test_uszkodzony_json_to_czytelny_blad(tmp_path):
    # Arrange
    (tmp_path / PLIK_SPRAWY).write_text('{"id": "s1", ', encoding="utf-8")
    # Act / Assert
    with pytest.raises(BladSprawy, match="uszkodzony JSON"):
        wczytaj(tmp_path)


def test_nieznane_pole_to_czytelny_blad(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    dane = json.loads((katalog / PLIK_SPRAWY).read_text(encoding="utf-8"))
    dane["watki"] = [{"id": "w", "adresat": "A", "literowka": 1}]
    (katalog / PLIK_SPRAWY).write_text(json.dumps(dane), encoding="utf-8")
    # Act / Assert
    with pytest.raises(BladSprawy, match="niepoprawne dane"):
        wczytaj(katalog)


def test_nowszy_format_odrzucony(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    dane = json.loads((katalog / PLIK_SPRAWY).read_text(encoding="utf-8"))
    dane["schema_version"] = SCHEMA_VERSION + 1
    (katalog / PLIK_SPRAWY).write_text(json.dumps(dane), encoding="utf-8")
    # Act / Assert
    with pytest.raises(BladSprawy, match="zaktualizuj plugin"):
        wczytaj(katalog)


def test_zmien_podbija_rewizje_i_nie_zostawia_plikow_tymczasowych(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    # Act
    zmien(katalog, lambda s: s.watki.clear())
    # Assert
    assert wczytaj(katalog).rewizja == 1
    assert sorted(p.name for p in katalog.iterdir() if p.name.endswith(".tmp")) == []


def test_blad_w_zmianie_nic_nie_zapisuje(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)

    def zla(s):
        s.tytul = "zmienione"
        raise BladSprawy("stop")

    # Act
    with pytest.raises(BladSprawy):
        zmien(katalog, zla)
    # Assert
    assert wczytaj(katalog).tytul == "T"
    assert wczytaj(katalog).rewizja == 0


def test_zapis_z_nieaktualna_rewizja_odrzucony(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    nieaktualna = wczytaj(katalog)
    zmien(katalog, lambda s: None)
    # Act / Assert
    with pytest.raises(KonfliktRewizji):
        zapisz(katalog, nieaktualna, oczekiwana_rewizja=nieaktualna.rewizja)


def _dopisz_zadania(katalog, ile):
    for _ in range(ile):
        zmien(
            katalog,
            lambda s: s.zadania.append(Zadanie(kolejne_id("a", s.zadania), "x", dt.date(2026, 1, 1))),
        )


def test_dwa_procesy_nie_gubia_zmian(tmp_path):
    # Arrange
    katalog = nowa(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    procesy = [ctx.Process(target=_dopisz_zadania, args=(katalog, 20)) for _ in range(2)]
    # Act
    for p in procesy:
        p.start()
    for p in procesy:
        p.join(timeout=60)
    # Assert
    sprawa = wczytaj(katalog)
    assert len(sprawa.zadania) == 40
    assert len({z.id for z in sprawa.zadania}) == 40
    assert sprawa.rewizja == 40


def test_lista_spraw_rozroznia_stary_format_i_pomija_katalogi_projektu(tmp_path):
    # Arrange
    nowa(tmp_path, "nowa-sprawa")
    stara = tmp_path / "stara-sprawa"
    stara.mkdir()
    (stara / "index.md").write_text("# SPRAWA: Stara\n", encoding="utf-8")
    for nazwa in ("BAZA_WIEDZY", "_SZABLONY", ".git"):
        (tmp_path / nazwa).mkdir()
    (tmp_path / "BAZA_WIEDZY" / "index.md").write_text("# Baza\n", encoding="utf-8")
    # Act
    lista = lista_spraw(tmp_path)
    # Assert
    assert [p.name for p in lista.sprawy] == ["nowa-sprawa"]
    assert [p.name for p in lista.stary_format] == ["stara-sprawa"]


def test_bajty_spoza_utf8_to_czytelny_blad(tmp_path):
    # Arrange
    (tmp_path / PLIK_SPRAWY).write_bytes(b'{"id": "\xff\xfe"}')
    # Act / Assert
    with pytest.raises(BladSprawy, match="sprawa.json"):
        wczytaj(tmp_path)


def test_nieczytelny_plik_to_czytelny_blad(tmp_path):
    # Arrange
    (tmp_path / PLIK_SPRAWY).mkdir()
    # Act / Assert
    with pytest.raises(BladSprawy, match="sprawa.json"):
        wczytaj(tmp_path)


@pytest.mark.parametrize("wersja", [0, True, "1", -1])
def test_zla_schema_version_to_czytelny_blad(tmp_path, wersja):
    # Arrange
    katalog = nowa(tmp_path)
    dane = json.loads((katalog / PLIK_SPRAWY).read_text(encoding="utf-8"))
    dane["schema_version"] = wersja
    (katalog / PLIK_SPRAWY).write_text(json.dumps(dane), encoding="utf-8")
    # Act / Assert
    with pytest.raises(BladSprawy, match="schema_version"):
        wczytaj(katalog)


def test_migracja_jest_stosowana(tmp_path, monkeypatch):
    # Arrange
    katalog = nowa(tmp_path)
    monkeypatch.setattr("kruczek_core.repozytorium.SCHEMA_VERSION", SCHEMA_VERSION + 1)
    monkeypatch.setattr(
        "kruczek_core.repozytorium.MIGRACJE",
        {SCHEMA_VERSION: lambda d: {**d, "schema_version": SCHEMA_VERSION + 1, "tytul": d["tytul"] + " (zmigrowane)"}},
    )
    # Act
    sprawa = wczytaj(katalog)
    # Assert
    assert sprawa.tytul.endswith("(zmigrowane)")


def test_brak_kroku_migracji_i_wyjatek_w_migracji_to_czytelny_blad(tmp_path, monkeypatch):
    # Arrange
    katalog = nowa(tmp_path)
    monkeypatch.setattr("kruczek_core.repozytorium.SCHEMA_VERSION", SCHEMA_VERSION + 1)
    monkeypatch.setattr("kruczek_core.repozytorium.MIGRACJE", {})
    # Act / Assert
    with pytest.raises(BladSprawy, match="migracj"):
        wczytaj(katalog)
    monkeypatch.setattr("kruczek_core.repozytorium.MIGRACJE", {SCHEMA_VERSION: lambda d: d["nie_ma"]})
    with pytest.raises(BladSprawy, match="niepoprawne dane"):
        wczytaj(katalog)


@pytest.mark.parametrize(
    "zawartosc",
    [
        "﻿# SPRAWA: X\n".encode(),
        b"\xef\xbb\xbf# SPRAWA: X\n",
        b"\n\n# SPRAWA: X\n",
        b"# SPRAWA: X\n\xff\n",
    ],
)
def test_lista_spraw_stary_format_odporna_na_bom_pusta_linie_i_zle_bajty(tmp_path, zawartosc):
    # Arrange
    stara = tmp_path / "stara"
    stara.mkdir()
    (stara / "index.md").write_bytes(zawartosc)
    # Act
    lista = lista_spraw(tmp_path)
    # Assert
    assert [p.name for p in lista.stary_format] == ["stara"]


def test_nieudany_replace_nie_zostawia_tmp_i_nie_psuje_sprawy(tmp_path, monkeypatch):
    # Arrange
    katalog = nowa(tmp_path)

    def zepsuty(*a, **k):
        raise OSError("dysk")

    monkeypatch.setattr("kruczek_core.repozytorium.os.replace", zepsuty)
    # Act
    with pytest.raises(OSError):
        zmien(katalog, lambda s: s.watki.clear())
    monkeypatch.undo()
    # Assert
    assert [p.name for p in katalog.iterdir() if p.name.endswith(".tmp")] == []
    assert wczytaj(katalog).rewizja == 0


@pytest.mark.parametrize(
    "zawartosc",
    ["# Sprawa: x\n", "---\ntytul: x\n---\n", "", "Spamer\n=====\n"],
)
def test_stary_format_to_kazdy_folder_z_index_md_bez_sprawa_json(tmp_path, zawartosc):
    # Arrange
    stara = tmp_path / "stara"
    stara.mkdir()
    (stara / "index.md").write_text(zawartosc, encoding="utf-8")
    (tmp_path / "bez-indexu").mkdir()
    # Act
    lista = lista_spraw(tmp_path)
    # Assert
    assert [p.name for p in lista.stary_format] == ["stara"]
    assert lista.sprawy == []


def test_plik_w_wersji_1_wczytany_jako_v2(tmp_path):
    # Arrange — plik z wersji rozwojowej: nadanie z1, doręczenie z2, które zamknęło sprawdzenie doręczenia a1
    katalog = tmp_path / "s"
    katalog.mkdir()
    v1 = {
        "id": "s1", "tytul": "T", "wlasciciel": "w", "strona_przeciwna": "X",
        "schema_version": 1, "rewizja": 3, "zamknieta": False, "wynik": None,
        "uczestnicy": [], "watki": [{"id": "firma", "adresat": "X"}], "pisma": [], "dowody": [],
        "zdarzenia": [
            {"id": "z1", "data": "2026-10-01", "typ": "nadanie", "opis": "", "watek": "firma", "dowody": []},
            {"id": "z2", "data": "2026-10-03", "typ": "doreczenie", "opis": "", "watek": "firma", "dowody": []},
        ],
        "terminy": [{"id": "t1", "podstawa": "x", "od_zdarzenia": "z2", "dlugosc": "14d",
                     "data_konca": "2026-10-19", "watek": "firma", "szacunek": False, "czyj": "adresata"}],
        "zadania": [{"id": "a1", "opis": "sprawdź datę doręczenia", "aktywne_od": "2026-10-02",
                     "termin": None, "watek": "firma", "regula": "sprawdz-doreczenie", "termin_id": "t1",
                     "zrobione": "2026-10-03", "zdarzenie_id": "z1", "zamkniete_przez": "z2"}],
    }
    (katalog / PLIK_SPRAWY).write_text(json.dumps(v1), encoding="utf-8")
    # Act
    s = wczytaj(katalog)
    zmien(katalog, lambda s: None)
    # Assert
    assert s.schema_version == SCHEMA_VERSION == 2
    assert s.znajdz_zdarzenie("z2").dotyczy == "z1"
    assert s.znajdz_zdarzenie("z1").godzina is None
    assert json.loads((katalog / PLIK_SPRAWY).read_text(encoding="utf-8"))["schema_version"] == 2


def _index(katalog, tresc):
    katalog.mkdir(parents=True, exist_ok=True)
    (katalog / "index.md").write_text(tresc, encoding="utf-8")


def test_lista_spraw_schodzi_do_podprojektu_o_jeden_poziom(tmp_path):
    # Arrange
    _index(tmp_path / "podprojekt", "﻿\n# Rejestr spraw\n")
    nowa(tmp_path / "podprojekt", "sprawa-a")
    _index(tmp_path / "podprojekt" / "sprawa-b", "# Sprawa: B\n")
    for ukryty in ("_SZABLONY", ".git", "BAZA_WIEDZY"):
        nowa(tmp_path / "podprojekt", ukryty)
    nowa(tmp_path / "podprojekt" / "sprawa-a", "za-gleboko")
    # Act
    lista = lista_spraw(tmp_path)
    # Assert
    assert [p.relative_to(tmp_path).as_posix() for p in lista.sprawy] == ["podprojekt/sprawa-a"]
    assert [p.relative_to(tmp_path).as_posix() for p in lista.stary_format] == ["podprojekt/sprawa-b"]


def test_czy_folder_sprawy_ignoruje_wielkosc_liter_naglowka(tmp_path):
    # Arrange
    _index(tmp_path / "duze", "# SPRAWA: A\n")
    _index(tmp_path / "male", "# Sprawa: A\n")
    _index(tmp_path / "rejestr", "# Rejestr spraw\n")
    # Act / Assert
    assert czy_folder_sprawy(tmp_path / "duze") and czy_folder_sprawy(tmp_path / "male")
    assert not czy_folder_sprawy(tmp_path / "rejestr")


def test_lista_spraw_zbiera_foldery_bez_indexu_i_sprawa_json(tmp_path):
    # Arrange
    nowa(tmp_path, "sprawa-a")
    (tmp_path / "kopia 2").mkdir()
    for ukryty in ("_to_delete", ".git", "BAZA_WIEDZY"):
        (tmp_path / ukryty).mkdir()
    # Act
    lista = lista_spraw(tmp_path)
    # Assert
    assert [p.name for p in lista.bez_indexu] == ["kopia 2"]
    assert [p.name for p in lista.sprawy] == ["sprawa-a"]


def test_brak_sprawa_json_przy_index_md_wskazuje_migracje(tmp_path):
    # Arrange
    (tmp_path / "index.md").write_text("# Sprawa: Stara\n", encoding="utf-8")
    # Act / Assert
    with pytest.raises(BladSprawy, match="stary format — przenieś: /kruczek:migruj"):
        wczytaj(tmp_path)


def test_brak_sprawa_json_bez_index_md_wskazuje_zalozenie(tmp_path):
    # Act / Assert
    with pytest.raises(BladSprawy, match="załóż sprawę: teczka.py nowa"):
        wczytaj(tmp_path)
