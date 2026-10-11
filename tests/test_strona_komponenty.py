"""Komponenty JinjaX w izolacji: render → asercje na HTML."""

import datetime as dt
import re

import pytest
from jinja2.exceptions import UndefinedError
from kruczek_core.model import Zadanie
from kruczek_strona.ekrany import (
    EkranSekcji,
    KartaKrokow,
    KartaZadania,
    Komunikat,
    Powiadomienie,
    Wiersz,
    Wpis,
)
from kruczek_strona.katalog import KOMPONENTY, utworz_katalog

D = dt.date


@pytest.fixture
def katalog():
    return utworz_katalog("token-testowy")


def render(katalog, nazwa, widok="przeglad", **kw):
    return katalog.render(nazwa, _globals={"widok": widok}, **kw)


def karta(akcja="zrobione", opis="Wyślij pismo", status="ours", klucz="sprawa-a", watek="firma"):
    return KartaZadania(klucz, Zadanie("a3", opis, D(2026, 10, 1), watek=watek), status,
                        "do 13.10.2026 · zostały 4 dni", "Osoba Testowa: 7 dni — art. 1 testowej ustawy",
                        ["urzędy zamknięte 13.10.2026 (test) — wyślij wcześniej"], akcja, "/kruczek:eskalacja sprawa-a")


@pytest.mark.parametrize("status, slowo", [("overdue", "Po terminie"), ("soon", "Wkrótce"), ("ours", "Nasz termin"),
                                           ("waiting", "Czekam"), ("estimate", "Szacunek")])
def test_status_chip_ikona_i_slowo(katalog, status, slowo):
    # Act
    html = render(katalog, "StatusChip", status=status)
    # Assert
    assert f'data-status="{status}"' in html and slowo in html and 'class="k-icon"' in html


def test_nieznana_ikona_to_blad_renderu(katalog):
    # Act / Assert
    with pytest.raises(UndefinedError):
        render(katalog, "Icon", name="nie-ma-takiej")


def test_case_ref_link_watek_i_id_zadania(katalog):
    # Act
    html = render(katalog, "CaseRef", url="/sprawa/sprawa-a", klucz="sprawa-a", watek="firma", zadanie_id="a3")
    # Assert
    assert html == ('<span class="k-ref"><a href="/sprawa/sprawa-a">sprawa-a</a>'
                    '<span class="k-ref__sep">/</span>firma · a3</span>')


def test_case_ref_bez_linku_ma_sam_watek_a_bez_niczego_nie_renderuje_sie(katalog):
    # Act
    sam_watek = render(katalog, "CaseRef", url="/sprawa/sprawa-a", klucz="sprawa-a", watek="firma", pokaz_sprawe=False)
    pusty = render(katalog, "CaseRef", url="/sprawa/sprawa-a", klucz="sprawa-a", pokaz_sprawe=False)
    # Assert
    assert sam_watek == '<span class="k-ref">wątek: firma</span>'
    assert pusty.strip() == ""


def test_case_ref_w_widoku_sprawy_numer_zadania_bez_poprzedzajacego_separatora(katalog):
    # Act
    bez_watku = render(katalog, "CaseRef", url="/sprawa/sprawa-a", klucz="sprawa-a", zadanie_id="a3",
                       pokaz_sprawe=False)
    z_watkiem = render(katalog, "CaseRef", url="/sprawa/sprawa-a", klucz="sprawa-a", watek="firma", zadanie_id="a3",
                       pokaz_sprawe=False)
    # Assert
    assert bez_watku == '<span class="k-ref">a3</span>'
    assert z_watkiem == '<span class="k-ref">wątek: firma · a3</span>'


def test_task_card_zrobione_formularz_z_tokenem_i_opisem(katalog):
    # Act
    html = render(katalog, "TaskCard", karta=karta())
    # Assert
    assert 'hx-post="/sprawa/sprawa-a/zadania/a3/zrobione"' in html
    assert 'name="token" value="token-testowy"' in html and 'name="widok" value="przeglad"' in html
    assert 'name="opis" value="Wyślij pismo"' in html
    assert "Osoba Testowa: 7 dni" in html and "urzędy zamknięte 13.10.2026 (test) — wyślij wcześniej" in html
    assert 'href="/sprawa/sprawa-a">sprawa-a</a>' in html and "Pokaż sprawę" in html


def test_task_card_escapuje_tekst_ze_sprawy(katalog):
    # Act
    html = render(katalog, "TaskCard", karta=karta(opis='<script>alert(1)</script>" onmouseover="x'))
    # Assert
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert '" onmouseover="x' not in html


def test_task_card_doreczenie_w_widoku_sprawy_ma_pole_daty(katalog):
    # Act
    html = render(katalog, "TaskCard", widok="sprawa", karta=karta("doreczenie"), pokaz_sprawe=False,
                  blad="Wpisz datę doręczenia.", wartosc="32.13.2026")
    # Assert
    assert 'hx-post="/sprawa/sprawa-a/zadania/a3/doreczenie"' in html
    assert '<label for="' in html and "Data doręczenia" in html and 'inputmode="numeric"' in html
    assert 'aria-invalid="true"' in html and 'role="alert"' in html and "Wpisz datę doręczenia." in html
    assert 'value="32.13.2026"' in html and "Zapisz doręczenie" in html
    assert "wątek: firma" in html and "Pokaż sprawę" not in html


def test_task_card_doreczenie_w_przegladzie_prowadzi_do_sprawy(katalog):
    # Act
    html = render(katalog, "TaskCard", karta=karta("doreczenie"))
    # Assert
    assert "Wpisz doręczenie" in html and 'href="/sprawa/sprawa-a#z-' in html and "<form" not in html


def test_task_card_polecenie_do_kopiowania_i_zrobione_jako_drugorzedne(katalog):
    # Act
    html = render(katalog, "TaskCard", karta=karta("polecenie"))
    # Assert
    assert 'value="/kruczek:eskalacja sprawa-a"' in html and "readonly" in html and "data-kopiuj=" in html
    assert 'aria-live="polite"' in html
    assert re.search(r'<button class="btn" data-variant="ghost" type="submit">.*Zrobione', html, re.DOTALL)


def test_task_card_wkrotce_bez_akcji(katalog):
    # Act
    html = render(katalog, "TaskCard", karta=karta(""))
    # Assert
    assert "<form" not in html and "Kopiuj" not in html


def test_start_steps_lista_krokow_i_polecenie(katalog):
    # Arrange
    kroki = [Zadanie("a1", "Ustalić dane", D(2026, 10, 1), zrobione=D(2026, 10, 2)),
             Zadanie("a2", "Nadać pismo", D(2026, 10, 1))]
    # Act
    html = render(katalog, "StartSteps", kroki=KartaKrokow("sprawa-a", kroki, 1, "Dalej ze sprawą sprawa-a"))
    # Assert
    assert "1 z 2 kroków" in html and 'data-state="done"' in html and "— zrobione" in html
    assert 'value="Dalej ze sprawą sprawa-a"' in html and "<form" not in html


def test_wait_row_w_widoku_sprawy_bez_linku_do_sprawy(katalog):
    # Arrange
    w = Wiersz("sprawa-a", "hourglass", "Czekam na odpowiedź: Firma X sp. z o.o.", "firma", "ok. 22.10.2026",
               "szacunek · zostały 2 dni")
    # Act
    przeglad = render(katalog, "WaitRow", wiersz=w)
    sprawa = render(katalog, "WaitRow", wiersz=w, pokaz_sprawe=False)
    # Assert
    assert 'href="/sprawa/sprawa-a"' in przeglad and "ok. 22.10.2026" in przeglad
    assert "href" not in sprawa and "wątek: firma" in sprawa


def test_timeline_dowody_jako_tekst_bez_linkow(katalog):
    # Arrange
    w = Wpis("09.10.2026", "in", "Odpowiedź", "proof", ["wątek: firma"], ["ARCHIWUM/2026-10-09_email.eml"])
    # Act
    html = render(katalog, "Timeline", wpisy=[w])
    # Assert
    assert "ARCHIWUM/2026-10-09_email.eml" in html and "<a" not in html
    assert 'data-kind="in"' in html and "Dowód" in html


def test_toaster_z_cofnij_wysyla_pola_formularzem(katalog):
    # Arrange
    p = Powiadomienie("Zapisano doręczenie 10.10.2026.", "/sprawa/sprawa-a/zdarzenia/z2/cofnij",
                      {"typ": "doreczenie", "data": "2026-10-10"})
    # Act
    html = render(katalog, "Toaster", powiadomienie=p)
    # Assert
    assert 'id="toaster"' in html and 'role="status"' in html and 'data-duration="8000"' in html
    assert 'hx-post="/sprawa/sprawa-a/zdarzenia/z2/cofnij"' in html and 'name="data" value="2026-10-10"' in html
    assert ">Cofnij</button>" in html


def test_komunikat_z_poleceniem_dla_claude(katalog):
    # Arrange
    k = Komunikat("Tego wpisu nie cofniesz już tutaj", "Popraw go w rozmowie z Claude:", "warning",
                  "/kruczek:chronologia sprawa-a")
    # Act
    html = render(katalog, "PageAlert", alert=k)
    # Assert
    assert 'data-variant="warning"' in html and 'role="alert"' in html
    assert 'value="/kruczek:chronologia sprawa-a"' in html


@pytest.mark.parametrize("nazwa, dane", [
    ("PageAlert", {"alert": Komunikat("Nie zapisano", "Pokazuję aktualny stan.", szczegoly="zadanie a2 już zrobione")}),
    ("ErrorPage", {"title": "Nie zapisano", "details": "zadanie a2 już zrobione"}),
], ids=["alert", "strona-bledu"])
def test_szczegoly_techniczne_zwiniete_tym_samym_komponentem(katalog, nazwa, dane):
    # Act
    html = render(katalog, nazwa, **dane)
    # Assert
    assert ('<details class="k-details"><summary>Szczegóły techniczne</summary>'
            "<pre>zadanie a2 już zrobione</pre></details>") in html


def test_komunikat_bez_szczegolow_nie_ma_details(katalog):
    # Act
    html = render(katalog, "PageAlert", alert=Komunikat("Nie zapisano", "Pokazuję aktualny stan."))
    # Assert
    assert "<details" not in html


def test_formularz_akcji_bez_przenoszenia_atrybutow_starego_elementu(katalog):
    # Arrange — htmx 4 w fazie settle kopiuje atrybuty ze starego elementu o tym samym id na nowy
    # (pole daty po 422 pokazywało starą wartość); settle:0 to wyłącza
    # Act
    html = render(katalog, "ActionForm", akcja="/sprawa/sprawa-a/zadania/a3/zrobione")
    # Assert
    assert 'hx-swap="outerHTML settle:0"' in html and 'hx-target="#tresc-dynamiczna"' in html


def test_layout_bez_kodu_inline_i_bez_zasobow_z_sieci(katalog):
    # Act
    html = render(katalog, "Layout", tytul="Co robić", _content="<p>x</p>")
    # Assert
    assert '<html lang="pl">' in html and '<a class="k-skip" href="#tresc">' in html and '<main id="tresc"' in html
    assert re.findall(r"<script[^>]*>", html) == ['<script src="/static/kruczek.js">',
                                                  '<script src="/static/htmx.min.js" defer>',
                                                  '<script src="/static/basecoat.min.js" defer>']
    assert "http://" not in html and "https://" not in html


def test_sekcje_w_widoku_sprawy_przekazuja_blad_i_wartosc_do_karty(katalog):
    # Arrange
    sekcje = EkranSekcji([], [karta("doreczenie")], [], [], [], None)
    # Act
    html = render(katalog, "Sections", widok="sprawa", s=sekcje, pokaz_sprawe=False,
                  bledy={"a3": "Wpisz datę doręczenia."}, wartosci={"a3": "32.13.2026"})
    # Assert
    assert "Wpisz datę doręczenia." in html and 'value="32.13.2026"' in html


def test_sekcje_w_widoku_sprawy_przekazuja_blad_i_wartosc_do_karty_po_terminie(katalog):
    # Arrange
    sekcje = EkranSekcji([karta("doreczenie", status="overdue")], [], [], [], [], None)
    # Act
    html = render(katalog, "Sections", widok="sprawa", s=sekcje, pokaz_sprawe=False,
                  bledy={"a3": "Wpisz datę doręczenia."}, wartosci={"a3": "32.13.2026"})
    # Assert
    assert 'aria-labelledby="s-po"' in html
    assert 'aria-invalid="true"' in html and "Wpisz datę doręczenia." in html and 'value="32.13.2026"' in html


def test_zaden_komponent_nie_ma_style_ani_handlerow_on():
    # Arrange — CSP: style-src 'self' i script-src 'self' blokują style="" i onclick=""
    zrodla = {p.name: p.read_text(encoding="utf-8") for p in KOMPONENTY.rglob("*.jinja")}
    # Act
    zle = [n for n, t in zrodla.items() if re.search(r"\sstyle=|\son[a-z]+=", t)]
    # Assert
    assert zle == []
