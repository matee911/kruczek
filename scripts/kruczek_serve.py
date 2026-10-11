#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi==0.141.1", "pydantic==2.13.5", "starlette==1.7.0", "jinjax==0.66", "jinja2==3.1.6",
#     "uvicorn==0.54.0", "python-multipart==0.0.32",
# ]
# [tool.uv]
# exclude-newer = "2026-09-27T23:59:59Z"
# ///
"""kruczek_serve.py — lokalna strona teczki: Po terminie, Teraz, Czekam, Wkrótce, Bez ruchu, Sprawa.

Uruchamianie: uv run --script scripts/kruczek_serve.py <projekt> [--port 8765]
Strona nasłuchuje tylko na 127.0.0.1 i nie udostępnia plików dowodów.
Kody wyjścia: 0 zatrzymana (Ctrl+C), 1 błąd uruchomienia, 2 złe argumenty.
Na poziomie importu tylko stdlib — biblioteki strony ładują się dopiero w main().
"""

from __future__ import annotations

import argparse
import re
import socket
import sys
import tomllib
from pathlib import Path

HOST = "127.0.0.1"
DOMYSLNY_PORT = 8765
_NAGLOWEK = re.compile(r"^# /// script$(.*?)^# ///$", re.MULTILINE | re.DOTALL)


def zaleznosci_skryptu() -> list[str]:
    """Zależności z nagłówka PEP 723 tego pliku (test pilnuje zgodności z grupą `serve` w pyproject).

    >>> "fastapi==0.141.1" in zaleznosci_skryptu()
    True
    """
    blok = _NAGLOWEK.search(Path(__file__).read_text(encoding="utf-8")).group(1)
    toml = "".join(linia[2:] if linia.startswith("# ") else linia[1:] for linia in blok.splitlines(keepends=True))
    return tomllib.loads(toml)["dependencies"]


def _port(tekst: str) -> int:
    """
    >>> _port("8765")
    8765
    """
    try:
        port = int(tekst)
    except ValueError:
        raise argparse.ArgumentTypeError(f"błąd: port to liczba 1–65535, a nie {tekst!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"błąd: port {port} poza zakresem 1–65535")
    return port


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kruczek_serve.py", description="Lokalna strona teczki (tylko 127.0.0.1).")
    p.add_argument("projekt", type=Path, help="katalog projektu ze sprawami")
    p.add_argument("--port", type=_port, default=DOMYSLNY_PORT)
    return p


def _port_wolny(port: int) -> bool:
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, port))
        except OSError:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    if not a.projekt.is_dir():
        print(f"błąd: {a.projekt} nie jest katalogiem projektu", file=sys.stderr)
        return 1
    if not _port_wolny(a.port):
        print(f"błąd: port {a.port} jest zajęty — podaj inny: --port {a.port + 1}", file=sys.stderr)
        return 1
    try:
        import uvicorn
        from kruczek_strona.app import utworz_aplikacje
        from kruczek_strona.zaleznosci import Ustawienia
    except ImportError:
        print("błąd: brak bibliotek strony — uruchom przez: uv run --script scripts/kruczek_serve.py <projekt>",
              file=sys.stderr)
        return 1
    print(f"kruczek: http://{HOST}:{a.port}/  (Ctrl+C zatrzymuje)", flush=True)
    uvicorn.run(utworz_aplikacje(Ustawienia(projekt=a.projekt)), host=HOST, port=a.port, log_level="warning",
                server_header=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
