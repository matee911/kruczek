"""Aplikacja strony (FastAPI). Trasy są cienkie: zależności z zaleznosci.py, słowa i dane ekranów
z ekrany.py; terminy, statusy i zapis liczy kruczek_core (RepozytoriumSpraw.zmien z czystymi
operacjami rdzenia — blokada + świeże dane). Trasy dotykające plików to zwykłe `def`: FastAPI
uruchamia je w puli wątków, więc blokujące I/O nie zatrzymuje pętli zdarzeń."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from kruczek_core.model import BladSprawy
from kruczek_core.projekt import przeglad_projektu
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kruczek_strona.ekrany import (
    BLAD_DOMYSLNY,
    BLEDY_HTTP,
    NIE_MA_SPRAWY_TRESC,
    NIE_MA_SPRAWY_TYTUL,
    SPRAWA_USZKODZONA_TRESC,
    SPRAWA_USZKODZONA_TYTUL,
    STARY_FORMAT_TRESC,
    STARY_FORMAT_TYTUL,
    WROC_DO_LISTY_SPRAW,
    ekran_co_robic,
    ekran_sprawy,
)
from kruczek_strona.format import polecenie
from kruczek_strona.katalog import utworz_katalog
from kruczek_strona.zaleznosci import (
    Dzis,
    Klucz,
    NieMaSprawy,
    Repo,
    StronaHTML,
    Ustawienia,
    strona_bledu,
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


async def _nie_ma_sprawy(request: Request, e: NieMaSprawy) -> HTMLResponse:
    if e.stary_format:
        return strona_bledu(request.app.state.katalog, request, 404, STARY_FORMAT_TYTUL, STARY_FORMAT_TRESC,
                            polecenie("migruj", e.klucz))
    return strona_bledu(request.app.state.katalog, request, 404, NIE_MA_SPRAWY_TYTUL, NIE_MA_SPRAWY_TRESC)


async def _blad_http(request: Request, e: HTTPException) -> HTMLResponse:
    return strona_bledu(request.app.state.katalog, request, e.status_code,
                        BLEDY_HTTP.get(e.status_code, BLAD_DOMYSLNY), WROC_DO_LISTY_SPRAW)


def _trasy() -> APIRouter:
    trasy = APIRouter(default_response_class=HTMLResponse)

    @trasy.get("/")
    def przeglad(strona: StronaHTML, repo: Repo, d: Dzis) -> HTMLResponse:
        return strona.html("strony.Przeglad", "przeglad", ekran=ekran_co_robic(przeglad_projektu(repo, d), d))

    @trasy.get("/sprawa/{klucz:path}")
    def sprawa(klucz: Klucz, strona: StronaHTML, repo: Repo, d: Dzis) -> HTMLResponse:
        try:
            s, kal = repo.wczytaj(klucz), repo.kalendarz(klucz)
        except BladSprawy as e:
            return strona.blad(422, SPRAWA_USZKODZONA_TYTUL, SPRAWA_USZKODZONA_TRESC, szczegoly=str(e))
        return strona.html("strony.Sprawa", "sprawa", ekran=ekran_sprawy(klucz, s, kal, d))

    return trasy


def utworz_aplikacje(ustawienia: Ustawienia) -> FastAPI:
    """Nowa aplikacja na każde wywołanie (osobny stan i osobne dependency_overrides). Bez dokumentacji
    API (/docs, /redoc, /openapi.json) — strona to HTML dla jednej osoby, nie publiczne API."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,
                  middleware=[Middleware(Naglowki), Middleware(TrustedHostMiddleware, allowed_hosts=DOZWOLONE_HOSTY)])
    app.state.ustawienia = ustawienia
    app.state.katalog = utworz_katalog(ustawienia.token)
    app.add_exception_handler(NieMaSprawy, _nie_ma_sprawy)
    app.add_exception_handler(HTTPException, _blad_http)
    app.include_router(_trasy())
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
