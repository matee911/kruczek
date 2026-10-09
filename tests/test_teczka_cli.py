import datetime as dt
import json

import pytest

import teczka
from kruczek_core import widok


def uruchom(capsys, *argv):
    kod = teczka.main(["--dzis", "2026-10-20", *argv])
    wyjscie = capsys.readouterr()
    return kod, wyjscie.out, wyjscie.err


@pytest.fixture
def projekt(tmp_path, capsys):
    uruchom(capsys, "nowa", str(tmp_path / "spamer"), "--tytul", "Spamer", "--strona", "X sp. z o.o.")
    uruchom(capsys, "watek", str(tmp_path / "spamer"), "firma", "--adresat", "X sp. z o.o.")
    return tmp_path


def test_przeplyw_nadanie_i_co_robic(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zdarzenie", sprawa, "--typ", "nadanie", "--data", "2026-10-08", "--watek", "firma",
            "--termin", "14d", "--podstawa", "art. 7 u.r.")
    uruchom(capsys, "zadanie", sprawa, "snapshot Web Archive", "--aktywne-od", "+7d")
    # Act
    kod, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 0
    assert "TERAZ" in out and "sprawdź datę doręczenia" in out
    assert "CZEKAM" in out and "do 2026-10-22 (szacunek)" in out
    assert "WKRÓTCE" in out and "snapshot Web Archive" in out


def test_moj_termin_z_wplywu_w_teraz(projekt, capsys):
    # Arrange — decyzja doręczona 12.10, 14 dni na odwołanie
    uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "wplyw", "--data", "2026-10-12",
            "--watek", "firma", "--termin", "14d", "--podstawa", "pouczenie w decyzji")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    teraz = out.split("CZEKAM")[0]
    assert "termin 2026-10-26" in teraz


def test_stary_format_wypisany(projekt, capsys):
    # Arrange
    stara = projekt / "stara"
    stara.mkdir()
    (stara / "index.md").write_text("# SPRAWA: Stara\n", encoding="utf-8")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert "STARY FORMAT" in out and "stara" in out


def test_uszkodzony_json_kod_1_bez_tracebacku(projekt, capsys):
    # Arrange
    (projekt / "spamer" / "sprawa.json").write_text("{", encoding="utf-8")
    # Act
    kod, _, err = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 1
    assert "uszkodzony JSON" in err
    assert "Traceback" not in err


def test_termin_wymaga_podstawy(projekt, capsys):
    # Act
    kod, _, err = uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "nadanie",
                          "--watek", "firma", "--termin", "14d")
    # Assert
    assert kod == 1
    assert "--podstawa" in err


def test_zrobione(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zadanie", sprawa, "x", "--aktywne-od", "2026-10-01")
    # Act
    kod, out, _ = uruchom(capsys, "zrobione", sprawa, "a1")
    # Assert
    assert kod == 0 and "a1" in out
    dane = json.loads((projekt / "spamer" / "sprawa.json").read_text(encoding="utf-8"))
    assert dane["zadania"][0]["zrobione"] == "2026-10-20"


def test_renderuj_tworzy_bloki(projekt, capsys):
    # Arrange
    index = projekt / "spamer" / "index.md"
    index.write_text("# SPRAWA: Spamer\n", encoding="utf-8")
    # Act
    kod, _, _ = uruchom(capsys, "renderuj", str(projekt / "spamer"))
    # Assert
    assert kod == 0
    assert "<!-- kruczek:zadania -->" in index.read_text(encoding="utf-8")


def test_dzien_wolny_przelicza_otwarte_terminy(projekt, capsys):
    # Arrange — nadanie 2026-10-08 + 14d → 2026-10-22 (czwartek)
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zdarzenie", sprawa, "--typ", "nadanie", "--data", "2026-10-08", "--watek", "firma",
            "--termin", "14d", "--podstawa", "x")
    # Act
    kod, out, _ = uruchom(capsys, "dzien-wolny", "2026-10-22", "--podstawa", "Dz.U. 2026 poz. 9999",
                          "--projekt", str(projekt))
    # Assert
    assert kod == 0
    assert "t1: 2026-10-22 → 2026-10-23" in out


@pytest.mark.parametrize(
    "tekst, oczekiwana",
    [("2026-11-03", dt.date(2026, 11, 3)), ("+14d", dt.date(2026, 11, 3)), ("+2t", dt.date(2026, 11, 3))],
)
def test_parsuj_date(tekst, oczekiwana):
    # Act / Assert
    assert teczka.parsuj_date(tekst, dt.date(2026, 10, 20)) == oczekiwana


def test_bez_podkomendy_kod_2(capsys):
    # Act
    with pytest.raises(SystemExit) as e:
        teczka.main([])
    # Assert
    assert e.value.code == 2


def test_co_robic_nieistniejacy_katalog_kod_1_bez_tracebacku(tmp_path, capsys):
    # Act
    kod, _, err = uruchom(capsys, "co-robic", str(tmp_path / "nie-ma"))
    # Assert
    assert kod == 1
    assert "błąd:" in err
    assert "Traceback" not in err


def test_uszkodzony_plik_dni_wolnych_kod_1_bez_tracebacku(projekt, capsys):
    # Arrange
    (projekt / ".kruczek").mkdir()
    (projekt / ".kruczek" / "dni-wolne.json").write_text("{", encoding="utf-8")
    # Act
    kod, _, err = uruchom(capsys, "przelicz", str(projekt / "spamer"))
    # Assert
    assert kod == 1
    assert "uszkodzony plik dni wolnych" in err
    assert "Traceback" not in err


def _zaloz_sprawe(capsys, projekt, nazwa, tytul):
    uruchom(capsys, "nowa", str(projekt / nazwa), "--tytul", tytul, "--strona", "Y")
    return projekt / nazwa


def test_co_robic_z_folderu_sprawy_pokazuje_caly_projekt(projekt, capsys, monkeypatch):
    # Arrange
    spamer = projekt / "spamer"
    inna = _zaloz_sprawe(capsys, projekt, "inna", "Inna")
    uruchom(capsys, "zadanie", str(spamer), "zadanie spamera")
    uruchom(capsys, "zadanie", str(inna), "zadanie innej")
    monkeypatch.chdir(spamer)
    # Act
    kod, out, err = uruchom(capsys, "co-robic")
    # Assert
    assert kod == 0
    assert "zadanie spamera" in out.split("CZEKAM")[0] and "zadanie innej" in out.split("CZEKAM")[0]
    assert "uwaga:" in err and "folder sprawy" in err


def test_dzien_wolny_z_folderu_sprawy_zapisuje_w_projekcie(projekt, capsys):
    # Act
    kod, out, err = uruchom(capsys, "dzien-wolny", "2026-11-13", "--podstawa", "Dz.U. 2026 poz. 1",
                            "--projekt", str(projekt / "spamer"))
    # Assert
    assert kod == 0
    assert (projekt / ".kruczek" / "dni-wolne.json").exists()
    assert not (projekt / "spamer" / ".kruczek").exists()
    assert "folder sprawy" in err
    assert "zapisano dzień wolny 2026-11-13" in out


def test_pusty_projekt_brak_spraw(tmp_path, capsys):
    # Act
    kod, out, _ = uruchom(capsys, "co-robic", str(tmp_path))
    # Assert
    assert kod == 0
    assert f"brak spraw w {tmp_path}" in out
    assert "TERAZ" not in out


def test_uszkodzona_sprawa_nie_chowa_pozostalych(projekt, capsys):
    # Arrange
    inna = _zaloz_sprawe(capsys, projekt, "inna", "Inna")
    uruchom(capsys, "zadanie", str(inna), "zadanie innej")
    (projekt / "spamer" / "sprawa.json").write_text("{", encoding="utf-8")
    # Act
    kod, out, err = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 1
    assert "zadanie innej" in out.split("CZEKAM")[0]
    assert "BŁĘDY" in out and "spamer: " in out.split("BŁĘDY")[1]
    assert "uszkodzony JSON" in err and "Traceback" not in err


def test_dzien_wolny_z_uszkodzona_sprawa_przelicza_pozostale(projekt, capsys):
    # Arrange
    inna = _zaloz_sprawe(capsys, projekt, "inna", "Inna")
    uruchom(capsys, "watek", str(inna), "firma", "--adresat", "Y")
    uruchom(capsys, "zdarzenie", str(inna), "--typ", "nadanie", "--data", "2026-10-08", "--watek", "firma",
            "--termin", "14d", "--podstawa", "x")
    (projekt / "spamer" / "sprawa.json").write_text("{", encoding="utf-8")
    # Act
    kod, out, _ = uruchom(capsys, "dzien-wolny", "2026-10-22", "--podstawa", "p", "--projekt", str(projekt))
    # Assert
    assert kod == 1
    assert out.index("zapisano dzień wolny") < out.index("inna: t1: 2026-10-22 → 2026-10-23")
    assert "BŁĘDY" in out


@pytest.mark.parametrize("termin", ["14 dni", "99999r"])
def test_zly_termin_kod_1_bez_tracebacku(projekt, capsys, termin):
    # Act
    kod, _, err = uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "nadanie", "--watek", "firma",
                          "--termin", termin, "--podstawa", "x")
    # Assert
    assert kod == 1
    assert "błąd:" in err and "Traceback" not in err


def test_renderuj_index_nie_w_utf8_to_blad_sprawy(projekt, capsys):
    # Arrange
    (projekt / "spamer" / "index.md").write_bytes(b"# SPRAWA: \xff\xfe\n")
    # Act
    kod, _, err = uruchom(capsys, "renderuj", str(projekt / "spamer"))
    # Assert
    assert kod == 1
    assert "index.md: nie jest w UTF-8" in err and "Traceback" not in err


def test_renderuj_nie_zostawia_plikow_tymczasowych(projekt, capsys):
    # Arrange
    (projekt / "spamer" / "index.md").write_text("# SPRAWA: Spamer\n", encoding="utf-8")
    # Act
    uruchom(capsys, "renderuj", str(projekt / "spamer"))
    # Assert
    assert [p.name for p in (projekt / "spamer").glob(".*.tmp")] == []


def test_stary_format_wskazuje_nowa_sprawe(projekt, capsys):
    # Arrange
    (projekt / "stara").mkdir()
    (projekt / "stara" / "index.md").write_text("# Sprawa: Stara\n", encoding="utf-8")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert "migracja w kolejnej wersji; nowa sprawa: teczka.py nowa" in out


def test_bez_argumentow_wypisuje_pomoc_i_kod_2(capsys):
    # Act
    with pytest.raises(SystemExit) as e:
        teczka.main([])
    # Assert
    assert e.value.code == 2
    assert "usage:" in capsys.readouterr().out


def test_pomoc_typu_wyjasnia_kierunek(capsys):
    # Act
    with pytest.raises(SystemExit):
        teczka.main(["zdarzenie", "--help"])
    # Assert
    out = capsys.readouterr().out
    assert "wplyw" in out and "doreczenie" in out and "adresat odpisał Tobie" in out


def test_doreczenie_przy_dwoch_pismach_wymaga_dotyczy(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    for data in ("2026-10-01", "2026-10-08"):
        uruchom(capsys, "zdarzenie", sprawa, "--typ", "nadanie", "--data", data, "--watek", "firma",
                "--termin", "14d", "--podstawa", "x")
    # Act
    kod, _, err = uruchom(capsys, "zdarzenie", sprawa, "--typ", "doreczenie", "--data", "2026-10-09",
                          "--watek", "firma")
    kod2, out2, _ = uruchom(capsys, "zdarzenie", sprawa, "--typ", "doreczenie", "--data", "2026-10-09",
                            "--watek", "firma", "--dotyczy", "z1")
    # Assert
    assert kod == 1 and "--dotyczy" in err and "Traceback" not in err
    assert kod2 == 0 and "(od doręczenia)" in out2


def test_zamknieta_sprawa_znika_z_przegladu(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zadanie", sprawa, "coś", "--aktywne-od", "2026-10-01")
    # Act
    kod, out, _ = uruchom(capsys, "zamknij", sprawa, "--wynik", "wygrana")
    _, przeglad, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 0 and "wygrana" in out
    assert "coś" not in przeglad


def test_zdarzenie_z_godzina_i_pewnoscia(projekt, capsys):
    # Act
    kod, _, _ = uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "telefon", "--data", "2026-10-08",
                        "--godzina", "14:32", "--pewnosc", "wlasne_oswiadczenie", "--opis", "dzwonili")
    zly, _, err = uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "fakt", "--godzina", "9:5")
    # Assert
    dane = json.loads((projekt / "spamer" / "sprawa.json").read_text(encoding="utf-8"))
    assert kod == 0 and (dane["zdarzenia"][0]["godzina"], dane["zdarzenia"][0]["pewnosc"]) == ("14:32", "wlasne_oswiadczenie")
    assert zly == 1 and "GG:MM" in err


def test_popraw_zdarzenie_cli(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zdarzenie", sprawa, "--typ", "nadanie", "--data", "2026-10-08", "--watek", "firma",
            "--termin", "14d", "--podstawa", "x")
    # Act
    kod, out, _ = uruchom(capsys, "popraw-zdarzenie", sprawa, "z1", "--data", "2026-10-09")
    # Assert
    assert kod == 0 and "t1: 2026-10-22 → 2026-10-23" in out


def test_cofnij_zle_wpisane_doreczenie_cli(projekt, capsys):
    # Arrange — decyzję sądu wpisano jako doręczenie zamiast wpływu
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zdarzenie", sprawa, "--typ", "nadanie", "--data", "2026-10-01", "--watek", "firma",
            "--termin", "14d", "--podstawa", "x")
    uruchom(capsys, "zdarzenie", sprawa, "--typ", "doreczenie", "--data", "2026-10-12", "--watek", "firma")
    # Act
    kod, out, _ = uruchom(capsys, "cofnij-zdarzenie", sprawa, "z2")
    # Assert
    dane = json.loads((projekt / "spamer" / "sprawa.json").read_text(encoding="utf-8"))
    assert kod == 0 and "cofnięto z2" in out
    assert (dane["terminy"][0]["od_zdarzenia"], dane["terminy"][0]["szacunek"]) == ("z1", True)


def test_co_robic_pokazuje_folder_po_terminie_i_termin_w_wkrotce(projekt, capsys):
    # Arrange
    sprawa = str(projekt / "spamer")
    uruchom(capsys, "zadanie", sprawa, "odwołanie", "--aktywne-od", "2026-10-01", "--termin", "2026-10-15")
    uruchom(capsys, "zadanie", sprawa, "snapshot", "--aktywne-od", "+3d", "--termin", "+5d")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    teraz, reszta = out.split("CZEKAM")
    assert "spamer:" in teraz and "PO TERMINIE (5 dni)" in teraz
    assert "termin 2026-10-25" in reszta.split("WKRÓTCE")[1]


def test_co_robic_sekcja_bez_ruchu_z_liczba_dni_ze_stalej(projekt, capsys):
    # Arrange
    uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "fakt", "--data", "2026-08-01")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert f"BEZ RUCHU (ponad {widok.DNI_BEZ_RUCHU} dni)" in out
    assert "spamer: Spamer — ostatni ruch 2026-08-01" in out


def test_co_robic_etykiety_podprojektu_i_pominiete_foldery_bez_indexu(projekt, capsys):
    # Arrange
    podprojekt = projekt / "podprojekt"
    podprojekt.mkdir()
    (podprojekt / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    uruchom(capsys, "nowa", str(podprojekt / "sprawa-a"), "--tytul", "A", "--strona", "Y")
    uruchom(capsys, "zadanie", str(podprojekt / "sprawa-a"), "zrób to")
    (projekt / "kopia 2").mkdir()
    # Act
    kod, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 0
    assert "podprojekt/sprawa-a: A — zrób to" in out
    assert "POMINIĘTO (brak index.md)" in out and "kopia 2" in out.split("POMINIĘTO")[1]


def test_co_robic_bez_pominietych_nie_wypisuje_sekcji(projekt, capsys):
    # Arrange / Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert "POMINIĘTO" not in out


def test_co_robic_stary_format_w_podprojekcie_z_etykieta(projekt, capsys):
    # Arrange
    stara = projekt / "podprojekt" / "sprawa-b"
    stara.mkdir(parents=True)
    (projekt / "podprojekt" / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    (stara / "index.md").write_text("# Sprawa: B\n", encoding="utf-8")
    # Act
    _, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert "podprojekt/sprawa-b" in out.split("STARY FORMAT")[1]


def test_duplikat_id_sprawy_w_dwoch_folderach_to_blad_z_obiema_nazwami(projekt, capsys):
    # Arrange — kopia folderu razem z sprawa.json
    kopia = projekt / "spamer 2"
    kopia.mkdir()
    (kopia / "sprawa.json").write_text((projekt / "spamer" / "sprawa.json").read_text(encoding="utf-8"),
                                       encoding="utf-8")
    uruchom(capsys, "zadanie", str(kopia), "tylko w kopii")
    # Act
    kod, out, _ = uruchom(capsys, "co-robic", str(projekt))
    # Assert
    assert kod == 1
    bledy = out.split("BŁĘDY")[1]
    assert "spamer 2" in bledy and "spamer" in bledy.replace("spamer 2", "")
    assert "spamer 2: Spamer — tylko w kopii" in out


def test_projekt_to_najbardziej_zewnetrzny_rejestr_spraw(tmp_path):
    # Arrange
    (tmp_path / "podprojekt" / "sprawa-a").mkdir(parents=True)
    (tmp_path / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    (tmp_path / "podprojekt" / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    inna = tmp_path / "inna"
    inna.mkdir()
    # Act / Assert
    assert teczka._projekt(tmp_path / "podprojekt" / "sprawa-a") == tmp_path.resolve()
    assert teczka._projekt(inna) == tmp_path.resolve()


def test_zapis_odswieza_index_md(projekt, capsys):
    # Arrange
    index = projekt / "spamer" / "index.md"
    index.write_text("# SPRAWA: Spamer\n\nnotatki\n", encoding="utf-8")
    # Act
    kod, _, _ = uruchom(capsys, "zdarzenie", str(projekt / "spamer"), "--typ", "fakt", "--opis", "coś się stało")
    # Assert
    assert kod == 0 and "coś się stało" in index.read_text(encoding="utf-8")


def test_dzien_wolny_odswieza_index_md_spraw(projekt, capsys):
    # Arrange
    index = projekt / "spamer" / "index.md"
    index.write_text("# SPRAWA: Spamer\n\nnotatki\n", encoding="utf-8")
    uruchom(capsys, "zadanie", str(projekt / "spamer"), "zadanie z dnia wolnego")
    # Act
    kod, _, _ = uruchom(capsys, "dzien-wolny", "2026-12-24", "--podstawa", "test", "--projekt", str(projekt))
    # Assert
    assert kod == 0 and "zadanie z dnia wolnego" in index.read_text(encoding="utf-8")


def test_zapis_udany_mimo_zepsutych_znacznikow_kod_0_z_uwaga(projekt, capsys):
    # Arrange
    index = projekt / "spamer" / "index.md"
    index.write_text("# SPRAWA: Spamer\n<!-- kruczek:zadania -->\n", encoding="utf-8")
    # Act
    kod, _, err = uruchom(capsys, "zadanie", str(projekt / "spamer"), "x")
    # Assert
    dane = json.loads((projekt / "spamer" / "sprawa.json").read_text(encoding="utf-8"))
    assert kod == 0 and len(dane["zadania"]) == 1
    assert "zapisano, ale index.md nie odświeżony" in err


def test_renderuj_w_folderze_bez_sprawy_nie_zostawia_blokady(tmp_path, capsys):
    # Arrange
    (tmp_path / "x").mkdir()
    # Act
    kod, _, _ = uruchom(capsys, "renderuj", str(tmp_path / "x"))
    # Assert
    assert kod == 1
    assert not (tmp_path / "x" / ".sprawa.lock").exists()


def test_wlasciciel_domyslnie_biezacy_uzytkownik(tmp_path, capsys, monkeypatch):
    # Arrange
    monkeypatch.setattr(teczka, "_uzytkownik", lambda: "ktos")
    # Act
    uruchom(capsys, "nowa", str(tmp_path / "s"), "--tytul", "T", "--strona", "X")
    # Assert
    assert json.loads((tmp_path / "s" / "sprawa.json").read_text(encoding="utf-8"))["wlasciciel"] == "ktos"
