"""Prawdziwy silnik PDF nie wdrukowuje plików z file:// — niezależnie od walidacji treści pisma."""
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parent.parent
SKRYPT = KORZEN / "scripts" / "build_pismo.py"
SZABLON = KORZEN / "templates" / "pismo.html"
SEKRET_RGB, KONTROLA_RGB = (0x13, 0x57, 0x9B), (0x2E, 0x8B, 0x57)
SEKRET_TEKST = "SEKRET-7Q2X"

pytestmark = pytest.mark.skipif(not (shutil.which("pdfimages") and shutil.which("pdftotext")),
                                reason="brak pdfimages/pdftotext (poppler)")


def _png(sciezka, szer, wys, rgb):
    """Jednokolorowy PNG RGB bez kanału alfa."""
    def kawalek(typ, dane):
        return struct.pack(">I", len(dane)) + typ + dane + struct.pack(">I", zlib.crc32(typ + dane))
    wiersz = b"\x00" + bytes(rgb) * szer
    sciezka.write_bytes(b"\x89PNG\r\n\x1a\n" + kawalek(b"IHDR", struct.pack(">IIBBBBB", szer, wys, 8, 2, 0, 0, 0))
                        + kawalek(b"IDAT", zlib.compress(wiersz * wys)) + kawalek(b"IEND", b""))


def _obrazy(pdf, katalog):
    """Obrazy z PDF-u jako (szerokość, wysokość, piksele RGB) — `pdfimages` bez flag daje P6 (RGB) albo P5 (szarość)."""
    subprocess.run(["pdfimages", str(pdf), str(katalog / "img")], check=True)
    wynik = []
    for plik in sorted(katalog.glob("img-*.p?m")):
        dane = plik.read_bytes()
        m = re.match(rb"(P[56])\s+(\d+)\s+(\d+)\s+\d+\s", dane)
        if not m:
            continue  # P4 (1 bit) — maski, nie obrazy z kolorem
        kanaly, szer, wys = (3 if m[1] == b"P6" else 1), int(m[2]), int(m[3])
        piks = dane[m.end():m.end() + szer * wys * kanaly]
        rgb = [tuple(piks[i:i + 3]) if kanaly == 3 else (piks[i],) * 3 for i in range(0, len(piks), kanaly)]
        wynik.append((szer, wys, rgb))
    return wynik


def _w_kolorze(rgb, kolor):
    return sum(all(abs(a - b) <= 8 for a, b in zip(p, kolor)) for p in rgb) / max(len(rgb), 1)


def _zbuduj(tmp_path, zrodlo):
    obraz, tekst, kontrola = tmp_path / "sekret.png", tmp_path / "sekret.txt", tmp_path / "kontrola.png"
    _png(obraz, 7, 3, SEKRET_RGB)
    _png(kontrola, 5, 2, KONTROLA_RGB)
    tekst.write_text(SEKRET_TEKST, encoding="utf-8")
    zalaczniki = ["-z", f"{kontrola}:Zdjęcie"]
    html = SZABLON.read_text(encoding="utf-8")
    if zrodlo == "szablon":
        wstawka = (f'<p><img src="{obraz.as_uri()}"></p><iframe src="{tekst.as_uri()}"></iframe>'
                   f'<object data="{tekst.as_uri()}"></object><div style="background: url({obraz.as_uri()})">x</div>')
        html = html.replace("<!--KRUCZEK:TRESC:END-->", wstawka + "<!--KRUCZEK:TRESC:END-->")
    else:
        md = tmp_path / "transkrypcja.md"
        md.write_text(f"# Transkrypcja\n\n![x]({obraz.as_uri()})\n", encoding="utf-8")
        zalaczniki += ["-z", f"{md}:Transkrypcja"]
    szablon = tmp_path / "pismo.html"
    szablon.write_text(html, encoding="utf-8")
    pdf = tmp_path / "p.pdf"
    r = subprocess.run([sys.executable, str(SKRYPT), str(szablon), "-o", str(pdf), *zalaczniki],
                       capture_output=True, text=True, check=False, timeout=180)
    return r, pdf


@pytest.mark.parametrize("zrodlo", ["szablon", "zalacznik_md"])
def test_walidacja_ominieta_silnik_i_tak_blokuje_file(tmp_path, zrodlo):
    # Arrange
    if zrodlo == "zalacznik_md" and not shutil.which("pandoc"):
        pytest.skip("brak pandoc — załącznik .md idzie jako <pre> bez obrazka")
    # Act
    r, pdf = _zbuduj(tmp_path, zrodlo)
    wyjscie = r.stdout + r.stderr
    if "brak silnika PDF" in wyjscie:
        pytest.skip("brak silnika PDF")
    if "Silnik:    wkhtmltopdf" in r.stdout:
        pytest.skip("wkhtmltopdf — ryzyko szczątkowe")
    if "zaktualizuj weasyprint albo zainstaluj Chrome" in wyjscie:
        pytest.skip("weasyprint bez --allowed-protocols i bez Chrome — ryzyko szczątkowe")
    assert r.returncode == 0, wyjscie  # walidacja treści tu nie działa — blokować ma silnik
    # Assert
    katalog = tmp_path / "obrazy"
    katalog.mkdir()
    obrazy = _obrazy(pdf, katalog)
    assert any(_w_kolorze(rgb, KONTROLA_RGB) > 0.9 for _, _, rgb in obrazy), "brak obrazu kontrolnego data:"
    assert not [o for o in obrazy if _w_kolorze(o[2], SEKRET_RGB) > 0.9], \
        "piksele obrazu z file:// trafiły do PDF-u"
    tekst = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    assert SEKRET_TEKST not in tekst
