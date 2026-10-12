"""index.md ma kilku pisarzy (render bloków, manifest.py) — żaden nie może zgubić notatek usera ani
cudzego wpisu, a tekst z danych nie może zepsuć znaczników bloków."""

import datetime as dt
import subprocess
import sys
import threading
import time
from pathlib import Path

import manifest
import pytest
from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.operacje import dodaj_watek, dodaj_zdarzenie, nowa_sprawa
from kruczek_core.projekt import odswiez_index

MANIFEST = Path(__file__).resolve().parent.parent / "scripts" / "manifest.py"
DZIS = dt.date(2026, 10, 11)
NOTATKI = "# Sprawa: test\n\n## Stan faktyczny\n\nNOTATKA-USERA\n"


@pytest.fixture
def sprawa(tmp_path: Path) -> Path:
    katalog = tmp_path / "sprawa-a"
    katalog.mkdir()
    nowa_sprawa(katalog, "Reklamacja", "Firma X sp. z o.o.", "Osoba Testowa")
    dodaj_watek(katalog, "firma-x", "Firma X")
    (katalog / "index.md").write_text(NOTATKI, encoding="utf-8")
    odswiez_index(katalog)
    (katalog / "ARCHIWUM").mkdir()
    return katalog


def _wstaw(katalog: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(MANIFEST), "wstaw", str(katalog / "index.md"), str(katalog)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _kod(proces: subprocess.Popen, timeout: float = 30) -> int:
    """Kod wyjścia procesu; po przekroczeniu `timeout` zabija go i zgłasza TimeoutExpired (proces
    wiszący na blokadzie nie zawiesza testów). Zamyka potoki — pytest -W error traktuje niezamknięte jak błąd."""
    try:
        proces.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proces.kill()
        proces.communicate()
        raise
    return proces.returncode


def test_kod_przerywa_wiszacy_proces_po_timeoucie():
    # Arrange
    proces = subprocess.Popen(["sleep", "30"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start = time.monotonic()
    # Act / Assert
    with pytest.raises(subprocess.TimeoutExpired):
        _kod(proces, timeout=0.5)
    assert time.monotonic() - start < 10 and proces.poll() is not None


def test_wstaw_czeka_na_render_i_nie_gubi_wpisu(sprawa):
    # Arrange — render trzyma blokadę sprawy (hook `przed` działa pod nią)
    (sprawa / "ARCHIWUM" / "nowy.txt").write_text("b", encoding="utf-8")
    procesy = []

    def manifest_w_trakcie_renderu(tekst: str) -> str:
        p = _wstaw(sprawa)
        procesy.append(p)
        with pytest.raises(subprocess.TimeoutExpired):
            p.wait(timeout=3)  # manifest.py czeka na blokadę, zamiast pisać w trakcie renderu
        return tekst

    # Act
    uwaga = odswiez_index(sprawa, przed=manifest_w_trakcie_renderu)
    kod = _kod(procesy[0])
    # Assert
    tekst = (sprawa / "index.md").read_text(encoding="utf-8")
    assert uwaga is None and kod == 0
    assert "nowy.txt" in tekst and "NOTATKA-USERA" in tekst


def test_wstaw_nie_obcina_index_przed_zapisem(sprawa, monkeypatch):
    # Arrange — w chwili zapisu index.md musi mieć pełną starą treść (render czytający go wtedy nic nie traci)
    idx = sprawa / "index.md"
    widziane = []
    prawdziwy = manifest.zapisz_tekst_atomowo

    def podgladaj(plik: Path, tresc: str) -> None:
        widziane.append(idx.read_text(encoding="utf-8"))
        prawdziwy(plik, tresc)

    monkeypatch.setattr(manifest, "zapisz_tekst_atomowo", podgladaj)
    monkeypatch.setattr(sys, "argv", ["manifest.py", "wstaw", str(idx), str(sprawa)])
    # Act
    manifest.main()
    # Assert
    tekst = idx.read_text(encoding="utf-8")
    assert widziane and "NOTATKA-USERA" in widziane[0]
    assert "NOTATKA-USERA" in tekst and manifest.START in tekst


def test_wyscig_renderu_i_wstaw_na_prawdziwych_procesach(sprawa):
    # Arrange — render w pętli (jak strona) i manifest.py jako osobny proces (jak /kruczek:dowod)
    idx = sprawa / "index.md"
    notatki = "NOTATKA-USERA\n" + ("Lorem ipsum dolor sit amet. " * 700) + "\nKONIEC-NOTATEK\n"
    idx.write_text("# Sprawa: test\n\n## Stan faktyczny\n\n" + notatki, encoding="utf-8")
    odswiez_index(sprawa)
    stop = threading.Event()

    def renderuj_w_petli():
        while not stop.is_set():
            odswiez_index(sprawa)
            time.sleep(0.001)  # flock nie kolejkuje — bez przerwy proces manifest.py mógłby długo czekać

    watek = threading.Thread(target=renderuj_w_petli, daemon=True)
    # Act
    watek.start()
    straty = 0
    try:
        for i in range(30):
            (sprawa / "ARCHIWUM" / f"plik{i}.txt").write_text(str(i), encoding="utf-8")
            assert _kod(_wstaw(sprawa)) == 0
            if "KONIEC-NOTATEK" not in idx.read_text(encoding="utf-8"):
                straty += 1
    finally:
        stop.set()
        watek.join(timeout=10)
    # Assert
    tekst = idx.read_text(encoding="utf-8")
    assert straty == 0
    assert "plik29.txt" in tekst and "KONIEC-NOTATEK" in tekst
