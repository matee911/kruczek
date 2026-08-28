#!/usr/bin/env python3
"""run_tests.py — jeden punkt wejścia do wszystkich testów kruczka.

Odkrywa testy zamiast wymieniać je z nazwy. Powód: dopóki CI wołało konkretne pliki,
dołożenie nowego pliku testowego albo doctestu w nowym module nie uruchamiało niczego
i nikt tego nie zauważał — test, który nie chodzi, jest gorszy niż jego brak, bo daje
fałszywe poczucie pokrycia.

Zbiera dwa rodzaje testów:
  * unittest — wszystkie scripts/test_*.py
  * doctest  — ze WSZYSTKICH importowalnych modułów w scripts/

Drugie działa dopiero od czasu, gdy skrypty CLI dostały podkreślenia zamiast myślników
(myślnik jest niedozwolony w nazwie modułu Pythona). Każdy skrypt ma
`if __name__ == "__main__"`, więc import nie odpala nic poza definicjami.

Tylko stdlib — kruczek nie ma zależności runtime i nie zamierza ich mieć.

Użycie:
    run_tests.py            # wszystko
    run_tests.py -v         # z listą testów
"""

import doctest
import importlib
import os
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def moduly():
    """Nazwy importowalnych modułów w scripts/, bez plików testowych.

    Pomijamy pliki z myślnikiem w nazwie — gdyby taki wrócił do repo, nie jest
    modułem i import by się wywalił. Zamiast przemilczeć, mówimy o tym głośno
    w main().
    """
    out, nieimportowalne = [], []
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py") or fn.startswith("test_"):
            continue
        stem = fn[:-3]
        if stem == "run_tests":
            continue
        if "-" in stem:
            nieimportowalne.append(fn)
            continue
        out.append(stem)
    return out, nieimportowalne


def zbuduj_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.discover(SCRIPTS, pattern="test_*.py", top_level_dir=SCRIPTS))

    nazwy, nieimportowalne = moduly()
    z_doctestami = []
    for nazwa in nazwy:
        mod = importlib.import_module(nazwa)
        try:
            suite.addTests(doctest.DocTestSuite(mod))
        except ValueError:
            # DocTestSuite rzuca ValueError, gdy moduł nie ma ANI JEDNEGO doctestu.
            # To nie jest błąd — większość skryptów CLI ich nie ma.
            continue
        z_doctestami.append(nazwa)

    return suite, z_doctestami, nieimportowalne


def main():
    verbosity = 2 if "-v" in sys.argv else 1
    sys.path.insert(0, SCRIPTS)

    suite, z_doctestami, nieimportowalne = zbuduj_suite()

    print(f"Moduły z doctestami: {', '.join(z_doctestami) or 'brak'}")
    if nieimportowalne:
        print(
            "UWAGA — pominięto (myślnik w nazwie, nie da się zaimportować): "
            + ", ".join(nieimportowalne)
        )

    wynik = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if wynik.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
