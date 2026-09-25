"""Testy eurlex.sh — skrypt uruchamiany jako proces, EUR-Lex podmieniony lokalnym serwerem.

Given/When/Then:
  Given poprawny CELEX i EUR-Lex odpowiada dokumentem
  When  pobieram html/pdf
  Then  plik jest zapisany, dostaję SHA-256, a zapytanie niesie uczciwy User-Agent kruczka

  Given EUR-Lex odpowiada wyzwaniem AWS WAF (202 + x-amzn-waf-action: challenge)
  When  pobieram dokument
  Then  skrypt kończy się kodem 2, nie zostawia pustego pliku i odsyła do WebFetch

  Given błędny CELEX albo nieznany język
  When  uruchamiam skrypt
  Then  kończy się kodem 1, zanim cokolwiek pójdzie w sieć
"""

import hashlib
import http.server
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

SKRYPT = Path(__file__).with_name("eurlex.sh")
PDF = b"%PDF-1.4 atrapa"
HTML = b"<html><head><title>62010CJ0618</title></head><body>wyrok</body></html>"


class Atrapa(http.server.BaseHTTPRequestHandler):
    """Odpowiada zgodnie z `tryb` ustawionym na serwerze; zapamiętuje nagłówki zapytań."""

    def do_GET(self):
        self.server.zapytania.append((self.path, dict(self.headers)))
        tryb = self.server.tryb
        if tryb == "waf":
            self.send_response(202)
            self.send_header("x-amzn-waf-action", "challenge")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if tryb == "html-zamiast-pdf" or "/TXT/HTML/" in self.path:
            body, ctype = HTML, "text/html; charset=UTF-8"
        else:
            body, ctype = PDF, "application/pdf"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class EurlexTestCase(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), Atrapa)
        self.srv.tryb = "ok"
        self.srv.zapytania = []
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def uruchom(self, *args):
        env = dict(
            os.environ,
            EURLEX_BASE=f"http://127.0.0.1:{self.srv.server_port}",
            # świeży TMPDIR = brak znacznika poprzedniego zapytania, więc bez czekania crawl-delay
            TMPDIR=str(self.cwd),
        )
        return subprocess.run(
            ["bash", str(SKRYPT), *args], cwd=self.cwd, env=env,
            capture_output=True, text=True, timeout=30,
        )


class TestPobieranie(EurlexTestCase):
    def test_pdf_zapisany_z_suma_i_domyslna_nazwa(self):
        # Act
        r = self.uruchom("pdf", "62010CJ0618")
        # Assert
        self.assertEqual(r.returncode, 0, r.stderr)
        plik = self.cwd / "CELEX_62010CJ0618_PL.pdf"
        self.assertEqual(plik.read_bytes(), PDF)
        self.assertIn(hashlib.sha256(PDF).hexdigest(), r.stdout)
        sciezka, _ = self.srv.zapytania[0]
        self.assertEqual(sciezka, "/legal-content/PL/TXT/PDF/?uri=CELEX:62010CJ0618")

    def test_html_w_innym_jezyku_do_wskazanego_pliku(self):
        # Act
        r = self.uruchom("html", "32016R0679", "en", "rodo.html")
        # Assert
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.cwd / "rodo.html").read_bytes(), HTML)
        sciezka, _ = self.srv.zapytania[0]
        self.assertEqual(sciezka, "/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679")

    def test_wersja_skonsolidowana_z_data(self):
        r = self.uruchom("html", "02016R0679-20160504")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.cwd / "CELEX_02016R0679-20160504_PL.html").exists())

    def test_user_agent_kruczka_nie_przegladarki(self):
        self.uruchom("pdf", "62010CJ0618")
        _, naglowki = self.srv.zapytania[0]
        ua = naglowki.get("User-Agent", "")
        self.assertTrue(ua.startswith("kruczek/"), ua)
        self.assertNotIn("Mozilla", ua)


class TestOdmowy(EurlexTestCase):
    def test_wyzwanie_waf_konczy_sie_kodem_2_bez_pliku(self):
        # Arrange
        self.srv.tryb = "waf"
        # Act
        r = self.uruchom("pdf", "62010CJ0618")
        # Assert
        self.assertEqual(r.returncode, 2)
        self.assertIn("WebFetch", r.stderr)
        self.assertFalse((self.cwd / "CELEX_62010CJ0618_PL.pdf").exists())

    def test_html_zamiast_pdf_to_blad_bez_pliku(self):
        # EUR-Lex przy braku PDF-u w danym języku potrafi oddać stronę HTML z kodem 200
        self.srv.tryb = "html-zamiast-pdf"
        r = self.uruchom("pdf", "62010CJ0618")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.cwd / "CELEX_62010CJ0618_PL.pdf").exists())

    def test_celex_malymi_literami_normalizowany(self):
        r = self.uruchom("pdf", "62010cj0618")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.cwd / "CELEX_62010CJ0618_PL.pdf").exists())

    def test_bledny_celex_bez_zapytania(self):
        r = self.uruchom("pdf", "62010CJ0618&foo=bar")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.srv.zapytania, [])

    def test_nieznany_jezyk_bez_zapytania(self):
        r = self.uruchom("html", "62010CJ0618", "XX")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.srv.zapytania, [])

    def test_bez_argumentow_pokazuje_uzycie(self):
        r = self.uruchom()
        self.assertEqual(r.returncode, 1)
        self.assertIn("eurlex.sh html", r.stdout)


if __name__ == "__main__":
    unittest.main()
