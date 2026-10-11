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
from kruczek_core.model import BladSprawy
from kruczek_core.projekt import (
    PlikoweRepozytorium,
    RepozytoriumSpraw,
    przeglad_projektu,
)
from kruczek_core.repozytorium import KonfliktRewizji
from pydantic import BaseModel, ConfigDict, Field

from kruczek_strona.ekrany import (
    KONFLIKT,
    SPRAWA_USZKODZONA_TRESC,
    SPRAWA_USZKODZONA_TYTUL,
    Powiadomienie,
    alert_bez_zapisu,
    alert_index_nieaktualny,
    ekran_co_robic,
    ekran_sprawy,
)


class Ustawienia(BaseModel):
    """Ustawienia jednej uruchomionej strony. Token jest nowy przy każdym starcie, więc formularz
    ze starej karty (sprzed restartu) niczego nie zapisze."""

    model_config = ConfigDict(frozen=True)
    projekt: Path
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32), min_length=1)


class Odrzucone(Exception):
    """Zapis nie pochodzi z tej strony (token, Sec-Fetch-Site) — 403 bez danych spraw."""


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

    def _czesc(self) -> str:
        """htmx dostaje sam fragment #tresc-dynamiczna, zwykłe żądanie — całą stronę."""
        return "Tresc" if "hx-request" in self.request.headers else ""

    def widok_przegladu(self, status: int = 200, **dane) -> HTMLResponse:
        ekran = ekran_co_robic(przeglad_projektu(self.repo, self.dzis), self.dzis)
        return self.html(f"strony.Przeglad{self._czesc()}", "przeglad", status, ekran=ekran, **dane)

    def widok_sprawy(self, klucz: str, status: int = 200, **dane) -> HTMLResponse:
        """Sprawa o nieczytelnym sprawa.json → 422 z tym samym tekstem po GET i po akcji."""
        try:
            s, kal = self.repo.wczytaj(klucz), self.repo.kalendarz(klucz)
        except BladSprawy as e:
            return self.blad(422, SPRAWA_USZKODZONA_TYTUL, SPRAWA_USZKODZONA_TRESC, szczegoly=str(e))
        ekran = ekran_sprawy(klucz, s, kal, self.dzis)
        return self.html(f"strony.Sprawa{self._czesc()}", "sprawa", status, ekran=ekran, **dane)

    def widok_po_akcji(self, widok: str, klucz: str, status: int = 200, **dane) -> HTMLResponse:
        if widok == "sprawa":
            return self.widok_sprawy(klucz, status, **dane)
        return self.widok_przegladu(status, **dane)

    def bez_zapisu(self, widok: str, klucz: str, e: BladSprawy) -> HTMLResponse:
        if isinstance(e, KonfliktRewizji):
            return self.widok_po_akcji(widok, klucz, 409, alert=KONFLIKT)
        return self.widok_po_akcji(widok, klucz, 400, alert=alert_bez_zapisu(e))

    def po_zapisie(self, widok: str, klucz: str, powiadomienie: Powiadomienie) -> HTMLResponse:
        uwaga = self.repo.odswiez_widok(klucz)
        alert = alert_index_nieaktualny(uwaga) if uwaga else None
        return self.widok_po_akcji(widok, klucz, alert=alert, powiadomienie=powiadomienie)


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


async def z_tej_strony(request: Request, token: Annotated[str, Depends(token_sesji)]) -> None:
    """Zapis tylko z tej strony: bez Sec-Fetch-Site z innej witryny i z tokenem sesji (porównanie na
    bajtach — token z polskimi znakami nie daje 500). Zależność trasy, więc działa przed walidacją
    formularza i przed sprawdzeniem klucza."""
    if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
        raise Odrzucone
    wyslany = (await request.form()).get("token")
    if not isinstance(wyslany, str) or not secrets.compare_digest(wyslany.encode(), token.encode()):
        raise Odrzucone
