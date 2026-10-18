"""archiwa.sh: `lokalnie` nie zdradza drugiej stronie, kto zbiera dowód; `pobierz` zapisuje snapshot taki, jaki był."""

import gzip
import hashlib
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SKRYPT = Path(__file__).resolve().parent.parent / "scripts" / "archiwa.sh"


class _Zapis(http.server.BaseHTTPRequestHandler):
    agenci: list[str] = []

    def do_GET(self):  # noqa: N802 — nazwa wymagana przez http.server
        _Zapis.agenci.append(self.headers.get("User-Agent", ""))
        tresc = b"<p>Regulamin</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def log_message(self, *args):
        pass


class _OdpowiedzGzip(http.server.BaseHTTPRequestHandler):
    """Serwer albo CDN, który zawsze odpowiada skompresowaną treścią z `Content-Encoding: gzip`."""

    def do_GET(self):  # noqa: N802 — nazwa wymagana przez http.server
        tresc = gzip.compress(b"<p>Regulamin</p>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def log_message(self, *args):
        pass


def _uruchom(obsluga):
    serwer = http.server.ThreadingHTTPServer(("127.0.0.1", 0), obsluga)
    threading.Thread(target=serwer.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serwer.server_address[1]}/regulamin"
    serwer.shutdown()
    serwer.server_close()


@pytest.fixture
def adres():
    _Zapis.agenci = []
    yield from _uruchom(_Zapis)


@pytest.fixture
def adres_gzip():
    yield from _uruchom(_OdpowiedzGzip)


def test_lokalnie_bez_kontaktu_nazwy_narzedzia_i_modelu_w_user_agencie(tmp_path, adres):
    # Arrange — serwer drugiej strony nie może się dowiedzieć, kto i czym zbiera dowód
    srodowisko = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    srodowisko["KRUCZEK_MODEL"] = "claude-test"
    # Act
    wynik = subprocess.run(
        ["bash", str(SKRYPT), "lokalnie", adres, str(tmp_path), "--kontakt", "osoba.testowa@odbiorca.example"],
        env=srodowisko, capture_output=True, text=True, timeout=60, check=False,
    )
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    assert len(_Zapis.agenci) == 1
    ua = _Zapis.agenci[0].lower()
    assert [s for s in ("@", "odbiorca", "kruczek", "claude") if s in ua] == []
    assert _Zapis.agenci[0] in next(tmp_path.glob("*.zrzut.md")).read_text(encoding="utf-8")


def test_lokalnie_zapisuje_odpowiedz_skompresowana_przez_serwer_rozpakowana(tmp_path, adres_gzip):
    # Arrange — w teczce ma wylądować treść strony, a nie bajty gzip pod nazwą .html i z ich sumą
    srodowisko = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    # Act
    wynik = subprocess.run(
        ["bash", str(SKRYPT), "lokalnie", adres_gzip, str(tmp_path)],
        env=srodowisko, capture_output=True, text=True, timeout=60, check=False,
    )
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    tresc = next(tmp_path.glob("*.html")).read_bytes()
    assert tresc == b"<p>Regulamin</p>"
    metryczka = next(tmp_path.glob("*.zrzut.md")).read_text(encoding="utf-8")
    assert hashlib.sha256(tresc).hexdigest() in metryczka
    assert "rozpakowana przez curl" in metryczka


#: curl na PATH udający Internet Archive: snapshot `id_` przychodzi z kodowaniem z chwili zapisu (gzip),
#: a rozpakowuje go — jak prawdziwy curl — tylko wywołanie z --compressed.
SZTUCZNY_CURL = """\
import gzip, os, sys
argi = sys.argv[1:]
snapshot = next((a for a in argi if "web.archive.org/web/" in a), None)
if snapshot is None:
    sys.exit(0)
if os.environ.get("CURL_KOD"):
    sys.exit(int(os.environ["CURL_KOD"]))
typ, tresc = {".pdf": ("application/pdf", b"%PDF-1.4 regulamin"), ".png": ("image/png", b"\\x89PNG zrzut")}.get(
    os.path.splitext(snapshot)[1], ("text/html; charset=UTF-8", b"<p>Regulamin</p>"))
typ = os.environ.get("CURL_TYP", typ)
with open(argi[argi.index("-o") + 1], "wb") as plik:
    plik.write(tresc if "--compressed" in argi and not os.environ.get("CURL_GZIP") else gzip.compress(tresc))
if "-w" in argi:
    sys.stdout.write(argi[argi.index("-w") + 1].replace("%{content_type}", typ))
"""


def _pobierz(tmp_path, adres, **zmienne):
    katalog_bin = tmp_path / "bin"
    katalog_bin.mkdir()
    curl = katalog_bin / "curl"
    curl.write_text(f"#!{sys.executable}\n{SZTUCZNY_CURL}", encoding="utf-8")
    curl.chmod(0o755)
    srodowisko = {**os.environ, **zmienne, "PATH": f"{katalog_bin}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", str(SKRYPT), "pobierz", adres, "20261018002004", str(tmp_path / "out"),
         "--kontakt", "osoba.testowa@odbiorca.example"],
        env=srodowisko, capture_output=True, text=True, timeout=60, check=False,
    )


@pytest.mark.parametrize(("adres", "nazwa", "tresc"), [
    ("https://firma-x.example/regulamin", "wayback-20261018002004-firma-x.example.html", b"<p>Regulamin</p>"),
    ("https://firma-x.example/regulamin.pdf", "wayback-20261018002004-firma-x.example.pdf", b"%PDF-1.4 regulamin"),
    ("https://firma-x.example/zrzut.png", "wayback-20261018002004-firma-x.example.png", b"\x89PNG zrzut"),
])
def test_pobierz_zapisuje_snapshot_rozpakowany_z_rozszerzeniem_wg_typu(tmp_path, adres, nazwa, tresc):
    # Arrange — w ARCHIWUM ma trafić treść strony, a nie bajty gzip pod nazwą .html
    # Act
    wynik = _pobierz(tmp_path, adres)
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    pliki = sorted((tmp_path / "out").iterdir())
    assert [p.name for p in pliki] == [nazwa]
    assert pliki[0].read_bytes() == tresc


def test_pobierz_rozpoznaje_typ_tresci_bez_wzgledu_na_wielkosc_liter(tmp_path):
    # Arrange — Internet Archive odtwarza Content-Type serwera, a typy MIME nie rozróżniają wielkości liter
    # Act
    wynik = _pobierz(tmp_path, "https://firma-x.example/regulamin.pdf", CURL_TYP="application/PDF")
    # Assert
    assert wynik.returncode == 0, wynik.stderr
    pliki = sorted((tmp_path / "out").iterdir())
    assert [p.name for p in pliki] == ["wayback-20261018002004-firma-x.example.pdf"]
    assert pliki[0].read_bytes() == b"%PDF-1.4 regulamin"


def test_pobierz_podaje_kod_bledu_curla_i_nic_nie_zapisuje(tmp_path):
    # Act
    wynik = _pobierz(tmp_path, "https://firma-x.example/regulamin", CURL_KOD="22")
    # Assert
    assert wynik.returncode == 1
    assert "curl 22" in wynik.stderr
    assert list((tmp_path / "out").iterdir()) == []


def test_pobierz_odrzuca_snapshot_zapisany_jako_gzip(tmp_path):
    # Arrange — gdyby rozpakowanie znów zawiodło, błąd ma być głośny, a nie suma kontrolna bajtów gzip
    # Act
    wynik = _pobierz(tmp_path, "https://firma-x.example/regulamin", CURL_GZIP="1")
    # Assert
    assert wynik.returncode == 1
    assert "gzip" in wynik.stderr
    assert list((tmp_path / "out").iterdir()) == []
