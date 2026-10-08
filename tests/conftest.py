import pytest

from kruczek_core.dni_wolne import Kalendarz, wczytaj_kalendarz


@pytest.fixture
def kalendarz() -> Kalendarz:
    """Kalendarz z jednorazowymi dniami z pluginu, bez pliku projektu."""
    return wczytaj_kalendarz(None)
