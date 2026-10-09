"""Hook SessionStart: bez uv/curl/jq mówi wprost, co zainstalować; z kompletem milczy."""

import json
import os
import subprocess
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parent.parent
SKRYPT = KORZEN / "scripts" / "sprawdz-zaleznosci.sh"


def _uruchom(tmp_path, programy):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for nazwa in programy:
        plik = bin_dir / nazwa
        plik.write_text("#!/bin/sh\nexit 0\n")
        plik.chmod(0o755)
    return subprocess.run(
        ["/bin/bash", str(SKRYPT)],
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
    )


def test_hook_jest_zarejestrowany_na_starcie_sesji():
    # Arrange
    konfiguracja = json.loads((KORZEN / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    # Act
    polecenia = [h["command"] for wpis in konfiguracja["hooks"]["SessionStart"] for h in wpis["hooks"]]

    # Assert
    assert polecenia == ['"${CLAUDE_PLUGIN_ROOT}/scripts/sprawdz-zaleznosci.sh"']
    assert os.access(SKRYPT, os.X_OK)


def test_z_kompletem_narzedzi_milczy(tmp_path):
    # Arrange / Act
    wynik = _uruchom(tmp_path, ["uv", "curl", "jq"])

    # Assert
    assert wynik.returncode == 0
    assert wynik.stdout == ""


@pytest.mark.parametrize(
    ("brak", "instrukcja"),
    [
        (["uv"], "brew install uv"),
        (["uv"], "astral.sh/uv/install.sh"),
        (["jq"], "jq"),
        (["uv", "curl", "jq"], "curl"),
    ],
)
def test_bez_narzedzia_podaje_komende_instalacji(tmp_path, brak, instrukcja):
    # Arrange
    programy = [p for p in ("uv", "curl", "jq") if p not in brak]

    # Act
    wynik = _uruchom(tmp_path, programy)
    dane = json.loads(wynik.stdout)

    # Assert
    assert wynik.returncode == 0
    assert instrukcja in dane["systemMessage"]
    assert dane["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    for nazwa in brak:
        assert nazwa in dane["hookSpecificOutput"]["additionalContext"]


def test_claude_md_projektu_mowi_co_zrobic_bez_uv(tmp_path):
    # Arrange
    tekst = (KORZEN / "scripts" / "gen-claude-md.sh").read_text(encoding="utf-8")

    # Act / Assert
    assert "env: uv" in tekst
    assert "brew install uv" in tekst
