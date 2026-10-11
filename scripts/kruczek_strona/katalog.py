"""Katalog komponentów JinjaX strony. Autoescape włączony — JinjaX sam go nie włącza."""

from __future__ import annotations

from pathlib import Path

import jinja2
import jinjax
from kruczek_core.widok import DNI_BEZ_RUCHU

from kruczek_strona.format import data_pl, dzien_tygodnia, odmiana
from kruczek_strona.ikony import IKONY

KOMPONENTY = Path(__file__).resolve().parent / "components"


def utworz_katalog(token: str) -> jinjax.Catalog:
    """Komponent = plik w components/ (nazwy jak w design systemie). `token` sesji trafia do każdego
    formularza (ActionForm); `widok` ("przeglad" | "sprawa") podaje każde render(…, _globals=…)."""
    katalog = jinjax.Catalog(
        jinja_env=jinja2.Environment(autoescape=True),
        globals={"token": token, "IKONY": IKONY, "DNI_BEZ_RUCHU": DNI_BEZ_RUCHU},
        filters={"data_pl": data_pl, "dzien_tygodnia": dzien_tygodnia, "odmiana": odmiana},
    )
    katalog.add_folder(KOMPONENTY)
    return katalog
