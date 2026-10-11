"""Strona na prawdziwym katalogu projektu (integracja): pliki spraw, bezpieczeństwo, zapis
i współbieżność z CLI. Logika tras na repozytorium w pamięci — tests/test_strona_trasy.py."""

import datetime as dt
import json
import re

import pytest
from fastapi.testclient import TestClient
from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.operacje import (
    cofnij_zdarzenie,
    dodaj_watek,
    dodaj_zadanie,
    dodaj_zdarzenie,
    nowa_sprawa,
)
from kruczek_core.reguly import SpecTerminu
from kruczek_strona.app import MAKS_FORMULARZ, utworz_aplikacje
from kruczek_strona.zaleznosci import Ustawienia, dzis

DZIS = dt.date(2026, 10, 20)
TOKEN = "token-testowy"
HX = {"HX-Request": "true"}


def klient_projektu(projekt, base_url="http://127.0.0.1"):
    """Prawdziwe repozytorium plikowe; podmieniony tylko zegar. Nowa aplikacja na każdy test."""
    app = utworz_aplikacje(Ustawienia(projekt=projekt, token=TOKEN))
    app.dependency_overrides[dzis] = lambda: DZIS
    return TestClient(app, base_url=base_url)


@pytest.fixture
def projekt(tmp_path):
    a = tmp_path / "sprawa-a"
    a.mkdir()
    nowa_sprawa(a, "Sprawa testowa A", "Firma X sp. z o.o.", "opiekun1", w_imieniu="Osoba Testowa")
    dodaj_watek(a, "firma", "Firma X sp. z o.o.")
    dodaj_zdarzenie(a, "nadanie", dt.date(2026, 10, 8), Kalendarz(), DZIS, watek="firma",
                    termin=SpecTerminu("14d", "art. 7 u.r."))
    dodaj_zadanie(a, "snapshot Web Archive", dt.date(2026, 10, 1))
    (tmp_path / "stara").mkdir()
    (tmp_path / "stara" / "index.md").write_text("# Sprawa: stara\n", encoding="utf-8")
    (tmp_path / "kopia 2").mkdir()
    zepsuta = tmp_path / "zepsuta"
    zepsuta.mkdir()
    (zepsuta / "sprawa.json").write_text("{", encoding="utf-8")
    return tmp_path


@pytest.fixture
def klient(projekt):
    return klient_projektu(projekt, "http://127.0.0.1:8765")


def dane_sprawy(projekt, klucz="sprawa-a"):
    return json.loads((projekt / klucz / "sprawa.json").read_text(encoding="utf-8"))


def zadanie(projekt, opis=None, regula=None):
    return next(a for a in dane_sprawy(projekt)["zadania"]
                if (opis is None or a["opis"] == opis) and (regula is None or a["regula"] == regula))


def klient_ze_sprawa(tmp_path, klucz):
    (tmp_path / "podprojekt").mkdir()
    (tmp_path / "podprojekt" / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    katalog = tmp_path / klucz
    katalog.mkdir()
    nowa_sprawa(katalog, "T", "Firma X sp. z o.o.", "opiekun1")
    dodaj_zadanie(katalog, "zadanie testowe", dt.date(2026, 10, 1))
    return klient_projektu(tmp_path)


def post(klient, sciezka, naglowki=HX, **pola):
    return klient.post(sciezka, data={"token": TOKEN, **pola}, headers=naglowki)


# --- ekrany z plików projektu ---------------------------------------------------------------------

def test_przeglad_pokazuje_sekcje_i_problemy_projektu(klient):
    # Act
    r = klient.get("/")
    # Assert
    assert r.status_code == 200
    html = r.text
    assert "snapshot Web Archive" in html                                    # Teraz
    assert "Firma X sp. z o.o.: ok. 22.10.2026" in html                      # sprawdzenie doręczenia (szacunek)
    assert "Czekam na odpowiedź: Firma X sp. z o.o." in html and "ok. 22.10.2026" in html
    assert "stara" in html and "/kruczek:migruj" in html                      # stary format
    assert "kopia 2" in html                                                 # pominięto
    assert "zepsuta" in html and "uszkodzony JSON" in html                   # błędy
    assert "wtorek" in html and "20.10.2026" in html


def test_przeglad_ta_sama_lista_zadan_co_co_robic(projekt, klient, capsys):
    # Arrange — TERAZ i WKRÓTCE z CLI: „[a1] klucz: tytuł / wątek — opis  dopiski”
    import teczka
    teczka.main(["--dzis", DZIS.isoformat(), "co-robic", str(projekt)])
    cli = capsys.readouterr().out
    opisy_cli = re.findall(r"^\s+(?:od \S+\s+)?\[a\d+\] [^\n]*? — (.+?)(?:  .*)?$", cli, re.MULTILINE)
    # Act
    html = klient.get("/").text
    # Assert
    assert len(opisy_cli) == 3  # 2 w TERAZ, 1 w WKRÓTCE
    assert all(opis in html for opis in opisy_cli)


def test_dowody_jako_tekst_bez_linkow(projekt, klient):
    # Arrange
    dodaj_zdarzenie(projekt / "sprawa-a", "fakt", dt.date(2026, 10, 9), Kalendarz(), DZIS,
                    dowody=["ARCHIWUM/2026-10-09_email_firma.eml"])
    # Act
    r = klient.get("/sprawa/sprawa-a")
    # Assert
    assert "ARCHIWUM/2026-10-09_email_firma.eml" in r.text
    assert "href=\"ARCHIWUM" not in r.text and "href=\"/ARCHIWUM" not in r.text


@pytest.mark.parametrize("klucz", ["sprawa ze spacją ąę", "podprojekt/sprawa-b"])
def test_sprawa_z_nazwa_ze_spacja_i_w_podprojekcie(tmp_path, klucz):
    # Arrange
    k = klient_ze_sprawa(tmp_path, klucz)
    link = k.get("/").text.split('href="/sprawa/')[1].split('"')[0]
    # Act
    r = k.get("/sprawa/" + link)
    # Assert
    assert r.status_code == 200 and "zadanie testowe" in r.text


@pytest.mark.parametrize("sciezka", ["/sprawa/../../etc/passwd", "/sprawa/%2e%2e/x", "/sprawa/nie-ma",
                                     "/sprawa/.kruczek", "/sprawa/kopia 2"])
def test_klucz_spoza_spisu_404(klient, sciezka):
    # Act
    r = klient.get(sciezka)
    # Assert
    assert r.status_code == 404


def test_stara_sprawa_mowi_o_migracji(klient):
    # Act
    r = klient.get("/sprawa/stara")
    # Assert
    assert r.status_code == 404 and "/kruczek:migruj stara" in r.text


def test_uszkodzona_sprawa_strona_bledu_ze_szczegolami(klient):
    # Act
    r = klient.get("/sprawa/zepsuta")
    # Assert
    assert r.status_code == 422 and "Nie da się odczytać tej sprawy" in r.text and "uszkodzony JSON" in r.text


# --- bezpieczeństwo -------------------------------------------------------------------------------

def test_obcy_host_odrzucony(klient):
    # Act
    r = klient.get("/", headers={"host": "zly.example"})
    # Assert
    assert r.status_code == 400 and "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_localhost_z_portem_dozwolony(klient):
    # Act / Assert
    assert klient.get("/", headers={"host": "localhost:8765"}).status_code == 200


def test_naglowki_bezpieczenstwa_i_csp_bez_zewnetrznych_zrodel(klient):
    # Act
    r = klient.get("/")
    # Assert
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src 'self'" in csp and "font-src 'self'" in csp
    assert "http" not in csp and "unsafe" not in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store" and "server" not in r.headers


def test_strona_bez_style_inline_i_skryptow_inline(klient):
    # Act
    html = klient.get("/sprawa/sprawa-a").text + klient.get("/").text
    # Assert
    assert " style=" not in html
    assert all("src=" in tag for tag in re.findall(r"<script[^>]*>", html))


def test_static_tylko_z_katalogu_strony(klient, projekt):
    # Act / Assert
    assert klient.get("/static/kruczek.css").status_code == 200
    assert klient.get("/static/fonts/archivo-latin-ext-wdth-normal.woff2").status_code == 200
    assert klient.get("/static/../app.py").status_code == 404
    assert klient.get("/static/%2e%2e/app.py").status_code == 404
    assert klient.get("/static/../../sprawa-a/sprawa.json").status_code == 404


def test_brak_tras_do_plikow_spraw(klient):
    # Act / Assert — dowody i sprawa.json nie są serwowane żadną drogą
    for sciezka in ["/sprawa-a/sprawa.json", "/sprawa/sprawa-a/sprawa.json", "/sprawa/sprawa-a/ARCHIWUM/x.eml"]:
        assert klient.get(sciezka).status_code == 404


def test_bez_dokumentacji_api(klient):
    # Act / Assert — FastAPI domyślnie wystawia /docs, /redoc i /openapi.json; strona ich nie ma
    for sciezka in ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"]:
        assert klient.get(sciezka).status_code == 404


@pytest.mark.parametrize("pola, naglowki", [
    ({"opis": "snapshot Web Archive"}, HX),
    ({"token": "zly", "opis": "snapshot Web Archive"}, HX),
    ({"token": "żółć", "opis": "snapshot Web Archive"}, HX),
    ({"token": TOKEN, "opis": "snapshot Web Archive"}, {**HX, "sec-fetch-site": "cross-site"}),
], ids=["bez-tokenu", "zly-token", "token-z-polskimi-znakami", "cross-site"])
def test_zapis_z_obcej_strony_odrzucony(projekt, klient, pola, naglowki):
    # Arrange
    zid = zadanie(projekt, "snapshot Web Archive")["id"]
    # Act
    r = klient.post(f"/sprawa/sprawa-a/zadania/{zid}/zrobione", data=pola, headers=naglowki)
    # Assert
    assert r.status_code == 403 and "Nie zapisano" in r.text and TOKEN not in r.text
    assert zadanie(projekt, "snapshot Web Archive")["zrobione"] is None


def test_za_duzy_formularz_odrzucony_bez_zapisu(projekt, klient):
    # Arrange — FastAPI czyta cały formularz przed zależnościami; limit stoi przed aplikacją
    zid = zadanie(projekt, "snapshot Web Archive")["id"]
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="x" * (MAKS_FORMULARZ + 1))
    # Assert
    assert r.status_code == 413 and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert zadanie(projekt, "snapshot Web Archive")["zrobione"] is None


# --- zapis do sprawa.json i współbieżność z CLI ---------------------------------------------------

def test_zrobione_zapisuje_odswieza_fragment_i_daje_cofnij(projekt, klient):
    # Arrange
    zid = zadanie(projekt, "snapshot Web Archive")["id"]
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 200 and r.text.startswith('<div id="tresc-dynamiczna"')
    assert "Oznaczono jako zrobione: „snapshot Web Archive”." in r.text
    assert f'hx-post="/sprawa/sprawa-a/zadania/{zid}/cofnij-zrobione"' in r.text
    assert zadanie(projekt, "snapshot Web Archive")["zrobione"] == "2026-10-20"


def test_dwa_zrobione_pod_rzad_bez_falszywego_konfliktu(projekt, klient):
    # Arrange
    dodaj_zadanie(projekt / "sprawa-a", "drugie", dt.date(2026, 10, 1))
    pierwsze, drugie = zadanie(projekt, "snapshot Web Archive")["id"], zadanie(projekt, "drugie")["id"]
    # Act
    r1 = post(klient, f"/sprawa/sprawa-a/zadania/{pierwsze}/zrobione", opis="snapshot Web Archive")
    r2 = post(klient, f"/sprawa/sprawa-a/zadania/{drugie}/zrobione", opis="drugie")
    # Assert
    assert (r1.status_code, r2.status_code) == (200, 200)


def test_zadanie_zmienione_w_cli_to_konflikt_i_nic_nie_zapisane(projekt, klient):
    # Arrange — strona pokazała zadanie z nadania; w CLI cofnięto nadanie razem z jego zadaniami
    # i dodano inne zadanie
    dane = dane_sprawy(projekt)
    widziane = next(a for a in dane["zadania"] if a["zdarzenie_id"] == dane["zdarzenia"][-1]["id"])
    cofnij_zdarzenie(projekt / "sprawa-a", dane["zdarzenia"][-1]["id"], Kalendarz())
    dodaj_zadanie(projekt / "sprawa-a", "całkiem inne", dt.date(2026, 10, 1))
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{widziane['id']}/zrobione", opis=widziane["opis"])
    # Assert
    assert r.status_code == 409 and "Sprawa zmieniła się w międzyczasie" in r.text
    assert all(a["zrobione"] is None for a in dane_sprawy(projekt)["zadania"])


def test_zrobione_zepsute_znaczniki_index_alert_ale_zapisane(projekt, klient):
    # Arrange
    (projekt / "sprawa-a" / "index.md").write_text("<!-- kruczek:zadania -->\n", encoding="utf-8")
    zid = zadanie(projekt, "snapshot Web Archive")["id"]
    # Act
    r = post(klient, f"/sprawa/sprawa-a/zadania/{zid}/zrobione", opis="snapshot Web Archive")
    # Assert
    assert r.status_code == 200 and "nie odświeżony" in r.text
    assert zadanie(projekt, "snapshot Web Archive")["zrobione"] == "2026-10-20"


@pytest.mark.parametrize("klucz", ["sprawa ze spacją ąę", "podprojekt/sprawa-b"])
def test_zrobione_dla_klucza_ze_spacja_i_w_podprojekcie(tmp_path, klucz):
    # Arrange
    k = klient_ze_sprawa(tmp_path, klucz)
    link = k.get("/").text.split('href="/sprawa/')[1].split('"')[0]
    # Act
    r = post(k, f"/sprawa/{link}/zadania/a1/zrobione", opis="zadanie testowe")
    # Assert
    assert r.status_code == 200 and "Oznaczono jako zrobione" in r.text
