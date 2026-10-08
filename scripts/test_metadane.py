"""Testy metadane.sh — skrypt uruchamiany jako proces na prawdziwym pliku OOXML.

Given plik .docx z datą w nazwie i datami w docProps/core.xml
When  uruchamiam metadane.sh
Then  w tabeli są daty z metadanych, autor i liczba rewizji,
      a rozbieżność roku w nazwie i w metadanych jest oflagowana
"""

import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

SKRYPT = Path(__file__).with_name("metadane.sh")

CORE_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
    'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<dc:creator>Jan Kowalski</dc:creator><cp:revision>1</cp:revision>"
    '<dcterms:created xsi:type="dcterms:W3CDTF">2026-03-02T10:00:00Z</dcterms:created>'
    '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-03-05T12:00:00Z</dcterms:modified>'
    "</cp:coreProperties>"
)


@unittest.skipUnless(shutil.which("unzip"), "metadane.sh czyta OOXML przez unzip")
class TestOoxml(unittest.TestCase):
    def test_daty_autor_i_rozbieznosc_z_core_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            docx = Path(tmp, "2024-05-01_umowa_test.docx")
            with zipfile.ZipFile(docx, "w") as z:
                z.writestr("docProps/core.xml", CORE_XML)

            # Act
            wynik = subprocess.run(
                ["bash", str(SKRYPT), str(docx)],
                capture_output=True,
                text=True,
                check=False,
            )

            # Assert
            self.assertEqual(wynik.returncode, 0, wynik.stderr)
            self.assertIn("2026-03-02T10:00:00Z", wynik.stdout)
            self.assertIn("Author:Jan Kowalski", wynik.stdout)
            self.assertIn("⚠RevWersje:1", wynik.stdout)
            self.assertIn("⚠RozbieznosDat", wynik.stdout)


class TestPorownanieDat(unittest.TestCase):
    def test_metadane_bez_roku_nie_przerywaja_skryptu(self):
        """grep bez trafienia pod `set -o pipefail` kończył skrypt bez wiersza tabeli."""
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            eml = Path(tmp, "2026-01-01_email_bez-daty.eml")
            eml.write_text("Subject: x\n\ntresc\n", encoding="utf-8")

            # Act
            wynik = subprocess.run(
                ["bash", str(SKRYPT), str(eml)],
                capture_output=True,
                text=True,
                check=False,
            )

            # Assert
            self.assertEqual(wynik.returncode, 0, wynik.stderr)
            wiersz = next(
                l for l in wynik.stdout.splitlines() if l.startswith("2026-01-01_email")
            )
            self.assertNotIn("⚠RozbieznosDat", wiersz)


if __name__ == "__main__":
    unittest.main(verbosity=2)
