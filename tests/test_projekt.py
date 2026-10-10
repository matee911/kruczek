import datetime as dt

import pytest
from kruczek_core.model import BladSprawy
from kruczek_core.operacje import nowa_sprawa
from kruczek_core.projekt import PlikoweRepozytorium, RepozytoriumSpraw, odswiez_index


def _sprawa(katalog, tytul="T"):
    katalog.mkdir(parents=True)
    nowa_sprawa(katalog, tytul, "Firma X sp. z o.o.", "opiekun1")


@pytest.fixture
def projekt(tmp_path):
    _sprawa(tmp_path / "sprawa-a")
    _sprawa(tmp_path / "sprawa ze spacją ąę")
    (tmp_path / "podprojekt").mkdir()
    (tmp_path / "podprojekt" / "index.md").write_text("# Rejestr spraw\n", encoding="utf-8")
    _sprawa(tmp_path / "podprojekt" / "sprawa-b")
    (tmp_path / "stara").mkdir()
    (tmp_path / "stara" / "index.md").write_text("# Sprawa: stara\n", encoding="utf-8")
    (tmp_path / "kopia 2").mkdir()
    return tmp_path


def test_spis_daje_klucze_wzgledem_projektu(projekt):
    # Arrange
    repo = PlikoweRepozytorium(projekt)
    # Act
    spis = repo.spis()
    # Assert
    assert spis.sprawy == ["podprojekt/sprawa-b", "sprawa ze spacją ąę", "sprawa-a"]
    assert spis.stary_format == ["stara"]
    assert spis.bez_indexu == ["kopia 2"]


def test_plikowe_repozytorium_spelnia_protokol(projekt):
    # Arrange / Act
    repo: RepozytoriumSpraw = PlikoweRepozytorium(projekt)
    # Assert
    assert repo.wczytaj("podprojekt/sprawa-b").tytul == "T"


@pytest.mark.parametrize("klucz", ["../x", "/etc", ".kruczek", "", "sprawa-a/../sprawa-a", "nie-ma"])
def test_klucz_spoza_spisu_odrzucony(projekt, klucz):
    # Arrange
    repo = PlikoweRepozytorium(projekt)
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie ma sprawy"):
        repo.katalog(klucz)


def test_klucz_starego_formatu_mowi_o_migracji(projekt):
    # Arrange
    repo = PlikoweRepozytorium(projekt)
    # Act / Assert
    with pytest.raises(BladSprawy, match="migruj"):
        repo.wczytaj("stara")


def test_zmien_przez_klucz_zapisuje(projekt):
    # Arrange
    repo = PlikoweRepozytorium(projekt)
    # Act
    repo.zmien("sprawa ze spacją ąę", lambda s: setattr(s, "wynik", None))
    # Assert
    assert repo.wczytaj("sprawa ze spacją ąę").rewizja == 1


def test_kalendarz_sprawy_z_folderow_nadrzednych(projekt):
    # Arrange
    (projekt / ".kruczek").mkdir()
    (projekt / ".kruczek" / "dni-wolne.json").write_text(
        '[{"data": "2030-01-02", "podstawa": "test", "tylko_urzedy": false}]', encoding="utf-8")
    repo = PlikoweRepozytorium(projekt)
    # Act
    kal = repo.kalendarz("podprojekt/sprawa-b")
    # Assert
    assert kal.czy_wolny(dt.date(2030, 1, 2))


def test_odswiez_index_bez_index_md_nic_nie_robi(projekt):
    # Act / Assert
    assert odswiez_index(projekt / "sprawa-a") is None


def test_odswiez_index_zle_znaczniki_zwraca_ostrzezenie(projekt):
    # Arrange
    (projekt / "sprawa-a" / "index.md").write_text("<!-- kruczek:zadania -->\n", encoding="utf-8")
    # Act
    uwaga = odswiez_index(projekt / "sprawa-a")
    # Assert
    assert uwaga is not None and "nie odświeżony" in uwaga


def test_odswiez_index_poprawne_znaczniki_aktualizuja_sekcje(projekt):
    # Arrange
    index = projekt / "sprawa-a" / "index.md"
    index.write_text("<!-- kruczek:zadania -->\nstare\n<!-- /kruczek:zadania -->\n", encoding="utf-8")
    # Act
    uwaga = odswiez_index(projekt / "sprawa-a")
    # Assert
    assert uwaga is None
    tekst = index.read_text(encoding="utf-8")
    assert "stare" not in tekst
    assert "<!-- kruczek:zadania -->" in tekst
