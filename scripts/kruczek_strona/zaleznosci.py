"""Zależności strony (FastAPI `Depends`): ustawienia, repozytorium spraw, „dziś”, token sesji,
katalog komponentów i odpowiedzi HTML.

Stan żyje w `app.state` aplikacji z fabryki `utworz_aplikacje` — bez globali modułowych. Testy
podmieniają funkcje z tego modułu w `app.dependency_overrides` (repozytorium w pamięci, stały dzień);
każdy test ma własną aplikację, więc podmiany nie przechodzą między testami.
"""

import datetime as dt
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import jinjax
from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from kruczek_core.projekt import PlikoweRepozytorium, RepozytoriumSpraw
from pydantic import BaseModel, ConfigDict, Field


class Ustawienia(BaseModel):
    """Ustawienia jednej uruchomionej strony. Token jest nowy przy każdym starcie, więc formularz
    ze starej karty (sprzed restartu) niczego nie zapisze."""

    model_config = ConfigDict(frozen=True)
    projekt: Path
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32), min_length=1)


class NieMaSprawy(Exception):
    """Klucz spoza spisu projektu — 404, nic nie przeczytane; `stary_format` — sprawa sprzed sprawa.json."""

    def __init__(self, klucz: str, stary_format: bool = False) -> None:
        super().__init__(klucz)
        self.klucz = klucz
        self.stary_format = stary_format


def ustawienia(request: Request) -> Ustawienia:
    return request.app.state.ustawienia


def repozytorium(ust: Annotated[Ustawienia, Depends(ustawienia)]) -> RepozytoriumSpraw:
    return PlikoweRepozytorium(ust.projekt)


def dzis() -> dt.date:
    return dt.date.today()


def token_sesji(ust: Annotated[Ustawienia, Depends(ustawienia)]) -> str:
    return ust.token


def katalog(request: Request) -> jinjax.Catalog:
    return request.app.state.katalog


Repo = Annotated[RepozytoriumSpraw, Depends(repozytorium)]
Dzis = Annotated[dt.date, Depends(dzis)]


def strona_bledu(kat: jinjax.Catalog, request: Request, status: int, tytul: str, tresc: str = "",
                 polecenie: str = "", szczegoly: str = "") -> HTMLResponse:
    """Strona błędu (htmx: sam fragment #tresc-dynamiczna). Używają jej też handlery wyjątków."""
    nazwa = "strony.BladTresc" if "hx-request" in request.headers else "strony.Blad"
    html = kat.render(nazwa, _globals={"widok": "przeglad"}, tytul=tytul, tresc=tresc, polecenie=polecenie,
                      szczegoly=szczegoly)
    return HTMLResponse(html, status_code=status)


@dataclass(frozen=True)
class Strona:
    """Odpowiedzi HTML: `html()` renderuje komponent wskazany przez trasę (cały dokument albo fragment —
    zależnie od komponentu); przełączanie na fragment dla htmx robi tylko `strona_bledu`."""

    request: Request
    katalog: jinjax.Catalog
    repo: RepozytoriumSpraw
    dzis: dt.date

    def html(self, nazwa: str, widok: str, status: int = 200, **dane) -> HTMLResponse:
        return HTMLResponse(self.katalog.render(nazwa, _globals={"widok": widok}, **dane), status_code=status)

    def blad(self, status: int, tytul: str, tresc: str = "", polecenie: str = "", szczegoly: str = "") -> HTMLResponse:
        return strona_bledu(self.katalog, self.request, status, tytul, tresc, polecenie, szczegoly)


def strona(request: Request, kat: Annotated[jinjax.Catalog, Depends(katalog)], repo: Repo, d: Dzis) -> Strona:
    return Strona(request, kat, repo, d)


StronaHTML = Annotated[Strona, Depends(strona)]


def klucz_ze_spisu(klucz: str, repo: Repo) -> str:
    """Klucz sprawy z adresu, tylko ze spisu projektu. Spoza spisu → NieMaSprawy, zanim cokolwiek przeczytamy."""
    spis = repo.spis()
    if klucz in spis.sprawy:
        return klucz
    raise NieMaSprawy(klucz, klucz in spis.stary_format)


Klucz = Annotated[str, Depends(klucz_ze_spisu)]
