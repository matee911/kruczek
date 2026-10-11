"""Trasy strony jednostkowo: repozytorium w pamięci i stały dzień przez app.dependency_overrides.
Operacje rdzenia prawdziwe — podmieniony jest tylko zapis na dysk. Pliki, współbieżność z CLI
i bezpieczeństwo HTTP — tests/test_strona.py."""

import copy
import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.operacje import (
    dopisz_watek,
    dopisz_zadanie,
    dopisz_zdarzenie,
    utworz_sprawe,
)
from kruczek_core.projekt import SpisProjektu
from kruczek_core.reguly import SpecTerminu
from kruczek_strona.app import utworz_aplikacje
from kruczek_strona.ekrany import BLAD_SERWERA_TYTUL
from kruczek_strona.zaleznosci import Ustawienia, dzis, repozytorium

DZIS = dt.date(2026, 10, 20)
TOKEN = "token-testowy"
HX = {"HX-Request": "true"}


class RepozytoriumWPamieci:
    """RepozytoriumSpraw bez plików: `zmien` działa na kopii i podmienia sprawę dopiero po udanej
    zmianie — jak zapis pod blokadą (wyjątek = nic nie zapisane)."""

    def __init__(self, sprawy, stary_format=(), uwaga=None):
        self.sprawy, self.stary_format = dict(sprawy), list(stary_format)
        self.uwaga = uwaga
        self.zapisy = 0

    def spis(self):
        return SpisProjektu(sorted(self.sprawy), self.stary_format, [])

    def wczytaj(self, klucz):
        return copy.deepcopy(self.sprawy[klucz])

    def zmien(self, klucz, zmiana):
        s = self.wczytaj(klucz)
        wynik = zmiana(s)
        s.rewizja += 1
        self.sprawy[klucz] = s
        self.zapisy += 1
        return wynik

    def kalendarz(self, klucz):
        return Kalendarz()

    def odswiez_widok(self, klucz):
        return self.uwaga


def sprawa_a():
    s = utworz_sprawe("Sprawa testowa A", "Firma X sp. z o.o.", "opiekun1", w_imieniu="Osoba Testowa")
    dopisz_watek(s, "firma", "Firma X sp. z o.o.")
    dopisz_zdarzenie(s, "nadanie", dt.date(2026, 10, 8), Kalendarz(), DZIS, watek="firma",
                     termin=SpecTerminu("14d", "art. 7 u.r."))
    dopisz_zadanie(s, "snapshot Web Archive", dt.date(2026, 10, 1))
    return s


def klient_z(repo):
    app = utworz_aplikacje(Ustawienia(projekt=Path("/nie-ma-takiego-katalogu"), token=TOKEN))
    app.dependency_overrides[repozytorium] = lambda: repo
    app.dependency_overrides[dzis] = lambda: DZIS
    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def repo():
    return RepozytoriumWPamieci({"sprawa-a": sprawa_a()}, stary_format=["stara"])


@pytest.fixture
def klient(repo):
    return klient_z(repo)


def zadanie(repo, opis=None, regula=None):
    return next(a for a in repo.sprawy["sprawa-a"].zadania
                if (opis is None or a.opis == opis) and (regula is None or a.regula == regula))


def post(klient, sciezka, naglowki=HX, **pola):
    return klient.post(sciezka, data={"token": TOKEN, **pola}, headers=naglowki)


# --- ekrany ---------------------------------------------------------------------------------------

def test_pusty_projekt_mowi_jak_zalozyc_sprawe():
    # Arrange
    k = klient_z(RepozytoriumWPamieci({}))
    # Act
    html = k.get("/").text
    # Assert
    assert "Nie ma tu jeszcze spraw" in html and "/kruczek:nowa-sprawa" in html


def test_sprawa_terminy_z_podstawa_strony_i_chronologia(klient):
    # Act
    r = klient.get("/sprawa/sprawa-a")
    # Assert
    assert r.status_code == 200
    assert "Sprawa testowa A" in r.text and "Osoba Testowa" in r.text and "Firma X sp. z o.o." in r.text
    assert "art. 7 u.r." in r.text and "ok. 22.10.2026" in r.text and "Szacunek" in r.text
    assert "Nadanie pisma" in r.text and "Zapisz doręczenie" in r.text


def test_nieznany_adres_strona_bledu_po_polsku(klient):
    # Act
    r = klient.get("/nie-ma-takiej-strony")
    # Assert — nie JSON FastAPI ({"detail": "Not Found"})
    assert r.status_code == 404 and "Nie ma takiej strony" in r.text and "detail" not in r.text


def test_podmiany_zaleznosci_nie_przechodza_miedzy_aplikacjami():
    # Arrange
    pierwsza = klient_z(RepozytoriumWPamieci({})).app
    # Act
    druga = utworz_aplikacje(Ustawienia(projekt=Path("/nie-ma-takiego-katalogu"), token=TOKEN))
    # Assert
    assert pierwsza.dependency_overrides and druga.dependency_overrides == {}


def test_nieobsluzony_wyjatek_strona_bledu_po_polsku_z_naglowkami(repo):
    # Arrange
    def zepsute():
        raise OSError("dysk niedostępny")

    app = klient_z(repo).app
    app.dependency_overrides[repozytorium] = zepsute
    k = TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False)
    # Act
    r = k.get("/")
    # Assert
    assert r.status_code == 500 and BLAD_SERWERA_TYTUL in r.text and "dysk niedostępny" not in r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
