#!/usr/bin/env python3
"""Unit testy logiki regex z kontrola_pisma.py. Tylko stdlib."""

import unittest
from kontrola_logika import (
    find_placeholders,
    find_attachment_page_headers,
    find_attachment_list_items,
    find_cross_references,
    find_numbering_gaps_and_duplicates,
    titles_match,
    find_paragraph_numbering_issues,
    find_sha256_hashes,
)

SHA = "4f3548f05b0e47d9fa6ddd1e658fb7dee0c2a3c96a479f3c8770e18aeb8bb7e7"
SHA2 = "b298d2c29007f8973da8bd5e29ecd5fcb5932a113ae3e4065f709e2b62143e81"


class TestFindPlaceholders(unittest.TestCase):
    def test_wykrywa_pole(self):
        t = "Wzywa Pan [imię i nazwisko] do zapłaty."
        self.assertEqual(find_placeholders(t), ["[imię i nazwisko]"])

    def test_ignoruje_cytat_z_nawiasem(self):
        t = 'W odpowiedzi na „Re: [Zamówienie 2027]" informuję.'
        self.assertEqual(find_placeholders(t), [])

    def test_ignoruje_date(self):
        self.assertEqual(find_placeholders("Termin: [2026-08-18]"), [])

    def test_ignoruje_liczbe(self):
        self.assertEqual(find_placeholders("Kwota: [123.45]"), [])

    def test_wiele_pol(self):
        t = "[data doręczenia] oraz [numer sprawy]"
        self.assertEqual(find_placeholders(t), ["[data doręczenia]", "[numer sprawy]"])

    def test_brak_pol(self):
        self.assertEqual(find_placeholders("Treść pisma bez pól."), [])

    def test_za_krotkie_pomijane(self):
        self.assertEqual(find_placeholders("[ab]"), [])

    def test_wiele_pol_rownoczesnie(self):
        t = "Pełnomocnik [imię pełnomocnika], nr PESEL [numer PESEL]."
        wynik = find_placeholders(t)
        self.assertIn("[imię pełnomocnika]", wynik)
        self.assertIn("[numer PESEL]", wynik)


class TestFindAttachmentPageHeaders(unittest.TestCase):
    def test_pauza_em(self):
        t = "Załącznik nr 1 — Umowa z dnia 01.01.2026"
        self.assertEqual(
            find_attachment_page_headers(t), [("1", "Umowa z dnia 01.01.2026")]
        )

    def test_myslnik_zwykly(self):
        t = "Załącznik nr 2 - Faktura VAT"
        self.assertEqual(find_attachment_page_headers(t), [("2", "Faktura VAT")])

    def test_pauza_en(self):
        t = "Załącznik nr 3 – Protokół odbioru"
        self.assertEqual(find_attachment_page_headers(t), [("3", "Protokół odbioru")])

    def test_brak(self):
        self.assertEqual(find_attachment_page_headers("Brak załączników."), [])

    def test_wiele(self):
        t = "Załącznik nr 1 — Umowa\nZałącznik nr 2 — Faktura"
        self.assertEqual(
            find_attachment_page_headers(t), [("1", "Umowa"), ("2", "Faktura")]
        )

    def test_case_insensitive(self):
        t = "ZAŁĄCZNIK NR 3 — Regulamin"
        self.assertEqual(find_attachment_page_headers(t), [("3", "Regulamin")])

    def test_nie_wykrywa_formatu_dwukropek(self):
        t = "Załącznik nr 1: Tytuł"
        self.assertEqual(find_attachment_page_headers(t), [])


class TestFindAttachmentListItems(unittest.TestCase):
    def test_podstawowy(self):
        t = "Załącznik nr 1: Umowa (plik umowa.pdf)"
        self.assertEqual(
            find_attachment_list_items(t), [("1", "Umowa (plik umowa.pdf)")]
        )

    def test_brak(self):
        self.assertEqual(find_attachment_list_items("Brak."), [])

    def test_wiele(self):
        t = "Załącznik nr 1: Umowa\nZałącznik nr 2: Faktura"
        self.assertEqual(
            find_attachment_list_items(t), [("1", "Umowa"), ("2", "Faktura")]
        )

    def test_wariant_bez_ogonkow(self):
        t = "Zalacznik nr 5: Opinia techniczna"
        self.assertEqual(find_attachment_list_items(t)[0][0], "5")

    def test_nie_wykrywa_formatu_myslnik(self):
        t = "Załącznik nr 1 — Protokół odbioru"
        self.assertEqual(find_attachment_list_items(t), [])


class TestFindCrossReferences(unittest.TestCase):
    def test_skrot_zal(self):
        self.assertEqual(find_cross_references("Zob. zał. 3."), {3})

    def test_pelne_slowo(self):
        self.assertEqual(find_cross_references("Dowód w załączniku nr 2."), {2})

    def test_kombinacja(self):
        self.assertEqual(
            find_cross_references("Dowód w zał. 1 oraz załączniku nr 2."), {1, 2}
        )

    def test_deduplicacja(self):
        self.assertEqual(find_cross_references("zał. 1 i zał. 1"), {1})

    def test_brak(self):
        self.assertEqual(find_cross_references("Brak odesłań."), set())

    def test_odmiany_fleksyjne(self):
        t = "załącznika nr 1, załącznikiem nr 2, załączników nr 3"
        self.assertEqual(find_cross_references(t), {1, 2, 3})


class TestFindNumberingGapsAndDuplicates(unittest.TestCase):
    def test_bez_problemow(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1, 2, 3]), ([], []))

    def test_dziura(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1, 3]), ([2], []))

    def test_duplikat(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1, 1, 2]), ([], [1]))

    def test_pusta_lista(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([]), ([], []))

    def test_dziura_i_duplikat(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1, 2, 2, 4]), ([3], [2]))

    def test_jeden_element(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1]), ([], []))

    def test_wiele_dziur(self):
        self.assertEqual(find_numbering_gaps_and_duplicates([1, 5]), ([2, 3, 4], []))


class TestTitlesMatch(unittest.TestCase):
    def test_identyczne(self):
        self.assertTrue(titles_match("Umowa najmu", "Umowa najmu"))

    def test_sufiks_plik_ignorowany(self):
        self.assertTrue(
            titles_match(
                "Umowa z dnia 01.01.2026", "Umowa z dnia 01.01.2026 (plik umowa.pdf)"
            )
        )

    def test_rozne(self):
        self.assertFalse(titles_match("Umowa najmu", "Faktura VAT"))

    def test_tytuł_na_stronie_dluzszy(self):
        self.assertTrue(
            titles_match(
                "Wydruk korespondencji e-mail z dnia 12.01.2025",
                "Wydruk korespondencji e-mail",
            )
        )

    def test_rozne_whitespace_normalizowane(self):
        self.assertTrue(titles_match("Umowa   najmu", "Umowa najmu"))

    def test_pusty_po_usunieciu_sufiksu(self):
        self.assertTrue(titles_match("Cokolwiek", "(plik cos.pdf)"))


class TestFindParagraphNumberingIssues(unittest.TestCase):
    def test_poprawna_numeracja(self):
        t = "1.  Pierwsze.\n2.  Drugie.\n3.  Trzecie."
        self.assertEqual(find_paragraph_numbering_issues(t), ([], []))

    def test_przeskok(self):
        t = "1.  Pierwsze.\n3.  Trzecie."
        self.assertEqual(find_paragraph_numbering_issues(t), ([], [(1, 3)]))

    def test_duplikat(self):
        t = "1.  Pierwsze.\n1.  Drugie."
        self.assertEqual(find_paragraph_numbering_issues(t), ([1], []))

    def test_brak_numeracji(self):
        self.assertEqual(find_paragraph_numbering_issues("Brak numeracji."), ([], []))

    def test_jeden_ustep(self):
        self.assertEqual(find_paragraph_numbering_issues("1.  Jedyny."), ([], []))

    def test_jeden_odstep_nie_liczy(self):
        # "2. tekst" (jeden spacja) nie jest ustępem wg formatu
        t = "1.  Pierwszy\n2. NieUstep\n3.  Trzeci"
        dups, skoki = find_paragraph_numbering_issues(t)
        self.assertIn((1, 3), skoki)


class TestFindSha256Hashes(unittest.TestCase):
    def test_jedna_suma(self):
        self.assertEqual(find_sha256_hashes(f"SHA-256: {SHA}"), {SHA})

    def test_dwie_sumy(self):
        self.assertEqual(find_sha256_hashes(f"{SHA} {SHA2}"), {SHA, SHA2})

    def test_brak(self):
        self.assertEqual(find_sha256_hashes("Brak sum."), set())

    def test_za_krotka(self):
        self.assertEqual(find_sha256_hashes("a" * 63), set())

    def test_wielkie_litery_nie_pasuja(self):
        self.assertEqual(find_sha256_hashes("A" * 64), set())

    def test_deduplicacja(self):
        self.assertEqual(find_sha256_hashes(f"{SHA} {SHA}"), {SHA})


if __name__ == "__main__":
    unittest.main(verbosity=2)
