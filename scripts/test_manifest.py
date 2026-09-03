"""Unit testy manifest.py — sumy kontrolne i manifest plików sprawy.

Bez zewnętrznych binarek (manifest.py operuje wyłącznie na systemie plików), więc
w przeciwieństwie do kontrola_pisma.py czy build_pismo.py da się to przetestować
wprost, bez mockowania subprocess.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import manifest


def uruchom(argv):
    """Woła manifest.main() z podanym argv, zwraca (wyjście stdout, kod wyjścia)."""
    old_argv = sys.argv
    buf = io.StringIO()
    try:
        sys.argv = ["manifest.py", *argv]
        with redirect_stdout(buf):
            try:
                manifest.main()
                kod = 0
            except SystemExit as e:
                kod = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    finally:
        sys.argv = old_argv
    return buf.getvalue(), kod


class TestWalk(unittest.TestCase):
    def test_znajduje_pliki(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_text("a")
            Path(tmp, "b.txt").write_text("b")
            wynik = sorted(rel for _, rel in manifest.walk(tmp))
            self.assertEqual(wynik, ["a.txt", "b.txt"])

    def test_pomija_skip_dirs_i_ukryte_pliki(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".git"))
            Path(tmp, ".git", "config").write_text("x")
            Path(tmp, ".DS_Store").write_text("x")
            Path(tmp, "widoczny.txt").write_text("x")
            wynik = sorted(rel for _, rel in manifest.walk(tmp))
            self.assertEqual(wynik, ["widoczny.txt"])

    def test_pomija_pliki_manifestu(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SHA256SUMS.txt").write_text("x")
            Path(tmp, "index.md").write_text("x")
            Path(tmp, "dowod.txt").write_text("x")
            wynik = sorted(rel for _, rel in manifest.walk(tmp))
            self.assertEqual(wynik, ["dowod.txt"])

    def test_pomija_dowiazania_symboliczne(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "prawdziwy.txt").write_text("x")
            os.symlink(
                os.path.join(tmp, "prawdziwy.txt"), os.path.join(tmp, "link.txt")
            )
            wynik = sorted(rel for _, rel in manifest.walk(tmp))
            self.assertEqual(wynik, ["prawdziwy.txt"])


class TestRows(unittest.TestCase):
    def test_zawiera_sha_rozmiar_i_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "plik.txt").write_bytes(b"tresc")
            wynik = manifest.rows(tmp)
            self.assertEqual(len(wynik), 1)
            r = wynik[0]
            self.assertEqual(r["rel"], "plik.txt")
            self.assertEqual(r["size"], "5 B")
            self.assertEqual(len(r["sha"]), 64)
            self.assertRegex(r["mtime"], r"^\d{4}-\d{2}-\d{2}$")

    def test_pusty_katalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(manifest.rows(tmp), [])


class TestTable(unittest.TestCase):
    def test_zawiera_naglowek_i_wiersz(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "plik.txt").write_bytes(b"x")
            wynik = manifest.table(tmp)
            self.assertIn("| Plik | Data pliku | Rozmiar | SHA-256 |", wynik)
            self.assertIn("`plik.txt`", wynik)
            self.assertIn("Plików: 1.", wynik)

    def test_pusty_katalog_zero_plikow(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Plików: 0.", manifest.table(tmp))


class TestMainSkan(unittest.TestCase):
    def test_wypisuje_tabele(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_text("a")
            out, kod = uruchom(["skan", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("a.txt", out)


class TestMainSumy(unittest.TestCase):
    def test_zapisuje_sha256sums(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            out, kod = uruchom(["sumy", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("Zapisano", out)
            p = Path(tmp, "SHA256SUMS.txt")
            self.assertTrue(p.exists())
            self.assertIn("a.txt", p.read_text())


class TestMainSprawdz(unittest.TestCase):
    def test_ok_gdy_zgodne(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            uruchom(["sumy", tmp])
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("OK", out)

    def test_wykrywa_brakujacy_plik(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            uruchom(["sumy", tmp])
            os.remove(os.path.join(tmp, "a.txt"))
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 1)
            self.assertIn("BRAK PLIKU: a.txt", out)

    def test_wykrywa_niezgodna_sume(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            uruchom(["sumy", tmp])
            Path(tmp, "a.txt").write_bytes(b"zmienione")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 1)
            self.assertIn("NIEZGODNA SUMA: a.txt", out)

    def test_wykrywa_nowy_plik(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            uruchom(["sumy", tmp])
            Path(tmp, "b.txt").write_bytes(b"b")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("NOWY PLIK", out)
            self.assertIn("b.txt", out)

    def test_ignoruje_puste_linie_w_sha256sums(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            sha = manifest.rows(tmp)[0]["sha"]
            Path(tmp, "SHA256SUMS.txt").write_text(f"\n{sha}  a.txt\n\n")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("OK", out)

    def test_bez_sha256sums_pomija_porownanie(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("pomijam porównanie", out)

    def test_index_md_z_odnaleziona_suma(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            wynik = manifest.rows(tmp)
            sha = wynik[0]["sha"]
            Path(tmp, "index.md").write_text(f"Suma: {sha}\n")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 0)
            self.assertIn("index.md: 1 sum, wszystkie odnalezione: True", out)

    def test_index_md_z_suma_bez_pliku(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            obca_suma = "a" * 64
            Path(tmp, "index.md").write_text(f"Suma: {obca_suma}\n")
            out, kod = uruchom(["sprawdz", tmp])
            self.assertEqual(kod, 1)
            self.assertIn("SUMA W index.md BEZ ODPOWIADAJĄCEGO PLIKU", out)


class TestMainWstaw(unittest.TestCase):
    def test_wymaga_dwoch_argumentow(self):
        with tempfile.TemporaryDirectory() as tmp:
            idx = os.path.join(tmp, "index.md")
            Path(idx).write_text("treść")
            _out, kod = uruchom(["wstaw", idx])
            self.assertNotEqual(kod, 0)

    def test_dopisuje_blok_gdy_brak_znacznikow(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            idx = os.path.join(tmp, "index.md")
            Path(idx).write_text("# Sprawa\n\ntreść wstępu\n")
            _out, kod = uruchom(["wstaw", idx, tmp])
            self.assertEqual(kod, 0)
            txt = Path(idx).read_text()
            self.assertIn(manifest.START, txt)
            self.assertIn(manifest.END, txt)
            self.assertIn("a.txt", txt)
            self.assertIn("treść wstępu", txt)

    def test_podmienia_istniejacy_blok(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_bytes(b"a")
            idx = os.path.join(tmp, "index.md")
            stary_blok = f"{manifest.START}\nSTARA TREŚĆ\n{manifest.END}"
            Path(idx).write_text(f"# Sprawa\n\n{stary_blok}\n")
            _out, kod = uruchom(["wstaw", idx, tmp])
            self.assertEqual(kod, 0)
            txt = Path(idx).read_text()
            self.assertNotIn("STARA TREŚĆ", txt)
            self.assertIn("a.txt", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
