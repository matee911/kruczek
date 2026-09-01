"""eml_forensics_raport.py — renderowanie sekcji raportu markdown.

Bez I/O — wejście: fakty wyekstrahowane przez eml_forensics_logika.py, wyjście: linie
markdown dopisywane przez callback W (zwykle `list.append`). Orchestracja (CLI, zapis
plików, argparse) żyje w eml_forensics.py.

Zasady redakcyjne, wymuszone przez wnioski z niezależnych przeglądów raportów:

1. **Cytat jest cytatem.** Blok ``` zawiera dosłowną wartość jednego nagłówka,
   podpisaną jego nazwą. Nigdy sklejki kilku nagłówków.
2. **Nie ma pola „typowe wartości”.** Każda lista pochodzi z pliku; jeśli czegoś
   nie ma, raport pisze, że tego nie ma.
3. **Fakt negatywny jest ustaleniem.** „Brak załączników”, „brak Reply-To”,
   „zero obrazów” — stwierdzane wprost, nie przemilczane.
4. **Zero kwalifikacji.** Raport nie pisze, czy coś jest podszyciem, obfuskacją,
   spamem ani czy wysyłka jest „uwierzytelniona”. Podaje wartość, źródło i zakres
   tego, co dana wartość obejmuje. Wnioski wyciąga człowiek.
5. **Kategoria danej jest widoczna.** Adres publiczny nie stoi w jednej liście
   z identyfikatorem wewnętrznym ani z wartością zadeklarowaną przez klienta.
"""

import datetime
import itertools
import re
import zoneinfo
from collections.abc import Callable, Iterable

from eml_forensics_logika import (
    Address,
    Alignment,
    ArcSet,
    Artifact,
    AuthHeader,
    DkimSignature,
    DomainRef,
    HiddenElement,
    HtmlComment,
    HtmlResource,
    MimePart,
    NetAddress,
    ReceivedHop,
    StylesheetRule,
    Token,
    auth_methods_by_name,
    classify_comments,
    deobfuscate,
    describe_protocol,
    document_metadata,
    find_word_splitting_spans,
    glued_tag_boundaries,
    html_document_structure,
    invalid_hostnames,
    message_id_parts,
    mixed_character_encodings,
    named_entities,
    numeric_entities,
    parse_date_header,
    parse_dcc_metrics,
    received_chain_continuity,
    split_quoted,
    unusual_characters,
)

type WriteLine = Callable[[str], None]

#: Strefa czasowa odbiorcy. Stały offset +2 był błędem: dla wiadomości z okresu
#: zimowego (CET = UTC+1) raport podawał czas lokalny przesunięty o godzinę —
#: w całym korpusie, nie tylko w jednym pliku. `zoneinfo` zna reguły przejścia.
WARSAW = zoneinfo.ZoneInfo("Europe/Warsaw")


def escape_pipe(text: object) -> str:
    r"""Escape'uje pipe'y dla tabeli markdown.

    >>> print(escape_pipe("a|b"))
    a\|b
    >>> print(escape_pipe("bez pipe'ow"))
    bez pipe'ow
    """
    return str(text).replace("|", "\\|")


def code(text: object) -> str:
    """Wartość w backtickach, z zabezpieczeniem pipe'ów i pustki.

    >>> code("abc")
    '`abc`'
    >>> code(None)
    '—'
    >>> code("")
    '—'
    >>> code("a|b")
    '`a\\\\|b`'
    """
    if text is None or str(text) == "":
        return "—"
    return f"`{escape_pipe(text)}`"


def write_no_findings(W: WriteLine, message: str) -> None:
    """Stwierdzenie negatywne — pełnoprawne ustalenie, nie luka w raporcie.

    >>> lines = []
    >>> write_no_findings(lines.append, "Brak nagłówka X")
    >>> lines
    ['**Ustalenie negatywne:** Brak nagłówka X\\n']
    """
    W(f"**Ustalenie negatywne:** {message}\n")


def write_table_or_finding(
    W: WriteLine,
    headers: list[str],
    rows: Iterable[list[str]],
    empty_message: str,
) -> int:
    """Tabela, a gdy nie ma czego pokazać — ustalenie negatywne. Nigdy cisza.

    Zdejmuje najczęstszy kształt w tym module: 42 wywołania `write_table`
    i 63 `write_no_findings` to w większości ta sama para „są dane / nie ma
    danych”, rozpisywana ręcznie przy każdej sekcji. Rozpisywana ręcznie
    bywała też **niekompletna** — gałąź pusta gdzieniegdzie nie pisała nic,
    więc czytelnik nie odróżniał „sprawdzone, brak” od „niesprawdzone”.

    >>> lines = []
    >>> write_table_or_finding(lines.append, ["A"], [["1"]], "Brak A.")
    1
    >>> lines[0]
    '| A |'
    >>> lines = []
    >>> write_table_or_finding(lines.append, ["A"], [], "Brak A.")
    0
    >>> lines
    ['**Ustalenie negatywne:** Brak A.\\n']
    """
    written = write_table(W, headers, rows)
    if not written:
        write_no_findings(W, empty_message)
    return written


def row(*cells: object) -> list[str]:
    """Wiersz tabeli z `code()` nałożonym na każdą komórkę.

    `code(...)` występuje w tym module **148 razy**, prawie zawsze w komórce
    wiersza. Mapowanie po wierszu zamiast po komórce skraca wywołania i usuwa
    klasę literówek, w której jedna komórka z pięciu zostawała bez `code()`.

    >>> row("a", None, 7)
    ['`a`', '—', '`7`']
    """
    return [code(c) for c in cells]


def labelled_rows(pairs: Iterable[tuple[str, object]]) -> list[list[str]]:
    """Wiersze „etykieta → wartość” z pominięciem pozycji bez wartości.

    Kształt `[[etykieta, code(wartosc)] ...]` z filtrem `!= "—"` powtarza się
    w tabelach tagów podpisów, pól skoku i cech pliku.

    >>> labelled_rows([("`d=`", "a.pl"), ("`l=`", None)])
    [['`d=`', '`a.pl`']]
    """
    return [[label, code(value)] for label, value in pairs if code(value) != "—"]


def write_table(W: WriteLine, headers: list[str], rows: Iterable[list[str]]) -> int:
    """Tabela markdown bez pustych linii w środku — te łamały render w §2.5 i §6.5.

    Zwraca liczbę wypisanych wierszy, żeby wołający nie musiał materializować
    iteratora po raz drugi.

    >>> lines = []
    >>> write_table(lines.append, ["A", "B"], [["1", "2"], ["3", "4"]])
    2
    >>> lines
    ['| A | B |', '|---|---|', '| 1 | 2 |', '| 3 | 4 |', '']
    >>> lines = []
    >>> write_table(lines.append, ["A"], [])
    0
    >>> lines
    []
    """
    materialized = [list(row) for row in rows]
    if not materialized:
        return 0
    W("| " + " | ".join(headers) + " |")
    W("|" + "---|" * len(headers))
    for row in materialized:
        W("| " + " | ".join(row) + " |")
    W("")
    return len(materialized)


def format_local(dt: datetime.datetime) -> str:
    """Czas w strefie z nagłówka, w UTC i w czasie warszawskim — trzy zapisy, jeden moment.

    Raporty podawały wyłącznie UTC, przez co godzina w nazwie pliku (`1408`)
    nie zgadzała się z niczym w materiale.

    >>> dt = datetime.datetime(2026, 8, 20, 12, 8, 26, tzinfo=datetime.timezone.utc)
    >>> format_local(dt)
    '2026-08-20 12:08:26 +0000 | 2026-08-20 12:08:26 UTC | 2026-08-20 14:08:26 CEST'

    Zimą obowiązuje CET (UTC+1) — stały offset +2 dawał tu godzinę 10:29:

    >>> zima = datetime.datetime(2025, 12, 2, 8, 29, 38, tzinfo=datetime.timezone.utc)
    >>> format_local(zima)
    '2025-12-02 08:29:38 +0000 | 2025-12-02 08:29:38 UTC | 2025-12-02 09:29:38 CET'
    """
    original = dt.strftime("%Y-%m-%d %H:%M:%S %z")
    utc = dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    warsaw = dt.astimezone(WARSAW)
    local = warsaw.strftime("%Y-%m-%d %H:%M:%S ") + (warsaw.tzname() or "")
    return f"{original} | {utc} | {local}"


def format_duration(seconds: float) -> str:
    """Sekundy w formie czytelnej — `20278s` nic nie mówi, `5 h 37 min 58 s` mówi.

    >>> format_duration(0)
    '0 s'
    >>> format_duration(2186)
    '36 min 26 s (2186 s)'
    >>> format_duration(20278)
    '5 h 37 min 58 s (20278 s)'
    >>> format_duration(-3)
    '-3 s'
    """
    total = int(seconds)
    if abs(total) < 60:
        return f"{total} s"
    sign = "-" if total < 0 else ""
    total = abs(total)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts = ([f"{hours} h"] if hours else []) + [f"{minutes} min", f"{secs} s"]
    return f"{sign}{' '.join(parts)} ({sign}{total} s)"


# ──────────────────────────── 1. identyfikacja ────────────────────────────


def write_identification(
    addresses: dict[str, list[Address]],
    subject: str | None,
    date_value: str | None,
    literal_vs_parsed: tuple[tuple[str, str | None, str | None], ...],
    header_list: tuple[str, ...],
    W: WriteLine,
) -> None:
    """Sekcja 1: adresy z rozbiciem na nazwę wyświetlaną, część lokalną i domenę.

    Nazwa wyświetlana bywa jedyną nośną daną w nagłówku (`From: Google
    <nadawca@niepowiązana.pl>`), a tag `+` w części lokalnej wskazuje kanał
    pozyskania adresu. Poprzednia wersja przepisywała cały nagłówek jednym
    ciągiem, przez co ani jedno, ani drugie nie było danymi w raporcie.

    >>> lines = []
    >>> addrs = {"From": [Address("Marka", "nadawca@wysylka.pl")],
    ...          "To": [Address("", "klient+kanal@odbiorca.pl")]}
    >>> porownania = (("Subject", "Temat", "Temat"),
    ...                ("Date", "Mon, 1 Jun 2026 10:34:21 +0000",
    ...                 "Mon, 01 Jun 2026 10:34:21 +0000"))
    >>> write_identification(addrs, "Temat", "Mon, 01 Jun 2026 10:34:21 +0000",
    ...                      porownania, ("From", "To", "Subject"), lines.append)
    >>> out = "\\n".join(lines)
    >>> "Marka" in out and "wysylka.pl" in out
    True
    >>> "klient+kanal@odbiorca.pl" in out
    True
    >>> "kanal" in out
    True

    Wartość dosłowna stoi obok sparsowanej — parser dopełnia dzień zerem,
    a raport podawał tę formę z etykietą „dosłownie z nagłówka”:

    >>> "Mon, 1 Jun 2026" in out and "Mon, 01 Jun 2026" in out
    True
    >>> "Nagłówków w pliku: **3**" in out
    True

    Nagłówek, w którym bajty i wynik parsera są identyczne, NIE trafia do tabeli
    rozbieżności — wcześniej stał tam `Date` ze zgodnymi kolumnami, a pod spodem
    zdanie „wartości różnią się”:

    >>> "Bajty z pliku są identyczne" in out and "`Subject`" in out
    True
    >>> "Nagłówków, w których bajty z pliku różnią się od wyniku parsera: **1**" in out
    True
    """
    W("## 1. Identyfikacja\n")
    if header_list:
        W(
            f"Nagłówków w pliku: **{len(header_list)}**, nazw unikalnych: "
            f"**{len({h.lower() for h in header_list})}**.\n"
        )
        W("```")
        W(", ".join(header_list))
        W("```\n")
    rows = []
    for header, entries in addresses.items():
        for address in entries:
            rows.append(
                [
                    code(header),
                    escape_pipe(address.display_name) or "—",
                    code(address.addr_spec),
                    code(address.domain),
                    code(address.tag),
                ]
            )
    write_table_or_finding(
        W,
        ["Nagłówek", "Nazwa wyświetlana", "Adres", "Domena", "Tag w części lokalnej"],
        rows,
        "Brak nagłówków adresowych.",
    )

    # Do tabeli trafiają WYŁĄCZNIE nagłówki, w których bajty z pliku różnią się
    # od wyniku parsera. Wcześniej wchodził tu także `Date` z identycznymi
    # kolumnami, a pod spodem stało zdanie „wartości różnią się” — czytelnik
    # dostawał ustalenie o rozbieżności tam, gdzie rozbieżności nie ma.
    comparisons = [
        (name, literal, str(sparsowane))
        for name, literal, sparsowane in (literal_vs_parsed or ())
        if literal and sparsowane and literal != str(sparsowane)
    ]
    identical_rows = [
        name
        for name, literal, sparsowane in (literal_vs_parsed or ())
        if literal and sparsowane and literal == str(sparsowane)
    ]
    if comparisons:
        write_table(
            W,
            ["Nagłówek", "Wartość dosłowna (bajty z pliku)", "Wartość po sparsowaniu"],
            [
                row(name, literal, sparsowane)
                for name, literal, sparsowane in comparisons
            ],
        )
        W(
            f"Nagłówków, w których bajty z pliku różnią się od wyniku parsera: "
            f"**{len(comparisons)}**. Przyczyną bywa kodowanie RFC 2047, zwinięcie "
            f"na kilka linii albo normalizacja parsera (np. dopełnienie dnia zerem); "
            f"kolumna druga to bajty z pliku, trzecia to wynik parsera.\n"
        )
    if identical_rows:
        write_no_findings(
            W,
            "Bajty z pliku są identyczne z wynikiem parsera w nagłówkach: "
            + ", ".join(code(n) for n in identical_rows)
            + " — nie ma tam kodowania ani zwinięcia.",
        )

    # Bez .lower(): przy nazwie wyświetlanej podszywającej się pod markę
    # wielkość liter jest cechą dowodu, a proza pod tabelą podawała `google`
    # tam, gdzie w pliku bajtowo stoi `Google`.
    display_names = {
        a.display_name.strip()
        for a in addresses.get("From", [])
        if a.display_name.strip()
    }
    from_domains = {a.domain for a in addresses.get("From", []) if a.domain}
    if display_names and from_domains:
        W(
            "\nNazwa wyświetlana w `From`: "
            + ", ".join(code(n) for n in sorted(display_names))
            + " — domena adresu: "
            + ", ".join(code(d) for d in sorted(from_domains))
            + ". Zestawienie podane bez oceny zgodności.\n"
        )
    W("")


def write_mime_section(
    tree: list[MimePart], attachments: list[MimePart], W: WriteLine
) -> None:
    """Sekcja 1.5: drzewo MIME z zagnieżdżeniem i jawne ustalenie o załącznikach.

    >>> lines = []
    >>> tree = [MimePart(0, "multipart/related", None, None, None, None, None, None, None),
    ...         MimePart(1, "multipart/alternative", None, None, None, None, None, None, None),
    ...         MimePart(2, "text/plain", "utf-8", "8bit", None, None, None, 12, "aa"),
    ...         MimePart(2, "text/html", "utf-8", "8bit", None, None, None, 34, "bb")]
    >>> write_mime_section(tree, [], lines.append)
    >>> out = "\\n".join(lines)
    >>> "multipart/alternative" in out
    True
    >>> "Brak załączników" in out
    True

    Brak części tekstowej jest ustaleniem, nie przemilczeniem:

    >>> lines = []
    >>> write_mime_section([MimePart(0, "text/html", "utf-8", "base64", None, None, None, 9, "cc")],
    ...                    [], lines.append)
    >>> "Brak części `text/plain`" in "\\n".join(lines)
    True
    """
    W("## 2. Struktura MIME i załączniki\n")
    if not tree:
        write_no_findings(W, "Brak części MIME.")
        W("")
        return

    W("```")
    for part in tree:
        prefix = "  " * part.depth + ("└─ " if part.depth else "")
        details = []
        if part.charset:
            details.append(f"charset={part.charset}")
        if part.encoding:
            details.append(part.encoding)
        if part.size is not None:
            details.append(f"{part.size} B")
        if part.filename:
            details.append(f"nazwa={part.filename}")
        if part.content_id:
            details.append(f"cid={part.content_id}")
        suffix = f"  ({', '.join(details)})" if details else ""
        W(f"{prefix}{part.content_type}{suffix}")
    W("```\n")
    W(
        "Rozmiary to liczba bajtów **po zdekodowaniu** transfer-encoding, "
        "z zakończeniami linii takimi, jakie są w pliku (CRLF liczy się jako "
        "dwa bajty). Zapisane artefakty `_tresc.*` mają te same bajty.\n"
    )

    types = {p.content_type for p in tree}
    if "text/plain" not in types:
        write_no_findings(
            W, "Brak części `text/plain` (wiadomość nie ma alternatywy tekstowej)."
        )
    if "text/html" not in types:
        write_no_findings(W, "Brak części `text/html`.")

    if attachments:
        write_table(
            W,
            [
                "Nazwa",
                "Typ",
                "Content-Disposition",
                "Content-ID",
                "Rozmiar (B)",
                "SHA-256",
            ],
            [
                [
                    code(a.filename),
                    code(a.content_type),
                    code(a.disposition),
                    code(a.content_id),
                    str(a.size if a.size is not None else "—"),
                    code(a.sha256),
                ]
                for a in attachments
            ],
        )
        inline = [a for a in attachments if a.disposition == "inline" or a.content_id]
        if inline:
            W(
                f"Części osadzone (`cid:`, ładowane z wnętrza wiadomości): **{len(inline)}**. "
                "Ich wyświetlenie nie powoduje żądania sieciowego.\n"
            )
        by_hash: dict[str, list[str]] = {}
        for part in attachments:
            if part.sha256:
                by_hash.setdefault(part.sha256, []).append(
                    part.filename or part.content_type
                )
        duplicates = {h: names for h, names in by_hash.items() if len(names) > 1}
        if duplicates:
            W(
                f"Części **bajtowo identyczne**: {sum(len(n) for n in duplicates.values())} "
                f"z {len(attachments)}; unikalnych: **{len(by_hash)}**.\n"
            )
            write_table(
                W,
                ["SHA-256", "Części o tej samej zawartości"],
                [
                    [code(digest), escape_pipe(", ".join(names))]
                    for digest, names in duplicates.items()
                ],
            )
        elif len(attachments) > 1:
            write_no_findings(W, "Żadne dwie części nie mają identycznej zawartości.")
    else:
        write_no_findings(
            W,
            "Brak załączników (`Content-Disposition: attachment`) i części osadzonych.",
        )
    W("")


# ──────────────────────────── 2. trasa ────────────────────────────


def write_received_section(
    hops: list[ReceivedHop], addresses: list[NetAddress], W: WriteLine
) -> None:
    """Sekcja 2: skoki Received z pełnym cytatem i adresy rozdzielone na kategorie.

    >>> lines = []
    >>> hop = ReceivedHop.parse("from mta.a.pl (mta.a.pl. [188.33.160.214]) by mx.b.pl "
    ...                          "with ESMTPA id X1 for <k+t@b.pl>; "
    ...                          "Tue, 21 Jul 2026 13:36:02 +0200", 1)
    >>> addrs = [NetAddress("188.33.160.214", "Received skok 1 (from)", "publiczny")]
    >>> write_received_section([hop], addrs, lines.append)
    >>> out = "\\n".join(lines)
    >>> "ESMTPA" in out and "mta.a.pl" in out
    True
    >>> "k+t@b.pl" in out
    True
    >>> "publiczny" in out
    True

    >>> lines = []
    >>> write_received_section([], [], lines.append)
    >>> "Brak nagłówków Received" in "\\n".join(lines)
    True
    """
    W("## 3. Droga wiadomości (Received, od najstarszego)\n")
    if not hops:
        # Wyjście z całej sekcji zabierało ze sobą inwentarz adresów, więc
        # wiadomość bez `Received`, ale z `X-Originating-IP` albo `client-ip=`
        # w `Received-SPF`, gubiła jedyny zapisany w pliku adres nadawcy.
        write_no_findings(W, "Brak nagłówków Received.")
        if addresses:
            W("\n**Adresy sieciowe występujące w wiadomości** (poza `Received`):\n")
            write_table(
                W,
                ["Adres", "Rola", "Kategoria"],
                [[code(a.value), escape_pipe(a.role), a.category] for a in addresses],
            )
        W("")
        return

    external = [h for h in hops if not h.is_internal]
    W(
        f"Skoków `Received` ogółem: **{len(hops)}**, w tym z klauzulą `from` "
        f"(przekazanie między hostami): **{len(external)}**, bez klauzuli `from` "
        f"(przekazanie wewnątrz jednej infrastruktury): **{len(hops) - len(external)}**.\n"
    )

    for hop in hops:
        W(
            f"### Skok {hop.index}{' — bez klauzuli `from`' if hop.is_internal else ''}\n"
        )
        W("```")
        W(hop.raw.strip())
        W("```\n")
        rows = [
            ["HELO (deklaracja klienta)", code(hop.helo)],
            [
                "rDNS (ustalony przez serwer)",
                "**nieustalony** (serwer zapisał `unknown`)"
                if (hop.rdns or "").lower() == "unknown"
                else code(hop.rdns),
            ],
            ["Adres IP", code(hop.ip)],
            ["by", code(hop.by)],
            ["Adres IP hosta `by`", code(hop.by_ip)],
            ["Protokół", code(hop.protocol)],
            ["Protokół — rozwinięcie", describe_protocol(hop.protocol) or "—"],
            ["TLS", code(hop.tls)],
            ["id", code(hop.queue_id)],
            ["for", code(hop.for_address)],
            [
                "Znacznik czasu",
                code(format_local(hop.timestamp)) if hop.timestamp else "—",
            ],
        ]
        write_table(W, ["Pole", "Wartość"], [r for r in rows if r[1] != "—"])
        # Wiersze puste są odfiltrowane, więc czytelnik nie odróżnia „pola nie
        # ma w nagłówku” od „parser go nie odczytał”. Dla pól, które niosą
        # dowód o pochodzeniu, mówimy to wprost.
        missing = [
            label
            for label, value in (
                ("rDNS (nazwa odwrotna klienta)", hop.rdns),
                ("HELO (nazwa zadeklarowana przez klienta)", hop.helo),
                ("Znacznik czasu", hop.timestamp),
            )
            if not value
        ]
        if missing:
            write_no_findings(
                W,
                f"Skok {hop.index} nie zawiera pól: "
                + ", ".join(f"**{e}**" for e in missing)
                + ". Brak rDNS znaczy, że serwer przyjmujący nie ustalił nazwy "
                "odwrotnej klienta albo jej nie zapisał.",
            )

    continuity = received_chain_continuity(hops)
    if continuity:
        # Test ciągłości: host, który przyjął wiadomość (`by`), powinien być
        # tym, który ją dalej nadaje (`from`). Raport liczył skoki i orzekał
        # o poprawności składniowej nazw, ale tego zestawienia nie robił —
        # a przerwa w łańcuchu to odcinek drogi bez żadnego nagłówka.
        W("\n**Ciągłość łańcucha — `by` skoku N wobec `from` skoku N+1:**\n")
        write_table(
            W,
            ["Przejście", "`by` skoku N", "`from` skoku N+1", "Zgodne?"],
            [
                [
                    f"{number} → {number + 1}",
                    code(receiver),
                    code(sender),
                    "tak" if matches else "**nie**",
                ]
                for number, receiver, sender, matches in continuity
            ],
        )
        gaps = [c for c in continuity if not c[3]]
        if gaps:
            W(
                f"Przejść, w których nazwy się nie zgadzają: **{len(gaps)}**. "
                f"Dla takiego odcinka plik nie zawiera nagłówka dokumentującego, "
                f"jak wiadomość trafiła z jednego hosta na drugi.\n"
            )
        else:
            write_no_findings(
                W,
                "Każdy skok zaczyna się na hoście, na którym skończył się "
                "poprzedni — łańcuch nie ma nieudokumentowanych odcinków.",
            )

    if addresses:
        W("**Adresy sieciowe występujące w wiadomości** (rozdzielone wg kategorii):\n")
        write_table(
            W,
            ["Adres", "Rola / źródło", "Kategoria"],
            [[code(a.value), a.role, a.category] for a in addresses],
        )
        routable = list(
            dict.fromkeys(a.value for a in addresses if a.category == "publiczny")
        )
        if routable:
            W(
                "Adresów unikalnych w kategorii `publiczny`: **"
                + str(len(routable))
                + "** — "
                + ", ".join(code(value) for value in routable)
                + ". Pozostałe pozycje tabeli to identyfikatory wewnętrzne "
                "albo adresy nieroutowalne — kategoria każdej z nich jest "
                "podana w kolumnie obok.\n"
            )
        else:
            write_no_findings(
                W, "Żaden z zebranych adresów nie należy do kategorii `publiczny`."
            )
    else:
        write_no_findings(W, "Nie znaleziono adresów IP w nagłówkach.")

    # Literał adresowy w HELO/EHLO ma być wg RFC 5321 §4.1.3 własnym adresem
    # klienta. Sprawdzanie tego WYŁĄCZNIE w parze z ustalonym publicznym IP
    # sprawiało, że skok deklarujący `helo=[127.0.0.1]` bez zapisanego adresu
    # źródłowego nie dawał żadnego ustalenia — a deklaracja jest w pliku.
    nonroutable_helo = [
        h
        for h in hops
        if h.helo
        and NetAddress.classify(h.helo.strip("[]"))
        not in {"nie jest adresem IP", "publiczny"}
    ]
    if nonroutable_helo:
        W(
            "\n**Skoki, w których klient zadeklarował w HELO adres nieroutowalny** "
            "(RFC 5321 §4.1.3 wymaga, by literał w EHLO był własnym adresem "
            "klienta):\n"
        )
        write_table(
            W,
            [
                "Skok",
                "HELO (deklaracja klienta)",
                "Kategoria adresu z HELO",
                "Adres źródłowy ustalony przez serwer",
            ],
            [
                [
                    str(h.index),
                    code(h.helo),
                    NetAddress.classify((h.helo or "").strip("[]")),
                    code(h.ip) if h.ip else "brak w nagłówku",
                ]
                for h in nonroutable_helo
            ],
        )

    invalid = invalid_hostnames(hops)
    if invalid:
        W("\n**Nazwy hostów niezgodne ze składnią RFC 1035:**\n")
        write_table(
            W,
            ["Miejsce", "Wartość", "Na czym polega niezgodność"],
            [[role, code(value), note] for role, value, note in invalid],
        )
    else:
        write_no_findings(
            W, "Wszystkie nazwy hostów w nagłówkach `Received` są składniowo poprawne."
        )

    issuers = {
        h.by
        for h in hops
        if h.by and NetAddress.classify(h.by.strip("[]")) == "nie jest adresem IP"
    }
    if len(issuers) > 1:
        W(
            f"Nazw hostów w klauzuli `by`: **{len(issuers)}** "
            "(literały adresów IP nie są tu liczone jako nazwy).\n"
        )
    W(
        "Raport pracuje wyłącznie na zawartości pliku. Przypisanie adresów do "
        "operatora, numeru AS i kraju wymaga zapytania RDAP/whois i **nie zostało "
        "wykonane** — to osobny, wykonalny krok.\n"
    )
    W("")


def write_timeline_section(
    timestamps: list[tuple[str, datetime.datetime]], W: WriteLine
) -> None:
    """Sekcja 2.5: oś czasu ze wszystkich znaczników — nie tylko z Date i Received.

    >>> lines = []
    >>> ts = [("Date", datetime.datetime(2026, 8, 7, 13, 6, 2, tzinfo=datetime.timezone.utc)),
    ...       ("DKIM-Signature t=", datetime.datetime(2026, 8, 7, 13, 6, 2, tzinfo=datetime.timezone.utc)),
    ...       ("Received skok 1", datetime.datetime(2026, 8, 7, 13, 42, 28, tzinfo=datetime.timezone.utc))]
    >>> write_timeline_section(ts, lines.append)
    >>> out = "\\n".join(lines)
    >>> "36 min 26 s" in out
    True
    >>> "DKIM-Signature t=" in out
    True
    >>> lines = []
    >>> write_timeline_section([], lines.append)
    >>> "Brak znaczników czasu" in "\\n".join(lines)
    True
    """
    W("## 4. Oś czasu\n")
    if not timestamps:
        write_no_findings(W, "Brak znaczników czasu w nagłówkach.")
        W("")
        return

    write_table(
        W,
        ["Źródło", "Strefa z nagłówka", "UTC", "Czas warszawski"],
        [
            [
                label,
                code(dt.strftime("%Y-%m-%d %H:%M:%S %z")),
                code(
                    dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                ),
                code(
                    dt.astimezone(WARSAW).strftime("%Y-%m-%d %H:%M:%S ")
                    + (dt.astimezone(WARSAW).tzname() or "")
                ),
            ]
            for label, dt in timestamps
        ],
    )

    ordered = sorted(timestamps, key=lambda item: item[1])
    if len(ordered) > 1:
        W("**Odstępy między kolejnymi znacznikami:**\n")
        for (label_a, dt_a), (label_b, dt_b) in itertools.pairwise(ordered):
            delta = (dt_b - dt_a).total_seconds()
            W(f"- {label_a} → {label_b}: **{format_duration(delta)}**")
        W("")
        span = (ordered[-1][1] - ordered[0][1]).total_seconds()
        W(f"Rozpiętość całej osi: **{format_duration(span)}**.\n")

        # `x=` to data WYGAŚNIĘCIA podpisu — zdarzenie przyszłe wobec wysyłki,
        # nie punkt doręczenia. Wciągnięte do rozpiętości dawało „12 h 30 min”
        # tam, gdzie wszystkie znaczniki doręczenia mieszczą się w 8 sekundach,
        # a tej ostatniej liczby raport nie podawał nigdzie.
        elapsed = [(label, dt) for label, dt in ordered if "x=" not in label]
        if len(elapsed) > 1 and len(elapsed) != len(ordered):
            actual = (elapsed[-1][1] - elapsed[0][1]).total_seconds()
            W(
                f"Rozpiętość **po pominięciu znaczników wygaśnięcia `x=`** "
                f"(to daty przyszłe wobec wysyłki, nie punkty doręczenia): "
                f"**{format_duration(actual)}**.\n"
            )
        # Czas tranzytu liczony wyłącznie po `Received` — to jedyny odcinek,
        # który mówi o drodze wiadomości, a nie o momentach jej podpisania.
        received = [(label, dt) for label, dt in ordered if "Received" in label]
        if len(received) > 1:
            transit = (received[-1][1] - received[0][1]).total_seconds()
            W(
                f"Czas tranzytu (od najstarszego do najnowszego `Received`): "
                f"**{format_duration(transit)}**, skoków ze znacznikiem: "
                f"**{len(received)}**.\n"
            )

        identical = [
            (a, b)
            for (a, dt_a), (b, dt_b) in itertools.pairwise(ordered)
            if int(dt_a.timestamp()) == int(dt_b.timestamp())
        ]
        for label_a, label_b in identical:
            W(f"- {label_a} i {label_b} wskazują **tę samą sekundę**.")
        if identical:
            W("")
    W("")


# ──────────────────────────── 3. uwierzytelnienie ────────────────────────────


def write_auth_section(headers: list[AuthHeader], W: WriteLine) -> None:
    """Sekcja 3: każdy nagłówek uwierzytelnienia cytowany osobno, z atrybucją.

    Poprzednia wersja sklejała `Authentication-Results` z `Received-SPF` w jeden
    blok i wypisywała wynik `arc=`, który powstawał z dopasowania podciągu w
    `dmarc=`. Blok podany jako cytat nie był cytatem.

    >>> lines = []
    >>> h = AuthHeader("Authentication-Results", 1, "mx.a.pl; dkim=pass header.i=@b.pl; spf=pass")
    >>> write_auth_section([h], lines.append)
    >>> out = "\\n".join(lines)
    >>> "mx.a.pl" in out
    True
    >>> "arc" in out.lower().replace("dmarc", "")
    False
    >>> lines = []
    >>> write_auth_section([], lines.append)
    >>> "Brak nagłówków" in "\\n".join(lines)
    True
    """
    W("## 5. Uwierzytelnienie — nagłówki dosłownie\n")
    if not headers:
        write_no_findings(
            W,
            "Brak nagłówków `Authentication-Results`, `ARC-Authentication-Results` i `Received-SPF`.",
        )
        W("")
        return

    for header in headers:
        W(
            f"**{header.name} #{header.index}**"
            + (f" — wystawca: {code(header.authserv_id)}" if header.authserv_id else "")
            + "\n"
        )
        W("```")
        W(header.raw)
        W("```\n")

    by_method = auth_methods_by_name(headers)
    if by_method:
        W("**Wyniki metod, z atrybucją do nagłówka, który je podał:**\n")
        rows = []
        for method, entries in by_method.items():
            for source, parsed in entries:
                props = ", ".join(f"{k}={v}" for k, v in parsed.props.items())
                rows.append(
                    [
                        code(method),
                        code(parsed.result),
                        source,
                        escape_pipe(props) or "—",
                    ]
                )
        write_table(W, ["Metoda", "Wynik", "Nagłówek źródłowy", "Właściwości"], rows)
        W(
            "Wyniki pochodzą od serwerów, które je wpisały. Raport ich nie weryfikował "
            "kryptograficznie — nie sprawdzano podpisów `b=`/`bh=` wobec rekordów DNS.\n"
        )
    else:
        write_no_findings(
            W, "W nagłówkach uwierzytelnienia nie ma rozpoznawalnych metod."
        )
    W("")


def write_dkim_section(
    signatures: list[DkimSignature],
    unsigned: list[str],
    transit: dict[str, list[str]],
    oversigned: list[str],
    W: WriteLine,
) -> None:
    """Sekcja 3.2: każda sygnatura z własnymi tagami; niepodpisane liczone z pliku.

    >>> lines = []
    >>> s1 = DkimSignature.parse("d=nadawca.pl; s=sel1; a=rsa-sha256; h=From:Subject; t=1786107962")
    >>> s2 = DkimSignature.parse("d=dostawca.example; s=sel2; h=From:Feedback-ID;")
    >>> write_dkim_section([s1, s2], ["Message-ID", "Precedence"], {"dopisane na trasie przez serwery pośredniczące": ["Received"]}, ["Cc"],
    ...                    lines.append)
    >>> out = "\\n".join(lines)
    >>> "nadawca.pl" in out and "dostawca.example" in out
    True
    >>> "sel2" in out
    True
    >>> "Message-ID" in out and "Precedence" in out
    True
    >>> "całe ciało" in out
    True
    >>> "Powód odjęcia" in out
    True
    >>> lines = []
    >>> write_dkim_section([], [], {}, [], lines.append)
    >>> "Brak nagłówka `DKIM-Signature`" in "\\n".join(lines)
    True
    """
    W("## 6. Podpisy DKIM\n")
    if not signatures:
        write_no_findings(W, "Brak nagłówka `DKIM-Signature`.")
        W("")
        return

    W(f"Nagłówków `DKIM-Signature`: **{len(signatures)}**.\n")
    for i, sig in enumerate(signatures, 1):
        W(f"### Sygnatura {i}\n")
        rows = [
            ["`d=` (domena podpisująca)", code(sig.domain)],
            ["`s=` (selektor)", code(sig.selector)],
            ["`a=` (algorytm)", code(sig.algorithm)],
            ["`c=` (kanonizacja)", code(sig.canonicalization)],
            ["`i=` (tożsamość)", code(sig.identity)],
            ["`bh=` (skrót ciała)", code(sig.body_hash)],
            ["`l=` (limit bajtów ciała)", code(sig.body_length)],
        ]
        if sig.timestamp:
            moment = datetime.datetime.fromtimestamp(
                sig.timestamp, tz=datetime.timezone.utc
            )
            rows.append([f"`t=` ({sig.timestamp})", code(format_local(moment))])
        if sig.expires:
            moment = datetime.datetime.fromtimestamp(
                sig.expires, tz=datetime.timezone.utc
            )
            rows.append([f"`x=` ({sig.expires})", code(format_local(moment))])
        # Tagi spoza stałej listy (`v=`, `q=`, `b=`) są w pliku, a tabela ich
        # nie pokazywała — mimo że sekcja deklaruje wypisanie tagów podpisu.
        rows += [[f"`{klucz}=`", code(value)] for klucz, value in sig.other_tags]
        write_table(W, ["Tag", "Wartość"], [r for r in rows if r[1] != "—"])
        # Brak tagu to ustalenie tej samej klasy co jego obecność. Raport
        # odnotowywał wyłącznie brak `l=`, choć brak `t=` (podpis bez znacznika
        # czasu) i `x=` (bez daty wygaśnięcia) jest równie odczytywalny z pliku.
        missing = [
            label
            for label, present in (
                ("`t=` (znacznik czasu podpisu)", sig.timestamp),
                ("`x=` (wygaśnięcie podpisu)", sig.expires),
                ("`l=` (limit bajtów ciała)", sig.body_length),
            )
            if not present
        ]
        if missing:
            write_no_findings(
                W,
                f"Sygnatura {i} nie zawiera tagów: "
                + ", ".join(missing)
                + (
                    " — brak `l=` znaczy, że podpisem objęte jest całe ciało."
                    if "`l=` (limit bajtów ciała)" in missing
                    else ""
                ),
            )

        W(f"**Podpisane nagłówki (`h=`)**: {code(', '.join(sig.signed_headers))}\n")
        duplicated = [
            h for h in set(sig.signed_headers) if sig.signed_headers.count(h) > 1
        ]
        if duplicated:
            W(
                "Nagłówki wymienione w `h=` więcej niż raz: "
                + ", ".join(code(h) for h in sorted(duplicated))
                + ".\n"
            )
        if sig.body_length is None:
            W("Brak tagu `l=` — podpisem objęte jest całe ciało wiadomości.\n")
        else:
            W(
                f"Tag `l={sig.body_length}` — podpisem objęte są pierwsze {sig.body_length} B ciała.\n"
            )

    if unsigned:
        W(
            "**Nagłówki nadawcy obecne w wiadomości i nieobjęte listą `h=` pierwszej "
            "sygnatury** (różnica zbiorów, po odjęciu nagłówków tranzytowych):\n"
        )
        W(", ".join(code(h) for h in unsigned) + "\n")
    else:
        write_no_findings(
            W, "Wszystkie nagłówki nadawcy są wymienione w `h=` pierwszej sygnatury."
        )

    if oversigned:
        W(
            "\n**Nagłówki wymienione w `h=`, których w wiadomości nie ma** — "
            f"**{len(oversigned)}**: "
            + ", ".join(code(h) for h in oversigned)
            + ". Podpis obejmuje pozycje puste, więc dopisanie któregokolwiek "
            "z nich w tranzycie unieważniłoby DKIM.\n"
        )
    else:
        write_no_findings(
            W, "Lista `h=` nie zawiera nagłówków nieobecnych w wiadomości."
        )

    if transit:
        W("\n**Nagłówki odjęte przed policzeniem różnicy, z podziałem na powód:**\n")
        write_table(
            W,
            ["Powód odjęcia", "Nagłówki", "Liczba"],
            [
                [reason, ", ".join(code(h) for h in names), str(len(names))]
                for reason, names in transit.items()
            ],
        )
    W(
        "Zakres podpisu obejmuje wyłącznie nagłówki z listy `h=` oraz ciało w zakresie "
        "wyznaczonym przez `l=` (lub całe, gdy `l=` nie ma).\n"
    )
    W("")


def write_arc_section(
    seals: list[ArcSet],
    signatures: list[DkimSignature],
    dkim: list[DkimSignature],
    W: WriteLine,
) -> None:
    """Sekcja 7: ARC — pieczęcie i podpisy wiadomości, z tagiem `cv=`.

    `cv=none` znaczy „nie było wcześniejszego łańcucha”; opis mówiący, że
    „pośrednicy zweryfikowali i zapieczętowali”, jest z nim sprzeczny.
    Sekcja pokazywała wyłącznie `ARC-Seal`, przez co ginęła lista `h=` podpisu
    ARC — jedyny zapis tego, które nagłówki istniały w chwili odbioru.

    >>> lines = []
    >>> seal = ArcSet(1, "posrednik.example", "arc-1", "none", 1787985652)
    >>> write_arc_section([seal], [], [], lines.append)
    >>> out = "\\n".join(lines)
    >>> "cv=" in out and "none" in out
    True
    >>> "brak wcześniejszego łańcucha" in out
    True
    >>> lines = []
    >>> write_arc_section([], [], [], lines.append)
    >>> "Brak nagłówków `ARC-Seal`" in "\\n".join(lines)
    True

    Zgodność `bh=` podpisu ARC z `bh=` podpisu DKIM jest ustaleniem o integralności
    ciała w tranzycie — raport miał obie wartości i ich nie zestawiał:

    >>> lines = []
    >>> arc = DkimSignature.parse("d=posrednik.example; s=a; h=From; bh=WSPOLNY")
    >>> sig = DkimSignature.parse("d=nadawca.example; s=b; h=From; bh=WSPOLNY")
    >>> write_arc_section([seal], [arc], [sig], lines.append)
    >>> "jest **identyczny**" in "\\n".join(lines)
    True
    """
    W("## 7. ARC (Authenticated Received Chain)\n")
    if not seals and not signatures:
        write_no_findings(W, "Brak nagłówków `ARC-Seal` i `ARC-Message-Signature`.")
        W("")
        return

    if seals:
        W("### 7.1. ARC-Seal\n")
        write_table(
            W,
            ["`i=`", "`d=`", "`s=`", "`cv=`", "`t=`"],
            [
                row(
                    seal.index,
                    seal.domain,
                    seal.selector,
                    seal.chain_validation,
                    format_local(
                        datetime.datetime.fromtimestamp(
                            seal.timestamp, tz=datetime.timezone.utc
                        )
                    )
                    if seal.timestamp
                    else None,
                )
                for seal in seals
            ],
        )
        for seal in seals:
            if seal.chain_validation == "none":
                W(
                    f"- `i={seal.index}; cv=none` — wg RFC 8617 oznacza **brak "
                    f"wcześniejszego łańcucha ARC**; pieczęć założył host "
                    f"`{seal.domain}` przy odbiorze."
                )
            elif seal.chain_validation:
                W(
                    f"- `i={seal.index}; cv={seal.chain_validation}` — wynik walidacji "
                    "łańcucha zastanego."
                )
        W("")
    else:
        write_no_findings(W, "Brak nagłówków `ARC-Seal`.")

    if signatures:
        W("### 7.2. ARC-Message-Signature\n")
        # Sortujemy po `i=`, bo to on ustala kolejność w łańcuchu ARC. Kolejność
        # z pliku bywa odwrotna do numeracji, a raport numerował „podpis nr 1/2”
        # po kolejności wystąpienia, przecząc tabeli pieczęci obok.
        for i, sig in enumerate(sorted(signatures, key=lambda x: x.identity or ""), 1):
            write_table(
                W,
                ["Tag", "Wartość"],
                [
                    ["`i=` (numer w łańcuchu)", code(sig.identity)],
                    ["`d=`", code(sig.domain)],
                    ["`s=`", code(sig.selector)],
                    ["`a=`", code(sig.algorithm)],
                    ["`c=` (kanonizacja)", code(sig.canonicalization)],
                    ["`bh=`", code(sig.body_hash)],
                    ["`h=` (podpisane nagłówki)", code(", ".join(sig.signed_headers))],
                ]
                # Tagi spoza stałej listy — `fh=`, `dara=`, `b=`, `v=`, `q=` —
                # są w pliku, a tabela ich nie pokazywała.
                + [[f"`{klucz}=`", code(value)] for klucz, value in sig.other_tags],
            )
            W(
                f"Lista `h=` podpisu ARC nr {i} zapisuje, które nagłówki zostały "
                "**objęte podpisem** — nie które istniały w chwili pieczętowania. "
                "Nagłówki spoza listy mogły istnieć i pozostać niepodpisane.\n"
            )
        arc_hashes = {s.body_hash for s in signatures if s.body_hash}
        dkim_hashes = {s.body_hash for s in dkim if s.body_hash}
        shared = arc_hashes & dkim_hashes
        if shared:
            W(
                "Skrót ciała `bh=` w podpisie ARC i w podpisie DKIM jest **identyczny** "
                f"({', '.join(code(h) for h in sorted(shared))}).\n"
            )
        elif arc_hashes and dkim_hashes:
            # Bez przyczyny: raport nie policzył żadnego `bh=`, więc wyjaśnienie
            # „to przez kanonizację” byłoby hipotezą podaną jako ustalenie —
            # w sekcji, której nagłówek deklaruje brak hipotez. Podajemy oba
            # `c=`, bo to fakty z pliku, i zostawiamy różnicę nierozstrzygniętą.
            canonicalizations = sorted(
                {
                    s.canonicalization
                    for s in list(signatures) + list(dkim)
                    if s.canonicalization
                }
            )
            W(
                "Skrót ciała `bh=` w podpisie ARC **różni się** od skrótu w podpisie "
                "DKIM. Raport **nie ustala przyczyny** — sprawdzenie wymagałoby "
                "policzenia obu skrótów, czego raport nie robi (patrz zastrzeżenie "
                "w sekcji o DKIM). Zadeklarowane kanonizacje `c=`: "
                + (", ".join(code(k) for k in canonicalizations) or "brak")
                + ".\n"
            )
    else:
        write_no_findings(W, "Brak nagłówków `ARC-Message-Signature`.")
    W("")


def write_dmarc_section(
    headers: list[AuthHeader], alignment: Alignment | None, W: WriteLine
) -> None:
    """Sekcja 3.5: wynik DMARC z polityką i policzone wyrównanie domen.

    Sam wynik „pass” bez polityki i bez wskazania, która metoda go zapewniła,
    jest daną niepełną: przy `p=NONE` nie ma egzekwowania, a `pass` oparte
    wyłącznie o DKIM znaczy co innego niż oparte o SPF.

    >>> lines = []
    >>> h = AuthHeader("Authentication-Results", 1,
    ...                "mx.a.pl; dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=nadawca.pl; "
    ...                "spf=pass smtp.mailfrom=bounce.dostawca.pl")
    >>> al = Alignment.compute("nadawca.pl", "bounce.dostawca.pl", ("nadawca.pl",))
    >>> write_dmarc_section([h], al, lines.append)
    >>> out = "\\n".join(lines)
    >>> "p=NONE" in out
    True
    >>> "SPF nie jest wyrównany" in out
    True
    >>> "DKIM jest wyrównany" in out
    True
    """
    W("## 9. DMARC i wyrównanie domen\n")
    found = False
    for header in headers:
        for method in header.methods:
            if method.method != "dmarc":
                continue
            found = True
            W(f"Wynik `dmarc={method.result}` z `{header.name} #{header.index}`.\n")
            if method.comment:
                W(f"Polityka podana w nawiasie: {code(method.comment)}\n")
            else:
                write_no_findings(
                    W, "Nagłówek nie podaje polityki domeny (brak `p=` w komentarzu)."
                )
    if not found:
        write_no_findings(W, "Brak wyniku `dmarc=` w nagłówkach uwierzytelnienia.")

    if alignment is None:
        W("")
        return

    W("\n**Wyrównanie (RFC 7489 §3.1) — policzone z domen obecnych w pliku:**\n")
    write_table(
        W,
        ["Element", "Domena"],
        [
            ["`From`", code(alignment.from_domain)],
            ["SPF `smtp.mailfrom`", code(alignment.mailfrom_domain)],
            ["DKIM `d=`", code(", ".join(alignment.dkim_domains))],
        ],
    )
    if alignment.spf_aligned is True:
        W(f"- SPF jest wyrównany z `From` (tryb {alignment.spf_alignment_mode}).")
    elif alignment.spf_aligned is False:
        W(
            f"- **SPF nie jest wyrównany** z `From`: "
            f"`{alignment.mailfrom_domain}` ≠ `{alignment.from_domain}`."
        )
    else:
        absent = [
            e
            for e, w in (
                ("`From`", alignment.from_domain),
                ("`smtp.mailfrom`", alignment.mailfrom_domain),
            )
            if not w
        ]
        # Alternatywa „brak A albo B” czytała się jak stwierdzenie o pliku,
        # w którym `From` jest obecny — nazywamy więc konkretnie brakujące pole.
        W(f"- Wyrównania SPF nie da się policzyć — w pliku brak: {', '.join(absent)}.")

    if alignment.dkim_aligned is True:
        W(
            "- DKIM jest wyrównany z `From` przez: "
            + ", ".join(code(d) for d in alignment.dkim_aligned_domains)
            + "."
        )
    elif alignment.dkim_aligned is False:
        W(
            "- **DKIM nie jest wyrównany** z `From` — żadna domena `d=` nie odpowiada domenie `From`."
        )
    else:
        absent = [
            e
            for e, w in (
                ("`From`", alignment.from_domain),
                ("podpisu DKIM", alignment.dkim_aligned_domains),
            )
            if not w
        ]
        W(f"- Wyrównania DKIM nie da się policzyć — w pliku brak: {', '.join(absent)}.")
    W(
        "\nDomena organizacyjna liczona jako dwie ostatnie etykiety. Bez listy publicznych "
        "sufiksów (poza stdlib) to przybliżenie — obie domeny podano wyżej dosłownie.\n"
    )
    W("")


def write_spam_headers_section(
    spam_headers: list[tuple[str, str]], W: WriteLine
) -> None:
    """Sekcja 3.4: nagłówki filtrów antyspamowych dowolnego producenta.

    Raport twierdził „brak nagłówków filtrów” przy wiadomości z Microsoft 365,
    bo szukał wyłącznie VADE i DCC.

    >>> lines = []
    >>> write_spam_headers_section([("x-forefront-antispam-report", "SCL:1;SFV:NSPM")], lines.append)
    >>> "SCL:1" in "\\n".join(lines)
    True
    >>> lines = []
    >>> write_spam_headers_section([("X-DCC--Metrics", "host 1024; Body=1 Fuz2=29281")], lines.append)
    >>> out = "\\n".join(lines)
    >>> "Fuz2" in out and "29281" in out
    True
    >>> lines = []
    >>> write_spam_headers_section([], lines.append)
    >>> "Brak nagłówków filtrów" in "\\n".join(lines)
    True
    """
    W("## 8. Nagłówki filtrów antyspamowych\n")
    if not spam_headers:
        write_no_findings(W, "Brak nagłówków filtrów antyspamowych.")
        W("")
        return

    write_table(
        W,
        ["Nagłówek", "Wartość"],
        [[code(name), escape_pipe(value)] for name, value in spam_headers],
    )
    for name, value in spam_headers:
        metrics = parse_dcc_metrics(value)
        if metrics:
            W(
                f"Liczniki z {code(name)} (ile razy filtr widział daną sumę kontrolną):\n"
            )
            write_table(
                W,
                ["Licznik", "Wartość"],
                [[code(key), str(count)] for key, count in metrics],
            )
    W(
        "Wartości pochodzą od systemów filtrujących na trasie. Raport przepisuje je "
        "bez interpretacji skali ocen poszczególnych producentów.\n"
    )
    W("")


# ──────────────────────────── 3.7–4.5 ────────────────────────────


def write_reply_to_section(addresses: dict[str, list[Address]], W: WriteLine) -> None:
    """Sekcja 3.7: Reply-To wobec From — z jawnym stwierdzeniem, gdy Reply-To nie ma.

    >>> lines = []
    >>> write_reply_to_section({"From": [Address("", "a@nadawca.pl")]}, lines.append)
    >>> "Brak nagłówka `Reply-To`" in "\\n".join(lines)
    True
    >>> lines = []
    >>> addrs = {"From": [Address("Osoba", "a@nadawca.pl")],
    ...          "Reply-To": [Address("Osoba", "b@inna.pl")]}
    >>> write_reply_to_section(addrs, lines.append)
    >>> out = "\\n".join(lines)
    >>> "inna.pl" in out and "nadawca.pl" in out
    True
    >>> "Nazwa wyświetlana jest w obu nagłówkach identyczna" in out
    True
    """
    W("## 10. Reply-To wobec From\n")
    from_list = addresses.get("From", [])
    reply_list = addresses.get("Reply-To", [])

    if not reply_list:
        write_no_findings(
            W,
            "Brak nagłówka `Reply-To`. Adres wskazany w `From`"
            + (f": {code(from_list[0].addr_spec)}" if from_list else " — brak")
            + ".",
        )
        W("")
        return

    write_table(
        W,
        ["Nagłówek", "Nazwa wyświetlana", "Adres", "Domena"],
        [
            [
                code(label),
                escape_pipe(a.display_name) or "—",
                code(a.addr_spec),
                code(a.domain),
            ]
            for label, entries in (("From", from_list), ("Reply-To", reply_list))
            for a in entries
        ],
    )
    from_domains = {a.domain for a in from_list if a.domain}
    reply_domains = {a.domain for a in reply_list if a.domain}
    if from_domains and reply_domains:
        if from_domains == reply_domains:
            W(
                f"Domeny `From` i `Reply-To` są identyczne: {code(', '.join(sorted(from_domains)))}.\n"
            )
        else:
            W(
                f"Domena `Reply-To` ({code(', '.join(sorted(reply_domains)))}) różni się od domeny "
                f"`From` ({code(', '.join(sorted(from_domains)))}).\n"
            )
    from_names = {a.display_name.strip() for a in from_list if a.display_name.strip()}
    reply_names = {a.display_name.strip() for a in reply_list if a.display_name.strip()}
    if from_names and from_names == reply_names:
        W("Nazwa wyświetlana jest w obu nagłówkach identyczna.\n")
    W("")


#: Nagłówki wysyłki masowej i automatyzacji, których obecność ORAZ nieobecność
#: jest ustaleniem. Sekcja sprawdzała wyłącznie `List-Unsubscribe`, więc reszta
#: nie pojawiała się w raporcie w żadnej postaci.
LIST_HEADER_NAMES = (
    "List-Unsubscribe",
    "List-Unsubscribe-Post",
    "List-Id",
    "List-Help",
    "List-Post",
    "List-Owner",
    "Precedence",
    "Auto-Submitted",
    "Feedback-ID",
    "X-Mailer",
    "X-Campaign",
    "X-EMAIL-ID",
    "X-Mail-From",
    "X-Abuse",
    "X-Report-Abuse",
    "X-Entity-Ref-ID",
    "Organization",
    "Content-Language",
    "X-Priority",
)


def write_list_headers_section(
    headers: dict[str, str], rfc8058: str | None, W: WriteLine
) -> None:
    """Sekcja 3.8: nagłówki listy wysyłkowej — cytat, bez tez o zawartości tokenów.

    Poprzednia wersja twierdziła, że adres odbiorcy „pojawia się w List-Unsubscribe
    (token Base64)" niezależnie od tego, co w tym nagłówku faktycznie było — w
    5 raportach adresu tam nie było wcale, w jednym token był hexem, w jednym
    nagłówka w ogóle nie było.

    >>> lines = []
    >>> write_list_headers_section({"List-Unsubscribe": "<https://a.pl/u/K1>, <mailto:u@a.pl>",
    ...                             "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    ...                            "nagłówek obecny, brak podpisu DKIM w wiadomości", lines.append)
    >>> out = "\\n".join(lines)
    >>> "https://a.pl/u/K1" in out and "u@a.pl" in out
    True
    >>> "RFC 8058" in out
    True
    >>> "brak podpisu DKIM w wiadomości" in out
    True
    >>> lines = []
    >>> write_list_headers_section({}, None, lines.append)
    >>> "Brak nagłówków wysyłki masowej" in "\\n".join(lines)
    True
    """
    W("## 11. Nagłówki wysyłki masowej i korelatory dostawcy\n")
    if not headers:
        write_no_findings(
            W,
            "Brak nagłówków wysyłki masowej (`List-Unsubscribe`, `List-Id`, "
            "`Precedence`, `Auto-Submitted`) i korelatorów dostawcy (`Feedback-ID`).",
        )
        W("")
        return

    for name, value in headers.items():
        W(f"**{name}**\n")
        W("```")
        W(value)
        W("```\n")

    # Komplet ustaleń negatywnych, nie tylko dla `List-Unsubscribe`. Sekcja
    # sprawdzała jeden nagłówek z trzynastu, więc „brak kanału skargowego”,
    # „brak oznaczenia wiadomości jako automatycznej” i „brak identyfikatora
    # kampanii” nie padały nigdzie — mimo że są odczytywalne z pliku.
    absent_headers = [n for n in LIST_HEADER_NAMES if n not in headers]
    if absent_headers:
        write_no_findings(
            W,
            "Nagłówki nieobecne w wiadomości: "
            + ", ".join(code(n) for n in absent_headers)
            + ".",
        )
    if "List-Unsubscribe-Post" in headers:
        W(
            "Obecność `List-Unsubscribe-Post` oznacza zadeklarowaną obsługę wypisu "
            "jednym żądaniem POST (RFC 8058).\n"
        )
        if rfc8058:
            W(
                f"Sprawdzenie wymogu RFC 8058 §3 (podpis DKIM nad nagłówkami listy): **{rfc8058}**.\n"
            )
    else:
        write_no_findings(
            W,
            "Brak `List-Unsubscribe-Post` — wypis nie jest zadeklarowany jako "
            "one-click (RFC 8058).",
        )
    W("")


def write_message_id_section(message_id: str | None, W: WriteLine) -> None:
    """Sekcja 4.5: Message-ID rozłożony na część lokalną i domenową.

    >>> lines = []
    >>> write_message_id_section("<12345.678@serwer.przyklad.pl>", lines.append)
    >>> out = "\\n".join(lines)
    >>> "serwer.przyklad.pl" in out
    True
    >>> lines = []
    >>> write_message_id_section("<736375451488@WIN7-02>", lines.append)
    >>> "nie jest nazwą domenową" in "\\n".join(lines)
    True
    >>> lines = []
    >>> write_message_id_section(None, lines.append)
    >>> "Brak nagłówka Message-ID" in "\\n".join(lines)
    True
    """
    import re

    W("## 13. Message-ID\n")
    if not message_id:
        write_no_findings(W, "Brak nagłówka Message-ID.")
        W("")
        return

    raw = str(message_id).strip()
    W("```")
    W(raw)
    W("```\n")
    inner = raw.strip("<>")
    local, _, domain_part = inner.rpartition("@")
    rows = [["część lokalna", code(local)], ["część po `@`", code(domain_part)]]
    write_table(W, ["Element", "Wartość"], rows)

    for label, value in message_id_parts(raw):
        W(f"Część lokalna zawiera **{label}**: {code(value)}\n")

    if domain_part and not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", domain_part):
        W(
            f"Część po `@` ({code(domain_part)}) **nie jest nazwą domenową** w rozumieniu "
            "RFC 1035 (brak kropki albo brak sufiksu).\n"
        )
    uuid_match = re.search(
        r"\b([0-9a-f]{8}-[0-9a-f]{4}-([0-9a-f])[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        inner,
        re.IGNORECASE,
    )
    if uuid_match:
        version = uuid_match.group(2)
        note = (
            f"wersja {version}"
            if version in "12345678"
            else f"znak wersji `{version}` — poza zakresem 1–8"
        )
        W(
            f"Zawiera identyfikator w formacie UUID {code(uuid_match.group(1))} ({note}).\n"
        )
    W("")


def write_domains_section(refs: list[DomainRef], W: WriteLine) -> None:
    """Sekcja 4: inwentarz domen ze wszystkich ról, z jawnym zakresem zliczania.

    Poprzednia wersja liczyła wiersze tabeli (`From`, `Reply-To`, `Return-Path`
    i hosty z linków), pomijając hosty z `Received`, `Message-ID` i `d=` DKIM,
    a licząc `www.w3.org` z deklaracji przestrzeni nazw XML.

    >>> lines = []
    >>> refs = [DomainRef("nadawca.pl", "From"), DomainRef("nadawca.pl", "DKIM d="),
    ...         DomainRef("mta.dostawca.pl", "Received skok 1 HELO")]
    >>> write_domains_section(refs, lines.append)
    >>> out = "\\n".join(lines)
    >>> "2" in out and "nadawca.pl" in out
    True
    >>> "From, DKIM d=" in out
    True
    >>> lines = []
    >>> write_domains_section([], lines.append)
    >>> "Nie znaleziono żadnych domen" in "\\n".join(lines)
    True
    """
    W("## 12. Inwentarz domen i hostów\n")
    if not refs:
        write_no_findings(W, "Nie znaleziono żadnych domen ani nazw hostów.")
        W("")
        return

    grouped: dict[str, list[str]] = {}
    for ref in refs:
        grouped.setdefault(ref.domain, [])
        if ref.role not in grouped[ref.domain]:
            grouped[ref.domain].append(ref.role)

    write_table(
        W,
        ["Domena / host", "Role, w jakich występuje"],
        [
            [code(domain), escape_pipe(", ".join(roles))]
            for domain, roles in grouped.items()
        ],
    )
    W(
        f"Nazw unikalnych: **{len(grouped)}**. Zakres zliczania: nagłówki adresowe, "
        "`Received` (HELO/rDNS/by), `Message-ID`, `d=` podpisów DKIM i ARC, wystawcy "
        "nagłówków uwierzytelnienia, nagłówki listy wysyłkowej oraz hosty zasobów "
        "z treści. Deklaracje przestrzeni nazw XML i DOCTYPE nie są liczone jako "
        "odwołania nadawcy.\n"
    )

    # Dwie ostatnie etykiety dawały `net.pl` — sufiks publiczny, nie domenę
    # nadrzędną — przez co hosty tego samego operatora nie były grupowane.
    parents: dict[str, list[str]] = {}
    for domain in grouped:
        parents.setdefault(Alignment._organizational(domain), []).append(domain)
    shared = {p: names for p, names in parents.items() if len(names) > 1}
    if shared:
        W("Nazwy współdzielące tę samą domenę nadrzędną (dwie ostatnie etykiety):\n")
        for parent, names in shared.items():
            W(f"- {code(parent)}: " + ", ".join(code(n) for n in names))
        W("")
    W("")


# ──────────────────────────── 5. wątek ────────────────────────────


def write_thread_section(
    subject: str | None,
    in_reply_to: str | None,
    references: str | None,
    W: WriteLine,
) -> None:
    """Sekcja 5: wątek — z wartościami nagłówków, nie samym „obecne / brak”.

    >>> lines = []
    >>> write_thread_section("Temat", "<a@mail.example>", "<a@mail.example>", lines.append)
    >>> out = "\\n".join(lines)
    >>> "a@mail.example" in out
    True
    >>> "1" in out
    True
    >>> lines = []
    >>> write_thread_section("Re: Temat", None, None, lines.append)
    >>> out = "\\n".join(lines)
    >>> "prefiks odpowiedzi" in out
    True
    >>> "Brak nagłówków `In-Reply-To` i `References`" in out
    True
    """
    import re

    W("## 14. Powiązanie z wątkiem\n")
    subject_text = str(subject or "")
    if re.match(r"\s*(re|odp|fwd|fw)\s*:", subject_text, re.IGNORECASE):
        W(f"Temat zawiera prefiks odpowiedzi: {code(subject_text)}\n")
    else:
        W(
            f"Temat nie zawiera prefiksu odpowiedzi (`Re:` / `Odp:` / `Fwd:`): {code(subject_text)}\n"
        )

    if not in_reply_to and not references:
        write_no_findings(
            W,
            "Brak nagłówków `In-Reply-To` i `References` — nagłówki nie wiążą wiadomości "
            "z żadną wcześniejszą.",
        )
        W("")
        return

    if in_reply_to:
        W("**In-Reply-To**\n")
        W("```")
        W(str(in_reply_to).strip())
        W("```\n")
    else:
        write_no_findings(W, "Brak nagłówka `In-Reply-To`.")

    if references:
        ids = re.findall(r"<[^>]+>", str(references))
        W(f"**References** — identyfikatorów w łańcuchu: **{len(ids)}**\n")
        W("```")
        for identifier in ids or [str(references).strip()]:
            W(identifier)
        W("```\n")
    else:
        write_no_findings(W, "Brak nagłówka `References`.")
    W("")


# ──────────────────────────── 6. tokeny i zasoby ────────────────────────────


def _token_result(token: Token) -> str:
    """Kolumna „Po zdekodowaniu” — wynik albo powód jego braku, nigdy jedno za drugie.

    Trzy różne stany pliku, wcześniej zlewane do jednego zdania „dane binarne,
    N B”: token zdekodowany do tekstu, token zdekodowany do bajtów, token
    **niezdekodowany**. Ostatni dawał „dane binarne, 0 B” — czyli brak wyniku
    podany jak wynik.

    >>> _token_result(Token("s", "YWJj", "base64", "abc", 3, "ab12cd34ef56"))
    "'abc'"
    >>> _token_result(Token("s", "kf0L", "base64", None, 16, "aa11bb22cc33"))
    'dane binarne, 16 B, sha256 `aa11bb22cc33…`'
    >>> _token_result(Token("s", "3454bd31-1a2b-4c3d-8e4f-56789abcdef0", "UUID",
    ...                     None, 16, "aa11", note="UUID wersja 4, wariant RFC 4122"))
    'UUID wersja 4, wariant RFC 4122'
    >>> _token_result(Token("s", "dd62", "hex (25 znaków, długość nieparzysta)",
    ...                     None, 0, "aa11", note="nie zdekodowano — nieparzysta liczba"))
    'nie zdekodowano — nieparzysta liczba (skrót z ciągu: `aa11…`)'
    """
    if token.decoded_text is not None:
        return repr(token.decoded_text)
    if token.byte_length == 0:
        # Brak wyniku opisujemy powodem, nie liczbą 0 — „0 B” czytało się jak
        # pusty ładunek, czyli jak ustalenie o zawartości tokenu.
        reason = token.note or "nie zdekodowano"
        return f"{reason} (skrót z ciągu: `{token.sha256_prefix}…`)"
    if token.note and token.note != "dane binarne":
        return token.note
    return f"dane binarne, {token.byte_length} B, sha256 `{token.sha256_prefix}…`"


def write_tokens_section(tokens: list[Token], W: WriteLine) -> None:
    """Sekcja 6: tokeny zakodowane — także te, które dekodują się do danych binarnych.

    „Nie wykryto tokenów” było w kilku raportach fałszywym zaprzeczeniem: token
    stał w ścieżce URL, w nagłówku albo był hexem, a detektor patrzył wyłącznie
    na base64 w parametrach query.

    >>> lines = []
    >>> t = Token("treść: parametr ct=", "YWJj", "base64", "abc", 3, "ab12cd34ef56")
    >>> write_tokens_section([t], lines.append)
    >>> out = "\\n".join(lines)
    >>> "abc" in out
    True
    >>> lines = []
    >>> binary = Token("treść: segment ścieżki", "kf0LaY8LJ9ce", "base64url", None, 16, "aa11bb22cc33")
    >>> write_tokens_section([binary], lines.append)
    >>> out = "\\n".join(lines)
    >>> "dane binarne" in out and "16 B" in out
    True
    >>> lines = []
    >>> write_tokens_section([], lines.append)
    >>> "Nie znaleziono ciągów" in "\\n".join(lines)
    True
    """
    W("## 15. Tokeny i identyfikatory zakodowane\n")
    if not tokens:
        write_no_findings(
            W,
            "Nie znaleziono ciągów dających się zdekodować jako base64/base64url/hex "
            "w URL-ach, ścieżkach ani nagłówkach.",
        )
        W("")
        return

    write_table(
        W,
        ["Miejsce", "Token (dosłownie)", "Kodowanie", "Po zdekodowaniu"],
        [
            [
                escape_pipe(t.source),
                code(t.raw if len(t.raw) <= 80 else t.raw[:77] + "…"),
                code(t.encoding),
                escape_pipe(_token_result(t)),
            ]
            for t in tokens
        ],
    )
    if any(t.decoded_text is not None for t in tokens):
        W(
            "Wartości tekstowe podane są w zapisie `repr()` — białe znaki na końcu "
            "(np. `\\n`) są cechą sposobu wytworzenia tokenu i nie zostały usunięte.\n"
        )
    if any(t.decoded_text is None and t.byte_length for t in tokens):
        W(
            "Dla wyników nieczytelnych podano długość i skrót "
            "**zdekodowanych bajtów**.\n"
        )
    # Nota o ciągach nieprzełożonych na bajty tylko wtedy, gdy taki wiersz jest
    # w tabeli. Drukowana zawsze, opisywała mechanizm bez pokrycia w wynikach.
    if any(t.decoded_text is None and not t.byte_length for t in tokens):
        W(
            "Ciągi, których nie dało się przełożyć na bajty (nieparzysta liczba "
            "znaków hex, brak wypełnienia base64), mają w kolumnie „Po zdekodowaniu” "
            "podany powód; skrót policzono wtedy z samego ciągu, nie z danych.\n"
        )
    W("")


def write_repeated_identifiers_section(
    repeated: list[tuple[str, list[str]]], W: WriteLine
) -> None:
    """Sekcja 6.2: ten sam identyfikator w kilku miejscach wiadomości.

    >>> lines = []
    >>> write_repeated_identifiers_section([("6a75d83a", ["Return-Path", "piksel"])], lines.append)
    >>> out = "\\n".join(lines)
    >>> "6a75d83a" in out and "Return-Path" in out
    True
    >>> lines = []
    >>> write_repeated_identifiers_section([], lines.append)
    >>> "Nie znaleziono identyfikatorów" in "\\n".join(lines)
    True
    """
    W("## 16. Identyfikatory powtarzające się w kilku miejscach\n")
    if not repeated:
        write_no_findings(
            W,
            "Nie znaleziono identyfikatorów występujących w więcej niż jednym miejscu.",
        )
        W("")
        return
    write_table(
        W,
        ["Identyfikator", "Miejsca wystąpienia", "Liczba"],
        [
            [code(token), escape_pipe(", ".join(places)), str(len(places))]
            for token, places in repeated
        ],
    )
    W(
        "Kolumna „Liczba” zlicza **miejsca z listy obok**, nie wszystkie wystąpienia "
        "ciągu w pliku. Zakres przeszukania: nagłówki adresowe i identyfikacyjne, "
        "pola `Received`, wartości podpisów, URL-e zasobów z treści oraz zdekodowane "
        "tokeny — nie obejmuje dowolnego wystąpienia podciągu w treści.\n"
    )


def _anchor_text_differs(resource: HtmlResource) -> bool:
    """Czy tekst kotwicy wygląda na adres inny niż jej cel `href`.

    Tekst `www.przyklad.pl` przy `href` prowadzącym na `przyklad.pl?token=…`
    to rozbieżność, której odbiorca nie widzi. Sprawdzanie wyłącznie tekstów
    zaczynających się od `http` przepuszczało wariant z gołą domeną.

    >>> _anchor_text_differs(HtmlResource("a", "https://a.pl?t=1", "www.a.pl", "https", "a.pl"))
    True
    >>> _anchor_text_differs(HtmlResource("a", "https://a.pl/x", "https://a.pl/x", "https", "a.pl"))
    False
    >>> _anchor_text_differs(HtmlResource("a", "https://a.pl/x", "Kliknij tutaj", "https", "a.pl"))
    False
    >>> _anchor_text_differs(HtmlResource("a", "https://a.pl/x", None, "https", "a.pl"))
    False
    """
    import re

    text = (resource.text or "").strip()
    if not text or text == resource.url:
        return False
    looks_like_url = text.startswith(("http://", "https://")) or bool(
        re.fullmatch(
            r"(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?", text, re.IGNORECASE
        )
    )
    return looks_like_url


def _label_or_absent(resource: HtmlResource) -> str:
    """Tekst/alt zasobu, z rozróżnieniem atrybutu pustego od nieobecnego.

    `alt=""` i brak `alt` to dwa różne stany pliku; wpisywanie w obu przypadkach
    „—” mieszało brak danych z daną pustą.

    >>> _label_or_absent(HtmlResource("img", "u", "Logo", "https", "a.pl"))
    'Logo'
    >>> _label_or_absent(HtmlResource("img", "u", None, "https", "a.pl", attrs='src=u alt=""'))
    '`alt` obecny, wartość pusta'
    >>> _label_or_absent(HtmlResource("img", "u", None, "https", "a.pl", attrs="src=u"))
    'brak atrybutu'
    >>> _label_or_absent(HtmlResource("a", "u", None, "https", "a.pl"))
    '—'

    Obecność `alt` czytamy z pola ustalonego przy ekstrakcji, nie z `attrs` —
    to ostatnie jest obcinane do 200 znaków, więc przy długim URL-u atrybut
    wypadał za granicę i raport pisał „brak atrybutu” o znaczniku, który go ma:

    >>> _label_or_absent(HtmlResource("img", "u", None, "https", "a.pl",
    ...                               attrs="src=" + "x" * 200, alt_present=True))
    '`alt` obecny, wartość pusta'
    """
    if resource.text:
        return escape_pipe(resource.text)
    if resource.kind == "img":
        if resource.alt_present or re.search(
            r"\balt\s*=", resource.attrs, re.IGNORECASE
        ):
            return "`alt` obecny, wartość pusta"
        return "brak atrybutu"
    return "—"


def _same_host(text: str | None, url: str) -> bool:
    """Czy host wypisany w tekście kotwicy to ten sam host, co w `href`.

    Bez tego rozróżnienia „tekst nie jest identyczny z celem” obejmowało zarówno
    brak schematu (`przyklad.pl` vs `https://przyklad.pl?t=1` — ten sam host),
    jak i odwołanie pod zupełnie inny host. To dwa różne ustalenia.

    >>> _same_host("przyklad.pl", "https://przyklad.pl?t=1")
    True
    >>> _same_host("www.przyklad.pl", "https://przyklad.pl/x")
    True
    >>> _same_host("przyklad.pl", "https://inny-host.example/x")
    False
    >>> _same_host(None, "https://przyklad.pl")
    False
    """
    import urllib.parse

    if not text:
        return False
    candidate = text.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        left = (urllib.parse.urlparse(candidate).hostname or "").removeprefix("www.")
        right = (urllib.parse.urlparse(url).hostname or "").removeprefix("www.")
    except ValueError:
        return False
    return bool(left) and left.lower() == right.lower()


def write_resources_section(resources: list[HtmlResource], W: WriteLine) -> None:
    """Sekcja 6.5: wszystkie zasoby z HTML — linki, obrazy, skrypty, arkusze, tła.

    Regex ograniczony do `<a href>` z tekstowym dzieckiem gubił kotwice
    opakowujące obraz albo `<span>`, a `<img>`/`<script>` nie były zbierane
    w ogóle — stąd „nie znaleziono linków” w wiadomościach z przyciskiem CTA
    i pikselem śledzącym.

    >>> lines = []
    >>> res = [HtmlResource("a", "https://a.pl/r?id=1", "Zobacz cennik", "https", "a.pl"),
    ...        HtmlResource("img", "https://t.pl/o.gif", "", "https", "t.pl", "1", "1"),
    ...        HtmlResource("script", "/bot/x.js", None, "względny", None)]
    >>> write_resources_section(res, lines.append)
    >>> out = "\\n".join(lines)
    >>> "Zobacz cennik" in out
    True
    >>> "1×1" in out
    True
    >>> "script" in out
    True
    >>> lines = []
    >>> write_resources_section([], lines.append)
    >>> "Treść nie zawiera żadnych odwołań" in "\\n".join(lines)
    True
    """
    W("## 17. Zasoby odwoływane z treści\n")
    if not resources:
        write_no_findings(
            W,
            "Treść nie zawiera żadnych odwołań (`<a href>`, `<img src>`, `<script src>`, "
            "`<link href>`, `url()` w CSS).",
        )
        W("")
        return

    write_table(
        W,
        [
            "Rodzaj",
            "URL (pełny)",
            "Tekst / alt",
            "Host",
            "Schemat",
            "Wystąpień",
            "Także jako",
        ],
        [
            [
                code(r.kind),
                code(r.url),
                _label_or_absent(r),
                code(r.host),
                code(r.scheme),
                str(r.occurrences),
                ", ".join(code(k) for k in r.also_as) if r.also_as else "—",
            ]
            for r in resources
        ],
    )

    by_kind: dict[str, int] = {}
    for resource in resources:
        by_kind[resource.kind] = by_kind.get(resource.kind, 0) + resource.occurrences
    W(
        "Zestawienie ilościowe (wystąpienia znaczników): "
        + ", ".join(f"`{k}` — **{v}**" for k, v in by_kind.items())
        + f". Wierszy w tabeli: **{len(resources)}**"
        + (
            " — powtórzone odwołania do tego samego URL-a są scalone, a ich krotność "
            "podana w kolumnie „Wystąpień”.\n"
            if any(r.occurrences > 1 for r in resources)
            else ". Żadne odwołanie nie powtarza się, więc nic nie scalono.\n"
        )
    )
    W(
        "Kolumna „Wystąpień” liczy znaczniki w części `text/html`; kolumna "
        "„Także jako” pokazuje inne zapisy tego samego URL-a, żeby jeden "
        "pobierany zasób nie liczył się kilka razy.\n"
    )

    pixels = [r for r in resources if r.is_pixel]
    if pixels:
        W(f"\n**Obrazy o zadeklarowanych wymiarach 1×1 (lub 0):** {len(pixels)}\n")
        write_table(
            W,
            ["URL", "Atrybuty ze znacznika"],
            [row(p.url, p.attrs) for p in pixels],
        )
    else:
        write_no_findings(W, "Brak obrazów o zadeklarowanych wymiarach 1×1.")

    plaintext = [r for r in resources if r.scheme == "http"]
    if plaintext:
        W(
            f"\nOdwołania po `http://` (bez TLS), unikalnych URL-i: **{len(plaintext)}**\n"
        )
        for resource in plaintext:
            W(f"- {code(resource.url)}")
        W("")

    remote = [r for r in resources if r.scheme in {"http", "https"} and r.kind != "a"]
    relative = [r for r in resources if r.scheme == "względny"]
    if remote:
        occurrence_count = sum(1 + len(r.also_as) for r in remote)
        multiplicity = (
            ""
            if occurrence_count == len(remote)
            else (
                f" Ten sam URL bywa zapisany na kilka sposobów — zapisów w treści "
                f"jest **{occurrence_count}**, pobieranych zasobów **{len(remote)}**."
            )
        )
        W(
            f"Zasobów pobieranych z sieci po `http`/`https` (unikalnych URL-i): "
            f"**{len(remote)}** "
            f"(hosty: {', '.join(code(h) for h in sorted({r.host for r in remote if r.host}))})."
            f"{multiplicity}\n"
        )
    else:
        write_no_findings(
            W, "Brak zasobów pobieranych po `http`/`https` przy wyświetleniu treści."
        )
    if relative:
        # Bez wniosku o „domenie renderującej”: wiadomość e-mail nie ma bazowego
        # adresu ani znacznika `<base>`, więc taki adres nie rozwiązuje się do
        # niczego. Zapisujemy sam kształt odwołania, nie jego skutek.
        W(
            f"\nOdwołań o adresie **względnym** (bez schematu i bez hosta): "
            f"**{len(relative)}**. Wiadomość nie deklaruje adresu bazowego "
            f"(`<base>`), więc raport nie ustala, do jakiego hosta takie "
            f"odwołanie by prowadziło; nie wchodzą do sumy powyżej.\n"
        )
        for resource in relative:
            W(f"- {code(resource.kind)} → {code(resource.url)}")
        W("")

    mismatched = [r for r in resources if r.kind == "a" and _anchor_text_differs(r)]
    if mismatched:
        W("\nKotwice, w których tekst wyświetlany wygląda na adres:\n")
        write_table(
            W,
            ["Tekst wyświetlany", "Cel href", "Host w tekście = host celu?"],
            [
                [
                    code(r.text),
                    code(r.url),
                    "tak" if _same_host(r.text, r.url) else "**nie**",
                ]
                for r in mismatched
            ],
        )
        W(
            "Kolumna trzecia rozdziela dwa różne zjawiska: sam brak dosłownej "
            "zgodności (np. tekst bez schematu albo bez parametrów) od odwołania "
            "do innego hosta niż wyświetlany.\n"
        )
    W("")


# ──────────────────────────── 7. konstrukcje HTML/Unicode ────────────────────────────


def write_html_constructs_section(
    src: str, text_body: str | None, W: WriteLine
) -> None:
    """Sekcja 7: konstrukcje HTML/Unicode — policzone i sklasyfikowane wg stanu.

    Poprzednia wersja opisywała warunkowe komentarze Outlooka jako „komentarze
    wewnątrz wyrazów", komórki układu jako „puste spany rozbijające wyrazy”,
    a preheader Mailchimpa jako element ukryty — i podawała liczbę typów w zdaniu
    o liczbie wystąpień.

    >>> lines = []
    >>> write_html_constructs_section(
    ...     '<!--[if mso]>x<![endif]--> sło<span></span>wo', None, lines.append)
    >>> out = "\\n".join(lines)
    >>> "warunkowy MSO/Outlook" in out
    True
    >>> "wewnątrz wyrazu" in out
    True
    >>> lines = []
    >>> write_html_constructs_section("zwykly tekst", None, lines.append)
    >>> "Nie znaleziono komentarzy HTML" in "\\n".join(lines)
    True
    """
    W("## 18. Konstrukcje HTML i Unicode\n")

    comments = classify_comments(src)
    W("### 18.1. Komentarze HTML\n")
    if comments:
        by_kind: dict[str, list[HtmlComment]] = {}
        for comment in comments:
            by_kind.setdefault(comment.kind, []).append(comment)
        write_table(
            W,
            ["Klasyfikacja", "Liczba wystąpień", "Przykład ze źródła"],
            [
                [kind, str(len(items)), code(items[0].text[:70])]
                for kind, items in by_kind.items()
            ],
        )
        opening = src.count("<!--")
        W(
            f"Dopasowanych komentarzy: **{len(comments)}**, klas: **{len(by_kind)}**. "
            f"Wystąpień samego ciągu `<!--`: **{opening}**"
            + (
                " — różnica bierze się z komentarzy warunkowych typu "
                "`<!--[if !mso]><!-->`, gdzie otwarcie i domknięcie nie tworzą pary."
                if opening != len(comments)
                else "."
            )
            + "\n"
        )
        splitting = [c for c in comments if c.splits_word]
        if not splitting:
            write_no_findings(
                W,
                "Żaden komentarz nie stoi wewnątrz wyrazu (sprawdzone przez znaki sąsiadujące).",
            )
    else:
        write_no_findings(W, "Nie znaleziono komentarzy HTML.")

    W("\n### 18.2. Znaczniki `<span>` wewnątrz wyrazów\n")
    spans = find_word_splitting_spans(src)
    if spans:
        W(
            f"Wystąpień: **{len(spans)}** (sprawdzone przez znaki bezpośrednio przed i po znaczniku).\n"
        )
        for example in spans[:10]:
            W(f"- {code(example)}")
        W("")
    else:
        write_no_findings(W, "Żaden znacznik `<span>` nie stoi wewnątrz wyrazu.")

    W("\n### 18.3. Znaki nietypowe\n")
    # Detektory dostawały wyłącznie część HTML, a liczby czytały się jak
    # całościowe — ten sam homoglif w części tekstowej nie był liczony.
    parts = [("text/html", src)] + ([("text/plain", text_body)] if text_body else [])
    rows = [
        [code(part), code(cp), str(count), name, note]
        for part, body in parts
        for cp, count, name, note in unusual_characters(body)
    ]
    write_table_or_finding(
        W,
        ["Część", "Code point", "Liczba", "Nazwa Unicode", "Uwaga"],
        rows,
        "Brak znaków zerowej szerokości i homoglifów ASCII w "
        + " i ".join(f"`{name}`" for name, _ in parts)
        + ".",
    )

    W("\n### 18.4. Encje HTML\n")
    entities = numeric_entities(src)
    if entities:
        total = sum(count for _, count in entities)
        W(f"Numerycznych — wystąpień: **{total}**, różnych: **{len(entities)}**.\n")
        W(" ".join(f"`{ent}`×{count}" for ent, count in entities[:20]) + "\n")
    else:
        write_no_findings(W, "Brak numerycznych encji HTML.")

    named = named_entities(src)
    if named:
        total = sum(count for _, count in named)
        W(f"\nNazwanych — wystąpień: **{total}**, różnych: **{len(named)}**.\n")
        W(" ".join(f"`{ent}`×{count}" for ent, count in named[:20]) + "\n")
    else:
        write_no_findings(W, "Brak nazwanych encji HTML.")

    # Zakres liczony ODDZIELNIE dla każdej części. Łączenie ich dawało
    # gwarantowany fałszywy pozytyw: `&nbsp;` w `text/html` i literalny U+00A0
    # w `text/plain` to nie niespójność kodowania, tylko normalna konsekwencja
    # `multipart/alternative` — w części tekstowej encje HTML nie mają znaczenia.
    # Ustalenie ma dotyczyć jednego dokumentu, bo tylko tam jest obserwacją.
    scope = "część `text/html`"
    mixed = mixed_character_encodings(src)
    if text_body:
        mixed_plain = mixed_character_encodings(text_body)
        if mixed_plain and not mixed:
            scope = "część `text/plain`"
            mixed = mixed_plain
        elif mixed_plain:
            scope = "każda część osobno"
            mixed = mixed + mixed_plain
    if mixed:
        W(f"\nZnaki zapisane **dwoma sposobami naraz** (zakres: {scope}):\n")
        write_table(
            W,
            ["Znak", "Jako encja", "Wystąpień jako encja", "Wystąpień wprost"],
            [
                [code(char), code(entity), str(as_entity), str(literal)]
                for char, entity, as_entity, literal in mixed
            ],
        )
    else:
        write_no_findings(
            W,
            "Żaden znak nie występuje jednocześnie jako encja i wprost — sprawdzone: "
            f"{scope}.",
        )

    W("\n### 18.5. Sklejenia na granicy znaczników liniowych\n")
    glued = glued_tag_boundaries(src)
    if glued:
        W(
            f"Miejsc, w których wyraz powstaje ze sklejenia dwóch sąsiednich "
            f"elementów liniowych bez separatora: **{len(glued)}**.\n"
        )
        for fragment in glued[:10]:
            W(f"- {code(fragment)}")
        W("")
    else:
        write_no_findings(
            W, "Brak sklejeń tekstu na granicy sąsiadujących znaczników liniowych."
        )

    W("\n### 18.6. Struktura i metadane dokumentu HTML\n")
    structure = html_document_structure(src)
    metadata = document_metadata(src)
    if structure or metadata:
        write_table(
            W,
            ["Element", "Stan / wartość"],
            [[code(name), state] for name, state in structure]
            + [[code(name), escape_pipe(value)] for name, value in metadata],
        )
        if not metadata:
            write_no_findings(W, "Dokument nie deklaruje tytułu ani atrybutu `lang`.")
    else:
        write_no_findings(W, "Treść nie zawiera znaczników HTML.")
    W("")


def _write_stylesheet_rules(stylesheet: list[StylesheetRule], W: WriteLine) -> None:
    """Reguły ukrywające z bloków `<style>`, z warunkiem i liczbą użyć klasy.

    >>> lines = []
    >>> _write_stylesheet_rules([StylesheetRule(".wideonly", "display:none", 2)],
    ...                         lines.append)
    >>> "wideonly" in "\\n".join(lines) and "bez warunku" in "\\n".join(lines)
    True
    >>> lines = []
    >>> _write_stylesheet_rules([], lines.append)
    >>> "Bloki `<style>` nie zawierają" in "\\n".join(lines)
    True

    Reguła z `@media` jest oznaczona swoim warunkiem, a zdanie podsumowujące
    nie przypisuje jej działania bezwarunkowego:

    >>> lines = []
    >>> _write_stylesheet_rules(
    ...     [StylesheetRule(".hiddentds", "display:none", 17, "@media (max-width:714px)")],
    ...     lines.append)
    >>> out = "\\n".join(lines)
    >>> "@media (max-width:714px)" in out
    True
    >>> "bez względu na kontekst" in out
    False
    """
    W("\n### Reguły ukrywające w blokach `<style>`\n")
    if not stylesheet:
        write_no_findings(W, "Bloki `<style>` nie zawierają reguł ukrywających.")
        return
    write_table(
        W,
        ["Selektor", "Deklaracje", "Elementów z tą klasą w treści", "Warunek"],
        [
            [
                code(rule.selector),
                code(rule.declarations),
                str(rule.usage),
                code(rule.condition) if rule.condition else "bez warunku",
            ]
            for rule in stylesheet
        ],
    )
    warunkowe = [r for r in stylesheet if r.condition]
    bezwarunkowe = [r for r in stylesheet if r.unconditional]
    if bezwarunkowe:
        W(
            f"\nReguł działających **bez warunku**: **{len(bezwarunkowe)}** — "
            f"usuwają element z widoku niezależnie od kontekstu renderowania.\n"
        )
    if warunkowe:
        W(
            f"\nReguł zagnieżdżonych w regule warunkowej: **{len(warunkowe)}**. "
            f"Obowiązują wyłącznie przy spełnionym warunku podanym w tabeli, "
            f"więc **nie są** ustaleniem o ukryciu treści w ogólnym przypadku.\n"
        )


def write_hidden_section(
    hidden: list[HiddenElement],
    stylesheet: list[StylesheetRule],
    styled_total: int,
    W: WriteLine,
) -> None:
    """Sekcja 19: elementy z deklaracjami CSS wpływającymi na widoczność.

    Dwie klasy, bo mają różną wartość dowodową. `display:none` działa niezależnie
    od kontekstu; `color:#FFFFFF` zależy od tła — biały tekst na niebieskim
    przycisku jest w pełni widoczny, a oznaczenie go jako ukrytego byłoby
    fałszywym dowodem wytworzonym przez narzędzie.

    >>> lines = []
    >>> el = HiddenElement("div", ("opacity:0.01", "max-height:0px"), "tekst ukryty",
    ...                     "opacity:0.01;max-height:0px")
    >>> write_hidden_section([el], [], 3, lines.append)
    >>> out = "\\n".join(lines)
    >>> "tekst ukryty" in out and "opacity:0.01" in out
    True
    >>> lines = []
    >>> write_hidden_section([], [], 0, lines.append)
    >>> "nie znaleziono deklaracji" in "\\n".join(lines)
    True

    Element pusty jest odnotowany, a nie pomijany — „nie znaleziono” przy pustym
    `<span>` z siedmioma takimi deklaracjami było nieprawdą:

    >>> lines = []
    >>> pusty = HiddenElement("span", ("display:none",), "", "display:none")
    >>> write_hidden_section([pusty], [], 1, lines.append)
    >>> "bez treści tekstowej" in "\\n".join(lines)
    True
    """
    W("## 19. Elementy z deklaracjami CSS wpływającymi na widoczność\n")
    W(
        f"Zakres: atrybuty `style` poszczególnych elementów (jest ich w treści "
        f"**{styled_total}**) **oraz** reguły z bloków `<style>`. Style ładowane "
        "z zewnętrznych arkuszy nie są dostępne w pliku, więc ustalenia tej sekcji "
        "dotyczą wyłącznie reguł zapisanych w wiadomości.\n"
    )
    if not hidden:
        write_no_findings(
            W,
            "W atrybutach `style` nie znaleziono deklaracji `display:none`, "
            "`visibility:hidden`, `opacity:0`, zerowej wysokości/szerokości, rozmiaru "
            "czcionki 0–1 px ani białego koloru tekstu bez zadeklarowanego tła.",
        )
        _write_stylesheet_rules(stylesheet, W)
        W("")
        return

    hiding = [h for h in hidden if h.kind == "ukrywające"]
    contrast = [h for h in hidden if h.kind != "ukrywające"]
    with_text = [h for h in hidden if h.text]
    # Etykieta mówi wprost, czego dotyczy liczba. „Elementów ogółem: 1” obok
    # zdania „atrybutów `style` jest w treści 24” czytało się jak sprzeczność —
    # a to dwie różne wielkości: wszystkie stylowane elementy kontra te
    # z deklaracjami istotnymi dla widoczności.
    W(
        f"Elementów **z deklaracjami istotnymi dla widoczności**: **{len(hidden)}** "
        f"(z {styled_total} elementów z atrybutem `style` w treści) — "
        f"z deklaracjami ukrywającymi: **{len(hiding)}**, z deklaracjami "
        f"kontrastu/rozmiaru: **{len(contrast)}**. "
        f"Z treścią tekstową: **{len(with_text)}**, łącznie "
        f"**{sum(len(h.text) for h in with_text)}** znaków.\n"
    )
    if styled_total > len(hidden):
        write_no_findings(
            W,
            f"Pozostałe **{styled_total - len(hidden)}** elementów z atrybutem "
            f"`style` nie niesie żadnej z badanych deklaracji — nie zostały "
            f"pominięte, tylko nie spełniają kryterium tej sekcji.",
        )

    number = itertools.count(1)
    for label, group, note in (
        (
            "Deklaracje ukrywające (działają niezależnie od tła)",
            hiding,
            (
                "Reguły z tej grupy działają niezależnie od koloru tła. Reguły "
                "z bloków `<style>` zagnieżdżone w `@media` obowiązują wyłącznie "
                "przy spełnionym warunku — warunek jest podany w tabeli niżej."
            ),
        ),
        (
            "Deklaracje kontrastu i rozmiaru (zależne od tła)",
            contrast,
            (
                "Te reguły **nie przesądzają** o widoczności. Kolumna „Tło "
                "zadeklarowane” pokazuje, czy element deklaruje własne tło; jeżeli "
                "nie — tło wynika z arkusza i kontekstu, których raport nie ustala."
            ),
        ),
    ):
        if not group:
            continue
        # Numer nadajemy dopiero przy druku — wcześniej pominięcie pustej grupy
        # zostawiało dziurę (19.1 → 19.3), która w dokumencie dowodowym sama
        # generuje pytanie „co wycięto”.
        W(f"### 19.{next(number)}. {label}\n")
        # Elementy BEZ treści (spacery układu) idą do jednej tabeli zbiorczej.
        # Rozpisane po jednej tabeli na sztukę zajmowały 22% raportu i przykryły
        # sobą błąd w regule `@media` leżący kilka linii niżej.
        empty = [e for e in group if not e.text]
        with_text = [e for e in group if e.text]
        if empty:
            W(
                f"Elementów **bez treści tekstowej** (deklaracje obecne, nic nie "
                f"ukrywają): **{len(empty)}** — zestawione zbiorczo:\n"
            )
            write_table(
                W,
                ["Znacznik", "Rozpoznane reguły", "Tło zadeklarowane"],
                [
                    [
                        code(f"<{e.tag}>"),
                        ", ".join(code(r) for r in e.rules),
                        code(e.background),
                    ]
                    for e in empty
                ],
            )
        if not with_text:
            W(f"{note}\n")
            continue
        for i, element in enumerate(with_text, 1):
            W(f"**Element {i} — `<{element.tag}>`**\n")
            write_table(
                W,
                ["Cecha", "Wartość"],
                [
                    [
                        "Rozpoznane reguły (podzbiór atrybutu `style`)",
                        ", ".join(code(r) for r in element.rules),
                    ],
                    ["Pełny atrybut `style`", code(element.style)],
                    ["Tło zadeklarowane na tym elemencie", code(element.background)],
                    ["Długość tekstu", f"{len(element.text)} znaków"],
                ],
            )
            if element.text:
                W("Tekst wewnątrz:\n")
                W("```")
                W(element.text)
                W("```\n")
        W(f"{note}\n")
    _write_stylesheet_rules(stylesheet, W)
    W("")


# ──────────────────────────── 8. treść ────────────────────────────


def write_content_section(
    html_body: str | None,
    text_body: str | None,
    comparison: dict[str, object],
    W: WriteLine,
) -> None:
    """Sekcja 8: treść widoczna, rozdzielona na własną i cytowaną, plus porównanie części.

    Poprzednia wersja wrzucała do „treści po usunięciu obfuskacji” arkusz stylów
    (~500 z 720 linii w jednym z raportów) i nie oddzielała 3 zdań nadawcy od
    22 kB zacytowanego pisma odbiorcy.

    >>> lines = []
    >>> write_content_section("<style>p{margin:0}</style><p>Dzien dobry.</p>", "Dzien dobry.",
    ...                        {"status": "obie części obecne", "urls_only_in_html": [],
    ...                         "urls_only_in_text": [], "text_similar": True, "word_overlap": 1.0},
    ...                        lines.append)
    >>> out = "\\n".join(lines)
    >>> "Dzien dobry." in out
    True
    >>> "margin" in out
    False
    >>> lines = []
    >>> write_content_section(None, None, {"status": "brak części text/html"}, lines.append)
    >>> "Wiadomość nie zawiera treści tekstowej" in "\\n".join(lines)
    True
    """
    W("## 20. Treść\n")
    source = html_body or text_body
    if not source:
        write_no_findings(W, "Wiadomość nie zawiera treści tekstowej.")
        W("")
        return

    plain = deobfuscate(source)
    # Nota o prefiksie tylko wtedy, gdy w treści faktycznie coś nim oznaczono.
    # Drukowana zawsze, obiecywała czytelnikowi oznaczenia, których nie było —
    # a w jednym pliku obiecywała inny prefiks, niż kod emituje.
    W(
        "Poniżej treść po usunięciu znaczników, arkuszy `<style>`, skryptów "
        "i sekcji `<head>`."
        + (
            " Fragmenty z deklaracjami CSS wpływającymi na widoczność są "
            "zachowane i oznaczone prefiksem `[DEKLARACJE: reguły]` — usunięcie "
            "ich skasowałoby dowód, pominięcie adnotacji podałoby je jako treść "
            "widoczną."
            if "[DEKLARACJE:" in plain
            else " W treści nie ma fragmentów z deklaracjami wpływającymi na "
            "widoczność, więc nic nie jest oznaczone prefiksem."
        )
        + "\n"
    )
    own, quoted = split_quoted(plain)

    if quoted:
        # Procent liczony z sumy PODANYCH składników — wcześniej mianownikiem
        # była długość sprzed podziału, więc czytelnik nie odtwarzał liczby
        # z dwóch liczb wydrukowanych obok niej.
        combined = len(own) + len(quoted)
        W(
            f"Treść własna nadawcy: **{len(own)}** znaków "
            f"(**{len(re.sub(r'\s', '', own))}** niebędących białymi). "
            f"Cytat wcześniejszej korespondencji: **{len(quoted)}** znaków "
            f"(**{100 * len(quoted) // max(1, combined)}%** sumy obu części).\n"
        )
        W("### Treść własna nadawcy\n")
        W("```")
        W(own or "(brak)")
        W("```\n")
        W("### Cytat wcześniejszej korespondencji\n")
        W("```")
        W(quoted)
        W("```\n")
    else:
        # Liczymy na DOKŁADNIE tym ciągu, który drukujemy. Wcześniej licznik
        # widział `\r\n`, a zapis raportu normalizował je do `\n`, więc podana
        # liczba nie odtwarzała się z bloku stojącego pod nią. Zakończenia linii
        # są osobno raportowane w sekcji o sumach kontrolnych, więc normalizacja
        # tutaj nie kasuje dowodu.
        printed = plain.replace("\r\n", "\n").replace("\r", "\n")
        non_whitespace = len(re.sub(r"\s", "", printed))
        W(
            f"Treść liczy **{len(printed)}** znaków, w tym **{non_whitespace}** "
            "niebędących białymi — obie liczby policzone na bloku poniżej, więc "
            "odtwarzają się z niego. Różnica to białe znaki: odstępy i złamania "
            "wierszy pozostałe po usunięciu znaczników. Zakończenia linii "
            "w pliku źródłowym podaje sekcja o sumach kontrolnych. "
            "Nie wykryto granicy cytatu.\n"
        )
        W("```")
        W(printed)
        W("```\n")

    W("### Porównanie części `text/plain` i `text/html`\n")
    status = comparison.get("status")
    if status != "obie części obecne":
        write_no_findings(W, f"Porównanie niemożliwe: {status}.")
        W("")
        return

    only_html = comparison.get("urls_only_in_html") or []
    only_text = comparison.get("urls_only_in_text") or []
    # Miara bez definicji nie nadaje się na dowód — czytelnik nie wie ani co
    # jest liczone, ani w którą stronę. Podajemy wzór i to, czego dotyczy różnica.
    W(
        f"Pokrycie słownictwa obu części: **{comparison.get('word_overlap')}**. "
        f"Miara: liczba słów wspólnych obu częściom podzielona przez liczbę słów "
        f"występujących w którejkolwiek z nich (indeks Jaccarda; 1.0 = identyczne "
        f"zbiory słów, 0.0 = rozłączne). Porównywane są słowa, nie kolejność "
        f"ani formatowanie.\n"
    )
    html_only = comparison.get("words_only_in_html") or []
    text_only = comparison.get("words_only_in_text") or []
    if html_only or text_only:
        W("Słowa występujące wyłącznie w jednej części:\n")
        write_table(
            W,
            ["Część", "Liczba słów", "Słowa"],
            [
                w
                for w in (
                    [
                        "`text/html`",
                        str(len(html_only)),
                        ", ".join(code(x) for x in html_only[:40]) or "—",
                    ],
                    [
                        "`text/plain`",
                        str(len(text_only)),
                        ", ".join(code(x) for x in text_only[:40]) or "—",
                    ],
                )
                if w[1] != "0"
            ],
        )
    else:
        write_no_findings(W, "Obie części zawierają dokładnie ten sam zbiór słów.")
    if isinstance(only_html, list) and only_html:
        W("URL-e obecne wyłącznie w `text/html`:\n")
        for url in only_html:
            W(f"- {code(url)}")
        W("")
    if isinstance(only_text, list) and only_text:
        W("URL-e obecne wyłącznie w `text/plain`:\n")
        for url in only_text:
            W(f"- {code(url)}")
        W("")
    if not only_html and not only_text:
        total = comparison.get("urls_total", 0)
        if total:
            write_no_findings(
                W, f"Obie części zawierają ten sam zbiór **{total}** URL-i."
            )
        else:
            write_no_findings(W, "Żadna z części nie zawiera URL-i.")
    W("")


# ──────────────────────────── 9. artefakty ────────────────────────────


def write_software_section(fingerprints: list[tuple[str, str]], W: WriteLine) -> None:
    """Sekcja 21: ślady oprogramowania — nagłówki klienta, boundary, generator HTML.

    `X-Mailer`, `User-Agent`, format `boundary` i `<meta name="Generator">` były
    w raportach pomijane albo wspominane tylko w prozie; nieobecność nagłówków
    klienta nie była odnotowywana wcale.

    >>> lines = []
    >>> write_software_section([("X-Mailer", "Sendy"), ("User-Agent", "(nagłówek nieobecny)")],
    ...                        lines.append)
    >>> out = "\\n".join(lines)
    >>> "Sendy" in out and "nieobecny" in out
    True
    >>> lines = []
    >>> write_software_section([], lines.append)
    >>> "Nie znaleziono żadnych śladów" in "\\n".join(lines)
    True
    """
    W("## 21. Ślady oprogramowania\n")
    if not fingerprints:
        write_no_findings(
            W,
            "Nie znaleziono żadnych śladów oprogramowania nadawczego w nagłówkach ani w treści.",
        )
        W("")
        return
    write_table(
        W,
        ["Źródło", "Wartość"],
        [[code(name), escape_pipe(value)] for name, value in fingerprints],
    )
    W("")


def write_artifacts_section(
    eml_basename: str,
    file_size: int,
    file_mtime_iso: str,
    sha256_original: str,
    endings: str,
    written: list[Artifact],
    W: WriteLine,
    date_header: str | None = None,
) -> None:
    """Sekcja 9: artefakty, sumy kontrolne i granice tego, co sumy poświadczają.

    `_naglowki.txt` bywał opisany jako „pełne nagłówki (wyciąg)” — a powstawał
    z re-serializacji przez parser (rozwinięte zwinięcia, zdekodowane RFC 2047,
    naprawiona składnia). Hash potwierdzał integralność rekonstrukcji, nie
    wierność oryginałowi; teraz raport mówi to wprost.

    >>> lines = []
    >>> art = Artifact("a.txt", "deadbeef", "opis")
    >>> write_artifacts_section("w.eml", 100, "2026-08-30T00:00:00", "cafebabe",
    ...                         "CRLF w całym pliku (9)", [art], lines.append)
    >>> out = "\\n".join(lines)
    >>> "a.txt" in out and "deadbeef" in out
    True
    >>> "mtime" in out
    True
    >>> "CRLF w całym pliku" in out
    True
    """
    W("## 22. Artefakty i sumy kontrolne\n")
    W(f"**Plik źródłowy**: {code(eml_basename)}\n")
    write_table(
        W,
        ["Cecha", "Wartość"],
        [
            ["Rozmiar", f"**{file_size}** bajtów"],
            ["Data modyfikacji pliku (mtime)", code(file_mtime_iso)],
            ["SHA-256", code(sha256_original)],
            ["Zakończenia linii", endings],
        ],
    )
    # Odstęp `Date` → `mtime`. Obie wartości były w raporcie (§4 i tu), różnicy
    # nie liczył nikt — mimo że sekcja o osi czasu liczy odstępy między każdą
    # parą znaczników. To jedyna liczba wiążąca wiadomość z kopią roboczą.
    date_value = parse_date_header(str(date_header)) if date_header else None
    if date_value:
        try:
            written_at = datetime.datetime.fromisoformat(file_mtime_iso)
        except ValueError:
            written_at = None
        if written_at is not None and written_at.tzinfo is not None:
            gap = (written_at - date_value).total_seconds()
            W(
                f"\nOdstęp od `Date` wiadomości ({code(format_local(date_value))}) "
                f"do `mtime` kopii roboczej: **{format_duration(gap)}**. "
                f"To odstęp do zapisu pliku w tym katalogu, nie do doręczenia.\n"
            )
    W(
        "`mtime` to znacznik systemu plików kopii roboczej — mówi, kiedy plik został "
        "zapisany w tym katalogu, a nie kiedy wiadomość powstała ani czy oryginał "
        "był modyfikowany wcześniej. Raport nie ustala pochodzenia pliku (z jakiej "
        "skrzynki, kto i kiedy go wyeksportował) — ta informacja nie jest zawarta "
        "w samym pliku.\n"
    )

    write_table(
        W,
        ["Plik", "SHA-256", "Opis"],
        [[code(a.name), code(a.sha256), a.description] for a in written],
    )
    W(
        "---\n_Raport wygenerowany mechanicznie przez `eml_forensics.py`. Zawiera "
        "wartości odczytane z pliku i wyliczenia na nich; nie zawiera kwalifikacji "
        "prawnej ani ocen charakteru wiadomości._"
    )


def write_identity_layers_section(
    layers: list[tuple[str, str]], registry: list[tuple[str, str, str]], W: WriteLine
) -> None:
    """Sekcja 23: warstwy deklarujące nadawcę i identyfikatory rejestrowe z treści.

    Obie tabele zestawiają wartości, które wcześniej leżały rozrzucone po pięciu
    sekcjach albo wyłącznie w prozie zrzutu treści. Zestawienie to fakt, nie
    ocena — sekcja nie orzeka o zgodności ani o charakterze wiadomości.

    >>> lines = []
    >>> write_identity_layers_section(
    ...     [("Domena `From`", "marka.pl"), ("Domena koperty (`Return-Path`)", "dostawca.pl")],
    ...     [("NIP", "836-167-65-10", "suma kontrolna poprawna")], lines.append)
    >>> out = "\\n".join(lines)
    >>> "marka.pl" in out and "dostawca.pl" in out
    True
    >>> "836-167-65-10" in out and "poprawna" in out
    True

    >>> lines = []
    >>> write_identity_layers_section([], [], lines.append)
    >>> "Brak warstw" in "\\n".join(lines)
    True
    """
    W("## 23. Warstwy tożsamości i identyfikatory z treści\n")
    if layers:
        W(
            "Każda warstwa deklaruje nadawcę niezależnie od pozostałych. "
            "Zestawienie podane **bez oceny zgodności** — wartości pochodzą "
            "z sekcji wcześniejszych, tu stoją obok siebie.\n"
        )
        write_table(
            W,
            ["Warstwa", "Wartość zadeklarowana"],
            [[label, code(value)] for label, value in layers],
        )
        domains = {w for e, w in layers if e.startswith("Domena") and "," not in w}
        if len(domains) > 1:
            # „Rejestrowalna” wymagałaby listy publicznych sufiksów, której nie
            # mamy w stdlib — `eu-west-1.amazonses.com` i `amazonses.com` to
            # jedna domena organizacyjna. Piszemy więc to, co faktycznie liczymy.
            W(
                f"Różnych nazw w warstwach adresowych: **{len(domains)}** "
                f"({', '.join(code(d) for d in sorted(domains))}). Liczone są "
                f"pełne nazwy hostów — bez listy publicznych sufiksów raport nie "
                f"sprowadza ich do domeny organizacyjnej.\n"
            )
    else:
        write_no_findings(W, "Brak warstw deklarujących nadawcę.")

    W("\n### 23.1. Identyfikatory rejestrowe i finansowe z treści\n")
    if registry:
        write_table(
            W,
            ["Rodzaj", "Wartość z treści", "Suma kontrolna"],
            [[kind, code(value), status] for kind, value, status in registry],
        )
        W(
            "Suma kontrolna jest **policzona z wartości zapisanej w pliku** "
            "(IBAN/NRB — mod-97 wg ISO 13616, NIP i REGON — wagi ustawowe). "
            "Raport nie sprawdza, czy identyfikator figuruje w jakimkolwiek "
            "rejestrze — to wymaga zapytania poza plikiem.\n"
        )
    else:
        write_no_findings(
            W,
            "W treści nie znaleziono numeru rachunku, NIP-u, KRS-u, REGON-u ani BDO.",
        )
    W("")
