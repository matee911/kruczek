"""Repozytorium plikowe: sprawa.json w katalogu sprawy.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from kruczek_core.model import (
    SCHEMA_VERSION,
    BladSprawy,
    Sprawa,
    do_slownika,
    z_slownika,
)

PLIK_SPRAWY = "sprawa.json"
_BLOKADA = ".sprawa.lock"
# Katalogi projektu, które nie są sprawami.
_NIE_SPRAWY = {"BAZA_WIEDZY"}

def _z_1_do_2(d: dict[str, Any]) -> dict[str, Any]:
    """v2 dodaje do zdarzeń godzinę, pewność i `dotyczy`. `dotyczy` odtwarzamy z zadań reguł:
    zdarzenie, które zamknęło zadanie utworzone przez nadanie, dotyczy tego nadania."""
    zdarzenia = [{**z} for z in d.get("zdarzenia", [])]
    po_id = {z["id"]: z for z in zdarzenia}
    for a in d.get("zadania", []):
        zamykajace = po_id.get(a.get("zamkniete_przez") or "")
        if zamykajace is not None and a.get("regula") and a.get("zdarzenie_id"):
            zamykajace.setdefault("dotyczy", a["zdarzenie_id"])
    return {**d, "schema_version": 2, "zdarzenia": zdarzenia}


# v → funkcja migrująca słownik z wersji v do v+1.
MIGRACJE: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _z_1_do_2}

T = TypeVar("T")


class KonfliktRewizji(BladSprawy):
    """Ktoś zapisał sprawę po tym, jak ją wczytałeś — wczytaj ponownie i powtórz zmianę."""


def wczytaj(katalog: Path) -> Sprawa:
    plik = katalog / PLIK_SPRAWY
    if not plik.exists():
        if (katalog / "index.md").is_file():
            raise BladSprawy(f"{katalog}: brak {PLIK_SPRAWY}, jest index.md — stary format — przenieś: /kruczek:migruj")
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


def _zapisz_tekst_atomowo(plik: Path, tresc: str) -> None:
    tmp = plik.with_name(f".{plik.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tresc)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, plik)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _zapisz_atomowo(katalog: Path, sprawa: Sprawa) -> None:
    _zapisz_tekst_atomowo(katalog / PLIK_SPRAWY, json.dumps(do_slownika(sprawa), ensure_ascii=False, indent=2) + "\n")


def przetworz_tekst(katalog: Path, nazwa: str, przetworz: Callable[[str], str]) -> Path:
    """Plik tekstowy sprawy (np. index.md): odczyt → przetworzenie → zapis atomowy, pod tą samą
    blokadą co sprawa.json. Brak pliku to pusty tekst; plik nie w UTF-8 to BladSprawy."""
    plik = katalog / nazwa
    with _blokada(katalog):
        try:
            tekst = plik.read_text(encoding="utf-8") if plik.exists() else ""
        except UnicodeDecodeError:
            raise BladSprawy(f"{nazwa}: nie jest w UTF-8") from None
        _zapisz_tekst_atomowo(plik, przetworz(tekst))
    return plik


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
    stary_format: list[Path]  # index.md bez sprawa.json — do migracji
    bez_indexu: list[Path] = field(default_factory=list)  # foldery najwyższego poziomu bez index.md i sprawa.json


def _naglowek(katalog: Path) -> str:
    """Pierwsza niepusta linia index.md (BOM i puste linie na początku pomijane), bez wielkości liter."""
    try:
        tekst = (katalog / "index.md").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    for linia in tekst.splitlines():
        if linia.strip():
            return linia.strip().casefold()
    return ""


def czy_folder_sprawy(katalog: Path) -> bool:
    """Folder ma sprawa.json albo index.md zaczynający się od „# Sprawa:” (wielkość liter, BOM
    i puste linie na początku nie przeszkadzają) — czyli jest teczką sprawy, a nie projektem."""
    return (katalog / PLIK_SPRAWY).exists() or _naglowek(katalog).startswith("# sprawa:")


def czy_rejestr_spraw(katalog: Path) -> bool:
    """index.md zaczyna się od „# Rejestr spraw” — folder jest projektem (podprojektem) ze sprawami w środku."""
    return _naglowek(katalog) == "# rejestr spraw"


def _podfoldery(projekt: Path) -> list[Path]:
    return sorted(
        p for p in projekt.iterdir()
        if p.is_dir() and not p.name.startswith((".", "_")) and p.name not in _NIE_SPRAWY
    )


def lista_spraw(projekt: Path) -> ListaSpraw:
    """Każdy folder najwyższego poziomu z index.md i bez sprawa.json to stary format,
    niezależnie od nagłówka — lepiej wypisać za dużo niż po cichu pominąć teczkę.
    Folder z index.md „# Rejestr spraw” to podprojekt: jego sprawy (o jeden poziom niżej)
    są wypisywane tak samo. Folder bez index.md i sprawa.json trafia do `bez_indexu`."""
    sprawy, stare, bez_indexu = [], [], []
    for k in _podfoldery(projekt):
        if (k / PLIK_SPRAWY).exists():
            sprawy.append(k)
        elif (k / "index.md").is_file():
            if czy_rejestr_spraw(k):
                for g in _podfoldery(k):
                    if (g / PLIK_SPRAWY).exists():
                        sprawy.append(g)
                    elif (g / "index.md").is_file():
                        stare.append(g)
            else:
                stare.append(k)
        else:
            bez_indexu.append(k)
    return ListaSpraw(sprawy, stare, bez_indexu)
