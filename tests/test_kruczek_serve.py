import importlib
import socket
import sys
import tomllib
from pathlib import Path

import kruczek_serve
import pytest

KORZEN = Path(__file__).resolve().parents[1]


def test_bez_argumentow_kod_2():
    # Act
    with pytest.raises(SystemExit) as e:
        kruczek_serve.main([])
    # Assert
    assert e.value.code == 2


def test_brak_katalogu_kod_1(tmp_path, capsys):
    # Act
    kod = kruczek_serve.main([str(tmp_path / "nie-ma")])
    # Assert
    assert kod == 1 and "błąd:" in capsys.readouterr().err


def test_zajety_port_kod_1(tmp_path, capsys):
    # Arrange
    s = socket.socket()
    s.bind((kruczek_serve.HOST, 0))
    s.listen()
    port = s.getsockname()[1]
    # Act
    try:
        kod = kruczek_serve.main([str(tmp_path), "--port", str(port)])
    finally:
        s.close()
    # Assert
    assert kod == 1 and "zajęty" in capsys.readouterr().err


def test_brak_bibliotek_czytelny_komunikat(tmp_path, capsys, monkeypatch):
    # Arrange — jak uruchomienie systemowym python3 bez bibliotek strony
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    monkeypatch.setattr(kruczek_serve, "_port_wolny", lambda port: True)
    # Act
    kod = kruczek_serve.main([str(tmp_path), "--port", "8765"])
    # Assert
    assert kod == 1 and "uv run --script" in capsys.readouterr().err


def test_modul_importuje_sie_bez_bibliotek_strony(monkeypatch):
    # Arrange — run_tests.py importuje każdy scripts/*.py systemowym Pythonem
    for nazwa in ("fastapi", "pydantic", "starlette", "jinjax", "jinja2", "uvicorn"):
        monkeypatch.setitem(sys.modules, nazwa, None)
    # Act
    importlib.reload(kruczek_serve)
    # Assert
    assert kruczek_serve.HOST == "127.0.0.1"


def test_zaleznosci_pep723_zgodne_z_grupa_serve():
    # Arrange
    grupa = tomllib.loads((KORZEN / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["serve"]
    # Act
    naglowek = kruczek_serve.zaleznosci_skryptu()
    # Assert
    assert sorted(naglowek) == sorted(grupa)


def test_nasluch_tylko_na_127_0_0_1_bez_opcji_host():
    # Act
    pomoc = kruczek_serve._parser().format_help()
    # Assert
    assert kruczek_serve.HOST == "127.0.0.1" and "--host" not in pomoc


@pytest.mark.parametrize("port", ["0", "-1", "65536", "abc"])
def test_port_poza_zakresem_kod_2(tmp_path, capsys, port):
    # Act
    with pytest.raises(SystemExit) as e:
        kruczek_serve.main([str(tmp_path), "--port", port])
    # Assert
    assert e.value.code == 2 and "błąd:" in capsys.readouterr().err


def test_port_po_zamknieciu_gniazda_jest_wolny():
    # Arrange — port świeżo użyty i zamknięty (TIME_WAIT) nie blokuje startu, jak w uvicornie
    s = socket.socket()
    s.bind((kruczek_serve.HOST, 0))
    port = s.getsockname()[1]
    s.close()
    # Act / Assert
    assert kruczek_serve._port_wolny(port)
