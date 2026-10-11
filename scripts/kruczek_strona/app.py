"""Aplikacja strony (FastAPI). Trasy są cienkie: zależności z zaleznosci.py, słowa i dane ekranów
z ekrany.py; terminy, statusy i zapis liczy kruczek_core (RepozytoriumSpraw.zmien z czystymi
operacjami rdzenia — blokada + świeże dane). Trasy dotykające plików to zwykłe `def`: FastAPI
uruchamia je w puli wątków, więc blokujące I/O nie zatrzymuje pętli zdarzeń."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from kruczek_core.model import BladSprawy
from kruczek_core.operacje import odznacz_zrobione, zaznacz_zrobione
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kruczek_strona.ekrany import (
    BLAD_DOMYSLNY,
    BLAD_SERWERA_TRESC,
    BLAD_SERWERA_TYTUL,
    BLEDY_HTTP,
    NIE_MA_SPRAWY_TRESC,
    NIE_MA_SPRAWY_TYTUL,
    NIE_ZAPISANO,
    ODRZUCONE_TRESC,
    STARY_FORMAT_TRESC,
    STARY_FORMAT_TYTUL,
    WROC_DO_LISTY_SPRAW,
    komunikat_formularza,
    powiadomienie_otwarte,
    powiadomienie_zrobione,
)
from kruczek_strona.format import polecenie
from kruczek_strona.formularze import FormularzZadania
from kruczek_strona.katalog import utworz_katalog
from kruczek_strona.zaleznosci import (
    Dzis,
    Klucz,
    NieMaSprawy,
    Odrzucone,
    Repo,
    StronaHTML,
    Ustawienia,
    strona_bledu,
    z_tej_strony,
)

STATIC = Path(__file__).resolve().parent / "static"
NAGLOWKI = {
    "content-security-policy": ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                "font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; "
                                "base-uri 'none'"),
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "cache-control": "no-store",
}
DOZWOLONE_HOSTY = ["127.0.0.1", "localhost"]
MAKS_FORMULARZ = 64 * 1024


class Naglowki:
    """Nagłówki bezpieczeństwa na każdej odpowiedzi (także 400 z TrustedHostMiddleware i plikach statycznych)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wyslij(wiadomosc: Message) -> None:
            if wiadomosc["type"] == "http.response.start":
                naglowki = MutableHeaders(scope=wiadomosc)
                for nazwa, wartosc in NAGLOWKI.items():
                    naglowki[nazwa] = wartosc
            await send(wiadomosc)

        await self.app(scope, receive, wyslij)


class LimitFormularza:
    """Ciało żądania zapisu: z podaną długością i najwyżej MAKS_FORMULARZ bajtów. FastAPI czyta formularz,
    zanim zadziała jakakolwiek zależność, więc limit stoi przed aplikacją."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in ("GET", "HEAD"):
            dlugosc = Headers(scope=scope).get("content-length", "")
            if not dlugosc.isdigit() or int(dlugosc) > MAKS_FORMULARZ:
                await PlainTextResponse(f"{NIE_ZAPISANO}: formularz jest za duży.", status_code=413)(
                    scope, receive, send)
                return
        await self.app(scope, receive, send)


async def _odrzucone(request: Request, _: Odrzucone) -> HTMLResponse:
    return strona_bledu(request.app.state.katalog, request, 403, NIE_ZAPISANO, ODRZUCONE_TRESC)


async def _nie_ma_sprawy(request: Request, e: NieMaSprawy) -> HTMLResponse:
    if e.stary_format:
        return strona_bledu(request.app.state.katalog, request, 404, STARY_FORMAT_TYTUL, STARY_FORMAT_TRESC,
                            polecenie("migruj", e.klucz))
    return strona_bledu(request.app.state.katalog, request, 404, NIE_MA_SPRAWY_TYTUL, NIE_MA_SPRAWY_TRESC)


async def _zly_formularz(request: Request, e: RequestValidationError) -> HTMLResponse:
    k = komunikat_formularza(e.errors())
    return strona_bledu(request.app.state.katalog, request, 422, k.tytul, k.tresc)


async def _blad_http(request: Request, e: HTTPException) -> HTMLResponse:
    return strona_bledu(request.app.state.katalog, request, e.status_code,
                        BLEDY_HTTP.get(e.status_code, BLAD_DOMYSLNY), WROC_DO_LISTY_SPRAW)


async def _blad_serwera(request: Request, e: Exception) -> HTMLResponse:
    """Nieobsłużony wyjątek: ServerErrorMiddleware leży na zewnątrz `Naglowki`, więc nagłówki
    bezpieczeństwa ustawiamy na tej odpowiedzi sami."""
    odpowiedz = strona_bledu(request.app.state.katalog, request, 500, BLAD_SERWERA_TYTUL, BLAD_SERWERA_TRESC)
    odpowiedz.headers.update(NAGLOWKI)
    return odpowiedz


def _trasy() -> APIRouter:
    trasy = APIRouter(default_response_class=HTMLResponse)
    zapis = [Depends(z_tej_strony)]

    @trasy.get("/")
    def przeglad(strona: StronaHTML) -> HTMLResponse:
        return strona.widok_przegladu()

    @trasy.get("/sprawa/{klucz:path}")
    def sprawa(klucz: Klucz, strona: StronaHTML) -> HTMLResponse:
        return strona.widok_sprawy(klucz)

    @trasy.post("/sprawa/{klucz:path}/zadania/{zadanie_id}/zrobione", dependencies=zapis)
    def zrobione(klucz: Klucz, zadanie_id: str, f: Annotated[FormularzZadania, Form()], strona: StronaHTML,
                 repo: Repo, d: Dzis) -> HTMLResponse:
        try:
            z = repo.zmien(klucz, lambda s: zaznacz_zrobione(s, zadanie_id, d, oczekiwany_opis=f.opis))
        except BladSprawy as e:
            return strona.bez_zapisu(f.widok, klucz, e)
        return strona.po_zapisie(f.widok, klucz, powiadomienie_zrobione(klucz, zadanie_id, z.opis))

    @trasy.post("/sprawa/{klucz:path}/zadania/{zadanie_id}/cofnij-zrobione", dependencies=zapis)
    def cofnij_zrobione(klucz: Klucz, zadanie_id: str, f: Annotated[FormularzZadania, Form()],
                        strona: StronaHTML, repo: Repo) -> HTMLResponse:
        try:
            z = repo.zmien(klucz, lambda s: odznacz_zrobione(s, zadanie_id, oczekiwany_opis=f.opis))
        except BladSprawy as e:
            return strona.bez_zapisu(f.widok, klucz, e)
        return strona.po_zapisie(f.widok, klucz, powiadomienie_otwarte(z.opis))

    return trasy


def utworz_aplikacje(ustawienia: Ustawienia) -> FastAPI:
    """Nowa aplikacja na każde wywołanie (osobny stan i osobne dependency_overrides). Bez dokumentacji
    API (/docs, /redoc, /openapi.json) — strona to HTML dla jednej osoby, nie publiczne API."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,
                  middleware=[Middleware(Naglowki), Middleware(TrustedHostMiddleware, allowed_hosts=DOZWOLONE_HOSTY),
                              Middleware(LimitFormularza)])
    app.state.ustawienia = ustawienia
    app.state.katalog = utworz_katalog(ustawienia.token)
    app.add_exception_handler(NieMaSprawy, _nie_ma_sprawy)
    app.add_exception_handler(Odrzucone, _odrzucone)
    app.add_exception_handler(RequestValidationError, _zly_formularz)
    app.add_exception_handler(HTTPException, _blad_http)
    app.add_exception_handler(Exception, _blad_serwera)
    app.include_router(_trasy())
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
