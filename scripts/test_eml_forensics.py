"""test_eml_forensics.py — regresje na konkretnych defektach wykrytych w przeglądach.

Każdy test odpowiada jednemu ustaleniu z niezależnych ocen raportów (`*_review.md`).
Nazwa testu mówi, co było zepsute; docstring cytuje zarzut. Doctesty w modułach
sprawdzają pojedyncze funkcje — tu sprawdzamy zachowanie całego skryptu na pełnych
wiadomościach, bo część defektów ujawniała się dopiero w złożeniu sekcji.

Dane są **zanonimizowane co do treści, nie co do formy**: adresy, domeny, nazwy
i identyfikatory zastąpiono wymyślonymi, ale zachowano składnię, długości pól,
kodowania i strukturę nagłówków — bo to one wyzwalały błędy.
"""

import datetime
import os
import re
import sys
import tempfile
import unittest
from email import message_from_string, policy
from pathlib import Path

import eml_forensics

#: Ścieżka do CLI liczona od tego pliku, nie od katalogu roboczego —
#: test uruchamiany spoza repo szedł na nieistniejącą ścieżkę i „przechodził”
#: dlatego, że skryptu nie było, a nie dlatego, że zachowanie jest poprawne.
CLI = Path(__file__).resolve().parent / "eml_forensics.py"
import eml_forensics_logika as logika
import eml_forensics_raport as raport


def build(headers: str, body: str = "tresc") -> str:
    return f"{headers.strip()}\n\n{body}"


def analyze(raw: str) -> str:
    """Uruchamia pełną ścieżkę skryptu na tekście .eml i zwraca raport."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wiadomosc.eml"
        path.write_bytes(raw.encode("utf-8"))
        report, _ = eml_forensics.build_report(path, Path(tmp))
        return report


class TestSfabrykowaneDane(unittest.TestCase):
    """Raport nie może zawierać wartości, których w pliku nie ma."""

    def test_dmarc_nie_produkuje_wyniku_arc(self):
        """„W wiadomości nie ma tokenu arc=. Parser dopasował podłańcuch w dmarc=."

        Zarzut powtórzony w 10 z 13 ocen — najczęstszy błąd całego zestawu.
        """
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "Authentication-Results: mx.odbiorca.pl;\n"
            "\tdkim=pass header.i=@przyklad.pl;\n"
            "\tspf=pass smtp.mailfrom=nadawca@przyklad.pl;\n"
            "\tdmarc=pass (p=NONE sp=NONE dis=NONE) header.from=przyklad.pl"
        )
        msg = message_from_string(raw, policy=policy.default)
        methods = [
            m.method for h in logika.extract_auth_headers(msg) for m in h.methods
        ]
        self.assertEqual(methods, ["dkim", "spf", "dmarc"])
        self.assertNotIn("arc", methods)

    def test_arc_wykryty_gdy_naprawde_jest(self):
        """Blokada podciągu nie może gubić prawdziwego wyniku `arc=`."""
        raw = build("Authentication-Results: mx.odbiorca.pl; arc=pass; dmarc=fail")
        msg = message_from_string(raw, policy=policy.default)
        methods = [
            m.method for h in logika.extract_auth_headers(msg) for m in h.methods
        ]
        self.assertEqual(methods, ["arc", "dmarc"])

    def test_naglowki_uwierzytelnienia_nie_sa_sklejane(self):
        """„Sklejka Authentication-Results z Received-SPF — cytat przestaje być cytatem."""
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "Received-SPF: pass (odbiorca.pl: domena autoryzuje) client-ip=198.18.7.9\n"
            "Authentication-Results: mx.odbiorca.pl; spf=pass smtp.mailfrom=nadawca@przyklad.pl"
        )
        report = analyze(raw)
        self.assertIn("**Received-SPF #1**", report)
        self.assertIn("**Authentication-Results #1**", report)
        # Wartości obu nagłówków nie mogą się znaleźć w jednym bloku cytatu.
        self.assertNotIn("client-ip=198.18.7.9;\nmx.odbiorca.pl", report)

    def test_niepodpisane_naglowki_liczone_z_pliku_nie_z_szablonu(self):
        """„Lista statyczna, nie wynik analizy — Cc i Bcc w wiadomości nie istnieją."""
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "Subject: Temat\n"
            "Message-ID: <abc@przyklad.pl>\n"
            "Precedence: bulk\n"
            "DKIM-Signature: v=1; d=przyklad.pl; s=sel; h=From:Subject; bh=AAAA"
        )
        report = analyze(raw)
        self.assertIn("Message-ID", report)
        self.assertIn("Precedence", report)
        for nieistniejacy in ("`Cc`", "`Bcc`", "`List-Unsubscribe`"):
            self.assertNotIn(
                nieistniejacy,
                report.split("## 6. Podpisy DKIM")[1].split("## 7.")[0],
                f"{nieistniejacy} nie występuje w wiadomości, a trafił na listę",
            )

    def test_adres_odbiorcy_nie_jest_zmyslany_ani_okrajany(self):
        """„Adres zapisany błędnie — klientacd@ zamiast klient+acd@; zgubiony `+`."

        W raportach pojawiał się też adres, którego w pliku nie było wcale.
        """
        raw = build("From: nadawca@przyklad.pl\nTo: klient+kanal@odbiorca.pl")
        report = analyze(raw)
        self.assertIn("klient+kanal@odbiorca.pl", report)
        self.assertNotIn("klientkanal@odbiorca.pl", report)

    def test_brak_tez_o_zawartosci_tokenu_list_unsubscribe(self):
        """„Adres odbiorcy pojawia się w List-Unsubscribe (token Base64)" — teza fałszywa.

        Raport ma cytować nagłówek, a nie orzekać, co token zawiera.
        """
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "To: klient@odbiorca.pl\n"
            "List-Unsubscribe: <mailto:wypis@dostawca.example?subject=Unsubscribe>"
        )
        report = analyze(raw)
        self.assertIn("wypis@dostawca.example", report)
        self.assertNotIn("Adres odbiorcy", report)


class TestZgubioneDowody(unittest.TestCase):
    """Raport nie może zaprzeczać istnieniu dowodu, który w pliku jest."""

    def test_kotwica_z_zagniezdzonym_znacznikiem_jest_widziana(self):
        """„Regex kończy się na >([^<]+)</a> — nie dopuszcza zagnieżdżonego <span>."""
        html = (
            '<a href="https://cel.example/x"><span style="color:#000">Zobacz</span></a>'
        )
        resources = logika.extract_html_resources(html)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].url, "https://cel.example/x")
        self.assertEqual(resources[0].text, "Zobacz")

    def test_kotwica_opakowujaca_obraz_jest_widziana(self):
        """„Kotwica nr 1 nie ma tekstu bezpośredniego, opakowuje <div> — parser ją zgubił."""
        html = '<a href="https://cel.example/cta"><img src="https://cdn.example/b.png"></a>'
        kinds = {r.kind for r in logika.extract_html_resources(html)}
        self.assertEqual(kinds, {"a", "img"})

    def test_piksel_sledzacy_jest_odnotowany(self):
        """„Tabela §6.5 parsuje wyłącznie <a href>, więc pixel 1×1 nie istnieje w raporcie."""
        html = '<img height="1" width="1" src="https://sledzenie.example/o/TOKEN.gif" alt="" />'
        resources = logika.extract_html_resources(html)
        self.assertTrue(resources[0].is_pixel)

    def test_script_i_stylesheet_sa_odnotowane(self):
        """„Znacznik <script> w treści maila" oraz arkusz CSS ładowany zdalnie."""
        html = (
            '<link rel="stylesheet" href="https://dostawca.example/s.css">'
            '<script type="text/javascript" src="/sciezka/skrypt.js"></script>'
        )
        kinds = sorted(r.kind for r in logika.extract_html_resources(html))
        self.assertEqual(kinds, ["link", "script"])

    def test_token_w_sciezce_url_jest_dekodowany(self):
        """„Raport szuka tylko Base64 w parametrach; tu identyfikatory są w path."""
        tokens = logika.decode_tokens(
            "https://dostawca.example/e/6a75d83a7b8c0129001949.gif"
        )
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].byte_length, 11)

    def test_token_binarny_jest_odnotowany_a_nie_pomijany(self):
        """„To opaque identyfikatory, nie zakodowany adres" — ale istnieją.

        Token nadal musi trafić do wyniku (to była pierwotna skarga). Zmieniła
        się kolumna „Po zdekodowaniu”: ciąg bez wypełnienia `=` nie jest dowodem
        na to, że cokolwiek w nim zakodowano, więc raport podaje jego kształt
        zamiast długości w bajtach i skrótu z przypadkowo zdekodowanych danych.
        """
        tokens = logika.decode_tokens(
            "https://dostawca.example/t/kf0LaY8LJ9ceWLx7YbKumw"
        )
        self.assertTrue(tokens)
        self.assertIsNone(tokens[0].decoded_text)
        self.assertEqual(tokens[0].byte_length, 0)
        self.assertIn("nie ustalono", tokens[0].encoding)
        self.assertIn("22 znaków", tokens[0].encoding)

    def test_token_z_wypelnieniem_jest_nadal_dekodowany(self):
        """Wypełnienie `=` to sygnał z pliku — wtedy dekodowanie ma podstawę."""
        tokens = logika.decode_tokens(
            "https://dostawca.example/?p=a2xpZW50YWNkQHByenlrbGFkLnBs"
        )
        self.assertEqual(tokens[0].decoded_text, "klientacd@przyklad.pl")
        self.assertEqual(tokens[0].encoding, "base64")

    def test_uuid_opis_nie_trafia_do_pola_z_danymi(self):
        """„Kolumna »Po zdekodowaniu« pokazuje 'UUID wersja 4' w repr()."

        Opis struktury to nie zawartość tokenu. Trzymany w `decoded_text`
        wyciekał do raportu jako rzekome dane i był przeszukiwany przez skaner
        powtórzeń jak treść wiadomości — stąd „znacznik” w tabeli §16.
        """
        token = logika.decode_tokens(
            "https://przyklad.pl/?id=3454bd31-1a2b-4c3d-8e4f-56789abcdef0"
        )[0]
        self.assertIsNone(token.decoded_text)
        self.assertIn("UUID wersja 4", token.note)

    def test_ukryty_blok_z_wieloma_regulami_jest_wykryty(self):
        """„Sześć niezależnych mechanizmów ukrycia naraz — §7 tego nie wykrył."""
        html = (
            '<div style="font-size:1px; line-height:1px; max-height:0px; max-width:0px; '
            'opacity:0.01; overflow:hidden; color:#ffffff">Tekst pomocniczy dla filtrow.</div>'
        )
        hidden = logika.find_hidden_elements(html)
        self.assertEqual(len(hidden), 1)
        self.assertEqual(hidden[0].text, "Tekst pomocniczy dla filtrow.")
        self.assertEqual(hidden[0].kind, "ukrywające")
        # Cztery reguły działające niezależnie od tła. `color:#ffffff` celowo nie
        # jest tu liczone — o widoczności białego tekstu decyduje tło.
        self.assertEqual(
            sorted(hidden[0].rules),
            ["font-size:1px", "max-height:0px", "max-width:0px", "opacity:0.01"],
        )

    def test_bialy_tekst_na_zadeklarowanym_tle_nie_jest_ukryty(self):
        """„Ten sam element ma background-color:#1965F7 i color:#FFFFFF — w pełni widoczny."

        Defekt wprowadzony przy poprzedniej poprawce: narzędzie wytwarzało własny
        fałszywy dowód, oznaczając przycisk CTA jako tekst ukryty.
        """
        przycisk = (
            '<div style="background-color:#1965F7;color:#FFFFFF;'
            'padding:12px">Zobacz cennik</div>'
        )
        self.assertEqual(logika.find_hidden_elements(przycisk), [])
        self.assertNotIn("DEKLARACJE", logika.deobfuscate(przycisk))
        self.assertIn("Zobacz cennik", logika.deobfuscate(przycisk))

    def test_krycie_nie_jest_wykluczane_przez_zadeklarowane_tlo(self):
        """„opacity:0.96 to deklaracja wprost wpływająca na widoczność — nie wykryta."

        Element z własnym tłem wypadał z sekcji w całości: `opacity` leżało
        w jednym worku z kolorem tekstu, więc zadeklarowane tło wykluczało oba.
        Krycie działa tak samo na każdym tle, więc tło nie może go wykluczyć.
        """
        przycisk = (
            '<div style="opacity:0.96;background-color:#1965F7;color:#FFFFFF">'
            "Zobacz cennik</div>"
        )
        el = logika.find_hidden_elements(przycisk)[0]
        self.assertEqual(el.rules, ("opacity:0.96",))
        self.assertEqual(el.kind, "kontrast/rozmiar")
        self.assertEqual(el.text, "Zobacz cennik")
        # Sam biały kolor tekstu nadal jest wykluczony przez niebieskie tło.
        self.assertNotIn("color:#FFFFFF", el.rules)

    def test_bialy_tekst_bez_tla_odnotowany_w_osobnej_klasie(self):
        """Fakt zostaje zapisany, ale nie jako dowód ukrycia — tła raport nie ustala."""
        el = logika.find_hidden_elements(
            '<span style="color: white; font-size: 4px">bełkot</span>'
        )[0]
        self.assertEqual(el.kind, "kontrast/rozmiar")
        self.assertIsNone(el.background)

    def test_pusty_element_z_deklaracjami_jest_odnotowany(self):
        """„Zapisano »nie ma«, gdy jest" — pusty <span> z siedmioma deklaracjami."""
        pusty = (
            '<span class="mcnPreviewText" style="display:none; font-size:0px;'
            "line-height:0px; max-height:0px; max-width:0px; opacity:0;"
            'overflow:hidden; visibility:hidden; mso-hide:all;"></span>'
        )
        hidden = logika.find_hidden_elements(pusty)
        self.assertEqual(len(hidden), 1)
        self.assertEqual(hidden[0].text, "")
        self.assertIn("display:none", hidden[0].rules)

    def test_homoglif_kropki_jest_wykryty(self):
        """„U+2024 to homoglif kropki — dokładnie klasa znaków, którą §7 ma wykrywać."""
        found = logika.unusual_characters("gwiazdy telewizji, m․in. dalej")
        self.assertEqual(found[0][0], "U+2024")

    def test_drugi_podpis_dkim_ma_wlasna_domene(self):
        """„Blok 2 wziął listę h= z drugiej sygnatury, ale d/s/bh z pierwszej."""
        raw = build(
            "DKIM-Signature: v=1; d=nadawca.example; s=selektor-a; h=From:Subject; bh=AAAA\n"
            "DKIM-Signature: v=1; d=dostawca.example; s=selektor-b; h=From:Feedback-ID; bh=BBBB"
        )
        msg = message_from_string(raw, policy=policy.default)
        sigs = logika.extract_dkim_signatures(msg)
        self.assertEqual(
            [s.domain for s in sigs], ["nadawca.example", "dostawca.example"]
        )
        self.assertEqual([s.selector for s in sigs], ["selektor-a", "selektor-b"])
        self.assertEqual([s.body_hash for s in sigs], ["AAAA", "BBBB"])

    def test_wartosci_in_reply_to_i_references_sa_podane(self):
        """„§5 mówi tylko »nagłówki obecne«. Nie podaje wartości."""
        raw = build(
            "Subject: Temat\n"
            "In-Reply-To: <watek-1@poczta.example>\n"
            "References: <watek-1@poczta.example>"
        )
        report = analyze(raw)
        self.assertIn("watek-1@poczta.example", report)
        self.assertIn("identyfikatorów w łańcuchu: **1**", report)


class TestBledneKlasyfikacje(unittest.TestCase):
    """Etykieta techniki musi odpowiadać temu, co w pliku faktycznie stoi."""

    def test_warunkowy_komentarz_outlooka_nie_jest_wewnatrz_wyrazu(self):
        """„25 z nich to warunkowe komentarze MSO. Żaden nie rozbija wyrazu."""
        comments = logika.classify_comments(
            "<td><!--[if gte mso 9]><v:rect><![endif]--></td>"
            "<!-- BEGIN TEMPLATE // --><p>tekst</p>"
        )
        kinds = [c.kind for c in comments]
        self.assertIn("warunkowy MSO/Outlook", kinds)
        self.assertIn("znacznik szablonu/generatora", kinds)
        self.assertNotIn("wewnątrz wyrazu", kinds)

    def test_span_w_komorce_ukladu_nie_rozbija_wyrazu(self):
        """„Wszystkie trzy to <td> <span></span> </td> — puste komórki siatki układu."""
        self.assertEqual(
            logika.find_word_splitting_spans("<td> <span></span> </td>"), []
        )

    def test_span_faktycznie_rozbijajacy_wyraz_jest_zliczony(self):
        """Przypadek odwrotny — technika, która naprawdę występuje, ma być widoczna."""
        found = logika.find_word_splitting_spans("wia<span></span>domosc")
        self.assertEqual(found, ["wia<span></span>domosc"])

    def test_id_microsoftu_nie_jest_adresem_ip(self):
        """„15.21.339.8 to wartość id, nie adres IP."""
        hop = logika.ReceivedHop.parse(
            "from a.example by b.example with Microsoft SMTP Server id 15.21.339.8", 1
        )
        self.assertIsNone(hop.ip)
        self.assertEqual(hop.queue_id, "15.21.339.8")

    def test_helo_nie_trafia_do_adresow_trasy(self):
        """„127.0.0.1 to wartość HELO podana przez klienta, nie adres węzła trasy."""
        raw = build(
            "Received: from [198.18.7.9] (helo=[127.0.0.1]) by mx.example with ESMTPA; "
            "Mon, 25 Aug 2026 17:43:52 +0000"
        )
        msg = message_from_string(raw, policy=policy.default)
        addresses = logika.collect_net_addresses(msg, logika.extract_hops(msg))
        petla = [a for a in addresses if a.value == "127.0.0.1"]
        self.assertTrue(petla, "adres HELO ma być odnotowany...")
        self.assertIn("HELO", petla[0].role, "...ale z etykietą deklaracji klienta")

    def test_protokol_nie_jest_czytany_z_nawiasu_tls(self):
        """„Regex złapał słowo po pierwszym `with` w (using TLSv1.3 with cipher ...)."""
        hop = logika.ReceivedHop.parse(
            "from a.example (a.example [198.18.7.9]) by b.example "
            "(Postfix) with ESMTPSA id ABC (using TLSv1.3 with cipher TLS_AES_256_GCM_SHA384)",
            1,
        )
        self.assertEqual(hop.protocol, "ESMTPSA")

    def test_rdns_z_nawiasu_jest_zachowany(self):
        """„Zgubiony rDNS vps-...vps.ovh.net — raport podaje samo IP."""
        hop = logika.ReceivedHop.parse(
            "from wysylka.przyklad.pl (host-198-18-7-9.dostawca.example. [198.18.7.9]) "
            "by mx.example with ESMTPS",
            1,
        )
        self.assertEqual(hop.helo, "wysylka.przyklad.pl")
        # Kropka końcowa FQDN zostaje — tabela deklaruje wartości dosłowne.
        self.assertEqual(hop.rdns, "host-198-18-7-9.dostawca.example.")
        self.assertEqual(hop.ip, "198.18.7.9")

    def test_adres_wewnetrzny_6to4_nie_stoi_obok_publicznego(self):
        """„Wewnętrzny identyfikator Google zrównany w liście z realnymi adresami."""
        raw = build(
            "Received: by 2002:a05:7109:c30a:b0:579:5199:ff53 with SMTP id x\n"
            "Received: from a.example (a.example [93.184.216.34]) by mx.example with ESMTPS"
        )
        msg = message_from_string(raw, policy=policy.default)
        addresses = logika.collect_net_addresses(msg, logika.extract_hops(msg))
        kategorie = {a.value: a.category for a in addresses}
        self.assertEqual(kategorie["93.184.216.34"], "publiczny")
        self.assertIn("6to4", kategorie["2002:a05:7109:c30a:b0:579:5199:ff53"])

    def test_adresy_exchange_w_nawiasie_bez_kwadratowych(self):
        """„Rzeczywiste adresy tego skoku: 2603:… (from) → 2603:… (by) — raport ich nie podaje."""
        hop = logika.ReceivedHop.parse(
            "from HOST1.example (2603:10a6:800:334::7) by HOST2.example "
            "(2603:10a6:20b:3e8::23) with Microsoft SMTP Server id 15.21.339.8",
            1,
        )
        self.assertEqual(hop.ip, "2603:10a6:800:334::7")
        self.assertEqual(hop.by_ip, "2603:10a6:20b:3e8::23")
        self.assertEqual(hop.queue_id, "15.21.339.8")

    def test_powtorzone_odwolanie_ma_licznik_wystapien(self):
        """Deduplikacja bez licznika zaniżałaby liczbę znaczników w wiadomości."""
        html = (
            '<a href="https://cel.example/x">raz</a>'
            '<a href="https://cel.example/x">dwa</a>'
            '<a href="https://cel.example/x">trzy</a>'
        )
        resources = logika.extract_html_resources(html)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].occurrences, 3)

    def test_deklaracja_xmlns_nie_jest_linkiem_w_tresci(self):
        """„www.w3.org nie jest linkiem — to deklaracja przestrzeni nazw."""
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>tresc</p></html>'
        self.assertEqual(logika.extract_html_resources(html), [])


class TestZakresIKompletnosc(unittest.TestCase):
    """Zakres analizy musi obejmować to, co w pliku jest — i mówić, czego nie ma."""

    def test_filtry_microsoftu_sa_wykrywane(self):
        """„Skrypt szuka wyłącznie VADE/DCC i pomija filtry Microsoft."""
        raw = build(
            "x-microsoft-antispam: BCL:0;ARA:1\n"
            "x-forefront-antispam-report: CIP:255.255.255.255;SCL:1;SFV:NSPM"
        )
        msg = message_from_string(raw, policy=policy.default)
        names = [n for n, _ in logika.extract_spam_headers(msg)]
        self.assertEqual(names, ["x-microsoft-antispam", "x-forefront-antispam-report"])

    def test_liczniki_dcc_sa_rozlozone(self):
        """„Raport nie dekoduje liczb — to jedyny ślad masowości wysyłki."""
        metrics = dict(
            logika.parse_dcc_metrics(
                "host.dostawca.example 1024; Body=1 Fuz1=1 Fuz2=29281"
            )
        )
        self.assertEqual(metrics, {"Body": 1, "Fuz1": 1, "Fuz2": 29281})

    def test_naglowki_surowe_nie_sa_normalizowane(self):
        """„_naglowki.txt powstaje po normalizacji przez parser, nie z surowych bajtów."

        Wadliwa składnia i kodowanie RFC 2047 muszą przetrwać w artefakcie.
        """
        raw_bytes = (
            b"Reply-To: kontakt@przyklad.pl: kontakt@przyklad.pl;\r\n"
            b"Subject: =?UTF-8?Q?Zapytanie?=\r\n"
            b"Date: Tue, 23 Jun 2026 09:00:02 GMT\r\n\r\nbody"
        )
        block = logika.raw_header_block(raw_bytes)
        self.assertIn("kontakt@przyklad.pl: kontakt@przyklad.pl;", block)
        self.assertIn("=?UTF-8?Q?Zapytanie?=", block)
        self.assertIn("09:00:02 GMT", block)

    def test_znaczniki_czasu_z_podpisow_sa_w_osi(self):
        """„Znacznik podpisu jest tożsamy z Date — raport tego nie zauważa."""
        raw = build(
            "Date: Fri, 07 Aug 2026 15:06:02 +0200\n"
            "DKIM-Signature: v=1; d=przyklad.pl; s=sel; h=From; t=1786107962; bh=AAAA\n"
            "ARC-Seal: i=1; d=odbiorca.example; cv=none; t=1786110148"
        )
        msg = message_from_string(raw, policy=policy.default)
        labels = [label for label, _ in logika.extract_timestamps(msg)]
        self.assertIn("DKIM-Signature t=", labels)
        self.assertIn("ARC-Seal t=", labels)

    def test_niestandardowy_format_daty_nie_jest_przemilczany(self):
        """„Format skoków 1–2 jest niestandardowy — parser go przemilcza."""
        self.assertIsNotNone(
            logika.parse_date_header("Sat, 29 Aug 2026 06:40:50.368 +0000 (UTC)")
        )
        self.assertIsNotNone(
            logika.parse_date_header("2026-08-29 06:40:50.390557031 +0000 UTC")
        )

    def test_arkusz_stylow_nie_trafia_do_tresci(self):
        """„~700 to niezdjęty arkusz <style>. Faktyczny tekst to 15 linii."""
        html = (
            "<style>.mcnBox{padding:0}@media only screen{.x{width:100%}}</style>"
            "<p>Dzien dobry.</p>"
        )
        self.assertEqual(logika.deobfuscate(html), "Dzien dobry.")

    def test_cytat_jest_oddzielony_od_tresci_wlasnej(self):
        """„Treść własna nadawcy to 3 zdania, reszta (~95%) to zacytowane pismo."""
        text = (
            "Dzien dobry.\n\nZglosznie przekazano do dzialu.\n\n"
            "W dniu 17-08-2026 16:59, klient@odbiorca.pl pisze:\n"
            "> dluga tresc wczesniejszego pisma"
        )
        own, quoted = logika.split_quoted(text)
        self.assertIn("Zglosznie przekazano", own)
        self.assertNotIn("dluga tresc", own)
        self.assertTrue(quoted.startswith("W dniu 17-08-2026"))

    def test_wyrownanie_spf_liczone_a_nie_zakladane(self):
        """„SPF pass dotyczy koperty, która nie jest wyrównana z From."""
        alignment = logika.Alignment.compute(
            "nadawca.example", "eu-west-1.dostawca.example", ("nadawca.example",)
        )
        self.assertFalse(alignment.spf_aligned)
        self.assertTrue(alignment.dkim_aligned)

    def test_domeny_zbierane_ze_wszystkich_rol(self):
        """„Pomija msysmt.pl (host MTA), google.com (ARC), matee.net (odbiorca)."""
        raw = build(
            "From: nadawca@marka.example\n"
            "To: klient@odbiorca.example\n"
            "Received: from mta-out.dostawca.example (mta-out.dostawca.example [198.18.7.9]) "
            "by mx.odbiorca.example with ESMTPS\n"
            "ARC-Seal: i=1; d=posrednik.example; cv=none\n"
            "DKIM-Signature: v=1; d=marka.example; s=sel; h=From; bh=AAAA"
        )
        msg = message_from_string(raw, policy=policy.default)
        hops = logika.extract_hops(msg)
        domains = {
            ref.domain
            for ref in logika.collect_domains(
                msg, hops, [], logika.extract_dkim_signatures(msg)
            )
        }
        for oczekiwana in (
            "marka.example",
            "odbiorca.example",
            "mta-out.dostawca.example",
            "mx.odbiorca.example",
            "posrednik.example",
        ):
            self.assertIn(oczekiwana, domains)

    def test_brak_zalacznikow_jest_stwierdzony_wprost(self):
        """„»Brak załączników« jest ustaleniem, nie brakiem ustalenia."""
        raw = build("From: nadawca@przyklad.pl\nContent-Type: text/html", "<p>x</p>")
        report = analyze(raw)
        self.assertIn("Brak załączników", report)
        self.assertIn("Brak części `text/plain`", report)

    def test_brak_reply_to_jest_stwierdzony_wprost(self):
        """„Sekcja pokazuje samo From i nie stwierdza wprost braku."""
        report = analyze(build("From: nadawca@przyklad.pl\nTo: klient@odbiorca.pl"))
        self.assertIn("Brak nagłówka `Reply-To`", report)

    def test_brak_naglowkow_klienta_jest_stwierdzony_wprost(self):
        """„Brak X-Mailer i User-Agent — żaden klient pocztowy ich nie pomija."""
        report = analyze(build("From: nadawca@przyklad.pl"))
        self.assertIn("(nagłówek nieobecny)", report)

    def test_format_boundary_pythona_jest_odnotowany(self):
        """„Boundary to sygnatura biblioteki email Pythona, nie klienta pocztowego."""
        raw = build(
            'Content-Type: multipart/mixed; boundary="===============4403652449191023895=="'
        )
        msg = message_from_string(raw, policy=policy.default)
        keys = [k for k, _ in logika.software_fingerprints(msg, None)]
        self.assertIn("Format boundary", keys)


class TestKorelacjaMiedzySekcjami(unittest.TestCase):
    """Fakty z różnych sekcji muszą być ze sobą zestawione — zarzut rundy 2."""

    def test_identyfikator_kolejki_wiaze_received_z_message_id(self):
        """„Sekcja, której jedynym zadaniem jest znajdowanie powtórzeń, go nie znalazła."""
        raw = build(
            "Message-ID: <20260721113602.3AA011B7B5F@serwer.example>\n"
            "Received: from a.example by b.example with ESMTPA id 3AA011B7B5F; "
            "Tue, 21 Jul 2026 13:36:02 +0200"
        )
        report = analyze(raw)
        sekcja = report.split("## 16.")[1].split("## 17.")[0]
        self.assertIn("3AA011B7B5F", sekcja)

    def test_krotki_identyfikator_naglowka_wiaze_sie_z_tokenem(self):
        """„X-EMAIL-ID: 4494 jest wprost w zdekodowanym payloadzie linku."""
        zrodla = {"X-EMAIL-ID": "4494", "token": 'a:5:{s:5:"email";i:4494;}'}
        wynik = logika.repeated_identifiers(zrodla, seeds=("4494",))
        self.assertEqual(wynik, [("4494", ["X-EMAIL-ID", "token"])])

    def test_message_id_z_timestampem_jest_rozlozony(self):
        """„Raport rozbija Message-ID na dwie części i nie dekoduje żadnej z nich."""
        czesci = logika.message_id_parts("<20260721113602.3AA011B7B5F@serwer.example>")
        self.assertEqual(czesci[0][0], "znacznik czasu YYYYMMDDHHMMSS")
        self.assertIn("2026-07-21 11:36:02", czesci[0][1])

    def test_rfc8058_bez_dkim_jest_ustaleniem(self):
        """„RFC 8058 wymaga podpisu DKIM nad nagłówkami listy — DKIM nie ma w ogóle."""
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "List-Unsubscribe: <https://przyklad.pl/u>\n"
            "List-Unsubscribe-Post: List-Unsubscribe=One-Click"
        )
        report = analyze(raw)
        self.assertIn("RFC 8058", report)
        self.assertIn("brak podpisu DKIM w wiadomości", report)

    def test_esmtpa_ma_rozwiniecie_normatywne(self):
        """„Sufiks A = wiadomość przyjęta po uwierzytelnieniu SMTP AUTH (RFC 3848)."""
        self.assertIn("SMTP AUTH", logika.describe_protocol("ESMTPA") or "")
        report = analyze(
            build(
                "Received: from a.example by b.example with ESMTPA id X; "
                "Tue, 21 Jul 2026 13:36:02 +0200"
            )
        )
        self.assertIn("SMTP AUTH", report)

    def test_nazwa_hosta_z_pusta_etykieta_jest_odnotowana(self):
        """„DESKTOP-QD51OAL..home — pusta etykieta DNS, nieodnotowana ani razu."""
        hop = logika.ReceivedHop.parse(
            "from DESKTOP-QD51OAL..home by mx.example with ESMTPA", 1
        )
        wynik = logika.invalid_hostnames([hop])
        self.assertEqual(wynik[0][1], "DESKTOP-QD51OAL..home")
        self.assertIn("pusta etykieta", wynik[0][2])

    def test_domena_organizacyjna_uwzglednia_sufiks_dwuczlonowy(self):
        """„Heurystyka dwóch etykiet dała dla sv318.home.net.pl domenę net.pl."""
        self.assertEqual(
            logika.Alignment._organizational("sv318.home.net.pl"), "home.net.pl"
        )
        self.assertEqual(
            logika.Alignment._organizational("cloudserver1-2.home.pl"), "home.pl"
        )

    def test_bh_arc_zestawione_z_bh_dkim(self):
        """„bh= w ARC-Message-Signature jest identyczne z bh= w DKIM-Signature."""
        raw = build(
            "DKIM-Signature: v=1; d=nadawca.example; s=a; h=From; bh=WSPOLNYHASH\n"
            "ARC-Seal: i=1; d=posrednik.example; cv=none\n"
            "ARC-Message-Signature: i=1; d=posrednik.example; s=b; h=From; bh=WSPOLNYHASH"
        )
        report = analyze(raw)
        self.assertIn("jest **identyczny**", report)

    def test_slady_generatora_czerpane_z_tresci(self):
        """„§18.1 i §21 patrzą na te same bajty i dochodzą do sprzecznych wniosków."""
        raw = build(
            "From: nadawca@przyklad.pl\nContent-Type: text/html",
            "<!-- NAME: SELL PRODUCTS --><title>*|MC:SUBJECT|*</title><p>x</p>",
        )
        report = analyze(raw)
        sekcja = report.split("## 21.")[1]
        self.assertIn("SELL PRODUCTS", sekcja)
        # Pipe'y są escape'owane dla tabeli markdown — porównujemy po odescapowaniu.
        self.assertIn("*|MC:SUBJECT|*", sekcja.replace("\\|", "|"))


class TestSzumIFalszyweTrafienia(unittest.TestCase):
    """Wpis w raporcie dowodowym musi być dowodem, a nie artefaktem dekodera."""

    def test_nazwa_pliku_nie_jest_tokenem_base64(self):
        """„openai-logo-email-header-2 dekoduje się do szumu. To artefakt dekodera."""
        self.assertEqual(
            logika.decode_tokens(
                "https://cdn.example/img/openai-logo-email-header-2.png"
            ),
            [],
        )

    def test_camelcase_bez_cyfr_nie_jest_tokenem(self):
        """„Ta sama wada wystąpiła w raporcie klubfitness (ExternalDevices)."""
        self.assertFalse(logika._plausible_opaque_token("ExternalDevices"))
        self.assertEqual(
            logika.decode_tokens("https://a.example/ExternalDevices/Newsletter/x"), []
        )

    def test_realny_token_binarny_nadal_przechodzi(self):
        """Filtr nie może wyciąć identyfikatora, który naprawdę jest tokenem."""
        tokens = logika.decode_tokens("https://a.example/t/kf0LaY8LJ9ceWLx7YbKumw")
        self.assertEqual(len(tokens), 1)

    def test_hex_8_4_4_4_12_bez_wariantu_nie_jest_uuid(self):
        """„Żaden z czterech nie ma wariantu RFC 4122 — cztery jednorodne tokeny, trzy etykiety."""
        for wartosc in (
            "6d0bb530-a3dc-826c-4d83-0b039daab294",
            "df7620c0-09a6-7fea-7188-58299f973a0b",
            "20f8a3e1-8946-3c6a-cc33-02aa989d9547",
        ):
            self.assertEqual(
                logika.describe_uuid(wartosc),
                "hex w formacie 8-4-4-4-12 (pole wariantu spoza RFC 4122 — nie UUID)",
                wartosc,
            )

    def test_poprawny_uuid_nadal_rozpoznany(self):
        """Zaostrzenie nie może gubić prawdziwych UUID-ów."""
        self.assertEqual(
            logika.describe_uuid("9d1821a1-bdae-4c7b-9196-e7f1bf4deebd"),
            "UUID wersja 4",
        )


class TestPelnoscOdczytu(unittest.TestCase):
    """Pola obecne w cytowanym nagłówku muszą trafić do tabeli tego nagłówka."""

    def test_tls_w_formacie_exim(self):
        """„Parser zna tylko format Google — ginie ślad dwóch różnych implementacji MTA."""
        hop = logika.ReceivedHop.parse(
            "from [198.18.7.9] (helo=[127.0.0.1]) by mail.example with esmtpsa "
            "(TLS1.3) tls TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256 id 1wyvBh-005gEL-IN",
            1,
        )
        self.assertIn("TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", hop.tls or "")

    def test_for_bez_nawiasow_katowych(self):
        """„Brakuje pola `for`, które raport sam cytuje trzy linijki wyżej."""
        hop = logika.ReceivedHop.parse(
            "from a.example by mail.example with esmtpsa id X for klient@odbiorca.pl; "
            "Mon, 25 Aug 2026 17:43:53 +0000",
            1,
        )
        self.assertEqual(hop.for_address, "klient@odbiorca.pl")

    def test_adres_z_designates_trafia_do_inwentarza(self):
        """„45.92.16.114 występuje w pliku 4 razy, tabela wykazuje 2."""
        raw = build(
            "Authentication-Results: mx.odbiorca.pl; spf=pass "
            "(odbiorca.pl: domain of a@b.pl designates 93.184.216.34 as permitted sender)"
        )
        msg = message_from_string(raw, policy=policy.default)
        role = [
            a.role
            for a in logika.collect_net_addresses(msg, logika.extract_hops(msg))
            if a.value == "93.184.216.34"
        ]
        self.assertIn("Authentication-Results (designates)", role)

    def test_encje_nazwane_sa_liczone(self):
        """„§18.4 sprawdza wyłącznie encje numeryczne i orzeka ich brak."""
        self.assertEqual(
            logika.named_entities("&hellip;&ndash;&ndash;"),
            [("&ndash;", 2), ("&hellip;", 1)],
        )

    def test_niespojne_kodowanie_tego_samego_znaku(self):
        """„Znak »ó« raz jako UTF-8, dwa razy jako &oacute; — w tym samym dokumencie."""
        wynik = logika.mixed_character_encodings("kt&oacute;ry, ktorego, który")
        self.assertEqual(wynik[0][0], "ó")
        self.assertEqual(wynik[0][1], "&oacute;")

    def test_sklejenie_na_granicy_znacznikow(self):
        """„Detektor pyta o znacznik wewnątrz wyrazu; tu jest granica dwóch znaczników."""
        html = '<span style="color:#000">Twoje uslugi bedą</span><strong>zawieszone</strong>'
        wynik = logika.glued_tag_boundaries(html)
        self.assertEqual(len(wynik), 1)
        self.assertIn("bedą</span><strong>zawieszone", wynik[0])

    def test_brak_struktury_dokumentu_html(self):
        """„<html> — 0, <head> — 0, <body> — 0. Raport nie ma sekcji o strukturze."""
        struktura = dict(
            logika.html_document_structure(
                "<p>&#8203;</p><meta charset='utf-8'><style>p{}</style>"
            )
        )
        self.assertEqual(struktura["<html>"], "brak")
        self.assertEqual(struktura["<body>"], "brak")
        self.assertIn("poza <head>", struktura["<meta> / <style>"])

    def test_naglowki_tranzytowe_sa_wymienione_wprost(self):
        """„Zdanie »nie z listy szablonowej« opisuje coś, czego kod nie robi."""
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "Message-ID: <1@przyklad.pl>\n"
            "Received: from a by b\n"
            "Authentication-Results: mx; spf=pass\n"
            "DKIM-Signature: v=1; d=przyklad.pl; s=s; h=From; bh=AAAA"
        )
        report = analyze(raw)
        self.assertIn("Powód odjęcia", report)
        self.assertIn("dopisane na trasie przez serwery pośredniczące", report)
        # `DKIM-Signature` ma własny powód — nie jest dopisywany na trasie.
        self.assertIn("nagłówek nie podpisuje sam siebie", report)


class TestAtrybutyBezCudzyslowow(unittest.TestCase):
    """Składnia bez cudzysłowów jest legalna — regex jej wymagający gubi dowody."""

    def test_alt_i_title_bez_cudzyslowow(self):
        """„Kolumna »Tekst / alt« = — dla wszystkich 14 wierszy. Każdy IMG ma alt i title."""
        html = "<IMG SRC=cid:5111373001-4 ALT=dell_9020 TITLE=dell_9020 WIDTH=308>"
        zasob = logika.extract_html_resources(html)[0]
        self.assertEqual(zasob.text, "dell_9020")

    def test_klasa_bez_cudzyslowow_jest_liczona(self):
        """„Klasa hiddentds jest użyta 17× na <TR>" — licznik pokazywał 0."""
        html = (
            "<STYLE>@media only screen and (max-width:714px){.hiddentds{display:none}}</STYLE>"
            "<TR class=hiddentds><TR class=hiddentds><TR class=hiddentds>"
        )
        regula = logika.stylesheet_hiding_rules(html)[0]
        selektor, deklaracje, uzycie = (
            regula.selector,
            regula.declarations,
            regula.usage,
        )
        self.assertEqual(
            (selektor, deklaracje, uzycie), (".hiddentds", "display:none", 3)
        )

    def test_zagniezdzone_elementy_nie_sa_pochlaniane(self):
        """„27 znaczników <TD> niesie FONT-SIZE: 0px. Raport pokazuje 9 z 27."

        `finditer` nie zwraca dopasowań nakładających się, więc wzorzec wymagający
        pary `<tag>…</tag>` konsumował komórki zagnieżdżone w tabeli.
        """
        html = (
            "<TABLE>"
            + "".join(
                f'<TD style="FONT-SIZE: 0px"><TABLE><TD style="FONT-SIZE: 0px">{i}</TD></TABLE></TD>'
                for i in range(5)
            )
            + "</TABLE>"
        )
        self.assertEqual(len(logika.find_hidden_elements(html)), 10)

    def test_mailto_z_wieloma_adresatami(self):
        """„Trzecie wystąpienie jest w treści: mailto:a@x.pl,%20b@gmail.com."""
        raw = build(
            "From: nadawca@przyklad.pl\nContent-Type: text/html",
            '<a href="mailto:kontakt@firma.example,%20kopia@poczta.example'
            '?subject=Rezygnacja">rezygnuj</a>',
        )
        report = analyze(raw)
        self.assertIn("poczta.example", report)
        self.assertIn("firma.example", report)

    def test_drugi_return_path_jest_widziany(self):
        """„Pominięty Return-Path #2 — a to on bywa jedynym śladem adresu u źródła."""
        raw = build(
            "Return-Path: <bounce@dostawca.example>\n"
            "Return-Path: nadawca@poczta.example\n"
            "From: nadawca@poczta.example"
        )
        msg = message_from_string(raw, policy=policy.default)
        zrodla = eml_forensics.collect_identifier_sources(msg, [], [], [])
        self.assertIn("Return-Path #1", zrodla)
        self.assertIn("Return-Path #2", zrodla)

    def test_identyczne_zalaczniki_sa_zliczone(self):
        """„5 z 14 załączników jest bajtowo identycznych — raport nie robi dedupu."""
        czesci = "".join(
            f"--b\nContent-Type: image/png\nContent-Disposition: inline; "
            f'filename="{i}.png"\nContent-Transfer-Encoding: base64\n\nQUJD\n'
            for i in (1, 2, 3)
        )
        raw = 'Content-Type: multipart/mixed; boundary="b"\n\n' + czesci + "--b--\n"
        report = analyze(raw)
        self.assertIn("bajtowo identyczne", report)
        self.assertIn("unikalnych: **1**", report)

    def test_rozwiniecie_protokolu_nie_wnioskuje_z_nieobecnosci(self):
        """„»ESMTP bez TLS« to wnioskowanie z nieobecności znacznika, nie zapis w pliku."""
        opis = logika.describe_protocol("ESMTP") or ""
        self.assertIn("bez sufiksów", opis)
        self.assertNotIn("bez TLS i bez uwierzytelnienia", opis)


class TestRundaTrzecia(unittest.TestCase):
    """Defekty wykryte przez review poprawionego już skryptu."""

    def test_czas_lokalny_zima_to_cet(self):
        """„Zahardkodowany offset +2 psuje każdą wiadomość z okresu zimowego."

        Najcięższy błąd rundy 3 — dotyczył całego korpusu, nie jednego pliku.
        """
        zima = datetime.datetime(2025, 12, 2, 8, 29, 38, tzinfo=datetime.timezone.utc)
        self.assertIn("09:29:38 CET", raport.format_local(zima))
        lato = datetime.datetime(2026, 8, 20, 12, 8, 26, tzinfo=datetime.timezone.utc)
        self.assertIn("14:08:26 CEST", raport.format_local(lato))

    def test_piksel_z_wymiarami_w_css(self):
        """„Piksel 1px wpada w lukę między dwoma detektorami."""
        html = '<img src="https://t.example/x" alt="" style="width:1px;height:1px;"/>'
        self.assertTrue(logika.extract_html_resources(html)[0].is_pixel)

    def test_border_color_nie_jest_colourem_tekstu(self):
        """„Parser łapie po podciągu `color:` — w pliku są 2 takie border-top-color."""
        html = (
            '<table style="min-width:100%;border-top-width:2px;'
            'border-top-color: #FFFFFF;">tresc</table>'
        )
        self.assertEqual(logika.find_hidden_elements(html), [])

    def test_identyfikator_w_in_reply_to_i_references(self):
        """„Identyfikator występuje w dwóch nagłówkach — raport orzeka brak powtórzeń."""
        raw = build(
            "In-Reply-To: <20251201232301.d9c02c6ebd588842@poczta.example>\n"
            "References: <20251201232301.d9c02c6ebd588842@poczta.example>"
        )
        report = analyze(raw)
        sekcja = report.split("## 16.")[1].split("## 17.")[0]
        self.assertIn("d9c02c6ebd588842", sekcja)

    def test_znacznik_czasu_z_in_reply_to_w_osi(self):
        """„Oś czasu ma jeden wiersz zamiast dwóch i nie podaje odstępu 10 h 06 min."""
        raw = build(
            "Date: Tue, 2 Dec 2025 09:29:38 +0100\n"
            "In-Reply-To: <20251201232301.d9c02c6ebd588842@poczta.example>"
        )
        msg = message_from_string(raw, policy=policy.default)
        etykiety = [label for label, _ in logika.extract_timestamps(msg)]
        self.assertIn("Date", etykiety)
        self.assertTrue(any("In-Reply-To" in e for e in etykiety))

    def test_hex_w_naglowku_jest_dekodowany(self):
        """„Ścieżka hex istnieje w kodzie tylko dla treści, nie dla nagłówków."""
        raw = build("In-Reply-To: <20251201232301.d9c02c6ebd588842@poczta.example>")
        msg = message_from_string(raw, policy=policy.default)
        surowe = [t.raw for t in logika.decode_header_tokens(msg)]
        self.assertIn("d9c02c6ebd588842", surowe)

    def test_cudzyslow_atrybutu_nie_jest_znakiem_tresci(self):
        """„Jedyne dosłowne cudzysłowy to ograniczniki atrybutu w <div dir=»ltr«>."""
        self.assertEqual(
            logika.mixed_character_encodings('<div dir="ltr">&quot;cytat&quot;</div>'),
            [],
        )

    def test_url_w_nawiasie_kwadratowym_nie_tworzy_roznicy(self):
        """„Obie pozycje mają doklejony ] z notacji [https://…] z wersji tekstowej."""
        wynik = logika.compare_parts(
            '<a href="https://cel.example/u/K1">wypisz</a>',
            "wypisz [https://cel.example/u/K1]",
        )
        self.assertEqual(wynik["urls_only_in_html"], [])
        self.assertEqual(wynik["urls_only_in_text"], [])

    def test_uuid_zle_pole_wersji_a_nie_wariantu(self):
        """„Wariant to 8 = poprawny RFC 4122. Niepoprawne jest pole wersji (c)."""
        opis = logika.describe_uuid("7d20815d-6c66-c3e1-8e55-3896f9864c45") or ""
        self.assertIn("pole wersji", opis)
        self.assertNotIn("pole wariantu spoza", opis)

    def test_hex_nieparzystej_dlugosci_jest_odnotowany(self):
        """„25-znakowy identyfikator konta u dostawcy CDN pomijany przez próg parzystości."""
        tokeny = logika.decode_tokens(
            "https://cdn.example/dd62059d0971e97035204927b/images/x.png"
        )
        self.assertEqual(tokeny[0].raw, "dd62059d0971e97035204927b")
        self.assertIn("25 znaków", tokeny[0].encoding)

    def test_wszystkie_znaczniki_merge(self):
        """„Raport podaje *|MC:SUBJECT|*. W pliku są też *|IF:…|* i *|END:IF|*."""
        raw = build("From: nadawca@przyklad.pl\nContent-Type: text/html")
        msg = message_from_string(raw, policy=policy.default)
        tresc = "<title>*|MC:SUBJECT|*</title><!--*|IF:MC_PREVIEW_TEXT|*--><!--*|END:IF|*-->"
        wartosci = [
            v
            for k, v in logika.software_fingerprints(msg, tresc)
            if k == "Niepodstawiony znacznik merge"
        ]
        self.assertEqual(
            wartosci, ["*|MC:SUBJECT|*, *|IF:MC_PREVIEW_TEXT|*, *|END:IF|*"]
        )

    def test_zakonczenia_linii_sa_odnotowane(self):
        """„Cały plik ma CRLF, spójnie — fakt tani do zebrania, nieodnotowany."""
        self.assertIn("CRLF", logika.line_endings(b"a\r\nb\r\n"))
        report = analyze(build("From: nadawca@przyklad.pl"))
        self.assertIn("Zakończenia linii", report)

    def test_inwentarz_naglowkow(self):
        """„Wiadomość ma 25 nagłówków. Żadna sekcja ich nie wylicza."""
        report = analyze(build("From: a@b.pl\nTo: c@d.pl\nSubject: x"))
        self.assertIn("Nagłówków w pliku: **3**", report)

    def test_rozmiar_czesci_to_bajty_zdekodowane_z_crlf(self):
        """Rozmiar części = bajty po zdekodowaniu, z CRLF jak w pliku.

        Review liczyło 1220 zamiast 1253, bo normalizowało CRLF→LF. Zapisany
        artefakt ma te same bajty co część, więc obie liczby muszą się zgadzać —
        etykieta w raporcie mówi teraz wprost, czego dotyczą.
        """
        raw = (
            "Content-Type: text/plain; charset=utf-8\r\n"
            "Content-Transfer-Encoding: quoted-printable\r\n\r\n"
            "linia1\r\nlinia2\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wiadomosc.eml"
            path.write_bytes(raw.encode("utf-8"))
            eml_forensics.build_report(path, Path(tmp))
            czesc = (Path(tmp) / "wiadomosc_tresc.txt").read_bytes()
        self.assertEqual(len(czesc), 16)
        self.assertEqual(czesc.count(b"\r\n"), 2)

    def test_fragment_url_w_naglowku_nie_jest_tokenem(self):
        """„//googlerecenzja to wycięty kawałek stringa https://googlerecenzja.pl."

        Detektor wpisywał składnię URL-a do tabeli dowodowej obok prawdziwego tokenu.
        """
        raw = build(
            "List-Unsubscribe: <https://cel.example/wypis?unsubscribe=YWJjZGVmZ2hpams=>"
        )
        msg = message_from_string(raw, policy=policy.default)
        surowe = [t.raw for t in logika.decode_header_tokens(msg)]
        self.assertEqual(surowe, ["YWJjZGVmZ2hpams="])
        self.assertNotIn("//cel", " ".join(surowe))

    def test_verp_nie_jest_base64(self):
        """„Ciąg zawiera + (spoza base64url) i _ (spoza base64) — to VERP, nie base64."""
        self.assertEqual(
            logika._try_base64("newsletter+bounce_6a75d83a7b8c0129001949"), (None, "")
        )

    def test_sha256_opisuje_zdekodowane_bajty(self):
        """„sha256(31 zdekodowanych bajtów) ≠ sha256(surowego tokenu ASCII)."""
        import hashlib

        token = logika.decode_tokens("https://a.example/r?t=YWJjZGVmZ2hpams=")[0]
        oczekiwany = hashlib.sha256(b"abcdefghijk").hexdigest()[:12]
        self.assertEqual(token.sha256_prefix, oczekiwany)

    def test_hex_nieparzysty_nie_udaje_zera_bajtow(self):
        """„Raport pisze »dane binarne, 0 B« i podaje niepusty SHA-256."""
        token = logika.decode_tokens(
            "https://cdn.example/dd62059d0971e97035204927b/x.png"
        )[0]
        self.assertIn("długość nieparzysta", token.encoding)

    def test_pusty_alt_odrozniony_od_braku(self):
        """„— miesza brak atrybutu z atrybutem pustym; te stany są rozróżnialne."""
        z_pustym = logika.extract_html_resources(
            '<img src="https://a.example/x" alt="">'
        )[0]
        bez = logika.extract_html_resources('<img src="https://a.example/y">')[0]
        self.assertIn("wartość pusta", raport._label_or_absent(z_pustym))
        self.assertEqual(raport._label_or_absent(bez), "brak atrybutu")


class TestRundaCzwarta(unittest.TestCase):
    """Defekty z kompletu 16 ocen wygenerowanych przeciw kodowi po rundzie 3."""

    def test_data_bez_godziny_nie_jest_punktem_osi(self):
        """„X-SES-Outgoing nie zawiera godziny. Raport dopisał północ."

        Skutek: „rozpiętość osi 15 h 7 min” tam, gdzie realne znaczniki mieszczą
        się w jednej sekundzie — błąd rzędu 50 000×, w czterech plikach.
        """
        raw = build(
            "Date: Tue, 17 Mar 2026 15:07:33 +0000\nX-SES-Outgoing: 2026.03.17-23.249.218.110"
        )
        msg = message_from_string(raw, policy=policy.default)
        etykiety = [label for label, _ in logika.extract_timestamps(msg)]
        self.assertEqual(etykiety, ["Date"])

    def test_ten_sam_identyfikator_to_jeden_punkt_osi(self):
        """„In-Reply-To i References zawierają ten sam Message-ID — odstęp 0 s to artefakt."""
        raw = build(
            "In-Reply-To: <20251201232301.d9c02c6ebd588842@poczta.example>\n"
            "References: <20251201232301.d9c02c6ebd588842@poczta.example>"
        )
        msg = message_from_string(raw, policy=policy.default)
        self.assertEqual(len(logika.extract_timestamps(msg)), 1)

    def test_wariant_wielkosci_liter_naglowka_nie_dubluje_osi(self):
        """„W pliku jest jeden taki nagłówek — raport wymienia dwa źródła."""
        raw = build(
            "x-ms-exchange-crosstenant-originalarrivaltime: 19 Aug 2026 10:40:33.5094 (UTC)"
        )
        msg = message_from_string(raw, policy=policy.default)
        self.assertEqual(len(logika.extract_timestamps(msg)), 1)

    def test_ksztalty_ktore_nie_sa_base64(self):
        """„Smart_Send_3_1_6 dekoduje się do szumu, a raport podaje jego sha256."""
        for wartosc, opis in (
            ("E1wzgyG-00000002Ly9-309c", "identyfikator kolejki Exima"),
            ("Smart_Send_3_1_6", "nazwa i wersja programu"),
            ("RZEM_tot_wzn19", "nazwa kampanii"),
        ):
            self.assertEqual(logika.falszywy_ksztalt(wartosc), opis, wartosc)
        self.assertEqual(
            logika.decode_tokens("https://a.example/r?id=Smart_Send_3_1_6"), []
        )

    def test_licznik_dziesietny_nie_jest_hexem(self):
        """„7363754514882711723180 to licznik dziesiętny, nie hex (11 B)."""
        self.assertEqual(
            logika.decode_tokens("https://a.example/7363754514882711723180/x"), []
        )

    def test_tlo_z_bloku_style_rozstrzyga_kontrast(self):
        """„#templateFooter{background-color:#000000} — biały tekst na czarnej stopce."""
        html = (
            "<style>#templateFooter{background-color:#000000}</style>"
            '<td id="templateFooter" style="color:#FFFFFF">Firma sp. z o.o.</td>'
        )
        self.assertEqual(logika.find_hidden_elements(html), [])

    def test_beacon_jako_tlo_css_jest_zasobem(self):
        """„Element z width:1px;height:1px i obrazem w tle nie pojawia się w żadnej sekcji."""
        html = (
            '<div style="width:1px;height:1px;border-width:0;'
            'background:url(http://tracker.example/track/o/1/3/X)"></div>'
        )
        beacony = [
            r for r in logika.extract_html_resources(html) if r.kind == "beacon-css"
        ]
        self.assertEqual(len(beacony), 1)
        self.assertEqual(beacony[0].host, "tracker.example")

    def test_selektor_wariantu_emoji_jest_wykryty(self):
        """„U+FE0F ma kategorię Mn, nie Cf — filtr go przepuszczał."""
        kody = [kod for kod, _, _, _ in logika.unusual_characters("uwaga \u26a0\ufe0f")]
        self.assertIn("U+FE0F", kody)

    def test_tytul_i_jezyk_dokumentu(self):
        """„<title> nie występuje w raporcie ani razu" / „lang — 0 wystąpień."""
        meta = dict(
            logika.document_metadata(
                '<title>Kod weryfikacyjny</title><html lang="en"><p>Treść</p></html>'
            )
        )
        self.assertEqual(meta["<title>"], "Kod weryfikacyjny")
        self.assertEqual(meta["lang w <html>"], "en")

    def test_cudzyslow_nie_wchodzi_do_domeny_spf(self):
        """„Raport drukuje wniosek koperta.pl" ≠ nadawca.pl — z cudzysłowem."""
        metody = logika.AuthMethod.parse_all(
            'spf=pass (a.pl: autoryzacja) smtp.mailfrom="nadawca@koperta.pl"'
        )
        self.assertEqual(metody[0].props["smtp.mailfrom"], "nadawca@koperta.pl")

    def test_dkim_signature_nie_jest_naglowkiem_tranzytowym(self):
        """„DKIM-Signature tworzy nadawca, nie pośrednik — uzasadnienie nieprawdziwe."""
        raw = build(
            "From: a@b.pl\nX-VADE-SPAMSTATE: clean\n"
            "DKIM-Signature: v=1; d=b.pl; s=s; h=From; bh=AAAA"
        )
        report = analyze(raw)
        self.assertNotIn("dopisane na trasie po podpisaniu", report.split("## 7.")[0])

    def test_oversigning_jest_odnotowany(self):
        """„h= zawiera 13 nagłówków, których w wiadomości nie ma — technika celowa."""
        raw = build("From: a@b.pl\nSubject: x")
        msg = message_from_string(raw, policy=policy.default)
        self.assertEqual(
            logika.oversigned_headers(msg, ("From", "Subject", "Sender", "List-Id")),
            ["Sender", "List-Id"],
        )

    def test_ampersand_encji_nie_jest_znakiem_wprost(self):
        """„40 znaków & i wszystkie 40 otwierają encję. Gołych ampersandów: 0."""
        self.assertEqual(
            logika.mixed_character_encodings("&nbsp;&oacute;&raquo;tekst"), []
        )

    def test_kropka_konczaca_fqdn_zostaje(self):
        """„W pliku rDNS to cloudserver….home.pl. — tabela deklaruje dosłowność i gubi kropkę."""
        hop = logika.ReceivedHop.parse(
            "from a.example (host.przyklad.pl. [93.184.216.34]) by mx.example with ESMTPS",
            1,
        )
        self.assertEqual(hop.rdns, "host.przyklad.pl.")

    def test_domena_organizacyjna_grupuje_hosty_operatora(self):
        """„net.pl to sufiks publiczny, nie domena nadrzędna."""
        self.assertEqual(
            logika.Alignment._organizational("smtp2-1638.dostawca.net.pl"),
            "dostawca.net.pl",
        )

    def test_numeracja_podsekcji_bez_dziur(self):
        """„Numeracja skacze 19.1 → 19.3; dziura sama generuje pytanie »co wycięto«."""
        import re as _re

        report = analyze(
            build(
                "From: a@b.pl\nContent-Type: text/html",
                '<div style="display:none">ukryte</div><p>widoczne</p>',
            )
        )
        pod = [int(m) for m in _re.findall(r"^### 19\.(\d+)\. ", report, _re.MULTILINE)]
        self.assertEqual(pod, list(range(1, len(pod) + 1)))


class TestRundaPiata(unittest.TestCase):
    """Defekty z kompletu 16 ocen wygenerowanych przeciw kodowi po rundzie 4."""

    def test_licznik_znakow_niebialych_dziala(self):
        """„Treść liczy 730 znaków, w tym 730 niebędących białymi" — niemożliwe.

        Przyczyna: `re.sub(r"\\s", ...)` dopasowywało literalny backslash z `s`,
        nie biały znak. Błąd w 6 z 16 raportów.
        """
        report = analyze(
            build(
                "From: a@b.pl\nContent-Type: text/html",
                "<p>ala ma kota</p><p>i psa</p>",
            )
        )
        liczby = re.search(
            r"Treść liczy \*\*(\d+)\*\* znaków, w tym \*\*(\d+)\*\*", report
        )
        self.assertIsNotNone(liczby)
        self.assertLess(int(liczby.group(2)), int(liczby.group(1)))

    def test_komentarz_arc_nie_tworzy_fantomowych_wynikow(self):
        """„dkdomain=, spfdomain= pochodzą z wnętrza komentarza — 6 dodatkowych wierszy."""
        metody = logika.AuthMethod.parse_all(
            "arc=pass (i=1 spf=pass spfdomain=a.pl dkim=pass dkdomain=b.pl "
            "dmarc=pass fromdomain=c.pl)"
        )
        self.assertEqual([m.method for m in metody], ["arc"])

    def test_wystawca_tylko_gdy_wyglada_jak_host(self):
        """„dkim=none (message not signed) header.d=none wzięte za wystawcę."""
        naglowek = logika.AuthHeader(
            "Authentication-Results", 1, "dkim=none (message not signed) header.d=none"
        )
        self.assertIsNone(naglowek.authserv_id)
        self.assertEqual(
            logika.AuthHeader(
                "Authentication-Results", 1, "mx.a.pl; dkim=pass"
            ).authserv_id,
            "mx.a.pl",
        )

    def test_spacja_miedzy_znacznikami_to_nie_sklejenie(self):
        """„Dowód to 630041</strong> <strong>17, gdzie spacja JEST."""
        self.assertEqual(
            logika.glued_tag_boundaries("<strong>630041</strong> <strong>17</strong>"),
            [],
        )
        self.assertEqual(
            len(
                logika.glued_tag_boundaries(
                    "<span>bedą</span><strong>zawieszone</strong>"
                )
            ),
            1,
        )

    def test_kanal_alfa_w_colourze_jest_wykryty(self):
        """„#00000050 = czerń z kryciem 31% → renderuje się jako jasna szarość."""
        self.assertEqual(
            logika._low_contrast_rules("font-size:10px;color:#00000050"),
            ["color:#00000050"],
        )
        self.assertEqual(logika._low_contrast_rules("color:#000000"), [])

    def test_bialy_tekst_na_bialym_body_jest_ukryciem(self):
        """„body{background-color:#ffffff} + color:#ffffff — biały na białym."

        Sama obecność tła nie może wykluczać ustalenia; wyklucza je dopiero
        tło RÓŻNE od koloru tekstu.
        """
        html = (
            "<style>body{background-color:#ffffff}</style>"
            '<div style="color:#ffffff;font-size:1px">tekst pomocniczy</div>'
        )
        el = logika.find_hidden_elements(html)[0]
        self.assertEqual(el.kind, "ukrywające")
        self.assertIn("kolor tekstu identyczny z tłem (#ffffff)", el.rules)

    def test_myslnik_to_typografia_nie_homoglif(self):
        """„U+2014 → »wygląda jak -« ustawia polską typografię jako ryzyko."""
        wynik = logika.unusual_characters("słowo \u2014 drugie")
        self.assertEqual(wynik[0][0], "U+2014")
        self.assertIn("typografia", wynik[0][3])
        self.assertNotIn("wygląda jak", wynik[0][3])

    def test_wielokropek_i_strzalka_sa_liczone(self):
        """„Tabela pomija U+2026 (3×), U+2192, U+00AE."""
        kody = [k for k, _, _, _ in logika.unusual_characters("a\u2026b\u2192c\u00aed")]
        for oczekiwany in ("U+00AE", "U+2026", "U+2192"):
            self.assertIn(oczekiwany, kody)

    def test_indeks_strefy_adresu_zostaje(self):
        """„W pliku jest fe80::…%5 — raport uciął indeks strefy."""
        hop = logika.ReceivedHop.parse(
            "from a.example (host.example [fe80::7c4f:2705:e5e5:c03e%5]) by b.example",
            1,
        )
        self.assertEqual(hop.ip, "fe80::7c4f:2705:e5e5:c03e%5")

    def test_encje_liczone_w_kazdej_czesci_osobno(self):
        """„Zestawienie 6 encja / 6 wprost sugeruje mieszany zapis, którego nie ma."

        Poprzednia wersja porównywała OBIE części łącznie. To dawało wynik
        gwarantowany: `&nbsp;` w `text/html` i literalny U+00A0 w `text/plain`
        wychodzą zawsze przy `multipart/alternative`, bo w części tekstowej
        encje HTML nie mają znaczenia. Pokrycie w obrębie części wynosi zero,
        więc ustalenia nie ma.
        """
        raw = (
            'Content-Type: multipart/alternative; boundary="b"\n\n'
            "--b\nContent-Type: text/plain\n\ntekst\u00a0z\u00a0nbsp\n"
            "--b\nContent-Type: text/html\n\n<p>tekst&nbsp;z&nbsp;encja</p>\n--b--\n"
        )
        report = analyze(raw)
        self.assertNotIn("obie części MIME łącznie", report)
        self.assertIn(
            "Żaden znak nie występuje jednocześnie jako encja i wprost", report
        )

    def test_encje_numeryczne_sa_porownywane_z_zapisem_wprost(self):
        """„Wszystkie 6 znaków kodowanych encją występuje też dosłownie."

        Detektor sprawdzał wyłącznie encje **nazwane**, więc dla wiadomości
        rozbijającej wyrazy encjami numerycznymi (`Maj&#99;hrowicz` — jedno `c`
        encją, drugie wprost, w tym samym wyrazie) drukował ustalenie negatywne
        odwracające wymowę sekcji.
        """
        raw = build(
            "Content-Type: text/html",
            "<p>Maj&#99;hrowicz podpisal dokum&#101;nt, tekst c e</p>",
        )
        report = analyze(raw)
        self.assertIn("dwoma sposobami naraz", report)
        self.assertIn("&#99;", report)
        self.assertIn("&#101;", report)

    def test_procent_cytatu_z_podanych_skladnikow(self):
        """„11955/(1003+11955) = 92,3%, raport podaje 91% z innego mianownika."""
        raw = build(
            "From: a@b.pl",
            "Moja tresc.\n\nW dniu 17-08-2026 16:59, x@y.pl pisze:\n> " + "cytat " * 50,
        )
        report = analyze(raw)
        m = re.search(
            r"własna nadawcy: \*\*(\d+)\*\* znaków.*?"
            r"korespondencji: \*\*(\d+)\*\* znaków \(\*\*(\d+)%\*\*",
            report,
            re.DOTALL,
        )
        self.assertIsNotNone(m)
        wlasna, cytat, procent = (int(m.group(i)) for i in (1, 2, 3))
        self.assertEqual(procent, 100 * cytat // (wlasna + cytat))


class TestJakoscRaportu(unittest.TestCase):
    """Raport ma się renderować i nie zawierać ocen."""

    def test_tabele_nie_maja_pustych_linii_w_srodku(self):
        """„Pusta linia po wierszu nagłówkowym łamie tabelę Markdown."""
        lines: list[str] = []
        raport.write_table(lines.append, ["A", "B"], [["1", "2"]])
        self.assertEqual(lines[:3], ["| A | B |", "|---|---|", "| 1 | 2 |"])

    def test_odstepy_czasu_maja_jednostki_czytelne(self):
        """„Raport podaje suchą liczbę 20278s, bez jednostki czytelnej."""
        self.assertEqual(raport.format_duration(20278), "5 h 37 min 58 s (20278 s)")

    def test_raport_nie_orzeka_o_uwierzytelnieniu_wysylki(self):
        """„Wniosek szerszy niż dowód: »Wysyłka jest uwierzytelniona przez domenę«."""
        raw = build(
            "From: nadawca@przyklad.pl\n"
            "Authentication-Results: mx.odbiorca.pl; dkim=pass; spf=pass"
        )
        report = analyze(raw)
        self.assertNotIn("Wysyłka jest uwierzytelniona", report)
        self.assertNotIn("wyszła z infrastruktury autoryzowanej", report)

    def test_raport_nie_zawiera_zalecen(self):
        """Raport zbiera dowód; co z nim zrobić, decyduje czytelnik."""
        report = analyze(
            build("From: nadawca@przyklad.pl", '<a href="https://x.example">a</a>')
        )
        self.assertNotIn("Sprawdź WHOIS", report)
        self.assertNotIn("mogą utrudniać", report)

    def test_numeracja_sekcji_jest_ciagla(self):
        """„Brakuje §3.1, §3.6 przy obecnych §3.2–3.8 — utrudnia powoływanie się."""
        import re

        report = analyze(build("From: nadawca@przyklad.pl", "<p>x</p>"))
        numbers = [int(m) for m in re.findall(r"^## (\d+)\. ", report, re.MULTILINE)]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_kazda_sekcja_konczy_sie_ustaleniem(self):
        """Pusta sekcja bez treści to luka; ma być stwierdzenie negatywne."""
        report = analyze(build("From: nadawca@przyklad.pl", "goly tekst"))
        sekcje = report.split("\n## ")[1:]
        for sekcja in sekcje:
            tytul = sekcja.splitlines()[0]
            tresc = "\n".join(sekcja.splitlines()[1:]).strip()
            self.assertTrue(tresc, f"sekcja „{tytul}” jest pusta")


class TestRundaSzosta(unittest.TestCase):
    """Zarzuty z szóstej rundy recenzji — po jednym teście na defekt."""

    def test_media_query_nie_jest_regula_bezwarunkowa(self):
        """„.hiddentds jest w @media, raport podaje regułę jako bezwarunkową."

        Blok responsywny przedstawiony jako reguła usuwająca treść „bez względu
        na kontekst renderowania” to dowód ukrywania, którego plik nie zawiera.
        """
        html = (
            "<style>@media only screen and (max-width:714px)"
            "{.hiddentds{display:none}}</style><td class=hiddentds>x</td>"
        )
        regula = logika.stylesheet_hiding_rules(html)[0]
        self.assertEqual(regula.condition, "@media only screen and (max-width:714px)")
        self.assertFalse(regula.unconditional)
        report = analyze(build("Content-Type: text/html", html))
        self.assertIn("@media only screen and (max-width:714px)", report)
        self.assertNotIn("bez względu na kontekst", report)

    def test_ten_sam_url_to_jeden_pobierany_zasob(self):
        """„Zasobów: 5 przy 3 unikalnych — ten sam URL policzony jako 3 zapisy."

        Sekcja jednocześnie twierdziła, że żadne odwołanie się nie powtarza.
        """
        html = '<div style="width:1px;height:1px;background:url(https://t.example/p.gif)"></div>'
        zasoby = logika.extract_html_resources(html)
        self.assertEqual(len(zasoby), 1)
        self.assertEqual(zasoby[0].kind, "beacon-css")
        self.assertEqual(zasoby[0].also_as, ("css-url",))

    def test_alt_pusty_nie_jest_brakiem_atrybutu_przy_dlugim_url(self):
        """„alt=\"\" jest obecny, raport pisze »brak atrybutu«."

        Przyczyną było obcinanie `attrs` do 200 znaków — przy długim URL-u
        atrybut wypadał za granicę i znikał z raportu.
        """
        dlugi = '<img src="https://t.example/wf/open?upn=' + "x" * 200 + '" alt="" />'
        zasob = logika.extract_html_resources(dlugi)[0]
        self.assertTrue(zasob.alt_present)
        self.assertIn("wartość pusta", raport._label_or_absent(zasob))

    def test_naglowek_bez_roznicy_nie_trafia_do_tabeli_rozbieznosci(self):
        """„Zdanie »wartości różnią się« stoi pod tabelą, gdzie Date jest identyczny."""
        report = analyze(
            build(
                "From: a@przyklad.pl\n"
                "Subject: Zwykly temat\n"
                "Date: Mon, 01 Jun 2026 10:34:21 +0000"
            )
        )
        self.assertIn("Bajty z pliku są identyczne z wynikiem parsera", report)

    def test_ciag_bez_wypelnienia_nie_dostaje_zmyslonych_bajtow(self):
        """„To nie jest base64 — 34 »bajty« i ich sha256 to artefakt."""
        token = logika.decode_tokens(
            "https://przyklad.pl/?q=CAHYL8ScaKb5hjAuJ1yWpYn0xKMwqPnwzX"
        )[0]
        self.assertEqual(token.byte_length, 0)
        self.assertIn("nie ustalono", token.encoding)
        self.assertIn("bez wypełnienia", token.note)

    def test_uuid_nie_jest_ciety_na_cztery_identyfikatory(self):
        """„UUID-y rozbite na kawałki i liczone jako 4 niezależne pozycje."""
        u = "9d1821a1-bdae-4c7b-9196-e7f1bf4deebd"
        wynik = logika.repeated_identifiers(
            {"Message-ID": u, "treść: link": f"https://przyklad.pl/?c={u}"}
        )
        self.assertEqual(len(wynik), 1)
        self.assertEqual(wynik[0][0], u)

    def test_etykieta_domeny_nie_jest_korelatorem(self):
        """„Jako identyfikatory wpisane są fragmenty nazw domen."

        Realnych korelatorów było ~6, tabela miała 27 wierszy.
        """
        wynik = logika.repeated_identifiers(
            {
                "From": "a@newsletter.przyklad.pl",
                "Return-Path": "b@newsletter.przyklad.pl",
            }
        )
        self.assertEqual(wynik, [])

    def test_identyfikator_wtopiony_w_verp_jest_znajdowany(self):
        """„41634 spina kopertę, nagłówki listy i treść — brak go w §16."

        Ciąg jest podciągiem dłuższych tokenów, więc skaner całych słów nie
        widział go ani razu.
        """
        wynik = logika.repeated_identifiers(
            {
                "List-Id": "<41634.z.przyklad.pl>",
                "Return-Path": "sare0416342-klient=odbiorca.pl@z.przyklad.pl",
                "treść: img": "https://41634-2.n.przyklad.pl/so41634_9f.gif",
            },
            substring_seeds=("41634",),
        )
        self.assertEqual(wynik[0][0], "41634")
        self.assertEqual(len(wynik[0][1]), 3)

    def test_przerwa_w_lancuchu_received_jest_ustaleniem(self):
        """„by skoku 2 to AM9PR04MB8274, from skoku 3 to GVXPR05CU001 — brak testu."""
        raw = build(
            "Received: from c.przyklad.pl by mx3.przyklad.pl with ESMTP;"
            " Tue, 11 Aug 2026 10:00:02 +0000\n"
            "Received: from mx1.przyklad.pl by mx2.przyklad.pl with ESMTP;"
            " Tue, 11 Aug 2026 10:00:01 +0000\n"
            "Received: from klient.przyklad.pl by mx1.przyklad.pl with ESMTPA;"
            " Tue, 11 Aug 2026 10:00:00 +0000"
        )
        report = analyze(raw)
        self.assertIn("Ciągłość łańcucha", report)
        self.assertIn("**nie**", report)

    def test_numer_rachunku_jest_dana_a_nie_proza(self):
        """„Numer konta pojawia się wyłącznie jako fragment prozy w zrzucie treści."

        Dla wiadomości wzywającej do przelewu to najpoważniejszy brak. Suma
        kontrolna to obliczenie na danej z pliku, nie ocena wiadomości.
        """
        wynik = logika.registry_identifiers(
            "Wplac na 17 1090 2851 0000 0001 3017 6424, NIP: 836-167-65-10"
        )
        rodzaje = {r for r, _, _ in wynik}
        self.assertIn("NRB (bez kodu kraju)", rodzaje)
        self.assertIn("NIP", rodzaje)
        self.assertTrue(all("poprawna" in status for _, _, status in wynik))

    def test_content_id_ciala_nie_robi_z_niego_zalacznika(self):
        """„Części osadzone (cid:): 1 — a w HTML nie ma ani jednego cid:."

        Exchange nadaje Content-ID samej części text/html. Ciało trafiało do
        tabeli załączników, a zdanie „brak załączników” nie padało nigdzie.
        """
        cialo = logika.MimePart(
            1, "text/html", "utf-8", "base64", None, "<AD8@przyklad.pl>", None, 10, "ab"
        )
        self.assertEqual(logika.extract_attachments([cialo]), [])

    def test_czas_tranzytu_podany_obok_rozpietosci_osi(self):
        """„Rozpiętość 12 h 30 min oparta na x= — realny tranzyt to 8 s, brak go."""
        raw = build(
            "Date: Tue, 11 Aug 2026 10:00:00 +0000\n"
            "DKIM-Signature: d=a.pl; h=From; t=1786528800; x=1786573800\n"
            "Received: from b.pl by mx.pl with ESMTP; Tue, 11 Aug 2026 10:00:08 +0000\n"
            "Received: from a.pl by b.pl with ESMTPA; Tue, 11 Aug 2026 10:00:00 +0000"
        )
        report = analyze(raw)
        self.assertIn("Czas tranzytu", report)
        self.assertIn("pominięciu znaczników wygaśnięcia", report)

    def test_licznik_tresci_odtwarza_sie_z_wydrukowanego_bloku(self):
        """„Przeliczenie bloku daje 726, raport drukuje 730."

        Licznik widział `\r\n`, zapis raportu normalizował je do `\n`.
        """
        raw = (
            "Content-Type: text/html\r\n\r\n"
            "<body>Pierwsza linia<br>\r\nDruga linia<br>\r\nTrzecia</body>"
        )
        report = analyze(raw)
        m = re.search(r"Treść liczy \*\*(\d+)\*\* znaków, w tym \*\*(\d+)\*\*", report)
        self.assertIsNotNone(m)
        blok = re.search(r"```\n(.*?)\n```", report[m.end() :], re.DOTALL).group(1)
        self.assertEqual(int(m.group(1)), len(blok))
        self.assertEqual(int(m.group(2)), len(re.sub(r"\s", "", blok)))

    def test_slady_dostawcy_wysylki_nie_gina(self):
        """„Cztery nagłówki nazywają system wprost, §21 mówi »brak śladów«."""
        raw = build(
            "X-sare: Mail sent by SARE\n"
            "X-sare-abuse: In case of abuse send e-mail to: abuse@przyklad.pl\n"
            "Message-Id: <E1wzgyG-00000002Ly9-309c@mta.przyklad.pl>"
        )
        report = analyze(raw)
        self.assertIn("Mail sent by SARE", report)
        self.assertIn("Exim", report)

    def test_pokrycie_slownictwa_ma_definicje_i_rozwiniecie(self):
        """„Liczba 0.985 bez definicji miary — nie da się jej odtworzyć."""
        raw = (
            'Content-Type: multipart/alternative; boundary="b"\n\n'
            "--b\nContent-Type: text/plain\n\nalfa beta gamma delta\n"
            "--b\nContent-Type: text/html\n\n<p>alfa beta gamma</p>\n--b--\n"
        )
        report = analyze(raw)
        self.assertIn("indeks Jaccarda", report)
        self.assertIn("wyłącznie w jednej części", report)
        self.assertIn("delta", report)


class TestPokrycieSciezekDowodowych(unittest.TestCase):
    """Ścieżki niosące dowód, które nie miały ani jednego testu (pomiar coverage)."""

    def test_rozne_bh_nie_dostaje_wyjasnienia_przyczyny(self):
        """Raport nie policzył żadnego `bh=`, więc nie może podać, skąd różnica."""
        raw = build(
            "From: a@przyklad.pl\n"
            "DKIM-Signature: v=1; d=przyklad.pl; s=s; h=From; c=relaxed/simple; bh=AAA=\n"
            "ARC-Seal: i=1; d=posrednik.example; cv=none; t=1786107962\n"
            "ARC-Message-Signature: i=1; d=posrednik.example; s=t; h=From;"
            " c=relaxed/relaxed; bh=BBB="
        )
        report = analyze(raw)
        self.assertIn("**różni się**", report)
        self.assertIn("nie ustala przyczyny", report)
        self.assertIn("relaxed/simple", report)
        self.assertNotIn("to przez kanonizację", report)

    def test_tekst_kotwicy_wygladajacy_na_adres_jest_zestawiony_z_celem(self):
        """Tekst deklaruje jedną domenę, `href` prowadzi gdzie indziej."""
        raw = build(
            "Content-Type: text/html",
            '<a href="https://cel.example/x?t=1">www.przyklad.pl</a>',
        )
        report = analyze(raw)
        self.assertIn("Kotwice, w których tekst wyświetlany wygląda na adres", report)
        self.assertIn("**nie**", report)

    def test_sklejenia_na_granicy_znacznikow_sa_wypisane(self):
        """Wyraz powstaje ze sklejenia dwóch elementów liniowych bez separatora."""
        raw = build(
            "Content-Type: text/html",
            "<p><span>beda</span><strong>zawieszone</strong></p>",
        )
        report = analyze(raw)
        self.assertIn("ze sklejenia dwóch sąsiednich", report)
        self.assertIn("zawieszone", report)

    def test_odwolania_po_http_sa_wypisane_z_osobna(self):
        """Brak TLS przy pobieraniu zasobu to ustalenie o samym odwołaniu."""
        raw = build("Content-Type: text/html", '<img src="http://cel.example/p.gif">')
        report = analyze(raw)
        self.assertIn("Odwołania po `http://` (bez TLS)", report)
        self.assertIn("http://cel.example/p.gif", report)

    def test_url_obecny_tylko_w_jednej_czesci_jest_nazwany(self):
        """Rozjazd zbiorów URL-i między częściami to odrębne ustalenie."""
        raw = (
            'Content-Type: multipart/alternative; boundary="b"\n\n'
            "--b\nContent-Type: text/plain\n\nbez linku\n"
            "--b\nContent-Type: text/html\n\n"
            '<a href="https://cel.example/tylko-html">x</a>\n--b--\n'
        )
        report = analyze(raw)
        self.assertIn("URL-e obecne wyłącznie w `text/html`", report)
        self.assertIn("https://cel.example/tylko-html", report)

    def test_mieszany_zapis_wykryty_w_samej_czesci_tekstowej(self):
        """Gdy niespójność jest tylko w `text/plain`, zakres ma to nazwać."""
        raw = (
            'Content-Type: multipart/alternative; boundary="b"\n\n'
            "--b\nContent-Type: text/plain\n\nkt&oacute;ry i który\n"
            "--b\nContent-Type: text/html\n\n<p>bez encji</p>\n--b--\n"
        )
        report = analyze(raw)
        self.assertIn("część `text/plain`", report)

    def test_helo_z_adresem_nieroutowalnym_jest_ustaleniem(self):
        """`helo=[127.0.0.1]` — literał w EHLO ma być własnym adresem klienta."""
        raw = build(
            "Received: from klient.example (helo=[127.0.0.1]) by mx.example"
            " with ESMTPSA; Tue, 11 Aug 2026 10:00:00 +0000"
        )
        report = analyze(raw)
        self.assertIn("nieroutowalny", report)

    def test_brak_in_reply_to_i_references_to_dwa_ustalenia(self):
        """Wiadomość niepowiązana z wątkiem — obie nieobecności zapisane."""
        report = analyze(build("From: a@przyklad.pl\nSubject: Bez watku"))
        self.assertIn("Brak nagłówków `In-Reply-To` i `References`", report)

    def test_uuid_spoza_rfc4122_jest_opisany(self):
        """Nibble wersji poza 1–8 to inny fakt niż UUID nieznanej wersji."""
        opis = logika.describe_uuid("3454bd31-1a2b-dc3d-ee4f-56789abcdef0")
        self.assertIsNotNone(opis)
        self.assertIn("spoza RFC 4122", opis)

    def test_adres_z_klauzuli_by_trafia_do_inwentarza(self):
        """Adres hosta przyjmującego jest daną o trasie, nie ozdobą."""
        raw = build(
            "Received: from a.example by mx.example ([203.0.113.9])"
            " with ESMTP; Tue, 11 Aug 2026 10:00:00 +0000"
        )
        report = analyze(raw)
        self.assertIn("203.0.113.9", report)

    def test_client_ip_z_received_spf_trafia_do_inwentarza(self):
        """`client-ip=` bywa jedynym zapisem adresu nadawcy w pliku."""
        raw = build("Received-SPF: pass (przyklad.pl) client-ip=198.51.100.7;")
        report = analyze(raw)
        self.assertIn("198.51.100.7", report)

    def test_epoka_ms_z_x_received_jest_punktem_osi(self):
        """13-cyfrowa epoka w `X-Received` to niezależny znacznik czasu."""
        raw = build("X-Received: by 2002:a05:1 with SMTP id x.1786107962148;")
        report = analyze(raw)
        self.assertIn("X-Received (epoka ms)", report)
        self.assertIn("2026-08-07", report)

    def test_vfill_odwoluje_sie_do_tego_samego_zasobu(self):
        """VML `<v:fill src>` to ten sam zasób co tło CSS, innym zapisem."""
        zasoby = logika.extract_html_resources(
            '<v:fill src="https://cel.example/tlo.png" type="frame"/>'
        )
        self.assertEqual(zasoby[0].url, "https://cel.example/tlo.png")

    def test_title_uzupelnia_tekst_kotwicy_i_obrazu(self):
        """`title` bywa jedynym opisem, gdy tekst i `alt` są puste."""
        a = logika.extract_html_resources(
            '<a href="https://cel.example/x" title="Zobacz ofertę"></a>'
        )[0]
        self.assertIn("Zobacz ofertę", a.text)
        img = logika.extract_html_resources(
            '<img src="https://cel.example/i.png" alt="" title="Logo">'
        )[0]
        self.assertIn("Logo", img.text)

    def test_mta_z_received_jest_sladem_oprogramowania(self):
        """Nazwa MTA bywa jedyną identyfikacją oprogramowania w pliku."""
        raw = build(
            "Received: from a.example by mx.example (Postfix) with ESMTPA;"
            " Tue, 11 Aug 2026 10:00:00 +0000"
        )
        report = analyze(raw)
        self.assertIn("Postfix", report)

    def test_komentarz_generatora_jest_sladem(self):
        """`<!-- Created with ... -->` identyfikuje narzędzie wprost."""
        raw = build("Content-Type: text/html", "<!-- Created with Edytor 2.0 -->x")
        report = analyze(raw)
        self.assertIn("Edytor 2.0", report)

    def test_bledna_suma_kontrolna_iban_jest_ustaleniem(self):
        """Ciąg w kształcie IBAN-u z błędną sumą to inne ustalenie niż brak numeru."""
        wynik = logika.registry_identifiers("Konto: PL17109028510000000130176425")
        self.assertEqual(len(wynik), 1)
        self.assertIn("niepoprawna", wynik[0][2])

    def test_hosty_zasobow_wchodza_do_warstw_tozsamosci(self):
        """Host piksela bywa jedyną warstwą spoza domeny nadawcy."""
        zasob = logika.HtmlResource(
            "img", "https://cel.example/p.gif", None, "https", "cel.example"
        )
        warstwy = dict(
            logika.identity_layers(
                message_from_string("From: a@przyklad.pl\n\nx", policy=policy.default),
                [],
                [zasob],
            )
        )
        self.assertEqual(warstwy["Hosty zasobów pobieranych w treści"], "cel.example")

    def test_cli_konczy_sie_bledem_gdy_brak_pliku(self):
        """Ścieżka CLI też jest kodem — brak pliku ma dawać kontrolowany błąd."""
        import subprocess

        wynik = subprocess.run(
            [sys.executable, str(CLI), "/nie/ma/takiego.eml"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(wynik.returncode, 0)


class TestPokrycieUzupelniajace(unittest.TestCase):
    """Reszta ścieżek bez pokrycia — każda niesie ustalenie o pliku."""

    def test_wiadomosc_bez_czesci_mime(self):
        """Plik bez ciała to też stan do zapisania, nie pusty raport."""
        report = analyze("From: a@przyklad.pl\nSubject: Puste\n\n")
        self.assertIn("## 2.", report)

    def test_kilka_zalacznikow_z_identyczna_trescia(self):
        """Bajtowo identyczne załączniki to fakt o sposobie złożenia wiadomości."""
        czesc = (
            "--b\nContent-Type: image/png\nContent-Transfer-Encoding: base64\n"
            'Content-Disposition: attachment; filename="{}"\n\naGVsbG8=\n'
        )
        raw = (
            'Content-Type: multipart/mixed; boundary="b"\n\n'
            "--b\nContent-Type: text/html\n\n<p>x</p>\n"
            + czesc.format("a.png")
            + czesc.format("b.png")
            + "--b--\n"
        )
        report = analyze(raw)
        self.assertIn("a.png", report)
        self.assertIn("b.png", report)

    def test_wersja_uuid_jest_rozwinieta_w_sekcji_message_id(self):
        """Nibble wersji i wariantu to dane, nie ozdoba identyfikatora."""
        raw = build("Message-ID: <3454bd31-1a2b-4c3d-8e4f-56789abcdef0@przyklad.pl>")
        report = analyze(raw)
        self.assertIn("UUID", report)
        self.assertIn("wersja 4", report)

    def test_url_wylacznie_w_czesci_tekstowej(self):
        """Rozjazd w drugą stronę: adres jest w `text/plain`, nie ma go w HTML."""
        raw = (
            'Content-Type: multipart/alternative; boundary="b"\n\n'
            "--b\nContent-Type: text/plain\n\nhttps://cel.example/tylko-plain\n"
            "--b\nContent-Type: text/html\n\n<p>bez linku</p>\n--b--\n"
        )
        report = analyze(raw)
        self.assertIn("URL-e obecne wyłącznie w `text/plain`", report)

    def test_brak_samego_in_reply_to_przy_obecnym_references(self):
        """Dwa nagłówki wątku są niezależne — nieobecność każdego to osobny fakt."""
        raw = build("References: <a@przyklad.pl>\nSubject: Re: Temat")
        report = analyze(raw)
        self.assertIn("Brak nagłówka `In-Reply-To`", report)

    def test_parametr_sendgrid_jest_odescapowany(self):
        """`-2B`/`-2F`/`-3D` w URL-u to kodowanie dostawcy, nie treść tokenu."""
        tokeny = logika.decode_tokens(
            "https://cel.example/wf/open?upn=YWJjZGVmZ2hpams-3D"
        )
        self.assertTrue(
            any("odescapowaniu" in t.source for t in tokeny),
            [t.source for t in tokeny],
        )

    def test_adres_ipv4_z_dowolnego_naglowka_x(self):
        """`X-CLIENT-IP` bywa jedynym zapisem adresu klienta."""
        report = analyze(build("X-Originating-IP: [198.51.100.7]"))
        self.assertIn("198.51.100.7", report)


class TestOdtwarzalnosc(unittest.TestCase):
    """Raport dowodowy musi być odtwarzalny co do bajtu."""

    def test_raport_nie_zalezy_od_losowania_hashy(self):
        """„Ten sam plik daje raporty o różnej sumie kontrolnej."

        Iteracja po `set` łańcuchów idzie w kolejności zależnej od
        `PYTHONHASHSEED`, więc kolejność wierszy w tabeli identyfikatorów
        zmieniała się między uruchomieniami. Dwie osoby analizujące ten sam
        plik dostawały dokumenty o różnych sumach kontrolnych.
        """
        import subprocess

        raw = build(
            "From: a@przyklad.pl\nReturn-Path: <bounce7f3a91c4@przyklad.pl>\n"
            "List-Unsubscribe: <https://przyklad.pl/u/7f3a91c4/abcdef123456>\n"
            "Message-ID: <abcdef123456@przyklad.pl>\n"
            "Content-Type: text/html",
            '<a href="https://przyklad.pl/r/7f3a91c4/x">t</a>',
        )
        checksums = set()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w.eml"
            path.write_bytes(raw.encode("utf-8"))
            for seed in ("0", "1", "12345", "99991"):
                subprocess.run(
                    [sys.executable, str(CLI), str(path), "--outdir", tmp],
                    capture_output=True,
                    env={**os.environ, "PYTHONHASHSEED": seed},
                    check=True,
                )
                checksums.add((Path(tmp) / "w_analiza.md").read_bytes())
        self.assertEqual(len(checksums), 1, "raport różni się między uruchomieniami")


if __name__ == "__main__":
    unittest.main()
