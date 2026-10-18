"""test_linki_dowodu.py — rekomendacje archiwizacji linków z dowodu: reguły, stały format JSON, CLI."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import linki_dowodu
from linki_dowodu import Powod, Rekomendacja, czysty_url, ocen_link, ocen_plik

ODBIORCA = "osoba.testowa@odbiorca.example"
#: base64(ODBIORCA) — token śledzący z adresem odbiorcy
TOKEN = "b3NvYmEudGVzdG93YUBvZGJpb3JjYS5leGFtcGxl"
SPAM = (
    "From: Firma X <biuro@firma-x.example>\n"
    f"To: {ODBIORCA}\n"
    "List-Unsubscribe: <https://firma-x.example/u/1>, <mailto:wypisz@firma-x.example>\n"
    "Subject: Oferta\n"
    "Content-Type: text/html\n\n"
    f'<a href="https://sledzenie.example/r?u={TOKEN}">Oferta</a>'
    '<a href="https://firma-x.example/regulamin">Regulamin</a>'
    '<a href="https://firma-x.example/regulamin">Regulamin jeszcze raz</a>'
    '<img src="https://piksel.example/o.gif" width="1" height="1">'
    '<a href="https://firma-x.example/u/1">Wypisz się</a>'
)


def _plik(katalog, nazwa, tresc):
    sciezka = Path(katalog) / nazwa
    sciezka.write_bytes(tresc.encode("utf-8"))
    return sciezka


def _po_url(wynik):
    return {link["url"]: link for link in wynik["linki"]}


class TestRekomendacje(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wynik = ocen_plik(_plik(self._tmp.name, "2026-10-01_email_firma-x.eml", SPAM))
        self.linki = _po_url(self.wynik)

    def tearDown(self):
        self._tmp.cleanup()

    def test_token_z_adresem_odbiorcy_nie_archiwizuj(self):
        # Act
        link = self.linki[f"https://sledzenie.example/r?u={TOKEN}"]
        # Assert
        self.assertEqual(link["rekomendacja"], "NIE_ARCHIWIZUJ")
        self.assertEqual(link["powody"], ["TOKEN_Z_ADRESEM", "PARAMETRY"])

    def test_link_ze_slow_archiwizuj(self):
        # Act
        link = self.linki["https://firma-x.example/regulamin"]
        # Assert
        self.assertEqual((link["rekomendacja"], link["powody"]), ("ARCHIWIZUJ", ["SAME_SLOWA"]))

    def test_wypisanie_w_stopce_i_w_naglowku_to_jeden_wpis_nie_archiwizuj(self):
        # Arrange — ten sam URL w treści (przed nagłówkiem) nie może wygrać oceną „zwykły link”
        # Act
        link = self.linki["https://firma-x.example/u/1"]
        # Assert
        self.assertEqual(link["zrodla"], ["a", "List-Unsubscribe"])
        self.assertEqual(link["rekomendacja"], "NIE_ARCHIWIZUJ")
        self.assertIn("LINK_WYPISANIA", link["powody"])

    def test_zasob_osadzony_nie_archiwizuj(self):
        # Act
        link = self.linki["https://piksel.example/o.gif"]
        # Assert
        self.assertEqual(link["rekomendacja"], "NIE_ARCHIWIZUJ")
        self.assertIn("ZASOB_OSADZONY", link["powody"])

    def test_strona_glowna_domeny_bez_identyfikatora_archiwizuj(self):
        # Act
        domeny = {d["domena"]: d for d in self.wynik["domeny"]}
        # Assert
        self.assertEqual(set(domeny), {"sledzenie.example", "firma-x.example", "piksel.example"})
        self.assertEqual(domeny["sledzenie.example"]["strona_glowna"], "https://sledzenie.example/")
        self.assertEqual({d["rekomendacja"] for d in domeny.values()}, {"ARCHIWIZUJ"})

    def test_odbiorca_z_naglowka_to(self):
        # Assert
        self.assertEqual(self.wynik["odbiorcy"], [ODBIORCA])

    def test_mailto_pomijany_a_ten_sam_link_raz(self):
        # Act
        urle = [link["url"] for link in self.wynik["linki"]]
        # Assert
        self.assertFalse([u for u in urle if not u.startswith("https://")])
        self.assertEqual(urle.count("https://firma-x.example/regulamin"), 1)


class TestKsztaltLinku(unittest.TestCase):
    """ARCHIWIZUJ tylko przy pozytywnym kształcie — każdy inny link co najmniej ZAPYTAJ."""

    def test_identyfikator_bez_tokenu_zapytaj(self):
        for url in ("https://firma-x.example/c/Ab3xK9q", "https://firma-x.example/s/12345678",
                    "https://firma-x.example/l/user-8812734", "https://firma-x.example/regulamin-2026"):
            with self.subTest(url):
                # Act
                ocena = ocen_link(url, [ODBIORCA])
                # Assert
                self.assertEqual(ocena.rekomendacja, Rekomendacja.ZAPYTAJ)

    def test_czesc_lokalna_adresu_w_sciezce_nie_archiwizuj(self):
        # Act
        ocena = ocen_link("https://firma-x.example/dla/osoba-testowa", [ODBIORCA])
        # Assert
        self.assertEqual((ocena.rekomendacja, ocena.powody[0]), (Rekomendacja.NIE_ARCHIWIZUJ, Powod.ADRES_ODBIORCY))

    def test_adres_kodowany_dwa_razy_nie_archiwizuj(self):
        # Act
        ocena = ocen_link("https://firma-x.example/konto?e=osoba.testowa%2540odbiorca.example", [ODBIORCA])
        # Assert
        self.assertEqual(ocena.powody[0], Powod.ADRES_ODBIORCY)

    def test_fragment_jak_parametry_zapytaj(self):
        # Act
        ocena = ocen_link("https://firma-x.example/regulamin#u=k9", [])
        # Assert
        self.assertEqual((ocena.rekomendacja, ocena.powody), (Rekomendacja.ZAPYTAJ, (Powod.PARAMETRY,)))

    def test_identyfikator_w_nazwie_hosta_zapytaj(self):
        # Act
        ocena = ocen_link("https://x7k2p9q4.sledzenie.example/", [ODBIORCA])
        # Assert
        self.assertEqual((ocena.rekomendacja, ocena.powody), (Rekomendacja.ZAPYTAJ, (Powod.IDENTYFIKATOR,)))

    def test_czesc_lokalna_w_nazwie_hosta_nie_archiwizuj(self):
        # Act
        ocena = ocen_link("https://osoba-testowa.firma-x.example/", [ODBIORCA])
        # Assert
        self.assertEqual(ocena.rekomendacja, Rekomendacja.NIE_ARCHIWIZUJ)


class TestCzystyUrl(unittest.TestCase):
    """Link, którego problemem są tylko parametry, ma adres bez nich — do archiwum i Wayback bez pytania."""

    def test_parametry_sledzace_i_fragment_obciete(self):
        # Act
        ocena = ocen_link("https://firma-x.example/oferta?utm_source=newsletter&utm_medium=email#cena", [ODBIORCA])
        # Assert
        self.assertEqual(ocena.rekomendacja, Rekomendacja.ZAPYTAJ)
        self.assertEqual(czysty_url(ocena, [ODBIORCA]), "https://firma-x.example/oferta")

    def test_adres_odbiorcy_w_parametrze_obciety(self):
        # Act
        ocena = ocen_link("https://firma-x.example/oferta?e=osoba.testowa%40odbiorca.example", [ODBIORCA])
        # Assert
        self.assertEqual(ocena.rekomendacja, Rekomendacja.NIE_ARCHIWIZUJ)
        self.assertEqual(czysty_url(ocena, [ODBIORCA]), "https://firma-x.example/oferta")

    def test_pusta_sciezka_to_strona_glowna(self):
        # Act
        ocena = ocen_link("https://firma-x.example?utm_source=newsletter", [ODBIORCA])
        # Assert
        self.assertEqual(czysty_url(ocena, [ODBIORCA]), "https://firma-x.example/")

    def test_bez_czystego_gdy_sciezka_dalej_cos_niesie(self):
        for url in ("https://firma-x.example/c/Ab3xK9q?utm_source=newsletter",
                    "https://firma-x.example/dla/osoba-testowa?utm_source=newsletter",
                    f"https://firma-x.example/r/{TOKEN}?utm_source=newsletter",
                    "https://x7k2p9q4.sledzenie.example/oferta?utm_source=newsletter"):
            with self.subTest(url):
                # Act / Assert
                self.assertIsNone(czysty_url(ocen_link(url, [ODBIORCA]), [ODBIORCA]))

    def test_bez_czystego_dla_wypisania_zasobu_i_danych_logowania(self):
        for url, zrodla in (("https://firma-x.example/wypisz?id=1", ("a",)),
                            ("https://piksel.example/o.gif?u=1", ("img",)),
                            ("https://uzytkownik:haslo@firma-x.example/oferta?x=1", ("a",))):
            with self.subTest(url):
                # Act / Assert
                self.assertIsNone(czysty_url(ocen_link(url, [ODBIORCA], zrodla), [ODBIORCA]))

    def test_bez_czystego_dla_linku_juz_archiwizuj(self):
        # Act / Assert
        self.assertIsNone(czysty_url(ocen_link("https://firma-x.example/regulamin", [ODBIORCA]), [ODBIORCA]))

    def test_koncowka_przekierowania_bez_czystego(self):
        # Arrange — w SPAM link „Oferta” to przekierowanie z base64 adresu w parametrze
        with tempfile.TemporaryDirectory() as tmp:
            linki = _po_url(ocen_plik(_plik(tmp, "w.eml", SPAM)))
        # Act
        link = linki[f"https://sledzenie.example/r?u={TOKEN}"]
        klik = ocen_link("https://click.mailer.example/ls/click?upn=Xk2", [ODBIORCA])
        # Assert — sam tracker bez tokenu nie pokaże strony oferty
        self.assertEqual((link["rekomendacja"], link["czysty_url"]), ("NIE_ARCHIWIZUJ", None))
        self.assertIsNone(czysty_url(klik, [ODBIORCA]))
        self.assertIsNone(linki["https://firma-x.example/u/1"]["czysty_url"])

    def test_adres_docelowy_z_parametru_przekierowania(self):
        # Arrange
        przez_tracker = ("https://click.mailer.example/ls/click?upn=Xk2"
                         "&url=https%3A%2F%2Ffirma-x.example%2Foferta%3Futm_source%3Dnews")
        z_adresem = "https://click.mailer.example/ls/click?url=https%3A%2F%2Ffirma-x.example%2Fdla%2Fosoba-testowa"
        # Act / Assert
        self.assertEqual(czysty_url(ocen_link(przez_tracker, [ODBIORCA]), [ODBIORCA]), "https://firma-x.example/oferta")
        self.assertIsNone(czysty_url(ocen_link(z_adresem, [ODBIORCA]), [ODBIORCA]))

    def test_przekierowanie_ze_skryptu_bierze_cel_nie_tracker(self):
        for url in ("https://tracker.example/redirect.php?url=https%3A%2F%2Ffirma-x.example%2Foferta",
                    "https://tracker.example/out.php?url=https%3A%2F%2Ffirma-x.example%2Foferta"):
            with self.subTest(url):
                # Act / Assert
                self.assertEqual(czysty_url(ocen_link(url, [ODBIORCA]), [ODBIORCA]), "https://firma-x.example/oferta")
        self.assertIsNone(czysty_url(ocen_link(f"https://tracker.example/r.php?u={TOKEN}", [ODBIORCA]), [ODBIORCA]))

    def test_do_archiwizacji_bez_powtorzen(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            md = _plik(tmp, "notatka.md", "https://firma-x.example/oferta i https://firma-x.example/oferta?utm_source=x")
            # Act
            wynik = ocen_plik(md)
        # Assert
        self.assertEqual(wynik["do_archiwizacji"], ["https://firma-x.example/oferta"])


class TestHost(unittest.TestCase):
    """Link z wrogiego pliku do sieci lokalnej nie może wywołać zapytania z komputera użytkownika."""

    def test_siec_lokalna_nie_archiwizuj(self):
        for url in ("http://localhost:8080/shutdown", "http://[::1]:8080/admin", "http://router.local/reboot",
                    "http://intranet/panel", "http://192.168.1.1/", "http://serwer.home.arpa/",
                    "http://127.1/", "http://0x7f.1/"):
            with self.subTest(url):
                # Act
                ocena = ocen_link(url, [ODBIORCA])
                # Assert
                self.assertEqual(ocena.rekomendacja, Rekomendacja.NIE_ARCHIWIZUJ)
                self.assertIn(Powod.HOST_LOKALNY, ocena.powody)

    def test_siec_lokalna_za_trackerem_bez_czystego(self):
        # Act
        ocena = ocen_link("https://click.mailer.example/ls/click?url=http%3A%2F%2Frouter.local%2Fpanel", [ODBIORCA])
        # Assert
        self.assertIsNone(czysty_url(ocena, [ODBIORCA]))

    def test_publiczny_adres_ip_i_jawny_port_zapytaj(self):
        for url in ("https://8.8.8.8/oferta", "https://[2001:4860:4860::8888]/oferta", "https://firma-x.example:8443/oferta",
                    "https://firma-x.example:99999/oferta"):
            with self.subTest(url):
                # Act
                ocena = ocen_link(url, [ODBIORCA])
                # Assert
                self.assertEqual(ocena.rekomendacja, Rekomendacja.ZAPYTAJ)
                self.assertIn(Powod.HOST_NIETYPOWY, ocena.powody)

    def test_strona_glowna_hosta_ipv6_poprawnym_adresem(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            strona = _plik(tmp, "strona.html", '<a href="http://[::1]:8080/admin">Panel</a>')
            # Act
            domena = ocen_plik(strona)["domeny"][0]
        # Assert
        self.assertEqual((domena["strona_glowna"], domena["rekomendacja"]), ("https://[::1]/", "NIE_ARCHIWIZUJ"))


class TestDaneOdbiorcy(unittest.TestCase):
    """Imię i nazwisko albo nazwa domeny odbiorcy w slugu to nie „same słowa” — pyta użytkownik."""

    ODBIORCA_FIRMOWY = "jan@studio-testowe.example"

    def test_imie_i_nazwisko_w_slugu_zapytaj_i_bez_czystego(self):
        for url in ("https://firma-x.example/dla/jan-testowy", "https://firma-x.example/dla/jan-testowy?utm_source=x",
                    "https://firma-x.example/dla/testowy-jan"):
            with self.subTest(url):
                # Act
                ocena = ocen_link(url, [self.ODBIORCA_FIRMOWY], nazwy=["Jan Testowy"])
                # Assert
                self.assertEqual(ocena.rekomendacja, Rekomendacja.ZAPYTAJ)
                self.assertIn(Powod.DANE_ODBIORCY, ocena.powody)
                self.assertIsNone(czysty_url(ocena, [self.ODBIORCA_FIRMOWY], ["Jan Testowy"]))

    def test_nazwisko_bez_polskich_znakow(self):
        # Act
        ocena = ocen_link("https://firma-x.example/oferta/geslowska", [], nazwy=["Zażółcia Gęślowska"])
        # Assert
        self.assertEqual(ocena.powody, (Powod.DANE_ODBIORCY,))

    def test_nazwa_domeny_odbiorcy_spoza_poczty_darmowej(self):
        # Act
        firmowa = ocen_link("https://firma-x.example/audyt/studio-testowe", [self.ODBIORCA_FIRMOWY])
        darmowa = ocen_link("https://firma-x.example/outlook", ["jan@outlook.example"])
        # Assert
        self.assertEqual(firmowa.powody, (Powod.DANE_ODBIORCY,))
        self.assertEqual(darmowa.rekomendacja, Rekomendacja.ARCHIWIZUJ)

    def test_nazwa_z_naglowka_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            eml = _plik(tmp, "w.eml", f"From: Firma X <biuro@firma-x.example>\nTo: Jan Testowy <{self.ODBIORCA_FIRMOWY}>\n"
                        "Subject: Oferta\nContent-Type: text/html\n\n"
                        '<a href="https://firma-x.example/dla/jan-testowy">Twoja oferta</a>')
            # Act
            wynik = ocen_plik(eml)
        # Assert
        self.assertEqual((wynik["odbiorcy"], wynik["nazwy"]), ([self.ODBIORCA_FIRMOWY], ["Jan Testowy"]))
        self.assertEqual(wynik["linki"][0]["rekomendacja"], "ZAPYTAJ")
        self.assertEqual(wynik["do_archiwizacji"], [])


class TestDomenyNaglowkow(unittest.TestCase):
    """Domena nadawcy z nagłówków to też domena do zabezpieczenia — zwykle mówi, kto stoi za wysyłką."""

    NAGLOWKI = ("To: {odbiorca}\nSubject: Oferta\nContent-Type: text/html\n\n"
                '<a href="https://firma-x.example/regulamin">Regulamin</a>')

    def _wynik(self, naglowki_nadawcy):
        with tempfile.TemporaryDirectory() as tmp:
            eml = _plik(tmp, "w.eml", naglowki_nadawcy + self.NAGLOWKI.format(odbiorca=ODBIORCA))
            return ocen_plik(eml)

    def test_domena_nadawcy_bez_linku_do_niej_ma_strone_glowna_archiwizuj(self):
        # Act
        wynik = self._wynik("From: Firma X <biuro@wysylka-promo.example>\n")
        # Assert
        domeny = {d["domena"]: d for d in wynik["domeny"]}
        self.assertEqual(domeny["wysylka-promo.example"]["strona_glowna"], "https://wysylka-promo.example/")
        self.assertEqual(domeny["wysylka-promo.example"]["rekomendacja"], "ARCHIWIZUJ")

    def test_from_reply_to_return_path_i_sender_po_domenach_linkow_bez_received(self):
        # Act
        wynik = self._wynik("From: Firma X <biuro@wysylka-promo.example>\nReply-To: kontakt@odpowiedzi.example\n"
                            "Return-Path: <zwrot@wysylka-promo.example>\nSender: <wysylka@nadawca-techniczny.example>\n"
                            "Received: from serwer.pocztowy.example (serwer.pocztowy.example [192.0.2.1])\n")
        # Assert — bez powtórzeń, najpierw domeny linków, potem nagłówków
        self.assertEqual([d["domena"] for d in wynik["domeny"]],
                         ["firma-x.example", "wysylka-promo.example", "odpowiedzi.example", "nadawca-techniczny.example"])


class TestPlikiInneNizEml(unittest.TestCase):
    def test_adres_odbiorcy_z_argumentu_kodowany_procentowo(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            md = _plik(tmp, "2026-10-01_skan_umowa_tekst.md",
                       "Konto: https://firma-x.example/konto?login=osoba.testowa%40odbiorca.example.\n")
            # Act
            wynik = ocen_plik(md, ["Osoba.Testowa@odbiorca.example"])
        # Assert
        link = wynik["linki"][0]
        self.assertEqual(link["url"], "https://firma-x.example/konto?login=osoba.testowa%40odbiorca.example")
        self.assertEqual(link["rekomendacja"], "NIE_ARCHIWIZUJ")
        self.assertEqual(link["powody"][0], "ADRES_ODBIORCY")

    def test_parametry_bez_tokenu_zapytaj(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            md = _plik(tmp, "notatka.md", "https://firma-x.example/?utm_source=newsletter")
            # Act
            link = ocen_plik(md)["linki"][0]
        # Assert
        self.assertEqual((link["rekomendacja"], link["powody"]), ("ZAPYTAJ", ["PARAMETRY"]))

    def test_nieprzejrzysty_token_w_sciezce_zapytaj(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            md = _plik(tmp, "notatka.md", "https://firma-x.example/r/8f3a9c2e4b1d7f60a5e2")
            # Act
            link = ocen_plik(md)["linki"][0]
        # Assert
        self.assertEqual((link["rekomendacja"], link["powody"]), ("ZAPYTAJ", ["TOKEN_ZAKODOWANY"]))

    def test_obrazek_w_zapisanej_stronie_to_zasob_osadzony(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            strona = _plik(tmp, "20261001120000-firma-x.example.html",
                           '<p>Oferta</p><img src="https://piksel.example/o.gif">')
            # Act
            link = ocen_plik(strona)["linki"][0]
        # Assert
        self.assertEqual((link["zrodla"], link["rekomendacja"]), (["img"], "NIE_ARCHIWIZUJ"))


class TestFormat(unittest.TestCase):
    def test_wynik_ma_staly_ksztalt_i_wartosci_z_enumow(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Act
            wynik = ocen_plik(_plik(tmp, "w.eml", SPAM))
        # Assert
        self.assertEqual(set(wynik), {"plik", "odbiorcy", "nazwy", "linki", "domeny", "do_archiwizacji"})
        wpisy = [*wynik["linki"], *wynik["domeny"]]
        for link in wynik["linki"]:
            self.assertEqual(set(link), {"url", "domena", "zrodla", "rekomendacja", "powody", "czysty_url"})
            self.assertTrue(link["czysty_url"] is None or link["czysty_url"].startswith(("http://", "https://")))
        for domena in wynik["domeny"]:
            self.assertEqual(set(domena), {"domena", "strona_glowna", "rekomendacja", "powody"})
        for wpis in wpisy:
            self.assertIn(wpis["rekomendacja"], {r.value for r in Rekomendacja})
            self.assertTrue(wpis["powody"] and set(wpis["powody"]) <= {p.value for p in Powod})


class TestCli(unittest.TestCase):
    def _uruchom(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            kod = linki_dowodu.main(argv)
        return kod, out.getvalue(), err.getvalue()

    def test_cli_wypisuje_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            eml = _plik(tmp, "w.eml", SPAM)
            # Act
            kod, out, _ = self._uruchom([str(eml), "--odbiorca", "inny@odbiorca.example", "--nazwa", "Osoba Testowa"])
        # Assert
        self.assertEqual(kod, 0)
        self.assertIn("inny@odbiorca.example", json.loads(out)["odbiorcy"])
        self.assertEqual(json.loads(out)["nazwy"], ["Osoba Testowa"])

    def test_brak_pliku_kod_2(self):
        # Act
        kod, _, err = self._uruchom(["/nie/ma/takiego.eml"])
        # Assert
        self.assertEqual(kod, 2)
        self.assertIn("brak pliku", err)

    def test_nieobslugiwany_typ_kod_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            pdf = _plik(tmp, "umowa.pdf", "%PDF-1.4")
            # Act
            kod, _, err = self._uruchom([str(pdf)])
        # Assert
        self.assertEqual(kod, 2)
        self.assertIn("_tekst.md", err)


if __name__ == "__main__":
    unittest.main()
