"""Unit tests for dane_nadawcy_status.py's main() — the file I/O paths (missing file,
missing sender-data sections) that its pure helpers' doctests don't reach.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import dane_nadawcy_status as mod


def run_main(argv):
    old_argv = sys.argv
    buf = io.StringIO()
    try:
        sys.argv = ["dane_nadawcy_status.py", *argv]
        with redirect_stdout(buf):
            mod.main()
    finally:
        sys.argv = old_argv
    return buf.getvalue()


class TestMainMissingFile(unittest.TestCase):
    def test_reports_brak_for_every_critical_field(self):
        out = run_main(["/no/such/dane-nadawcy.md"])
        for pole in mod.KRYTYCZNE:
            self.assertIn(f"BRAK {pole}", out)
        self.assertIn("BRAK-PLIK", out)
        self.assertNotIn("NIP", out)


class TestMainWithFile(unittest.TestCase):
    def test_reports_ok_when_all_critical_fields_filled(self):
        table = (
            "| Pole | Wartość |\n"
            "| --- | --- |\n"
            "| Imię i nazwisko | Jan Kowalski |\n"
            "| Do korespondencji | ul. Przykładowa 1 |\n"
            "| Miejscowość w nagłówku pism | Warszawa |\n"
            "| E-mail w sprawach spornych | jan@example.pl |\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "dane-nadawcy.md")
            path.write_text(table, encoding="utf-8")
            out = run_main([str(path)])
        for pole in mod.KRYTYCZNE:
            self.assertIn(f"OK {pole}", out)
        self.assertNotIn("NIP", out)

    def test_nip_required_only_when_business_section_filled(self):
        table = "| Pole | Wartość |\n| --- | --- |\n| Firma | ACME sp. z o.o. |\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "dane-nadawcy.md")
            path.write_text(table, encoding="utf-8")
            out = run_main([str(path)])
        self.assertIn("BRAK NIP", out)


class TestArgvValidation(unittest.TestCase):
    def test_exits_without_exactly_one_argument(self):
        with self.assertRaises(SystemExit):
            run_main([])
        with self.assertRaises(SystemExit):
            run_main(["a", "b"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
