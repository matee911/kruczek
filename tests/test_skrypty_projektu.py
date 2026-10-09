import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKRYPTY = Path(__file__).resolve().parent.parent / "scripts"
BEZ_NARZEDZI = shutil.which("jq") is None or shutil.which("curl") is None
WYMAGA_JQ_CURL = pytest.mark.skipif(BEZ_NARZEDZI, reason="init-projekt.sh wymaga jq i curl")

ZADANIA_STARTOWE = [
    "Ustalić pełne dane rejestrowe drugiej strony",
    "Zebrać i zarchiwizować dowody (+ wersje tekstowe dla plików nietekstowych)",
    "Sprawdzić BAZĘ WIEDZY, uzupełnić brakujące przepisy",
    "Przygotować pismo",
    "Cross-check cytatów przed wysyłką",
    "Nadać i zarchiwizować potwierdzenie nadania",
]


def uruchom(skrypt, *argumenty, cwd):
    srodowisko = {**os.environ, "PYTHON": sys.executable}
    return subprocess.run(["bash", str(SKRYPTY / skrypt), *argumenty], cwd=cwd, env=srodowisko,
                          capture_output=True, text=True, check=False)


def test_nowa_sprawa_ma_sprawa_json_i_wygenerowana_chronologie(tmp_path):
    # Act
    wynik = uruchom("nowa-sprawa.sh", "X sp. z o.o.", "Reklamacja butów", str(tmp_path), cwd=tmp_path)
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    k = tmp_path / "x-sp-z-o-o"
    dane = json.loads((k / "sprawa.json").read_text(encoding="utf-8"))
    index = (k / "index.md").read_text(encoding="utf-8")
    assert (dane["tytul"], dane["strona_przeciwna"]) == ("Reklamacja butów", "X sp. z o.o.")
    assert "<!-- kruczek:chronologia -->" in index and "Założenie sprawy" in index
    assert "Najbliższy termin" not in index
    assert index.count("<!-- kruczek:zadania -->") == 1


def test_nowa_sprawa_ma_zadania_startowe_a_nie_liste_todo(tmp_path):
    # Act
    wynik = uruchom("nowa-sprawa.sh", "X", "Y", str(tmp_path), cwd=tmp_path)
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    surowe = (tmp_path / "x" / "sprawa.json").read_text(encoding="utf-8")
    index = (tmp_path / "x" / "index.md").read_text(encoding="utf-8")
    opisy = [z["opis"] for z in json.loads(surowe)["zadania"]]
    assert opisy == ZADANIA_STARTOWE
    assert "## 5." not in index and "## 6. Ścieżka eskalacji" in index
    assert "Wpisać termin kontrolny" not in index and "Wpisać termin kontrolny" not in surowe
    assert "Przygotować pismo" in index


def test_nowa_sprawa_drugi_raz_nic_nie_psuje(tmp_path):
    # Arrange
    uruchom("nowa-sprawa.sh", "X", "Y", str(tmp_path), cwd=tmp_path)
    przed = (tmp_path / "x" / "sprawa.json").read_text(encoding="utf-8")
    # Act
    wynik = uruchom("nowa-sprawa.sh", "X", "Y", str(tmp_path), cwd=tmp_path)
    # Assert
    assert wynik.returncode == 0
    assert (tmp_path / "x" / "sprawa.json").read_text(encoding="utf-8") == przed


def test_nowa_sprawa_stary_format_wskazuje_migracje(tmp_path):
    # Arrange
    k = tmp_path / "x"
    k.mkdir()
    (k / "index.md").write_text("# SPRAWA: X\n", encoding="utf-8")
    # Act
    wynik = uruchom("nowa-sprawa.sh", "X", "Y", str(tmp_path), cwd=tmp_path)
    # Assert
    assert wynik.returncode == 0
    assert "Sprawa w starym formacie" in wynik.stdout and "/kruczek:migruj" in wynik.stdout
    assert not (k / "sprawa.json").exists()


def test_nowa_sprawa_gdy_python_pada_nie_zostawia_index(tmp_path):
    # Arrange
    srodowisko = {**os.environ, "PYTHON": "false"}
    # Act
    wynik = subprocess.run(["bash", str(SKRYPTY / "nowa-sprawa.sh"), "X", "Y", str(tmp_path)],
                           cwd=tmp_path, env=srodowisko, capture_output=True, text=True, check=False)
    # Assert
    assert wynik.returncode != 0
    assert not (tmp_path / "x" / "index.md").exists()
    assert not (tmp_path / "x" / "ARCHIWUM").exists() and not (tmp_path / "x" / "ROBOCZE").exists()


@WYMAGA_JQ_CURL
def test_gitignore_projektu_idempotentny(tmp_path):
    # Arrange
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    # Act
    uruchom("init-projekt.sh", str(tmp_path), cwd=tmp_path)
    uruchom("init-projekt.sh", str(tmp_path), cwd=tmp_path)
    # Assert
    linie = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert linie.count(".sprawa.lock") == 1 and linie.count(".*.tmp") == 1 and "node_modules/" in linie


@WYMAGA_JQ_CURL
def test_gitignore_bez_koncowej_nowej_linii(tmp_path):
    # Arrange
    (tmp_path / ".gitignore").write_bytes(b"node_modules/")
    # Act
    uruchom("init-projekt.sh", str(tmp_path), cwd=tmp_path)
    uruchom("init-projekt.sh", str(tmp_path), cwd=tmp_path)
    # Assert
    linie = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert linie == ["node_modules/", ".sprawa.lock", ".*.tmp"]


@WYMAGA_JQ_CURL
def test_konwencje_z_szablonu(tmp_path):
    # Act
    uruchom("init-projekt.sh", str(tmp_path), cwd=tmp_path)
    # Assert
    assert (tmp_path / "KONWENCJE.md").read_text(encoding="utf-8") == \
        (SKRYPTY.parent / "templates" / "KONWENCJE.md").read_text(encoding="utf-8")
