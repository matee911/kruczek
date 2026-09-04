#!/usr/bin/env python3
"""eml_forensics.py — mechaniczna analiza wiadomości .eml pod kątem dowodowym.

Wypluwa raport markdown: droga wiadomości, uwierzytelnienie (SPF/DKIM/DMARC/ARC),
inwentarz domen, zasoby zdalne, tokeny identyfikujące, konstrukcje HTML/Unicode,
treść widoczna i ukryta, sumy kontrolne.

Raport podaje **wartości i ich źródła** — nie kwalifikuje wiadomości, nie stawia
hipotez o intencjach nadawcy i nie doradza, co z ustaleniami zrobić. Fakt negatywny
(„brak Reply-To”, „zero załączników”) jest zapisywany wprost, bo też jest ustaleniem.

Warstwy (ports & adapters):
    eml_forensics_logika.py  — ekstrakcja faktów z email.Message, bez I/O
    eml_forensics_raport.py  — renderowanie sekcji markdown z gotowych faktów, bez I/O
    eml_forensics.py         — ten plik: CLI, wczytanie/zapis plików, orchestracja

Użycie:
    eml_forensics.py wiadomosc.eml [--outdir KATALOG]

Zapisuje w --outdir (domyślnie obok pliku):
    <stem>_naglowki.txt      surowy blok nagłówków (bajty z pliku, bez normalizacji)
    <stem>_naglowki_norm.txt nagłówki po sparsowaniu (rozwinięte, zdekodowane)
    <stem>_tresc.html        część text/html po zdekodowaniu transfer-encoding
    <stem>_tresc.txt         część text/plain (jeśli jest)
    <stem>_analiza.md        raport
Bez zależności zewnętrznych (tylko stdlib).
"""

import argparse
import datetime
import email.message
import re
import sys
from pathlib import Path

from eml_forensics_logika import (
    Alignment,
    Artifact,
    HtmlResource,
    ReceivedHop,
    Token,
    build_mime_tree,
    collect_domains,
    collect_net_addresses,
    compare_parts,
    decode_header_tokens,
    decode_hop_tokens,
    decode_tokens,
    deobfuscate,
    extract_addresses,
    extract_arc_message_signatures,
    extract_arc_seals,
    extract_attachments,
    extract_auth_headers,
    extract_bodies,
    extract_dkim_signatures,
    extract_headers_text,
    extract_hops,
    extract_html_resources,
    extract_spam_headers,
    extract_timestamps,
    find_hidden_elements,
    header_names,
    identity_layers,
    line_endings,
    load_message,
    load_raw_bytes,
    organisations_in_content,
    oversigned_headers,
    raw_header_block,
    raw_header_value,
    registry_identifiers,
    repeated_identifiers,
    rfc8058_compliance,
    software_fingerprints,
    stylesheet_hiding_rules,
    unsigned_headers,
)
from eml_forensics_raport import (
    # Jedno źródło prawdy: ta sama krotka steruje zbieraniem wartości
    # i listą ustaleń negatywnych. Dwie osobne listy rozjeżdżały się cicho.
    LIST_HEADER_NAMES,
    write_arc_section,
    write_artifacts_section,
    write_auth_section,
    write_content_section,
    write_dkim_section,
    write_dmarc_section,
    write_domains_section,
    write_hidden_section,
    write_html_constructs_section,
    write_identification,
    write_identity_layers_section,
    write_list_headers_section,
    write_message_id_section,
    write_mime_section,
    write_received_section,
    write_repeated_identifiers_section,
    write_reply_to_section,
    write_resources_section,
    write_software_section,
    write_spam_headers_section,
    write_thread_section,
    write_timeline_section,
    write_tokens_section,
)
from utils import sha256_file as sha256


def save_text_file(path: Path, content: str) -> None:
    """Zapisuje zawartość do pliku tekstowego z kodowaniem UTF-8.

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as td:
    ...     p = Path(td) / "test.txt"
    ...     save_text_file(p, "hello")
    ...     p.read_text(encoding="utf-8")
    'hello'
    """
    path.write_text(content, encoding="utf-8")


def build_artifact(path: Path, description: str) -> Artifact:
    """Buduje Artifact z metadanymi zapisanego pliku (nazwa, SHA-256, opis).

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as td:
    ...     p = Path(td) / "test.txt"
    ...     _ = p.write_text("test")
    ...     build_artifact(p, "plik testowy").description
    'plik testowy'
    """
    return Artifact(name=path.name, sha256=sha256(path), description=description)


def collect_list_headers(msg: email.message.Message) -> dict[str, str]:
    """Nagłówki opisujące wysyłkę listową/masową, w kolejności z LIST_HEADER_NAMES.

    Nagłówek obecny z pustą wartością to inna obserwacja niż nagłówek nieobecny —
    dlatego pusty `X-Mailer` też trafia do wyniku, z jawną adnotacją.

    >>> from email import message_from_string, policy
    >>> src = "List-Unsubscribe: <https://a.pl/u>\\nPrecedence: bulk\\nX-Mailer:\\n\\nx"
    >>> collect_list_headers(message_from_string(src, policy=policy.default))
    {'List-Unsubscribe': '<https://a.pl/u>', 'Precedence': 'bulk', 'X-Mailer': '(nagłówek obecny, wartość pusta)'}
    >>> collect_list_headers(message_from_string("From: a@b.pl\\n\\nx", policy=policy.default))
    {}
    """
    out: dict[str, str] = {}
    for name in LIST_HEADER_NAMES:
        values = msg.get_all(name)
        if values is None:
            continue
        joined = " | ".join(str(v).strip() for v in values)
        out[name] = joined if joined else "(nagłówek obecny, wartość pusta)"
    return out


def collect_identifier_sources(
    msg: email.message.Message,
    hops: list[ReceivedHop],
    resources: list[HtmlResource],
    tokens: list[Token],
) -> dict[str, str]:
    """Miejsca, w których szukamy powtarzających się identyfikatorów.

    Sekcja „identyfikatory powtarzające się” przeglądała wcześniej tylko pięć
    nagłówków i URL-e z treści. Przez to nie znalazła ani identyfikatora kolejki
    Postfiksa wspólnego dla `Received` i `Message-ID`, ani wartości `X-EMAIL-ID`
    obecnej wprost w zdekodowanym ładunku linku śledzącego — czyli dokładnie
    tych powiązań, dla których sekcja istnieje.

    >>> from email import message_from_string, policy
    >>> src = ("Message-ID: <20260721113602.3AA011B7B5F@serwer.example>\\n"
    ...        "Received: from a.example by b.example with ESMTPA id 3AA011B7B5F\\n\\nx")
    >>> msg = message_from_string(src, policy=policy.default)
    >>> zrodla = collect_identifier_sources(msg, extract_hops(msg), [], [])
    >>> sorted(zrodla)
    ['Message-ID', 'Received skok 1 (HELO)', 'Received skok 1 (by)', 'Received skok 1 (id)']

    Nagłówki adresowe też są w zakresie — sekcja deklarowała je od początku,
    ale ich nie zbierała, więc licznik pokazywał 3 miejsca tam, gdzie inwentarz
    domen w tym samym raporcie wyliczał 7 ról tej samej nazwy:

    >>> src = "From: a@przyklad.pl\\nReply-To: b@przyklad.pl\\nReceived-SPF: pass\\n\\nx"
    >>> msg = message_from_string(src, policy=policy.default)
    >>> sorted(collect_identifier_sources(msg, [], [], []))
    ['From', 'Received-SPF', 'Reply-To']

    Wartości podpisów też są miejscem wystąpienia — inaczej sekcja nie ma czego
    porównać, gdy `bh=` powtarza się w DKIM i w ARC:

    >>> src = ("DKIM-Signature: v=1; d=a.pl; s=s; h=From; bh=WSPOLNY\\n"
    ...        "ARC-Message-Signature: i=1; d=b.pl; s=t; h=From; bh=WSPOLNY\\n\\nx")
    >>> msg = message_from_string(src, policy=policy.default)
    >>> sorted(collect_identifier_sources(msg, [], [], []))
    ['ARC-Message-Signature #1', 'DKIM-Signature #1']
    """
    out: dict[str, str] = {}
    seen_lower: set[str] = set()
    for name in (
        # Nagłówki adresowe — sekcja deklaruje je w zakresie, a nie było ich na
        # liście. Stąd licznik „3 miejsca” przy domenie, dla której inwentarz
        # domen w tym samym raporcie wyliczał 7 ról.
        "From",
        "Reply-To",
        "Sender",
        "Cc",
        "Return-Path",
        "Message-ID",
        "List-Unsubscribe",
        "List-Id",
        "Feedback-ID",
        "X-EmailGuid",
        "X-EMAIL-ID",
        "X-Campaign",
        "X-Mail-From",
        "X-Entity-ID",
        "X-SES-Outgoing",
        "X-Sid",
        "X-Return-Path",
        "X-Abuse",
        "To",
        "Delivered-To",
        # Bez nich ten sam identyfikator w `In-Reply-To` i `References` dawał
        # ustalenie „nie znaleziono powtórzeń” przy dwóch identycznych wartościach.
        "In-Reply-To",
        "References",
        # Nagłówki uwierzytelnienia to miejsce, w którym identyfikator koperty
        # powtarza się najczęściej — wykluczenie ich z zakresu nie miało
        # uzasadnienia i zaniżało liczniki najbardziej.
        "Received-SPF",
        "ARC-Authentication-Results",
    ):
        # `msg.get` jest niewrażliwe na wielkość liter, więc `Message-ID`
        # i `Message-Id` zwracają tę samą wartość — bez tego filtra ten sam
        # nagłówek liczył się w sekcji jako dwa różne miejsca wystąpienia.
        if name.lower() in seen_lower:
            continue
        values = msg.get_all(name) or []
        if not values:
            continue
        seen_lower.add(name.lower())
        # `get_all`, nie `get`: drugi `Return-Path` (wstawiony przez nadawcę,
        # poniżej bloku dopisanego przez serwer odbiorcy) był pomijany, a to on
        # bywa jedynym śladem adresu zwrotnego zadeklarowanego u źródła.
        for index, value in enumerate(values, 1):
            label = name if len(values) == 1 else f"{name} #{index}"
            out[label] = str(value)

    # Tylko pola, nie surowy nagłówek: `Received` w całości wnosi daty i nazwy
    # hostów, które powtarzają się w każdym skoku i zalałyby sekcję szumem.
    # Same pola HELO/rDNS/IP już nie są szumem — to nazwy i adresy, które
    # sekcja deklaruje w zakresie („pola `Received`”), a których nie zbierała.
    for hop in hops:
        if hop.queue_id:
            out[f"Received skok {hop.index} (id)"] = hop.queue_id
        if hop.for_address:
            out[f"Received skok {hop.index} (for)"] = hop.for_address
        if hop.helo:
            out[f"Received skok {hop.index} (HELO)"] = hop.helo
        if hop.rdns:
            out[f"Received skok {hop.index} (rDNS)"] = hop.rdns
        if hop.ip:
            out[f"Received skok {hop.index} (IP)"] = hop.ip
        if hop.by:
            out[f"Received skok {hop.index} (by)"] = hop.by

    for resource in resources:
        label = f"treść: {resource.kind} {resource.host or ''}".strip()
        out[label] = resource.url

    # Zdekodowana treść tokenu też jest miejscem wystąpienia — bez niej
    # `X-EMAIL-ID: 4494` i `email:4494` z ładunku Base64 zostają rozłączne.
    for token in tokens:
        if token.decoded_text:
            out[f"zdekodowany token ({token.source})"] = token.decoded_text

    # Skróty i podpisy: identyczne `bh=` w DKIM-Signature i ARC-Message-Signature
    # znaczy, że pośrednik policzył skrót ciała na tych samych bajtach, co serwer
    # podpisujący. Bez tych wartości sekcja nie miała czego porównać.
    for name in ("DKIM-Signature", "ARC-Message-Signature", "Authentication-Results"):
        for index, value in enumerate(msg.get_all(name) or [], 1):
            out[f"{name} #{index}"] = re.sub(r"\s+", "", str(value))

    return out


#: Źródła, w których szukamy wyłącznie pełnych wartości tagów. Wartości `bh=`
#: i `b=` to base64 ze znakami `+` i `/`, więc ogólny skaner rozbijałby je na
#: przypadkowe fragmenty i zamiast jednego ustalenia dawał trzy pozycje szumu.
SIGNATURE_SOURCES = frozenset(
    {
        "DKIM-Signature #1",
        "DKIM-Signature #2",
        "ARC-Message-Signature #1",
        "ARC-Message-Signature #2",
        "Authentication-Results #1",
        "Authentication-Results #2",
    }
)


def collect_seed_identifiers(msg: email.message.Message) -> tuple[str, ...]:
    """Wartości szukane wprost, niezależnie od progu długości skanera.

    Dwie klasy: krótkie identyfikatory kampanii z nagłówków `X-*` (bez nich
    `X-EMAIL-ID: 4494` nigdy nie spotka się z `email";i:4494;` z rozkodowanego
    ładunku linku) oraz pełne wartości tagów `bh=` i `b=` z podpisów.

    >>> from email import message_from_string, policy
    >>> src = ("X-EMAIL-ID: 4494\\n"
    ...        "DKIM-Signature: v=1; d=a.pl; s=s; h=From; bh=WSPOLNY/HASH+=; b=PODPIS123\\n\\nx")
    >>> collect_seed_identifiers(message_from_string(src, policy=policy.default))
    ('4494', 'WSPOLNY/HASH+=', 'PODPIS123')
    >>> collect_seed_identifiers(message_from_string("From: a@b.pl\\n\\nx", policy=policy.default))
    ()
    """
    seeds: list[str] = []
    for name in ("X-EMAIL-ID", "X-Campaign", "X-Sid", "X-Entity-Ref-ID", "X-EmailGuid"):
        value = msg.get(name)
        if value and len(str(value).strip()) >= 3:
            seeds.append(str(value).strip())

    for name in ("DKIM-Signature", "ARC-Message-Signature"):
        for raw in msg.get_all(name) or []:
            normalized = re.sub(r"\s+", "", str(raw))
            for tag in ("bh", "b"):
                match = re.search(rf"(?:^|;){tag}=([^;]+)", normalized)
                if match and match.group(1) not in seeds:
                    seeds.append(match.group(1))
    return tuple(seeds)


def collect_declared_identifiers(msg: email.message.Message) -> tuple[str, ...]:
    """Identyfikatory kampanii/konta zadeklarowane wprost przez nadawcę.

    `List-Id: <41634.z.przyklad.pl>` i `Feedback-ID: 41634m2:41634:…` nazywają
    identyfikator wprost. Ten sam ciąg bywa potem **wtopiony** w adres zwrotny
    VERP, w nazwę pliku piksela i w nazwę hosta — czyli w miejsca, w których
    skaner całych tokenów nigdy go nie znajdzie. Zwracamy je jako ziarna
    szukane jako podciąg, bo pochodzą z deklaracji w pliku, a nie z dopasowania.

    >>> from email import message_from_string, policy
    >>> src = ("List-Id: <41634.z.przyklad.pl>\\n"
    ...        "Feedback-ID: 41634m2:41634:newsletter:dostawca\\n\\nx")
    >>> collect_declared_identifiers(message_from_string(src, policy=policy.default))
    ('41634',)
    >>> collect_declared_identifiers(message_from_string("From: a@b.pl\\n\\nx",
    ...                                                  policy=policy.default))
    ()
    """
    found: list[str] = []

    def add(value: str) -> None:
        # Próg 4 znaków: krótsze ciągi cyfr trafiają się w danych przypadkowo,
        # a szukamy ich jako podciągu, więc fałszywe trafienie jest tanie do
        # wyprodukowania i drogie w odbiorze.
        if len(value) >= 4 and value not in found:
            found.append(value)

    for raw in msg.get_all("List-Id") or []:
        label = re.sub(r"[<>]", "", str(raw)).strip().split(".")[0]
        if re.fullmatch(r"[0-9]+", label):
            add(label)
    for raw in msg.get_all("Feedback-ID") or []:
        for field in str(raw).split(":"):
            if re.fullmatch(r"[0-9]{4,}", field.strip()):
                add(field.strip())
    return tuple(found)


def build_report(eml_path: Path, outdir: Path) -> tuple[str, Path]:
    """Buduje raport dla jednego pliku .eml i zapisuje artefakty; zwraca (raport, ścieżka).

    >>> import tempfile
    >>> from pathlib import Path
    >>> src = (b"From: Marka <nadawca@wysylka.pl>\\r\\n"
    ...        b"To: klient+kanal@odbiorca.pl\\r\\n"
    ...        b"Subject: Temat\\r\\n"
    ...        b"Date: Fri, 07 Aug 2026 15:06:02 +0200\\r\\n"
    ...        b"Content-Type: text/html\\r\\n\\r\\n"
    ...        b'<a href="https://sledzenie.example/r?ct=YWJjZGVmZ2hpams=">Oferta</a>')
    >>> with tempfile.TemporaryDirectory() as td:
    ...     p = Path(td) / "wiadomosc.eml"
    ...     _ = p.write_bytes(src)
    ...     report, out = build_report(p, Path(td))
    ...     "sledzenie.example" in report
    True
    """
    raw = load_raw_bytes(eml_path)
    msg = load_message(eml_path)
    stem = eml_path.stem

    raw_headers = raw_header_block(raw)
    normalized_headers = extract_headers_text(msg)
    html_body, text_body = extract_bodies(msg)

    path_raw_headers = outdir / f"{stem}_naglowki.txt"
    save_text_file(path_raw_headers, raw_headers + "\n")
    path_norm_headers = outdir / f"{stem}_naglowki_norm.txt"
    save_text_file(path_norm_headers, normalized_headers + "\n")

    written = [
        Artifact(
            name=eml_path.name,
            sha256=sha256(eml_path),
            description="oryginał wiadomości RFC 822 — DOWÓD GŁÓWNY, nie modyfikować",
        ),
        build_artifact(
            path_raw_headers,
            "surowy blok nagłówków — bajty z pliku do pierwszej pustej linii, "
            "bez rozwijania zwinięć i bez dekodowania RFC 2047",
        ),
        build_artifact(
            path_norm_headers,
            "nagłówki po sparsowaniu — zwinięcia rozwinięte, encoded-words zdekodowane, "
            "składnia znormalizowana przez parser; NIE jest kopią bajtową oryginału",
        ),
    ]
    if html_body is not None:
        path = outdir / f"{stem}_tresc.html"
        save_text_file(path, html_body)
        written.append(
            build_artifact(path, "część text/html po zdekodowaniu transfer-encoding")
        )
    if text_body is not None:
        path = outdir / f"{stem}_tresc.txt"
        save_text_file(path, text_body)
        written.append(
            build_artifact(path, "część text/plain po zdekodowaniu transfer-encoding")
        )

    source = html_body or text_body or ""

    lines: list[str] = []
    W = lines.append
    W(f"# Analiza techniczna wiadomości `{eml_path.name}`\n")
    W(
        f"Wygenerowano skryptem `eml_forensics.py`. SHA-256 pliku źródłowego: `{sha256(eml_path)}`\n"
    )
    W(
        "Raport zawiera wartości odczytane z pliku i wyliczenia na nich. Nie zawiera "
        "kwalifikacji prawnej, ocen charakteru wiadomości ani hipotez o intencjach "
        "nadawcy.\n"
    )

    addresses = extract_addresses(msg)
    hops = extract_hops(msg)
    dkim = extract_dkim_signatures(msg)
    auth_headers = extract_auth_headers(msg)
    resources = extract_html_resources(source)
    mime_tree = build_mime_tree(msg)

    # `From` i `Reply-To` też bywają zakodowane wg RFC 2047 i zwinięte — czyli
    # są dokładnie tym, co ta tabela ma pokazywać. Ograniczenie jej do `Subject`
    # i `Date` pomijało nazwę wyświetlaną, w której różnica bajt/parser ma
    # największe znaczenie dowodowe.
    write_identification(
        addresses,
        msg.get("Subject"),
        msg.get("Date"),
        tuple(
            (name, raw_header_value(raw_headers, name), msg.get(name))
            for name in ("Subject", "Date", "From", "Reply-To", "To")
        ),
        header_names(msg),
        W,
    )
    write_mime_section(mime_tree, extract_attachments(mime_tree), W)
    write_received_section(hops, collect_net_addresses(msg, hops), W)
    write_timeline_section(extract_timestamps(msg), W)

    write_auth_section(auth_headers, W)
    signed = dkim[0].signed_headers if dkim else ()
    wlasne, tranzytowe = unsigned_headers(msg, signed)
    write_dkim_section(dkim, wlasne, tranzytowe, oversigned_headers(msg, signed), W)
    write_arc_section(
        extract_arc_seals(msg), extract_arc_message_signatures(msg), dkim, W
    )
    write_spam_headers_section(extract_spam_headers(msg), W)

    from_domain = next((a.domain for a in addresses.get("From", []) if a.domain), None)
    mailfrom = None
    for header in auth_headers:
        for method in header.methods:
            if "smtp.mailfrom" in method.props:
                mailfrom = method.props["smtp.mailfrom"]
                break
    mailfrom_domain = mailfrom.rsplit("@", 1)[-1].lower() if mailfrom else None
    if mailfrom_domain is None:
        mailfrom_domain = next(
            (a.domain for a in addresses.get("Return-Path", []) if a.domain), None
        )
    alignment = Alignment.compute(
        from_domain, mailfrom_domain, tuple(s.domain for s in dkim)
    )
    write_dmarc_section(auth_headers, alignment, W)

    write_reply_to_section(addresses, W)
    write_list_headers_section(collect_list_headers(msg), rfc8058_compliance(msg), W)
    write_domains_section(collect_domains(msg, hops, resources, dkim), W)
    write_message_id_section(msg.get("Message-ID") or msg.get("Message-Id"), W)
    write_thread_section(
        msg.get("Subject"), msg.get("In-Reply-To"), msg.get("References"), W
    )

    tokens = (
        decode_tokens(source, "treść")
        + decode_header_tokens(msg)
        + decode_hop_tokens(hops)
    )
    write_tokens_section(tokens, W)

    write_repeated_identifiers_section(
        repeated_identifiers(
            collect_identifier_sources(msg, hops, resources, tokens),
            seeds=collect_seed_identifiers(msg),
            seed_only=SIGNATURE_SOURCES,
            substring_seeds=collect_declared_identifiers(msg),
        ),
        W,
    )

    write_resources_section(resources, W)
    write_html_constructs_section(source, text_body if html_body else None, W)
    write_hidden_section(
        find_hidden_elements(source),
        stylesheet_hiding_rules(source),
        len(re.findall(r"""style\s*=\s*["']""", source)),
        W,
    )
    write_content_section(html_body, text_body, compare_parts(html_body, text_body), W)
    write_software_section(software_fingerprints(msg, html_body), W)

    stat = eml_path.stat()
    # Identyfikatory szukane w treści WIDOCZNEJ (obie części), nie w nagłówkach —
    # numer rachunku i dane rejestrowe stoją w stopce wiadomości.
    scannable_text = " ".join(
        filter(None, [deobfuscate(html_body) if html_body else None, text_body])
    )
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
    # Sekcja tożsamości PRZED sekcją artefaktów: ta druga kończy się stopką
    # zamykającą dokument, więc wszystko dopięte po niej wisiało poza raportem.
    write_identity_layers_section(
        identity_layers(msg, dkim, resources),
        registry_identifiers(scannable_text),
        W,
        tuple(organisations_in_content(scannable_text)),
    )
    write_artifacts_section(
        eml_path.name,
        stat.st_size,
        mtime,
        sha256(eml_path),
        line_endings(raw),
        written,
        W,
        msg.get("Date"),
    )

    report = "\n".join(lines) + "\n"
    path_report = outdir / f"{stem}_analiza.md"
    save_text_file(path_report, report)
    return report, path_report


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("eml")
    parser.add_argument("--outdir", default=None)
    args = parser.parse_args()

    eml_path = Path(args.eml)
    outdir = Path(args.outdir) if args.outdir else eml_path.resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)

    report, path_report = build_report(eml_path, outdir)
    print(report)
    print(f"\n[zapisano] {path_report}", file=sys.stderr)


if __name__ == "__main__":
    main()
