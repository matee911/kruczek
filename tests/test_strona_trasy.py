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
from kruczek_core.reguly import REGULA_DORECZENIE, SpecTerminu
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


# --- kolejność kontroli i błędy formularza --------------------------------------------------------

def test_token_sprawdzany_przed_kluczem_i_ksztaltem_formularza(repo, klient):
    # Act — bez tokenu, klucz spoza spisu, brak pola opis
    r = klient.post("/sprawa/nie-ma/zadania/a1/zrobione", data={}, headers=HX)
    # Assert
    assert r.status_code == 403 and repo.zapisy == 0


def test_klucz_sprawdzany_przed_ksztaltem_formularza(repo, klient):
    # Act
    r = post(klient, "/sprawa/nie-ma/zadania/a1/zrobione")
    # Assert
    assert r.status_code == 404 and "Nie ma takiej sprawy" in r.text and repo.zapisy == 0


@pytest.mark.parametrize("sciezka, pola, pole", [
    ("/sprawa/sprawa-a/zadania/a2/zrobione", {}, "opis zadania"),
    ("/sprawa/sprawa-a/zadania/a2/zrobione", {"opis": "snapshot Web Archive", "widok": "inny"}, "widok"),
], ids=["brak-opisu", "nieznany-widok"])
def test_zly_ksztalt_formularza_po_polsku_bez_tekstow_pydantic(repo, klient, sciezka, pola, pole):
    # Act
    r = post(klient, sciezka, **pola)
    # Assert
    assert r.status_code == 422 and "Nie zapisano" in r.text and pole in r.text
    assert not any(slowo in r.text for slowo in ("Field required", "Input should", "pydantic", "detail"))
    assert repo.zapisy == 0


# --- zrobione -------------------------------------------------------------------------------------

def test_zrobione_bez_htmx_oddaje_cala_strone(repo, klient):
    # Arrange
    zid = zadanie(repo, "snapshot Web Archive").id
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", naglowki={}, opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 200 and r.text.startswith("<!doctype html>")


def test_cofnij_zrobione_otwiera_zadanie(repo, klient):
    # Arrange
    zid = zadanie(repo, "snapshot Web Archive").id
    post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/cofnij-zrobione", opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 200 and "Zadanie znów otwarte" in r.text
    assert zadanie(repo, "snapshot Web Archive").zrobione is None


def test_zadanie_o_tym_samym_numerze_z_innym_opisem_to_konflikt(repo, klient):
    # Arrange — numer zadania na stronie wskazuje dziś inne zadanie
    zid = zadanie(repo, "snapshot Web Archive").id
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="opis, który strona widziała wcześniej")
    # Assert
    assert r.status_code == 409 and "Sprawa zmieniła się w międzyczasie" in r.text
    assert zadanie(repo, "snapshot Web Archive").zrobione is None


def test_zrobione_juz_zrobione_400(repo, klient):
    # Arrange
    zid = zadanie(repo, "snapshot Web Archive").id
    post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 400 and "już zrobione" in r.text and repo.zapisy == 1


def test_uwaga_odswiezenia_index_to_alert_nie_blad_zapisu(repo):
    # Arrange
    repo.uwaga = "zapisano, ale index.md nie odświeżony: brak znacznika"
    zid = zadanie(repo, "snapshot Web Archive").id
    # Act
    r = post(klient_z(repo), f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 200 and "Zapisano, ale index.md nie jest aktualny" in r.text
    assert zadanie(repo, "snapshot Web Archive").zrobione == DZIS


# --- doręczenie -----------------------------------------------------------------------------------

@pytest.mark.parametrize("wpis, komunikat", [
    ("", "Wpisz datę doręczenia."),
    ("31.09.2026", "Wrzesień 2026 ma 30 dni."),
    ("21.10.2026", "Data jest z przyszłości."),
    ("07.10.2026", "Pismo nadano 08.10.2026 — doręczenie nie mogło być wcześniej."),
])
def test_doreczenie_zla_data_blad_pola_i_nic_nie_zapisane(repo, klient, wpis, komunikat):
    # Arrange
    sprawdzenie = zadanie(repo, regula=REGULA_DORECZENIE)
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{sprawdzenie.id}/doreczenie", widok="sprawa",
             opis=sprawdzenie.opis, data=wpis)
    # Assert
    assert r.status_code == 422
    assert komunikat in r.text and 'aria-invalid="true"' in r.text and f'value="{wpis}"' in r.text
    assert [z.typ for z in repo.sprawy["sprawa-a"].zdarzenia] == ["nadanie"] and repo.zapisy == 0


def test_cofnij_doreczenie_przywraca_szacunek(repo, klient):
    # Arrange
    sprawdzenie = zadanie(repo, regula=REGULA_DORECZENIE)
    post(klient, f"/sprawa/sprawa-a/zadania/{sprawdzenie.id}/doreczenie", widok="sprawa",
         opis=sprawdzenie.opis, data="10.10.2026")
    zid = repo.sprawy["sprawa-a"].zdarzenia[-1].id
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zdarzenia/{zid}/cofnij", widok="sprawa", typ="doreczenie", data="2026-10-10")
    # Assert
    assert r.status_code == 200 and "Cofnięto wpis doręczenia." in r.text
    s = repo.sprawy["sprawa-a"]
    assert [z.typ for z in s.zdarzenia] == ["nadanie"] and s.terminy[0].szacunek is True


def test_cofnij_z_data_nie_iso_to_blad_ksztaltu_po_polsku(repo, klient):
    # Act — toast wysyła datę ISO; inna postać to formularz spoza tej strony
    r = post(klient, "/sprawa/sprawa-a/zdarzenia/z1/cofnij", typ="nadanie", data="08.10.2026")
    # Assert
    assert r.status_code == 422 and "Nie zapisano" in r.text and "data" in r.text
    assert "Input should" not in r.text and repo.zapisy == 0
