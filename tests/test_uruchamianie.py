"""Skrypty Pythona uruchamiają się przez uv z Pythonem ≥ 3.11, niezależnie od systemowego python3."""

import os
import re
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parent.parent
SKRYPTY = KORZEN / "scripts"
WYKONYWALNE = sorted(p for p in SKRYPTY.glob("*.py") if os.access(p, os.X_OK))
SHEBANG = "#!/usr/bin/env -S uv run --script"
# Nagłówek PEP 723: wymagany Python ≥ 3.11; dalsze linie (zależności strony) dozwolone.
METADANE = re.compile(r'^# /// script\n# requires-python = ">=3\.11"\n(?:# .*\n)*?# ///$', re.MULTILINE)


def test_sa_skrypty_wykonywalne():
    # Arrange / Act
    nazwy = {p.name for p in WYKONYWALNE}

    # Assert
    assert {"teczka.py", "manifest.py", "eml_forensics.py", "kontrola_pisma.py", "build_pismo.py"} <= nazwy


@pytest.mark.parametrize("skrypt", WYKONYWALNE, ids=lambda p: p.name)
def test_skrypt_startuje_przez_uv_z_python_311(skrypt):
    # Arrange
    tekst = skrypt.read_text(encoding="utf-8")

    # Act
    pierwsza = tekst.splitlines()[0]

    # Assert
    assert pierwsza == SHEBANG
    assert METADANE.search(tekst)


def test_skille_i_skrypty_nie_wolaja_systemowego_python3_na_skryptach_kruczka():
    # Arrange
    pliki = [
        *KORZEN.joinpath("skills").rglob("*.md"),
        *KORZEN.joinpath("agents").glob("*.md"),
        *SKRYPTY.glob("*.sh"),
    ]
    wzorzec = re.compile(r"\bpython3?\s+\S*\b(?:" + "|".join(re.escape(p.name) for p in WYKONYWALNE) + r")")

    # Act
    trafienia = [
        f"{p.relative_to(KORZEN)}:{n}"
        for p in pliki
        if p.name != "smoketest.sh"
        for n, linia in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if wzorzec.search(linia)
    ]

    # Assert
    assert trafienia == []


def test_check_deps_wymaga_uv():
    # Arrange
    tekst = (SKRYPTY / "check-deps.sh").read_text(encoding="utf-8")

    # Act
    wymagane = re.search(r"^REQUIRED=\((.*)\)", tekst, re.MULTILINE).group(1).split()

    # Assert
    assert "uv" in wymagane
