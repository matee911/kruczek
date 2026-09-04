"""Unit tests for kontrola_pisma.py — wiring of kontrola_logika.py regex helpers and
utils.py print&mail checks into BLAD/OSTRZ, plus the logic unique to this script
(class="fill" detection, SHA-256-vs-filesystem matching, dowody.zip inspection).

The only mandatory external binary is pdftotext; pdfinfo/pdffonts are optional and
mocked per test. None need to be installed to run this suite.
"""

import io
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import kontrola_pisma
from utils import sha256_file

# A letter with no unfilled fields, no attachments, no paragraph numbering, and a
# signature block — every check in main() passes on this text by itself.
PISMO_OK = "Treść pisma bez zastrzeżeń, w pełni gotowa do wysyłki.\n\nZ poważaniem\n"


def run_main(argv):
    """Call kontrola_pisma.main() with the given argv, return (stdout, exit_code).

    main() always ends in sys.exit(1 if BLAD else 0), so exit_code is a plain int
    for every normal run; only the "can't even start" errors (missing PDF, missing
    pdftotext) exit with a human-readable string instead.
    """
    old_argv = sys.argv
    buf = io.StringIO()
    code = 0
    try:
        sys.argv = ["kontrola_pisma.py", *argv]
        with redirect_stdout(buf):
            try:
                kontrola_pisma.main()
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = old_argv
    return buf.getvalue(), code


def run_with_pdf_text(
    pdf_text, argv, *, which_map=None, pdfinfo_pages=None, pdffonts_output=""
):
    """Run main() with pdftotext/pdfinfo/pdffonts mocked; pdftotext always "available"
    and returning `pdf_text`, since every check depends on it. pdfinfo/pdffonts stay
    unavailable unless a caller opts in via which_map or the pdfinfo_pages/
    pdffonts_output kwargs, matching how main() itself guards each with shutil.which.
    """
    which_map = {"pdftotext": "/usr/bin/pdftotext", **(which_map or {})}

    def which(name):
        return which_map.get(name)

    def run(cmd, **kwargs):
        if cmd[0] == "pdftotext":
            return mock.Mock(stdout=pdf_text)
        if cmd[0] == "pdfinfo":
            stdout = f"Pages:          {pdfinfo_pages}\n" if pdfinfo_pages is not None else ""
            return mock.Mock(stdout=stdout)
        if cmd[0] == "pdffonts":
            return mock.Mock(stdout=pdffonts_output)
        raise AssertionError(f"unexpected command: {cmd}")

    with (
        mock.patch("kontrola_pisma.shutil.which", side_effect=which),
        mock.patch("kontrola_pisma.subprocess.run", side_effect=run),
    ):
        return run_main(argv)


def _pdffonts_table(*, unembedded=()):
    header = "name".ljust(38) + "type".ljust(18) + "emb"
    sep = "-" * 56
    rows = [
        "Liberation Serif".ljust(38) + "CID TrueType".ljust(18) + "yes",
        *(name.ljust(38) + "TrueType".ljust(18) + "no " for name in unembedded),
    ]
    return "\n".join([header, sep, *rows]) + "\n"


class KontrolaPismaTestCase(unittest.TestCase):
    """Base class: every test needs a real PDF file (existence-checked) and a real
    --sprawa directory (os.walk'd for SHA-256 matching) — only pdftotext/pdfinfo/
    pdffonts are worth mocking, since they're the only genuinely external tools.
    """

    def _run(self, pdf_text, extra_argv=(), pdf_bytes=b"%PDF-1.4 fake", **run_kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "pismo.pdf")
            sprawa = os.path.join(tmp, "sprawa")
            os.makedirs(sprawa)
            Path(pdf).write_bytes(pdf_bytes)
            return run_with_pdf_text(
                pdf_text, [pdf, "--sprawa", sprawa, *extra_argv], **run_kwargs
            )


class TestTekstPdf(unittest.TestCase):
    def test_exits_without_pdftotext(self):
        with (
            mock.patch("kontrola_pisma.shutil.which", return_value=None),
            self.assertRaises(SystemExit) as ctx,
        ):
            kontrola_pisma.tekst_pdf("dowolna.pdf")
        self.assertIn("brak pdftotext", str(ctx.exception.code))

    def test_calls_pdftotext_with_layout(self):
        with (
            mock.patch("kontrola_pisma.shutil.which", return_value="/usr/bin/pdftotext"),
            mock.patch(
                "kontrola_pisma.subprocess.run",
                return_value=mock.Mock(stdout="tekst"),
            ) as run,
        ):
            out = kontrola_pisma.tekst_pdf("pismo.pdf")
        run.assert_called_once_with(
            ["pdftotext", "-layout", "pismo.pdf", "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(out, "tekst")


class TestEntryErrors(unittest.TestCase):
    def test_exits_when_pdf_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sprawa = os.path.join(tmp, "sprawa")
            os.makedirs(sprawa)
            _stdout, code = run_with_pdf_text(
                PISMO_OK, [os.path.join(tmp, "brak.pdf"), "--sprawa", sprawa]
            )
        self.assertIn("brak pliku", str(code))

    def test_exits_when_pdftotext_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "pismo.pdf")
            sprawa = os.path.join(tmp, "sprawa")
            os.makedirs(sprawa)
            Path(pdf).write_bytes(b"%PDF-1.4")
            _stdout, code = run_with_pdf_text(
                PISMO_OK, [pdf, "--sprawa", sprawa], which_map={"pdftotext": None}
            )
        self.assertIn("brak pdftotext", str(code))


class TestCleanLetter(KontrolaPismaTestCase):
    def test_reports_ok_and_exit_code_zero(self):
        stdout, code = self._run(PISMO_OK)
        self.assertEqual(code, 0)
        self.assertIn("OK — kontrola mechaniczna bez zastrzeżeń.", stdout)


class TestPlaceholders(KontrolaPismaTestCase):
    def test_detects_unfilled_bracket_field(self):
        text = "Wzywa Pan [imię i nazwisko] do zapłaty.\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("Niewypełnione pola (1)", stdout)
        self.assertIn("--html", stdout)

    def test_detects_placeholder_marker(self):
        text = "Opis szkody: TODO uzupełnić po oględzinach.\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("został placeholder: „TODO”", stdout)

    def test_html_reports_unfilled_fill_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "pismo.html")
            Path(html).write_text(
                '<p class="fill">TU WPISAĆ KWOTĘ</p>', encoding="utf-8"
            )
            stdout, code = self._run(PISMO_OK, ["--html", html])
        self.assertEqual(code, 1)
        self.assertIn('Pola oznaczone class="fill" nadal niewypełnione (1)', stdout)

    def test_html_confirms_when_no_fill_class_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "pismo.html")
            Path(html).write_text("<p>Kwota: 500 zł</p>", encoding="utf-8")
            stdout, code = self._run(PISMO_OK, ["--html", html])
        self.assertEqual(code, 0)
        self.assertIn('wszystkie pola class="fill" wypełnione', stdout)


class TestAttachments(KontrolaPismaTestCase):
    def test_detects_numbering_gap(self):
        text = (
            "Załącznik nr 1 — Umowa\nZałącznik nr 3 — Faktura\n\nZ poważaniem\n"
        )
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("Dziury w numeracji stron załączników: brak nr [2]", stdout)

    def test_detects_duplicate_numbers(self):
        text = (
            "Załącznik nr 1 — Umowa\nZałącznik nr 1 — Umowa\n\nZ poważaniem\n"
        )
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("Powtórzone numery załączników: [1]", stdout)

    def test_detects_list_pages_mismatch(self):
        text = (
            "Załącznik nr 1 — Umowa\n\n"
            "Załącznik nr 2: Faktura (plik faktura.pdf)\n\nZ poważaniem\n"
        )
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("Lista załączników [2] nie zgadza się ze stronami załączników [1]", stdout)

    def test_detects_title_mismatch(self):
        text = (
            "Załącznik nr 1 — Umowa najmu\n\n"
            "Załącznik nr 1: Faktura VAT (plik faktura.pdf)\n\nZ poważaniem\n"
        )
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("tytuł na liście", stdout)
        self.assertIn("różni się od tytułu na stronie", stdout)

    def test_detects_reference_to_missing_attachment(self):
        text = "Dowód opisano w zał. 5, do pisma nieprzypięty.\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn(
            "Treść odsyła do załączników, których nie ma w piśmie: nr [5]", stdout
        )


class TestChecksums(KontrolaPismaTestCase):
    def test_detects_hash_with_no_matching_file(self):
        fake_hash = "a" * 64
        text = f"SHA-256: {fake_hash}\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn(
            f"Suma SHA-256 podana w piśmie nie odpowiada żadnemu plikowi w sprawie: {fake_hash}",
            stdout,
        )

    def test_confirms_hash_matching_a_case_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "pismo.pdf")
            sprawa = os.path.join(tmp, "sprawa")
            os.makedirs(sprawa)
            Path(pdf).write_bytes(b"%PDF-1.4")
            dowod = os.path.join(sprawa, "dowod.txt")
            Path(dowod).write_text("treść dowodu", encoding="utf-8")
            digest = sha256_file(dowod)
            text = f"SHA-256: {digest}\n\nZ poważaniem\n"
            stdout, code = run_with_pdf_text(text, [pdf, "--sprawa", sprawa])
        self.assertEqual(code, 0)
        self.assertIn("potwierdzone sumy kontrolne: 1", stdout)

    def test_walk_ignores_git_pycache_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "pismo.pdf")
            sprawa = os.path.join(tmp, "sprawa")
            os.makedirs(sprawa)
            os.makedirs(os.path.join(sprawa, ".git"))
            os.makedirs(os.path.join(sprawa, "__pycache__"))
            Path(pdf).write_bytes(b"%PDF-1.4")
            Path(sprawa, ".git", "config").write_text("x", encoding="utf-8")
            Path(sprawa, "__pycache__", "x.pyc").write_bytes(b"\x00")
            real = os.path.join(sprawa, "dowod.txt")
            Path(real).write_text("treść dowodu", encoding="utf-8")
            os.symlink(real, os.path.join(sprawa, "link.txt"))
            digest = sha256_file(real)
            text = f"SHA-256: {digest}\n\nZ poważaniem\n"
            stdout, code = run_with_pdf_text(text, [pdf, "--sprawa", sprawa])
        self.assertEqual(code, 0)
        self.assertIn("potwierdzone sumy kontrolne: 1", stdout)


class TestDowodyZip(KontrolaPismaTestCase):
    def test_reports_missing_zip_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_zip = os.path.join(tmp, "nope.zip")
            stdout, code = self._run(PISMO_OK, ["--zip", missing_zip])
        self.assertEqual(code, 1)
        self.assertIn(f"Wskazany {missing_zip} nie istnieje", stdout)

    def test_reports_empty_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "dowody.zip")
            with zipfile.ZipFile(zpath, "w"):
                pass
            stdout, code = self._run(PISMO_OK, ["--zip", zpath])
        self.assertEqual(code, 1)
        self.assertIn("dowody.zip jest pusty", stdout)

    def test_warns_when_sha256sums_missing_from_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "dowody.zip")
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("dowod.txt", "treść")
            stdout, code = self._run(PISMO_OK, ["--zip", zpath])
        self.assertEqual(code, 0)
        self.assertIn("dowody.zip: 1 plików", stdout)
        self.assertIn("nie zawiera SHA256SUMS.txt", stdout)

    def test_no_warning_when_sha256sums_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = os.path.join(tmp, "dowody.zip")
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("dowod.txt", "treść")
                z.writestr("SHA256SUMS.txt", "...")
            stdout, code = self._run(PISMO_OK, ["--zip", zpath])
        self.assertEqual(code, 0)
        self.assertNotIn("nie zawiera SHA256SUMS.txt", stdout)


class TestParagraphNumbering(KontrolaPismaTestCase):
    def test_detects_duplicate_paragraph_numbers(self):
        text = "1.  Pierwsze.\n1.  Drugie.\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 1)
        self.assertIn("Numery ustępów powtarzają się: [1]", stdout)

    def test_warns_on_paragraph_numbering_jump(self):
        text = "1.  Pierwsze.\n5.  Piąte.\n\nZ poważaniem\n"
        stdout, code = self._run(text)
        self.assertEqual(code, 0)
        self.assertIn("Przeskoki w numeracji ustępów: [(1, 5)]", stdout)


class TestPrintMailRequirements(KontrolaPismaTestCase):
    def test_oversized_pdf_is_a_warning_not_a_blocker(self):
        stdout, code = self._run(PISMO_OK, pdf_bytes=b"x" * (3 * 1024 * 1024))
        self.assertEqual(code, 0)
        self.assertIn("PDF ma 3.00 MB", stdout)
        self.assertIn("OSTRZEŻENIA", stdout)

    def test_too_many_sheets_is_blocking(self):
        stdout, code = self._run(
            PISMO_OK, which_map={"pdfinfo": "/usr/bin/pdfinfo"}, pdfinfo_pages=200
        )
        self.assertEqual(code, 1)
        self.assertIn("200 stron = 100 kartek — limit to 98 kartek", stdout)

    def test_unembedded_fonts_are_blocking(self):
        stdout, code = self._run(
            PISMO_OK,
            which_map={"pdffonts": "/usr/bin/pdffonts"},
            pdffonts_output=_pdffonts_table(unembedded=["Arial"]),
        )
        self.assertEqual(code, 1)
        self.assertIn("Fonty nieosadzone w PDF: Arial", stdout)


class TestSignature(KontrolaPismaTestCase):
    def test_warns_when_signature_block_missing(self):
        # Must avoid the substrings the regex itself looks for ("podpis", "Z poważaniem",
        # a run of underscores/dots) — a real closing line, deliberately left off here.
        stdout, code = self._run("Treść pisma, żadnego zwrotu na końcu.\n")
        self.assertEqual(code, 0)
        self.assertIn("nie widać bloku podpisu", stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
