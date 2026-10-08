"""Repozytorium plikowe: sprawa.json w katalogu sprawy (spec §4.4, §6).

Zapis zawsze pod blokadą (fcntl.flock na .sprawa.lock) i atomowo (plik tymczasowy
+ os.replace), z licznikiem `rewizja`. Dzięki temu CLI, strona i MCP mogą pisać tę
samą sprawę równolegle bez gubienia zmian, a przerwany zapis nie zostawia uciętego JSON-a.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from kruczek_core.model import SCHEMA_VERSION, BladSprawy, Sprawa, do_slownika, z_slownika

PLIK_SPRAWY = "sprawa.json"
_BLOKADA = ".sprawa.lock"
# Katalogi projektu, które nie są sprawami.
_NIE_SPRAWY = {"BAZA_WIEDZY"}

# v → funkcja migrująca słownik z wersji v do v+1. Pusty, dopóki format jest w wersji 1.
MIGRACJE: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}

T = TypeVar("T")


class KonfliktRewizji(BladSprawy):
    """Ktoś zapisał sprawę po tym, jak ją wczytałeś — wczytaj ponownie i powtórz zmianę."""


def wczytaj(katalog: Path) -> Sprawa:
    plik = katalog / PLIK_SPRAWY
    if not plik.exists():
        raise BladSprawy(f"{katalog}: brak {PLIK_SPRAWY} — załóż sprawę: teczka.py nowa {katalog} …")
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BladSprawy(f"{plik}: uszkodzony JSON (linia {e.lineno}): {e.msg}") from e
    wersja = dane.get("schema_version") if isinstance(dane, dict) else None
    if not isinstance(wersja, int):
        raise BladSprawy(f"{plik}: brak schema_version")
    if wersja > SCHEMA_VERSION:
        raise BladSprawy(
            f"{plik}: format w wersji {wersja}, ten kruczek zna najwyżej {SCHEMA_VERSION} — zaktualizuj plugin"
        )
    for v in range(wersja, SCHEMA_VERSION):
        dane = MIGRACJE[v](dane)
    try:
        return z_slownika(dane)
    except (KeyError, TypeError, ValueError) as e:
        raise BladSprawy(f"{plik}: niepoprawne dane: {e}") from e


@contextmanager
def _blokada(katalog: Path) -> Iterator[None]:
    with open(katalog / _BLOKADA, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _zapisz_atomowo(katalog: Path, sprawa: Sprawa) -> None:
    plik = katalog / PLIK_SPRAWY
    tmp = katalog / f".{PLIK_SPRAWY}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(do_slownika(sprawa), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, plik)


def zapisz_nowa(katalog: Path, sprawa: Sprawa) -> None:
    with _blokada(katalog):
        if (katalog / PLIK_SPRAWY).exists():
            raise BladSprawy(f"{katalog / PLIK_SPRAWY} już istnieje")
        _zapisz_atomowo(katalog, sprawa)


def zapisz(katalog: Path, sprawa: Sprawa, oczekiwana_rewizja: int) -> Sprawa:
    """Zapis sprawy wczytanej wcześniej (np. przez stronę). Odrzuca, jeśli ktoś zapisał w międzyczasie."""
    with _blokada(katalog):
        aktualna = wczytaj(katalog).rewizja
        if aktualna != oczekiwana_rewizja:
            raise KonfliktRewizji(
                f"{katalog}: sprawa zmieniła się w międzyczasie (rewizja {aktualna}, oczekiwano {oczekiwana_rewizja})"
            )
        sprawa.rewizja = aktualna + 1
        _zapisz_atomowo(katalog, sprawa)
    return sprawa


def zmien(katalog: Path, zmiana: Callable[[Sprawa], T]) -> T:
    """Wczytaj → zmień → zapisz pod blokadą. Wyjątek w `zmiana` = nic nie zapisane."""
    with _blokada(katalog):
        sprawa = wczytaj(katalog)
        wynik = zmiana(sprawa)
        sprawa.rewizja += 1
        _zapisz_atomowo(katalog, sprawa)
    return wynik


@dataclass(frozen=True)
class ListaSpraw:
    sprawy: list[Path]
    stary_format: list[Path]  # index.md „# SPRAWA:” bez sprawa.json — do migracji


def lista_spraw(projekt: Path) -> ListaSpraw:
    sprawy, stare = [], []
    for k in sorted(p for p in projekt.iterdir() if p.is_dir()):
        if k.name.startswith((".", "_")) or k.name in _NIE_SPRAWY:
            continue
        if (k / PLIK_SPRAWY).exists():
            sprawy.append(k)
        elif (k / "index.md").exists() and (k / "index.md").read_text(encoding="utf-8").startswith("# SPRAWA:"):
            stare.append(k)
    return ListaSpraw(sprawy, stare)
