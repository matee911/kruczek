"""Formularze zapisu jako modele pydantic — tylko kształt pól: które są, jakiego typu, jakie wartości wolno.

Reguły zostają tam, gdzie były: datę doręczenia (dd.mm.rrrr, nie z przyszłości) sprawdza
format.data_doreczenia, a „nie przed nadaniem” i „to nadal to samo zadanie” — kruczek_core. Token
sesji sprawdza zaleznosci.z_tej_strony, zanim cokolwiek z formularza zostanie użyte. Błędy kształtu
trafiają na stronę po polsku (ekrany.komunikat_formularza), nigdy jako komunikaty pydantic.
"""

from typing import Literal

from pydantic import BaseModel


class FormularzAkcji(BaseModel):
    """Pola wspólne: który widok odświeżyć po zapisie. Pole `token` pomija model (sprawdza je zależność)."""

    widok: Literal["przeglad", "sprawa"] = "przeglad"


class FormularzZadania(FormularzAkcji):
    """„Zrobione” i „Cofnij” po nim: opis zadania, które widziała strona (kontrola tożsamości w rdzeniu)."""

    opis: str
