import datetime as dt

import pytest

from kruczek_core.model import (
    SCHEMA_VERSION,
    BladSprawy,
    Dowod,
    Pismo,
    Sprawa,
    Termin,
    Uczestnik,
    Watek,
    Zadanie,
    Zdarzenie,
    do_slownika,
    kolejne_id,
    z_slownika,
)

D = dt.date


def pelna_sprawa() -> Sprawa:
    return Sprawa(
        id="abc123",
        tytul="Spamer X",
        wlasciciel="opiekun1",
        strona_przeciwna="X sp. z o.o.",
        uczestnicy=[Uczestnik("opiekun1", "opiekun"), Uczestnik("osoba1", "klientka")],
        watki=[Watek("firma", "X sp. z o.o.")],
        pisma=[Pismo("p1", "firma", 1, "wyslane", "WYSYLKA/pismo.pdf")],
        zdarzenia=[Zdarzenie("z1", D(2026, 10, 8), "nadanie", "wezwanie", "firma", ["ARCHIWUM/a.pdf"])],
        terminy=[Termin("t1", "wyznaczony w piśmie", "z1", "14d", D(2026, 10, 22), "firma", True),
                 Termin("t2", "pouczenie w decyzji", "z1", "14d", D(2026, 10, 22), "firma", False, "moj")],
        zadania=[
            Zadanie("a1", "sprawdź odpowiedź", D(2026, 10, 23), None, "firma", "sprawdz-odpowiedz", "t1", None, "z1"),
            Zadanie("a2", "zrobione z datami", D(2026, 10, 20), D(2026, 10, 30), "firma", None, None, D(2026, 10, 25)),
        ],
        dowody=[Dowod("ARCHIWUM/a.pdf", "f" * 64, D(2026, 10, 8))],
    )


def test_round_trip_przez_slownik():
    # Arrange
    sprawa = pelna_sprawa()
    # Act
    odtworzona = z_slownika(do_slownika(sprawa))
    # Assert
    assert odtworzona == sprawa


@pytest.mark.parametrize(
    ("lista", "pole", "zla_wartosc"),
    [
        ("zdarzenia", "typ", "kogos"),
        ("terminy", "czyj", "kogos"),
        ("uczestnicy", "rola", "kogos"),
        ("pisma", "stan", "kogos"),
    ],
)
def test_nieznana_wartosc_enumu_przy_odczycie_to_blad(lista, pole, zla_wartosc):
    # Arrange
    dane = do_slownika(pelna_sprawa())
    dane[lista][0][pole] = zla_wartosc
    # Act / Assert
    with pytest.raises(ValueError, match=pole):
        z_slownika(dane)


def test_daty_w_slowniku_jako_iso():
    # Act
    dane = do_slownika(pelna_sprawa())
    # Assert
    assert dane["zdarzenia"][0]["data"] == "2026-10-08"
    assert dane["schema_version"] == SCHEMA_VERSION


def test_dowod_domyslnie_wrazliwy_i_nieudostepniany():
    # Act
    dowod = Dowod("a.pdf", "0" * 64, D(2026, 1, 1))
    # Assert
    assert dowod.wrazliwy is True
    assert dowod.do_udostepnienia is False


def test_kolejne_id():
    # Arrange
    zadania = [Zadanie("a1", "x", D(2026, 1, 1)), Zadanie("a7", "y", D(2026, 1, 1))]
    # Act / Assert
    assert kolejne_id("a", zadania) == "a8"
    assert kolejne_id("z", []) == "z1"


def test_brak_watku_to_blad_sprawy():
    # Act / Assert
    with pytest.raises(BladSprawy, match="nie ma wątku 'uodo'"):
        pelna_sprawa().znajdz_watek("uodo")
