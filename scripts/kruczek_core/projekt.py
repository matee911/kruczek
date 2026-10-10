"""Projekt spraw jako repozytorium.

Sprawę wskazuje klucz: ścieżka jej folderu względem projektu (`sprawa-a`, `podprojekt/sprawa-b`).
CLI, strona i (później) serwer MCP rozmawiają z tym interfejsem — nie z tytułami ani ścieżkami
systemu plików — więc implementację plikową da się kiedyś podmienić bez zmian w wywołujących.
Klucz spoza spisu projektu jest odrzucany, zanim cokolwiek zostanie przeczytane.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from kruczek_core import repozytorium
from kruczek_core.dni_wolne import Kalendarz, kalendarz_sprawy
from kruczek_core.model import BladSprawy, Sprawa
from kruczek_core.render import renderuj

T = TypeVar("T")


@dataclass(frozen=True)
class SpisProjektu:
    sprawy: list[str]
    stary_format: list[str]
    bez_indexu: list[str]


class RepozytoriumSpraw(Protocol):
    def spis(self) -> SpisProjektu: ...

    def wczytaj(self, klucz: str) -> Sprawa: ...

    def zmien(self, klucz: str, zmiana: Callable[[Sprawa], T]) -> T: ...

    def kalendarz(self, klucz: str) -> Kalendarz: ...

    def odswiez_widok(self, klucz: str) -> str | None: ...


def odswiez_index(katalog: Path, przed: Callable[[str], str] = lambda t: t) -> str | None:
    """Odśwież bloki index.md po udanym zapisie. Zwraca ostrzeżenie zamiast rzucać —
    zapis już się udał, a powtórzenie polecenia zdublowałoby zdarzenie."""
    if not (katalog / "index.md").exists():
        return None
    try:
        kalendarz = kalendarz_sprawy(katalog)
        repozytorium.przetworz_tekst(
            katalog, "index.md", lambda tekst: renderuj(przed(tekst), repozytorium.wczytaj(katalog), kalendarz)
        )
    except (BladSprawy, OSError) as e:
        return f"zapisano, ale index.md nie odświeżony: {e}"
    return None


class PlikoweRepozytorium:
    def __init__(self, projekt: Path) -> None:
        self.projekt = projekt.resolve()

    def _klucz(self, katalog: Path) -> str:
        return katalog.relative_to(self.projekt).as_posix()

    def spis(self) -> SpisProjektu:
        lista = repozytorium.lista_spraw(self.projekt)
        return SpisProjektu(
            [self._klucz(k) for k in lista.sprawy],
            [self._klucz(k) for k in lista.stary_format],
            [self._klucz(k) for k in lista.bez_indexu],
        )

    def katalog(self, klucz: str) -> Path:
        spis = self.spis()
        if klucz not in spis.sprawy and klucz not in spis.stary_format:
            raise BladSprawy(f"w projekcie nie ma sprawy {klucz!r}")
        return self.projekt / klucz

    def wczytaj(self, klucz: str) -> Sprawa:
        return repozytorium.wczytaj(self.katalog(klucz))

    def zmien(self, klucz: str, zmiana: Callable[[Sprawa], T]) -> T:
        return repozytorium.zmien(self.katalog(klucz), zmiana)

    def kalendarz(self, klucz: str) -> Kalendarz:
        return kalendarz_sprawy(self.katalog(klucz))

    def odswiez_widok(self, klucz: str) -> str | None:
        return odswiez_index(self.katalog(klucz))
