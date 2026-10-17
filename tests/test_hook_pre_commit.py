"""Hook pre-commit: plik ze znacznikiem „nie commitować” w treści zatrzymuje commit."""

import shutil
import subprocess
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parent.parent
HOOK = KORZEN / ".githooks" / "pre-commit"


def _repo_z_plikiem(tmp_path, tresc):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "scripts").mkdir()
    # Atrapa testów: sprawdzamy tylko blokadę znacznika, nie prawdziwe testy kruczka.
    (tmp_path / "scripts" / "run_tests.py").write_text("raise SystemExit(0)\n")
    shutil.copytree(HOOK.parent, tmp_path / ".githooks")
    (tmp_path / "PLAN.md").write_text(tresc, encoding="utf-8")
    subprocess.run(["git", "add", "PLAN.md", "scripts"], cwd=tmp_path, check=True)


def _uruchom_hook(tmp_path):
    # PATH bez uv — hook bierze wtedy python3 z systemu, bez pobierania interpretera.
    return subprocess.run(
        ["/bin/bash", str(tmp_path / ".githooks" / "pre-commit")],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "znacznik",
    ["Nie commitować, nie wypychać.", "NIE COMMITOWAĆ", "Do not commit."],
)
def test_plik_ze_znacznikiem_wstrzymuje_commit(tmp_path, znacznik):
    # Arrange
    _repo_z_plikiem(tmp_path, f"**Status:** dokument roboczy, lokalny. {znacznik}\n")

    # Act
    wynik = _uruchom_hook(tmp_path)

    # Assert
    assert wynik.returncode == 1
    assert "PLAN.md" in wynik.stdout


def test_plik_bez_znacznika_przechodzi(tmp_path):
    # Arrange
    _repo_z_plikiem(tmp_path, "# Plan\n\nZwykły dokument.\n")

    # Act
    wynik = _uruchom_hook(tmp_path)

    # Assert
    assert wynik.returncode == 0, wynik.stdout


def test_blad_sprawdzania_wstrzymuje_commit(tmp_path):
    # Arrange
    _repo_z_plikiem(tmp_path, "# Plan\n\nZwykły dokument.\n")
    (tmp_path / ".git" / "index").write_bytes(b"uszkodzony indeks")

    # Act
    wynik = _uruchom_hook(tmp_path)

    # Assert
    assert wynik.returncode == 1
    assert "nie udało się sprawdzić" in wynik.stdout


def test_plany_w_katalogu_glownym_sa_ignorowane():
    # Arrange / Act
    wynik = subprocess.run(
        ["git", "check-ignore", "-q", "PLAN-COKOLWIEK-2026-01-01.md"], cwd=KORZEN, check=False
    )

    # Assert
    assert wynik.returncode == 0
