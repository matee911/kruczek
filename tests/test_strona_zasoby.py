import base64
import hashlib
import json
import shutil
from pathlib import Path

from kruczek_strona import budowa_css

STRONA = Path(__file__).resolve().parents[1] / "scripts" / "kruczek_strona"
STATIC = STRONA / "static"


def _podmien_katalogi(monkeypatch, kopia):
    for nazwa, wartosc in {"KATALOG": kopia, "CSS": kopia / "css", "KOMPONENTY": kopia / "components",
                           "WYNIK": kopia / "static" / "kruczek.css",
                           "VENDOR": kopia / "css" / "vendor" / "basecoat-css-1.0.2"}.items():
        monkeypatch.setattr(budowa_css, nazwa, wartosc)


def test_basecoat_vendorowany_zgodny_z_sumami_z_tarballa():
    # Act
    zle = budowa_css.niezgodne_z_sumami(budowa_css.VENDOR, "FILES.sha256")
    # Assert
    assert zle == []


def test_zasoby_statyczne_zgodne_z_sumami():
    # Act
    zle = budowa_css.niezgodne_z_sumami(STATIC, "ZASOBY.sha256")
    # Assert
    assert zle == []


def test_htmx_to_wersja_4_0_0_z_sumy_sha384():
    # Arrange
    dane = (STATIC / "htmx.min.js").read_bytes()
    # Act
    suma = base64.b64encode(hashlib.sha384(dane).digest()).decode()
    # Assert
    assert suma == "BvJpBiO8Kh31EqtJe5DRIeWrHWnCGkwytKs9NKFi86Hhw96dEqdEMzZDeK9iEGTc"


def test_basecoat_js_to_all_min_js_z_vendora():
    # Act / Assert
    assert (STATIC / "basecoat.min.js").read_bytes() == (budowa_css.VENDOR / "dist" / "js" / "all.min.js").read_bytes()


def test_tokens_css_wygenerowany_z_tokens_json():
    # Arrange
    tokens = json.loads((budowa_css.CSS / "tokens.json").read_text(encoding="utf-8"))
    # Act
    oczekiwany = budowa_css.tokens_css(tokens)
    # Assert
    assert (budowa_css.CSS / "tokens.css").read_text(encoding="utf-8") == oczekiwany


def test_kruczek_css_zbudowany_z_aktualnych_zrodel():
    # Arrange
    css = (STATIC / "kruczek.css").read_text(encoding="utf-8")
    # Act
    suma = budowa_css.suma_z_naglowka(css)
    # Assert — przy FAIL: uv run --script scripts/kruczek_strona/budowa_css.py i commit kruczek.css
    assert suma == budowa_css.suma_zrodel()


def test_kruczek_css_bez_zasobow_z_sieci():
    # Arrange
    css = (STATIC / "kruczek.css").read_text(encoding="utf-8")
    # Act / Assert
    assert "googleapis" not in css
    assert "url(http" not in css and "url(//" not in css and '@import"http' not in css
    assert "url(/static/fonts/archivo-latin-ext-wdth-normal.woff2)" in css


def test_fonty_maja_licencje_ofl():
    # Act / Assert
    for nazwa in ("archivo", "atkinson-hyperlegible-next", "atkinson-hyperlegible-mono"):
        assert "SIL Open Font License" in (STATIC / "fonts" / f"OFL-{nazwa}.txt").read_text(encoding="utf-8")


def test_sprawdz_wykrywa_zmiane_zrodla(tmp_path, monkeypatch):
    # Arrange — kopia drzewa strony ze zmienionym komponentem
    kopia = tmp_path / "kruczek_strona"
    shutil.copytree(STRONA, kopia, ignore=shutil.ignore_patterns("__pycache__"))
    (kopia / "components" / "Nowy.jinja").write_text('<p class="mt-4">x</p>\n', encoding="utf-8")
    _podmien_katalogi(monkeypatch, kopia)
    # Act
    problemy = budowa_css.sprawdz()
    # Assert
    assert problemy == ["static/kruczek.css nieaktualny"]


def test_suma_zrodel_pomija_pliki_ukryte(tmp_path, monkeypatch):
    # Arrange — kopia źródeł, do której system plików dorzucił .DS_Store
    kopia = tmp_path / "kruczek_strona"
    shutil.copytree(STRONA, kopia, ignore=shutil.ignore_patterns("__pycache__"))
    _podmien_katalogi(monkeypatch, kopia)
    przed = budowa_css.suma_zrodel()
    # Act
    (kopia / "css" / ".DS_Store").write_bytes(b"\x00junk")
    (kopia / "components" / ".DS_Store").write_bytes(b"\x00junk")
    # Assert
    assert budowa_css.suma_zrodel() == przed
