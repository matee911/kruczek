"""kontrola_logika.py — czyste funkcje logiki kontrola_pisma.py.

Bez I/O, bez subprocesów — wejście: tekst, wyjście: wynik. Testowalność bez PDF.
"""

import re
import collections

# Polskie cudzysłowy i angielskie — maskujemy cytaty, żeby nie wykryć nawiasów w cytatach
_QUOTE_RE = re.compile(r"[\u201e\u201c\"][^\u201d\u201c\"]{0,400}[\u201d\u201c\"]")

# Zawarto\u015b\u0107 nawiasu, kt\u00f3ra jest DAN\u0104, a nie polem do wype\u0142nienia: liczba, data, kwota
# \u2014 opcjonalnie z kr\u00f3tk\u0105 jednostk\u0105 na ko\u0144cu (z\u0142, PLN, dni, %, r.). Kluczowe jest to, \u017ce
# cz\u0119\u015b\u0107 liczbowa musi sta\u0107 NA POCZ\u0104TKU: "[123.45 z\u0142]" to dana, ale "[wpisz 3 dni]"
# zaczyna si\u0119 s\u0142owem i pozostaje polem do wype\u0142nienia.
#
# Bez tego kwota w nawiasie trafia\u0142a do listy niewype\u0142nionych p\u00f3l i BLOKOWA\u0141A wysy\u0142k\u0119
# gotowego pisma \u2014 fa\u0142szywy alarm na \u015bcie\u017cce heurystycznej (gdy kontroli nie podano --html).
_DANA_RE = re.compile(
    r"\[[\d.,:\s/-]+(?:\s*[A-Za-z\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b%]{1,4}\.?)?\]"
)


def find_placeholders(t: str) -> list:
    """Znajdź niewypełnione pola [w nawiasach] w tekście pisma.

    Maskuje cytaty w cudzysłowach — nawias w cytacie (np. „Re: [Zamówienie 2027]")
    nie jest polem do wypełnienia.

    >>> find_placeholders("Wzywa Pan [imię i nazwisko] do zapłaty.")
    ['[imię i nazwisko]']
    >>> find_placeholders('Temat: „Re: [Zamówienie 2027]" — brak reakcji.')
    []
    >>> find_placeholders("Kwota: [123.45 zł]")
    []
    >>> find_placeholders("Termin: [wpisz liczbę dni]")
    ['[wpisz liczbę dni]']
    >>> find_placeholders("Brak pól.")
    []
    >>> find_placeholders("[data doręczenia] i [numer sprawy]")
    ['[data doręczenia]', '[numer sprawy]']
    """
    tm = _QUOTE_RE.sub(lambda m: "\x00" * len(m.group(0)), t)
    return [
        x
        for x in re.findall(r"\[[^\]\n]{3,120}\]", tm)
        if not _DANA_RE.fullmatch(x) and re.search(r"[a-ząćęłńóśźż]", x)
    ]


def find_attachment_page_headers(t: str) -> list:
    """Znajdź nagłówki stron załączników: 'Załącznik nr N — Tytuł'.

    Forma skrócona ("zał. nr 2") NIE jest nagłówkiem strony załącznika — obsługuje ją
    find_cross_references jako odesłanie w treści. Gdyby łapać ją i tutaj, każde zdanie
    odsyłające do załącznika liczyłoby się jako jego strona i kontrola zgłaszałaby
    nieistniejący rozjazd między listą a stronami.

    >>> find_attachment_page_headers("Załącznik nr 1 — Umowa z dnia 01.01.2026")
    [('1', 'Umowa z dnia 01.01.2026')]
    >>> find_attachment_page_headers("Zal. nr 2 - Faktura VAT")
    []
    >>> find_attachment_page_headers("Brak załączników.")
    []
    >>> find_attachment_page_headers("Załącznik nr 1 — Umowa\\nZałącznik nr 2 — Faktura")
    [('1', 'Umowa'), ('2', 'Faktura')]
    """
    return re.findall(r"Za[łl][ąa]cznik\s+nr\s+(\d+)\s*[—–-]\s*(.+)", t, re.I)


def find_attachment_list_items(t: str) -> list:
    """Znajdź pozycje listy załączników: 'Załącznik nr N: Tytuł'.

    >>> find_attachment_list_items("Załącznik nr 1: Umowa (plik umowa.pdf)")
    [('1', 'Umowa (plik umowa.pdf)')]
    >>> find_attachment_list_items("Brak.")
    []
    >>> find_attachment_list_items("Załącznik nr 1: Umowa\\nZałącznik nr 2: Faktura")
    [('1', 'Umowa'), ('2', 'Faktura')]
    """
    return re.findall(r"Za[łl][ąa]cznik\s+nr\s+(\d+):\s*(.+)", t, re.I)


def find_cross_references(t: str) -> set:
    """Znajdź numery załączników przywołanych w treści pisma.

    >>> find_cross_references("Dowód w zał. 1 oraz załączniku nr 2.")
    {1, 2}
    >>> find_cross_references("Zob. zał. 3.")
    {3}
    >>> find_cross_references("Brak odesłań.")
    set()
    >>> find_cross_references("zał. 1 i zał. 1")
    {1}
    """
    refs = {int(x) for x in re.findall(r"zał\.\s*(\d+)", t, re.I)}
    refs |= {
        int(x)
        for x in re.findall(
            r"za[łl][ąa]cznik(?:a|iem|u|ach|ow|ów)?\s+nr\s*(\d+)", t, re.I
        )
    }
    return refs


def find_numbering_gaps_and_duplicates(numbers: list) -> tuple:
    """Znajdź dziury i duplikaty w liście numerów załączników.

    Zwraca (braki, duplikaty).

    >>> find_numbering_gaps_and_duplicates([1, 2, 3])
    ([], [])
    >>> find_numbering_gaps_and_duplicates([1, 3])
    ([2], [])
    >>> find_numbering_gaps_and_duplicates([1, 1, 2])
    ([], [1])
    >>> find_numbering_gaps_and_duplicates([])
    ([], [])
    >>> find_numbering_gaps_and_duplicates([1, 2, 2, 4])
    ([3], [2])
    """
    if not numbers:
        return [], []
    expected = list(range(1, max(numbers) + 1))
    gaps = sorted(set(expected) - set(numbers))
    dups = sorted(n for n, c in collections.Counter(numbers).items() if c > 1)
    return gaps, dups


def titles_match(title_on_page: str, title_on_list: str) -> bool:
    """Sprawdź czy tytuł na stronie załącznika zgadza się z tytułem na liście.

    Lista może mieć sufiks '(plik ...)' — jest ignorowany przy porównaniu.
    Porównanie metodą podzbioru (jeden zawiera drugi).

    >>> titles_match("Umowa z dnia 01.01.2026", "Umowa z dnia 01.01.2026 (plik umowa.pdf)")
    True
    >>> titles_match("Umowa najmu", "Faktura VAT")
    False
    >>> titles_match("Analiza techniczna wiadomości", "Analiza techniczna wiadomości")
    True
    >>> titles_match("Pełnomocnictwo", "Pełnomocnictwo (plik pelno.pdf)")
    True
    """
    a1 = re.sub(r"\s+", " ", title_on_page).strip().lower()
    a2 = re.sub(r"\(plik.*?\)", "", title_on_list).strip().lower()
    a2 = re.sub(r"\s+", " ", a2).strip()
    if not a2:
        return True
    return a2 in a1 or a1 in a2


def find_paragraph_numbering_issues(t: str) -> tuple:
    """Znajdź duplikaty i przeskoki w numeracji ustępów.

    Zwraca (duplikaty, przeskoki) gdzie przeskoki to lista (poprzedni, następny).

    >>> find_paragraph_numbering_issues("1.  Pierwsze.\\n2.  Drugie.\\n3.  Trzecie.")
    ([], [])
    >>> find_paragraph_numbering_issues("1.  Pierwsze.\\n3.  Trzecie.")
    ([], [(1, 3)])
    >>> find_paragraph_numbering_issues("1.  Pierwsze.\\n1.  Drugie.")
    ([1], [])
    >>> find_paragraph_numbering_issues("Brak numeracji.")
    ([], [])
    """
    ust = [
        int(m.group(1)) for m in re.finditer(r"^\s{0,8}(\d{1,3})\.\s{2,}\S", t, re.M)
    ]
    if not ust:
        return [], []
    dups = sorted(n for n, c in collections.Counter(ust).items() if c > 1)
    jumps = [
        (ust[i], ust[i + 1])
        for i in range(len(ust) - 1)
        if ust[i + 1] - ust[i] not in (0, 1)
    ]
    return dups, jumps


def find_sha256_hashes(t: str) -> set:
    """Wyciągnij sumy SHA-256 (64 hex znaki) z tekstu pisma.

    >>> find_sha256_hashes("SHA-256: 4f3548f05b0e47d9fa6ddd1e658fb7dee0c2a3c96a479f3c8770e18aeb8bb7e7")
    {'4f3548f05b0e47d9fa6ddd1e658fb7dee0c2a3c96a479f3c8770e18aeb8bb7e7'}
    >>> find_sha256_hashes("Brak sum.")
    set()
    >>> len(find_sha256_hashes("a" * 64 + " " + "b" * 64))
    2
    >>> find_sha256_hashes("za krótkie: " + "a" * 63)
    set()
    """
    return set(re.findall(r"\b([0-9a-f]{64})\b", t))
