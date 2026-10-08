import datetime as dt
import json
import multiprocessing

import pytest

from kruczek_core.model import SCHEMA_VERSION, BladSprawy, Sprawa, Zadanie, kolejne_id
from kruczek_core.repozytorium import (
    PLIK_SPRAWY,
    KonfliktRewizji,
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
    monkeypatch.setattr("kruczek_core.repozytorium.SCHEMA_VERSION", 2)
    monkeypatch.setattr(
        "kruczek_core.repozytorium.MIGRACJE",
        {1: lambda d: {**d, "schema_version": 2, "tytul": d["tytul"] + " (zmigrowane)"}},
    )
    # Act
    sprawa = wczytaj(katalog)
    # Assert
    assert sprawa.tytul.endswith("(zmigrowane)")


def test_brak_kroku_migracji_i_wyjatek_w_migracji_to_czytelny_blad(tmp_path, monkeypatch):
    # Arrange
    katalog = nowa(tmp_path)
    monkeypatch.setattr("kruczek_core.repozytorium.SCHEMA_VERSION", 2)
    monkeypatch.setattr("kruczek_core.repozytorium.MIGRACJE", {})
    # Act / Assert
    with pytest.raises(BladSprawy, match="migracj"):
        wczytaj(katalog)
    monkeypatch.setattr("kruczek_core.repozytorium.MIGRACJE", {1: lambda d: d["nie_ma"]})
    with pytest.raises(BladSprawy, match="niepoprawne dane"):
        wczytaj(katalog)


@pytest.mark.parametrize(
    "zawartosc",
    [
        "﻿# SPRAWA: X\n".encode("utf-8"),
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
