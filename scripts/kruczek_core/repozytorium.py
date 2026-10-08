"""Repozytorium plikowe: sprawa.json w katalogu sprawy (spec §4.4, §6).

Zapis zawsze pod blokadą (fcntl.flock na .sprawa.lock) i atomowo (plik tymczasowy
+ fsync + os.replace; przy błędzie plik tymczasowy jest usuwany), z licznikiem `rewizja`. Dzięki temu CLI, strona i MCP mogą pisać tę
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
    except UnicodeDecodeError as e:
        raise BladSprawy(f"{plik}: plik nie jest poprawnym UTF-8 (bajt {e.start})") from e
    except OSError as e:
        raise BladSprawy(f"{plik}: nie można odczytać pliku: {e.strerror or e}") from e
    wersja = dane.get("schema_version") if isinstance(dane, dict) else None
    if not isinstance(wersja, int) or isinstance(wersja, bool) or wersja < 1:
        raise BladSprawy(f"{plik}: brak lub zła schema_version")
    if wersja > SCHEMA_VERSION:
        raise BladSprawy(
            f"{plik}: format w wersji {wersja}, ten kruczek zna najwyżej {SCHEMA_VERSION} — zaktualizuj plugin"
        )
    try:
        for v in range(wersja, SCHEMA_VERSION):
            migracja = MIGRACJE.get(v)
            if migracja is None:
                raise BladSprawy(f"{plik}: brak migracji z wersji {v} do {v + 1}")
            dane = migracja(dane)
        return z_slownika(dane)
    except (KeyError, TypeError, ValueError) as e:
        raise BladSprawy(f"{plik}: niepoprawne dane: {e}") from e


@contextmanager
def _blokada(katalog: Path) -> Iterator[None]:
    if not katalog.is_dir():
        raise BladSprawy(f"{katalog}: katalog sprawy nie istnieje")
    with open(katalog / _BLOKADA, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _zapisz_atomowo(katalog: Path, sprawa: Sprawa) -> None:
    plik = katalog / PLIK_SPRAWY
    tmp = katalog / f".{PLIK_SPRAWY}.{os.getpid()}.tmp"
    tresc = json.dumps(do_slownika(sprawa), ensure_ascii=False, indent=2) + "\n"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tresc)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, plik)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


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


def _to_stary_format(index: Path) -> bool:
    """Pierwsza niepusta linia index.md to „# SPRAWA:” (BOM i puste linie na początku nie przeszkadzają)."""
    try:
        tekst = index.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    for linia in tekst.splitlines():
        if linia.strip():
            return linia.startswith("# SPRAWA:")
    return False


def lista_spraw(projekt: Path) -> ListaSpraw:
    sprawy, stare = [], []
    for k in sorted(p for p in projekt.iterdir() if p.is_dir()):
        if k.name.startswith((".", "_")) or k.name in _NIE_SPRAWY:
            continue
        if (k / PLIK_SPRAWY).exists():
            sprawy.append(k)
        elif _to_stary_format(k / "index.md"):
            stare.append(k)
    return ListaSpraw(sprawy, stare)
