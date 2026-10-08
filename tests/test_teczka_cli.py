import datetime as dt
import json

import pytest

import teczka


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
