"""eml_forensics_logika.py — czyste funkcje ekstrakcji faktów z wiadomości .eml.

Bez I/O poza wczytaniem pliku źródłowego (load_message, load_raw_bytes) i bez żadnego
formatowania markdown — wejście: email.Message albo tekst, wyjście: dane (str, list,
dataclass). Renderowanie raportu żyje w eml_forensics_raport.py, orchestracja (CLI,
zapis plików) w eml_forensics.py.

Zasada nadrzędna: **fakt, nie hipoteza**. Funkcje zwracają to, co w pliku jest —
z etykietą źródła. Nigdy nie zwracają wartości domyślnych „typowych dla takich
wiadomości", nie sklejają dwóch nagłówków w jeden i nie normalizują cytatów.
Kwalifikacja (czy coś jest „obfuskacją”, „podszyciem”, „spamem”) nie należy do tej
warstwy ani do raportu — to zadanie człowieka czytającego dowód.
"""

import base64
import binascii
import collections
import datetime
import email
import email.message
import email.policy
import email.utils
import hashlib
import html
import ipaddress
import itertools
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field, replace
from pathlib import Path

ZERO_WIDTH_CHARS = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE",
    0x00AD: "SOFT HYPHEN",
    0x2060: "WORD JOINER",
    0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0x200E: "LEFT-TO-RIGHT MARK",
    0x200F: "RIGHT-TO-LEFT MARK",
    0x2061: "FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR",
    0x2064: "INVISIBLE PLUS",
    # Selektor wariantu emoji — kategoria Unicode `Mn`, nie `Cf`, więc filtr
    # oparty wyłącznie na znakach sterujących go przepuszczał.
    0xFE0E: "VARIATION SELECTOR-15",
    0xFE0F: "VARIATION SELECTOR-16",
}

#: Znaki interpunkcyjne spoza ASCII, które są normalną typografią, nie próbą
#: podszycia. Zliczamy je osobno — opisanie en dasha jako „wygląda jak -”
#: ustawiało poprawną polską typografię jako sygnał ryzyka.
TYPOGRAPHY_CHARS = {
    0x2013: "EN DASH",
    0x2014: "EM DASH",
    0x2018: "LEFT SINGLE QUOTATION MARK",
    0x2019: "RIGHT SINGLE QUOTATION MARK",
    0x201C: "LEFT DOUBLE QUOTATION MARK",
    0x201D: "RIGHT DOUBLE QUOTATION MARK",
    0x201E: "DOUBLE LOW-9 QUOTATION MARK",
    0x2026: "HORIZONTAL ELLIPSIS",
    0x2192: "RIGHTWARDS ARROW",
    0x00AE: "REGISTERED SIGN",
    0x00A9: "COPYRIGHT SIGN",
    0x2122: "TRADE MARK SIGN",
    0x00B9: "SUPERSCRIPT ONE",
    0x00A7: "SECTION SIGN",
}

#: Znaki wyglądające jak zwykłe ASCII, ale mające inny code point. Klucz — znak
#: podejrzany, wartość — (nazwa Unicode, ASCII, na które wygląda). Lista jest krótka
#: i celowo obejmuje tylko homoglify spotykane realnie w treściach e-mail; szerszy
#: zbiór (pełne confusables UTS #39) wymagałby danych spoza stdlib.
HOMOGLYPHS = {
    "․": ".",  # ONE DOT LEADER
    "‧": ".",  # HYPHENATION POINT
    "．": ".",  # FULLWIDTH FULL STOP
    "。": ".",  # IDEOGRAPHIC FULL STOP
    " ": " ",  # NO-BREAK SPACE
    " ": " ",  # FIGURE SPACE
    " ": " ",  # NARROW NO-BREAK SPACE
    " ": " ",  # THIN SPACE
    "−": "-",  # MINUS SIGN
    "＠": "@",  # FULLWIDTH COMMERCIAL AT
    "а": "a",  # CYRILLIC SMALL LETTER A
    "е": "e",  # CYRILLIC SMALL LETTER IE
    "о": "o",  # CYRILLIC SMALL LETTER O
    "р": "p",  # CYRILLIC SMALL LETTER ER
    "с": "c",  # CYRILLIC SMALL LETTER ES
    "х": "x",  # CYRILLIC SMALL LETTER HA
    "ѕ": "s",  # CYRILLIC SMALL LETTER DZE
    "і": "i",  # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "ο": "o",  # GREEK SMALL LETTER OMICRON
    "Α": "A",  # GREEK CAPITAL LETTER ALPHA
}

#: Tokeny protokołu z klauzuli `with` nagłówka Received (RFC 5321 §4.4 + rozszerzenia).
#: Regex `with\s+(\w+)` bez tej listy łapie słowo „cipher” z `(using TLSv1.3 with
#: cipher ...)` — realny błąd z raportu 2026-08-10.
RECEIVED_PROTOCOLS = {
    "SMTP",
    "ESMTP",
    "ESMTPA",
    "ESMTPS",
    "ESMTPSA",
    "LMTP",
    "LMTPA",
    "LMTPS",
    "LMTPSA",
    "UTF8SMTP",
    "UTF8SMTPA",
    "UTF8SMTPS",
    "UTF8SMTPSA",
    "HTTP",
    "HTTPS",
    "MAPI",
    "LOCAL",
    "BSMTP",
    "QMQP",
}

#: Nagłówki, których obecność/wartość opisuje filtr antyspamowy po którejś stronie
#: trasy. Dopasowanie po prefiksie, bo każdy producent ma własny zestaw.
SPAM_HEADER_PREFIXES = (
    "x-spam",
    "x-vade",
    "x-dcc",
    "x-microsoft-antispam",
    "x-forefront-antispam",
    "x-ms-exchange-organization-scl",
    "x-ms-exchange-atpmessageproperties",
    "x-rspamd",
    "x-barracuda",
    "x-proofpoint",
    "x-sophos",
    "x-mailscanner",
    "x-virus",
    "x-bogosity",
    "x-quarantine",
    "x-fireeye",
)

#: URI używane jako identyfikator przestrzeni nazw / DTD, nie jako link nadawcy.
#: Bez tej listy `xmlns="http://www.w3.org/1999/xhtml"` trafia do „linków w treści”
#: i zawyża licznik domen (realny błąd w 4 raportach).
BOILERPLATE_URL_HOSTS = frozenset(
    {
        "www.w3.org",
        "w3.org",
        "schemas.microsoft.com",
        "www.microsoft.com/office",
        "purl.org",
        "ns.adobe.com",
    }
)


# ──────────────────────────── modele danych ────────────────────────────


@dataclass(frozen=True, slots=True)
class Address:
    """Jeden adres z nagłówka adresowego — nazwa wyświetlana i adres rozdzielone.

    Zachowuje część lokalną w całości, razem z tagiem `+`. Zgubienie `+` zmienia
    adres w dokumencie dowodowym na inny adres (błąd powtórzony w 6 raportach:
    `klient+acd@` zapisywane jako `klientacd@`).

    >>> a = Address.parse("Nazwa Wyswietlana <uzytkownik+tag@przyklad.pl>")
    >>> a.display_name
    'Nazwa Wyswietlana'
    >>> a.addr_spec
    'uzytkownik+tag@przyklad.pl'
    >>> a.local
    'uzytkownik+tag'
    >>> a.domain
    'przyklad.pl'
    >>> a.tag
    'tag'
    >>> Address.parse("bez.tagu@przyklad.pl").tag is None
    True
    >>> Address.parse("Google <nadawca@zupelnie-inna.pl>").display_name
    'Google'
    >>> Address.parse("").addr_spec
    ''
    """

    display_name: str
    addr_spec: str

    @classmethod
    def parse(cls, raw: str) -> "Address":
        name, addr = email.utils.parseaddr(str(raw or ""))
        return cls(display_name=name.strip(), addr_spec=addr.strip())

    @property
    def local(self) -> str:
        return (
            self.addr_spec.rsplit("@", 1)[0]
            if "@" in self.addr_spec
            else self.addr_spec
        )

    @property
    def domain(self) -> str | None:
        return (
            self.addr_spec.rsplit("@", 1)[1].lower() if "@" in self.addr_spec else None
        )

    @property
    def tag(self) -> str | None:
        """Sufiks po `+` w części lokalnej (subaddressing, RFC 5233)."""
        return self.local.split("+", 1)[1] if "+" in self.local else None


@dataclass(frozen=True, slots=True)
class AuthMethod:
    """Jedna metoda z nagłówka Authentication-Results: nazwa, wynik, właściwości.

    Regex `arc=` bez granicy tokenu dopasowuje się do podciągu w `dmarc=` — stąd
    „wynik ARC” w raportach wiadomości, które żadnego ARC nie miały.

    >>> [ (m.method, m.result) for m in AuthMethod.parse_all("dkim=pass header.i=@a.pl; dmarc=fail") ]
    [('dkim', 'pass'), ('dmarc', 'fail')]
    >>> [m.method for m in AuthMethod.parse_all("dmarc=pass")]
    ['dmarc']
    >>> AuthMethod.parse_all("spf=softfail (domena nie autoryzuje) smtp.mailfrom=a@b.pl")[0].props
    {'smtp.mailfrom': 'a@b.pl'}
    >>> AuthMethod.parse_all("spf=softfail (domena nie autoryzuje) smtp.mailfrom=a@b.pl")[0].comment
    'domena nie autoryzuje'
    >>> AuthMethod.parse_all("")
    []
    """

    method: str
    result: str
    comment: str | None
    props: dict[str, str]

    @classmethod
    def parse_all(cls, value: str) -> "list[AuthMethod]":
        text = re.sub(r"\s+", " ", str(value or ""))
        # Komentarze w nawiasach wycinamy PRZED szukaniem metod. Wnętrze komentarza
        # `arc=pass (i=1 spf=pass ... dkim=pass ... dmarc=pass ...)` to opis cudzego
        # sprawdzenia, nie osobne wyniki — parser robił z niego sześć dodatkowych
        # wierszy i sztucznie zwiększał liczbę „potwierdzeń”.
        bez_komentarzy = re.sub(r"\([^()]*\)", lambda m: " " * len(m.group(0)), text)
        # (?<![\w.-]) blokuje dopasowanie „arc” wewnątrz „dmarc” — bez tego każdy
        # nagłówek z wynikiem DMARC produkował w raporcie nieistniejący wynik ARC.
        pattern = re.compile(
            r"(?<![\w.-])(dkim-atps|dkim|spf|dmarc|arc|iprev|auth|bimi)"
            r"=([A-Za-z][A-Za-z0-9_-]*)",
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(bez_komentarzy))
        out: list[AuthMethod] = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            tail = text[m.end() : end]
            comment_match = re.search(r"\(([^)]*)\)", tail)
            # Właściwości bierzemy spoza nawiasu z komentarzem — w nawiasie stoi
            # polityka (`p=NONE sp=NONE`), która nie jest właściwością metody.
            outside = re.sub(r"\([^)]*\)", " ", tail)
            props = {
                # Wartości bywają w cudzysłowach (`smtp.mailfrom="a@b.pl"`); bez ich
                # zdjęcia domena w tabeli wyrównania kończyła się znakiem `"`,
                # a wniosek o braku wyrównania opierał się na literówce.
                k.lower(): v.strip("\"'")
                for k, v in re.findall(
                    r"([a-z][\w.-]*)=([^\s;()]+)", outside, re.IGNORECASE
                )
            }
            out.append(
                cls(
                    method=m.group(1).lower(),
                    result=m.group(2).lower(),
                    comment=comment_match.group(1).strip() if comment_match else None,
                    props=props,
                )
            )
        return out


@dataclass(frozen=True, slots=True)
class AuthHeader:
    """Jeden nagłówek uwierzytelnienia — cytowany dosłownie, z nazwą i kolejnością.

    Sklejenie `Authentication-Results` z `Received-SPF` w jeden blok robi z cytatu
    konstrukt parsera; w materiale dowodowym każdy nagłówek musi stać osobno,
    z atrybucją do hosta, który go dopisał.

    >>> h = AuthHeader(name="Authentication-Results", index=1, raw="mx.example.com; dkim=pass")
    >>> h.authserv_id
    'mx.example.com'
    >>> [m.method for m in h.methods]
    ['dkim']
    >>> AuthHeader(name="Received-SPF", index=1, raw="pass (example.com: ...)").authserv_id is None
    True

    W nagłówku ARC identyfikator serwera stoi za `i=N;` — bez pominięcia tego pola
    wystawca gubił się i raport nie mówił, kto dany wynik wpisał:

    >>> AuthHeader(name="ARC-Authentication-Results", index=1,
    ...            raw="i=1; mx.example.com; spf=pass").authserv_id
    'mx.example.com'
    """

    name: str
    index: int
    raw: str

    @property
    def authserv_id(self) -> str | None:
        """Identyfikator serwera, który nagłówek wystawił (pierwsze pole przed `;`)."""
        if self.name.lower() not in {
            "authentication-results",
            "arc-authentication-results",
        }:
            return None
        rest = re.sub(r"^\s*i=\d+\s*;\s*", "", self.raw)
        head = rest.split(";", 1)[0].strip()
        # Gdy nagłówek nie ma authserv-id, pierwsze pole jest już wynikiem
        # (`dkim=none (message not signed) header.d=none`) — branie go za wystawcę
        # wpisywało do raportu hosta, którego w pliku nie ma.
        if not head or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}", head
        ):
            return None
        return head

    @property
    def methods(self) -> list[AuthMethod]:
        return AuthMethod.parse_all(self.raw)


@dataclass(frozen=True, slots=True)
class DkimSignature:
    """Sparsowany nagłówek DKIM-Signature — wszystkie tagi, jedno źródło prawdy.

    >>> sig = DkimSignature.parse(
    ...     "v=1; d=przyklad.pl; s=selektor1; a=rsa-sha256; c=relaxed/simple; "
    ...     "t=1786107962; x=1786194362; h=From:Subject:Date; bh=YWJjZGVmZ2hpams="
    ... )
    >>> sig.domain, sig.selector, sig.algorithm, sig.canonicalization
    ('przyklad.pl', 'selektor1', 'rsa-sha256', 'relaxed/simple')
    >>> sig.signed_headers
    ('From', 'Subject', 'Date')
    >>> sig.timestamp
    1786107962
    >>> sig.expires
    1786194362
    >>> sig.body_length is None
    True
    >>> DkimSignature.parse("d=inna.pl; h=To:Cc;").selector is None
    True
    >>> DkimSignature.parse("h=To;") is None
    True

    Tag `l=` ogranicza podpis do pierwszych N bajtów ciała; jego brak znaczy, że
    podpisane jest całe ciało:

    >>> DkimSignature.parse("d=a.pl; h=From; l=1024;").body_length
    1024

    Tagi spoza stałej listy też są zapisane — `fh=` i `dara=` z podpisów ARC
    Google nie trafiały do raportu w ogóle, choć są w pliku:

    >>> DkimSignature.parse("d=a.pl; h=From; fh=WNiyod5=; dara=google.com").other_tags
    (('fh', 'WNiyod5='), ('dara', 'google.com'))
    """

    domain: str
    selector: str | None
    algorithm: str | None
    canonicalization: str | None
    body_hash: str | None
    signed_headers: tuple[str, ...]
    timestamp: int | None
    expires: int | None
    body_length: int | None
    identity: str | None
    #: Pozostałe tagi podpisu, w kolejności z pliku. Tabela wypisywała stałą
    #: listę pól, więc `fh=`, `dara=`, `v=`, `q=` i sama wartość `b=` nie
    #: pojawiały się w raporcie w ogóle — mimo że są w pliku.
    other_tags: tuple[tuple[str, str], ...] = ()

    @classmethod
    def parse(cls, raw: str) -> "DkimSignature | None":
        normalized = re.sub(r"\s+", "", str(raw))
        tags = dict(re.findall(r"(?:^|;)\s*([a-z]+)=([^;]*)", normalized))
        if "d" not in tags or "h" not in tags:
            return None

        def as_int(key: str) -> int | None:
            value = tags.get(key, "")
            return int(value) if value.isdigit() else None

        return cls(
            domain=tags["d"].strip(),
            selector=tags.get("s", "").strip() or None,
            algorithm=tags.get("a", "").strip() or None,
            canonicalization=tags.get("c", "").strip() or None,
            body_hash=tags.get("bh", "").strip() or None,
            signed_headers=tuple(h for h in tags["h"].strip().split(":") if h),
            timestamp=as_int("t"),
            expires=as_int("x"),
            body_length=as_int("l"),
            identity=tags.get("i", "").strip() or None,
            other_tags=tuple(
                (klucz, value.strip())
                for klucz, value in tags.items()
                if klucz not in {"d", "s", "a", "c", "bh", "h", "t", "x", "l", "i"}
                and value.strip()
            ),
        )


@dataclass(frozen=True, slots=True)
class ArcSet:
    """Jeden zestaw ARC (i=N): pieczęć, podpis wiadomości, wynik uwierzytelnienia.

    `cv=none` znaczy „nie było wcześniejszego łańcucha” — nie „pośrednicy
    zweryfikowali i zapieczętowali". Bez tego tagu opis ARC jest zmyślony.

    >>> s = ArcSet.parse_seal("i=1; a=rsa-sha256; d=example.com; s=arc-20240605; cv=none; t=1787985652")
    >>> s.index, s.domain, s.chain_validation, s.timestamp
    (1, 'example.com', 'none', 1787985652)
    >>> ArcSet.parse_seal("brak tagów") is None
    True
    """

    index: int | None
    domain: str | None
    selector: str | None
    chain_validation: str | None
    timestamp: int | None

    @classmethod
    def parse_seal(cls, raw: str | None) -> "ArcSet | None":
        if not raw:
            return None
        normalized = re.sub(r"\s+", "", str(raw))
        tags = dict(re.findall(r"(?:^|;)\s*([a-z]+)=([^;]*)", normalized))
        if not tags:
            return None
        index = tags.get("i", "")
        timestamp = tags.get("t", "")
        return cls(
            index=int(index) if index.isdigit() else None,
            domain=tags.get("d", "").strip() or None,
            selector=tags.get("s", "").strip() or None,
            chain_validation=tags.get("cv", "").strip() or None,
            timestamp=int(timestamp) if timestamp.isdigit() else None,
        )


def _bez_strefy(value: str) -> str:
    """Adres bez indeksu strefy — `ipaddress` nie przyjmuje sufiksu `%N`.

    >>> _bez_strefy("fe80::1%5")
    'fe80::1'
    >>> _bez_strefy("93.184.216.34")
    '93.184.216.34'
    """
    return value.split("%", 1)[0]


@dataclass(frozen=True, slots=True)
class NetAddress:
    """Adres sieciowy z nagłówka Received, z etykietą roli i kategorii.

    Bez rozdzielenia kategorii wewnętrzny identyfikator Google (`2002:a05:...`,
    prefiks 6to4 z osadzonym adresem prywatnym) stoi w raporcie obok jedynego
    realnego adresu nadawcy — błąd obecny we WSZYSTKICH badanych raportach.

    >>> NetAddress.classify("93.184.216.34")
    'publiczny'
    >>> NetAddress.classify("10.5.113.8")
    'prywatny'
    >>> NetAddress.classify("198.18.7.9")
    'prywatny'
    >>> NetAddress.classify("127.0.0.1")
    'pętla zwrotna'
    >>> NetAddress.classify("2002:a05:7109:c30a:b0:579:5199:ff53")
    'prefiks 2002::/16 z osadzonym 10.5.113.9 (adres prywatny — nie spełnia RFC 3056 dla 6to4)'
    >>> NetAddress.classify("2a01:111:f403:c202::7")
    'publiczny'
    >>> NetAddress.classify("15.21.339.8")
    'nie jest adresem IP'
    >>> NetAddress.classify("203.0.113.9")
    'dokumentacyjny (RFC 5737)'
    """

    value: str
    role: str
    category: str

    #: Zakresy z RFC 5737 / RFC 3849 — zarezerwowane na przykłady w dokumentacji.
    #: `ipaddress` zalicza je do `is_private`, przez co adres z przykładu wyglądałby
    #: w raporcie jak adres z sieci wewnętrznej nadawcy.
    DOC_RANGES = (
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
        ipaddress.ip_network("2001:db8::/32"),
    )

    @staticmethod
    def classify(value: str) -> str:
        try:
            addr = ipaddress.ip_address(_bez_strefy(value))
        except ValueError:
            return "nie jest adresem IP"
        if addr.version == 6 and str(addr).startswith("2002:"):
            # 6to4 (RFC 3056): 32 bity po prefiksie to osadzony adres IPv4.
            # Wyliczona wartość jest dowodem, sama etykieta „prywatny” już nie —
            # dlatego adres podajemy zawsze, a kategorię tylko jako dopisek.
            embedded = ipaddress.ip_address((int(addr) >> 80) & 0xFFFFFFFF)
            if embedded.is_private or embedded.is_loopback:
                # RFC 3056 §2 wymaga, by w prefiksie 2002::/16 osadzony był
                # globalnie routowalny adres IPv4. Adres prywatny go nie
                # spełnia, więc nazwanie tego „adresem 6to4” twierdziłoby
                # więcej, niż wynika z pliku — to wewnętrzny literał hosta.
                return (
                    f"prefiks 2002::/16 z osadzonym {embedded} "
                    f"(adres prywatny — nie spełnia RFC 3056 dla 6to4)"
                )
            return f"6to4, osadzony {embedded}"
        if addr.is_loopback:
            return "pętla zwrotna"
        if addr.is_link_local:
            return "link-local"
        if any(
            addr in net for net in NetAddress.DOC_RANGES if net.version == addr.version
        ):
            return "dokumentacyjny (RFC 5737)"
        if addr.is_private:
            return "prywatny"
        return "publiczny"


def _first_address(text: str) -> str | None:
    """Pierwszy adres IP w tekście — w nawiasach kwadratowych albo bez nich.

    Exchange zapisuje adres bez kwadratowych nawiasów (`(2603:10a6:800:334::7)`),
    Postfix z nawiasami (`[203.0.113.9]`). Regex ograniczony do wariantu z
    nawiasami gubił oba adresy skoku wewnątrz Microsoft 365.

    >>> _first_address("rdns.przyklad.pl. [93.184.216.34]")
    '93.184.216.34'
    >>> _first_address("2603:10a6:800:334::7")
    '2603:10a6:800:334::7'
    >>> _first_address("version=TLS1_2, cipher=TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384") is None
    True
    >>> _first_address("") is None
    True
    >>> _first_address("[fe80::7c4f:2705:e5e5:c03e%5]")
    'fe80::7c4f:2705:e5e5:c03e%5'
    """
    # `%5` na końcu to indeks strefy adresu link-local (`fe80::…%5`). Należy do
    # wartości zapisanej w pliku, a tabela deklaruje dosłowność — obcinanie go
    # gubiło bajty. Do klasyfikacji podajemy adres bez indeksu.
    bracketed = re.search(r"\[([0-9a-fA-F:.]+(?:%[0-9A-Za-z]+)?)\]", text)
    if bracketed and NetAddress.classify(_bez_strefy(bracketed.group(1))) != (
        "nie jest adresem IP"
    ):
        return bracketed.group(1)
    for candidate in re.findall(r"[0-9a-fA-F:.]{3,}(?:%[0-9A-Za-z]+)?", text):
        candidate = candidate.strip(".")
        if NetAddress.classify(_bez_strefy(candidate)) != "nie jest adresem IP":
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class ReceivedHop:
    """Jeden nagłówek Received rozłożony na pola, z zachowaniem surowej treści.

    >>> raw = ("from nadawca.przyklad.pl (rdns.przyklad.pl. [203.0.113.9]) "
    ...        "by mx.odbiorca.pl with ESMTPS id abc123 "
    ...        "(version=TLS1_3 cipher=TLS_AES_256_GCM_SHA384 bits=256/256) "
    ...        "for <odbiorca+tag@odbiorca.pl>; Tue, 11 Aug 2026 17:38:45 -0700")
    >>> hop = ReceivedHop.parse(raw, 1)
    >>> hop.helo
    'nadawca.przyklad.pl'
    >>> hop.rdns
    'rdns.przyklad.pl.'
    >>> hop.ip
    '203.0.113.9'
    >>> hop.by
    'mx.odbiorca.pl'
    >>> hop.protocol
    'ESMTPS'
    >>> hop.tls
    'version=TLS1_3 cipher=TLS_AES_256_GCM_SHA384 bits=256/256'
    >>> hop.queue_id
    'abc123'
    >>> hop.for_address
    'odbiorca+tag@odbiorca.pl'
    >>> hop.is_internal
    False

    Klauzula `with` nie może brać słowa po pierwszym `with` — w nawiasie TLS
    stoi „with cipher”:

    >>> ReceivedHop.parse("from a by b (using TLSv1.3 with cipher TLS_AES_256) with ESMTPSA id x", 1).protocol
    'ESMTPSA'

    `id 15.21.339.8` (Microsoft) to numer wersji, nie adres:

    >>> hop = ReceivedHop.parse("from a.pl by b.pl with Microsoft SMTP Server id 15.21.339.8", 1)
    >>> hop.ip is None
    True
    >>> hop.queue_id
    '15.21.339.8'

    `helo=[127.0.0.1]` to deklaracja klienta, nie adres węzła trasy:

    >>> hop = ReceivedHop.parse("from [91.124.130.177] (helo=[127.0.0.1]) by mx.pl with ESMTPA", 1)
    >>> hop.ip
    '91.124.130.177'
    >>> hop.helo
    '[127.0.0.1]'

    `Received: by ...` bez klauzuli `from` to skok wewnątrz infrastruktury odbiorcy:

    >>> ReceivedHop.parse("by 2002:a05:7109:c30a:b0:579:5199:ff53 with SMTP id x", 1).is_internal
    True
    """

    index: int
    raw: str
    helo: str | None
    rdns: str | None
    ip: str | None
    by: str | None
    by_ip: str | None
    protocol: str | None
    tls: str | None
    queue_id: str | None
    for_address: str | None
    timestamp: datetime.datetime | None

    @property
    def is_internal(self) -> bool:
        """Skok bez klauzuli `from` — przekazanie wewnątrz jednej infrastruktury."""
        return self.helo is None and self.ip is None

    @classmethod
    def parse(cls, raw: str, index: int) -> "ReceivedHop":
        text = re.sub(r"\s+", " ", str(raw)).strip()

        # Data stoi po ostatnim `;` — obcinamy ją, żeby nie mieszała się do pól.
        head, _, date_part = text.rpartition(";")
        if not head:
            head, date_part = text, ""

        from_match = re.match(r"from\s+(\S+)", head, re.IGNORECASE)
        from_token = from_match.group(1) if from_match else None
        helo = from_token

        # `from nazwa (rdns. [ip])` — nawias po nazwie HELO niesie rDNS i/lub adres.
        rdns = ip = None
        paren = re.match(r"from\s+\S+\s+\(([^)]*)\)", head, re.IGNORECASE)
        if paren:
            inside = paren.group(1)
            # `helo=[...]` to wartość zadeklarowana przez klienta, nie adres ustalony
            # przez serwer — wycinamy ją, zanim poszukamy adresu w nawiasie.
            helo_match = re.search(r"helo=(\[?[^\s)\]]+\]?)", inside, re.IGNORECASE)
            if helo_match:
                helo = helo_match.group(1)
                inside = inside.replace(helo_match.group(0), " ")
            ip = _first_address(inside)
            rdns_match = re.match(r"([A-Za-z0-9._-]+?\.?)\s*(?:\[|$)", inside)
            if rdns_match:
                candidate = rdns_match.group(1).rstrip(".")
                # `unknown` to wartość wpisana przez Postfiksa, gdy PTR się nie
                # rozwiązał albo nie zgadza się z HELO. Odrzucenie jej jako „nie
                # domena” po cichu kasowało dowód z nagłówka.
                if "." in candidate or candidate.rstrip(".").lower() == "unknown":
                    # Kropka końcowa FQDN zostaje: tabela deklaruje wartości
                    # dosłowne, a `rstrip(".")` gubił bajt obecny w pliku.
                    rdns = rdns_match.group(1)
        if ip is None and from_token:
            bare = from_token.strip("[]")
            if NetAddress.classify(bare) != "nie jest adresem IP":
                ip = bare

        by_match = re.search(r"\bby\s+([^\s(;]+)", head, re.IGNORECASE)
        # Exchange zapisuje adres odbierającego hosta w nawiasie bez kwadratowych:
        # `by NAZWA (2603:10a6:20b:3e8::23) with Microsoft SMTP Server`.
        by_paren = re.search(r"\bby\s+\S+\s+\(([^)]*)\)", head, re.IGNORECASE)
        by_ip = _first_address(by_paren.group(1)) if by_paren else None
        # `with` w nawiasie („using TLSv1.3 with cipher …”) nie jest klauzulą protokołu.
        protocol = None
        for candidate in re.findall(r"\bwith\s+([A-Za-z0-9]+)", head, re.IGNORECASE):
            if candidate.upper() in RECEIVED_PROTOCOLS:
                protocol = candidate.upper()
                break
        if protocol is None:
            with_any = re.search(
                r"\bwith\s+([A-Za-z0-9 ]+?)(?=\s+id\b|\s*\(|$)", head, re.IGNORECASE
            )
            protocol = with_any.group(1).strip() if with_any else None

        # Klauzula TLS bywa zagnieżdżona: `(using TLSv1.3 with cipher X (256/256 bits))`.
        # Regex domykający na pierwszym `)` ucinał wartość w połowie.
        tls_match = re.search(
            r"\((version=(?:[^()]|\([^()]*\))*|using (?:[^()]|\([^()]*\))*)\)",
            head,
            re.IGNORECASE,
        )
        if tls_match is None:
            # Exim zapisuje TLS inaczej: `(TLS1.3) tls TLS_ECDHE_RSA_WITH_...`.
            # Parser znający wyłącznie format Google gubił to pole, a razem z nim
            # ślad, że kolejne skoki negocjowały różne zestawy szyfrów.
            tls_match = re.search(r"(\(TLS[0-9.]+\)\s+tls\s+[A-Za-z0-9_]+)", head)
        id_match = re.search(r"\bid\s+([A-Za-z0-9._@-]+)", head, re.IGNORECASE)
        # Exim pisze `for adres@domena` bez nawiasów kątowych; wymaganie `<>`
        # gubiło to pole na skoku nadawcy, a zostawiało na skoku odbiorcy.
        for_match = re.search(
            r"\bfor\s+(?:<([^>]+)>|([^\s;<>]+@[^\s;<>]+))", head, re.IGNORECASE
        )

        timestamp = None
        if date_part.strip():
            timestamp = parse_date_header(date_part.strip())

        return cls(
            index=index,
            raw=str(raw),
            helo=helo,
            rdns=rdns,
            ip=ip,
            by=by_match.group(1) if by_match else None,
            by_ip=by_ip,
            protocol=protocol,
            tls=tls_match.group(1).strip() if tls_match else None,
            queue_id=id_match.group(1) if id_match else None,
            for_address=(for_match.group(1) or for_match.group(2))
            if for_match
            else None,
            timestamp=timestamp,
        )


@dataclass(frozen=True, slots=True)
class MimePart:
    """Węzeł drzewa MIME — z zagnieżdżeniem, rozmiarem i sumą kontrolną ciała.

    Płaska lista typów gubi informację, że `multipart/related` zawiera
    `multipart/alternative`, a dopiero ten dwie części tekstowe.
    """

    depth: int
    content_type: str
    charset: str | None
    encoding: str | None
    filename: str | None
    content_id: str | None
    disposition: str | None
    size: int | None
    sha256: str | None


@dataclass(frozen=True, slots=True)
class HtmlResource:
    """Zasób odwoływany z HTML: link, obraz, skrypt, arkusz stylów, tło CSS.

    Raport, który parsuje wyłącznie `<a href>`, nie widzi pikseli śledzących
    `<img width=1 height=1>` ani `<script src>` — a to one bywają jedynym śladem
    rejestrowania otwarcia wiadomości.
    """

    kind: str
    url: str
    text: str | None
    scheme: str
    host: str | None
    width: str | None = None
    height: str | None = None
    attrs: str = ""
    occurrences: int = 1
    #: Pozostałe zapisy, w których ten sam URL występuje w treści. Ten sam
    #: piksel bywa jednocześnie `background:url(…)` i elementem 1×1, więc
    #: liczony per zapis dawał „zasobów: 5” tam, gdzie pobierane są 3 —
    #: i przeczył zdaniu „żadne odwołanie się nie powtarza” z tej samej sekcji.
    also_as: tuple[str, ...] = ()
    #: Czy znacznik NIÓSŁ atrybut `alt` (niezależnie od jego wartości). Pole
    #: istnieje, bo `attrs` jest obcinane do 200 znaków, więc przy długim URL-u
    #: `alt=""` wypadało za granicę i raport pisał „brak atrybutu” o znaczniku,
    #: który ten atrybut ma. `alt=""` i brak `alt` to dwa różne stany pliku.
    alt_present: bool = False

    @property
    def is_pixel(self) -> bool:
        """Obraz o zadeklarowanych wymiarach 1×1 (albo 0) — z atrybutów albo z CSS.

        Wymiary bywają podane wyłącznie w `style="width:1px;height:1px"`. Detektor
        czytający same atrybuty `width=`/`height=` przepuszczał taki piksel, a drugi
        detektor szukał wyłącznie wartości zerowych — jedyny zasób śledzący
        w wiadomości wpadał w lukę między nimi i raport orzekał, że go nie ma.
        """
        if self.kind != "img":
            return False
        tiny = {"1", "0", "1px", "0px"}
        if self.width is not None and {self.width, self.height} <= tiny:
            return True
        normalized = re.sub(r"\s+", "", (_attr(self.attrs, "style") or "").lower())
        return bool(
            re.search(r"(?<![-a-z])width:[01]px", normalized)
            and re.search(r"(?<![-a-z])height:[01]px", normalized)
        )


@dataclass(frozen=True, slots=True)
class HiddenElement:
    """Element z deklaracjami CSS wpływającymi na widoczność — i jego tekst.

    Zwracamy same zadeklarowane reguły. `color:#ffffff` to fakt; „biały na białym”
    to już domysł o tle, którego wiadomość może w ogóle nie deklarować — dlatego
    `background` niesie tło zadeklarowane na tym samym elemencie, a `kind`
    oddziela reguły działające niezależnie od tła od tych, które od niego zależą.
    """

    tag: str
    rules: tuple[str, ...]
    text: str
    style: str
    kind: str = "ukrywające"
    background: str | None = None


@dataclass(frozen=True, slots=True)
class StylesheetRule:
    """Reguła ukrywająca z bloku `<style>` wraz z warunkiem, pod którym działa.

    `condition` niesie regułę warunkową (`@media`, `@supports`), w której reguła
    jest zagnieżdżona. Pominięcie tego pola zamieniało standardowy blok
    responsywny — `@media (max-width:714px){.hiddentds{display:none}}` — w dowód
    bezwarunkowego ukrywania treści, którego plik nie zawiera.
    """

    selector: str
    declarations: str
    usage: int
    condition: str | None = None

    @property
    def unconditional(self) -> bool:
        """Czy reguła działa bez względu na kontekst renderowania.

        >>> StylesheetRule(".a", "display:none", 1).unconditional
        True
        >>> StylesheetRule(".a", "display:none", 1, "@media print").unconditional
        False
        """
        return self.condition is None


@dataclass(frozen=True, slots=True)
class HtmlComment:
    """Komentarz HTML z klasyfikacją opartą na jego treści i otoczeniu.

    Zliczanie wszystkich `<!-- -->` jako „komentarzy wewnątrz wyrazów” opisywało
    warunkowe komentarze Outlooka i znaczniki szablonu Mailchimpa jako technikę
    omijania filtrów — w 6 raportach.
    """

    text: str
    kind: str
    splits_word: bool


@dataclass(frozen=True, slots=True)
class Token:
    """Ciąg zakodowany znaleziony w URL-u, nagłówku albo ścieżce — z pochodzeniem.

    `decoded_text` jest ustawione tylko wtedy, gdy dekodowanie dało tekst; dla
    danych binarnych zostaje `None`, a fakt zapisujemy jako liczbę bajtów i skrót.
    Odróżnienie „token nie istnieje” od „token istnieje, ale jest nieczytelny”
    jest istotne — pierwsze zaprzecza dowodowi, drugie go opisuje.
    """

    source: str
    raw: str
    encoding: str
    decoded_text: str | None
    byte_length: int
    #: SHA-256 **zdekodowanych bajtów**. Wcześniej liczony z surowego ciągu ASCII
    #: i renderowany w kolumnie „po zdekodowaniu” — skrót opisywał co innego,
    #: niż deklarowała etykieta.
    sha256_prefix: str
    #: Opis struktury tokenu (np. „UUID wersja 4, wariant RFC 4122”). Osobne pole,
    #: bo wcześniej taki opis trafiał do `decoded_text`, czyli do pola z DANYMI:
    #: raport drukował go w `repr()` jako rzekomą zawartość tokenu, a skaner
    #: powtórzeń przeszukiwał go jak treść wiadomości i zgłaszał słowo „znacznik”
    #: jako identyfikator powtarzający się w pliku.
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Artifact:
    """Metadane zapisanego pliku wyjściowego: nazwa, SHA-256, opis."""

    name: str
    sha256: str
    description: str


@dataclass(frozen=True, slots=True)
class Alignment:
    """Zgodność domen wymagana przez DMARC (RFC 7489 §3.1) — policzona, nie zgadnięta.

    >>> a = Alignment.compute("przyklad.pl", "bounce.dostawca.pl", ("przyklad.pl",))
    >>> a.spf_aligned, a.dkim_aligned
    (False, True)
    >>> a.dkim_aligned_domains
    ('przyklad.pl',)
    >>> b = Alignment.compute("mail.przyklad.pl", "przyklad.pl", ())
    >>> b.spf_aligned
    True
    >>> b.spf_alignment_mode
    'relaxed'
    >>> Alignment.compute(None, None, ()).spf_aligned is None
    True
    """

    from_domain: str | None
    mailfrom_domain: str | None
    dkim_domains: tuple[str, ...]
    spf_aligned: bool | None
    spf_alignment_mode: str | None
    dkim_aligned: bool | None
    dkim_aligned_domains: tuple[str, ...]

    #: Sufiksy dwuczłonowe spotykane w polskiej i brytyjskiej korespondencji.
    #: Bez nich `sv318.home.net.pl` dawało domenę organizacyjną `net.pl`,
    #: przez co dwa hosty tego samego operatora nie były rozpoznane jako para.
    MULTI_LABEL_SUFFIXES = frozenset(
        {
            "com.pl",
            "net.pl",
            "org.pl",
            "edu.pl",
            "gov.pl",
            "info.pl",
            "biz.pl",
            "waw.pl",
            "krakow.pl",
            "wroc.pl",
            "co.uk",
            "org.uk",
            "gov.uk",
            "ac.uk",
            "com.au",
            "co.jp",
            "com.br",
            "co.nz",
            "com.tr",
            "com.cn",
        }
    )

    @classmethod
    def _organizational(cls, domain: str) -> str:
        """Przybliżenie domeny organizacyjnej — z listą sufiksów dwuczłonowych.

        >>> Alignment._organizational("sv318.home.net.pl")
        'home.net.pl'
        >>> Alignment._organizational("mail.przyklad.pl")
        'przyklad.pl'
        >>> Alignment._organizational("przyklad.pl")
        'przyklad.pl'
        >>> Alignment._organizational("pl")
        'pl'
        """
        parts = domain.lower().rstrip(".").split(".")
        if len(parts) >= 3 and ".".join(parts[-2:]) in cls.MULTI_LABEL_SUFFIXES:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()

    @classmethod
    def compute(
        cls,
        from_domain: str | None,
        mailfrom_domain: str | None,
        dkim_domains: tuple[str, ...],
    ) -> "Alignment":
        spf_aligned = spf_mode = None
        if from_domain and mailfrom_domain:
            if from_domain.lower() == mailfrom_domain.lower():
                spf_aligned, spf_mode = True, "strict"
            elif cls._organizational(from_domain) == cls._organizational(
                mailfrom_domain
            ):
                spf_aligned, spf_mode = True, "relaxed"
            else:
                spf_aligned, spf_mode = False, None

        dkim_aligned = None
        aligned_domains: tuple[str, ...] = ()
        if from_domain and dkim_domains:
            org = cls._organizational(from_domain)
            aligned_domains = tuple(
                d for d in dkim_domains if cls._organizational(d) == org
            )
            dkim_aligned = bool(aligned_domains)

        return cls(
            from_domain=from_domain,
            mailfrom_domain=mailfrom_domain,
            dkim_domains=dkim_domains,
            spf_aligned=spf_aligned,
            spf_alignment_mode=spf_mode,
            dkim_aligned=dkim_aligned,
            dkim_aligned_domains=aligned_domains,
        )


@dataclass(frozen=True, slots=True)
class DomainRef:
    """Wystąpienie domeny (lub hosta) z etykietą roli, w której się pojawiła."""

    domain: str
    role: str


@dataclass(slots=True)
class Facts:
    """Komplet faktów wyekstrahowanych z jednej wiadomości — wejście dla raportu."""

    raw_headers: str = ""
    headers_normalized: str = ""
    header_names: tuple[str, ...] = ()
    addresses: dict[str, list[Address]] = field(default_factory=dict)
    hops: list[ReceivedHop] = field(default_factory=list)
    net_addresses: list[NetAddress] = field(default_factory=list)
    auth_headers: list[AuthHeader] = field(default_factory=list)
    dkim: list[DkimSignature] = field(default_factory=list)
    arc_seals: list[ArcSet] = field(default_factory=list)
    spam_headers: list[tuple[str, str]] = field(default_factory=list)
    mime_tree: list[MimePart] = field(default_factory=list)
    attachments: list[MimePart] = field(default_factory=list)
    html_body: str | None = None
    text_body: str | None = None
    resources: list[HtmlResource] = field(default_factory=list)
    hidden: list[HiddenElement] = field(default_factory=list)
    comments: list[HtmlComment] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)
    timestamps: list[tuple[str, datetime.datetime]] = field(default_factory=list)
    domains: list[DomainRef] = field(default_factory=list)
    alignment: Alignment | None = None


# ──────────────────────────── wczytanie i nagłówki ────────────────────────────


def load_message(path: str | Path) -> email.message.Message:
    """Wczytuje i parsuje plik .eml jako email.Message."""
    with open(path, "rb") as f:
        raw = f.read()
    return email.message_from_bytes(raw, policy=email.policy.default)


def load_raw_bytes(path: str | Path) -> bytes:
    """Wczytuje plik .eml jako surowe bajty, bez żadnego parsowania."""
    with open(path, "rb") as f:
        return f.read()


def raw_header_block(raw: bytes) -> str:
    r"""Surowy blok nagłówków — bajty do pierwszej pustej linii, bez normalizacji.

    `"\n".join(f"{k}: {v}" for k, v in msg.items())` daje nagłówki **po** rozwinięciu
    zwinięć, dekodowaniu RFC 2047 i naprawie wadliwej składni. Taki plik nie jest
    kopią dowodu — hash potwierdza integralność rekonstrukcji, nie oryginału.
    Ta funkcja zwraca to, co w pliku faktycznie stoi.

    >>> raw_header_block(b"From: a@b.pl\r\nSubject: =?UTF-8?Q?Zapytanie?=\r\n\r\ntresc")
    'From: a@b.pl\r\nSubject: =?UTF-8?Q?Zapytanie?='
    >>> raw_header_block(b"Subject: dlugi\r\n kontynuacja\r\n\r\nbody")
    'Subject: dlugi\r\n kontynuacja'
    >>> raw_header_block(b"From: a@b.pl\n\nbody")
    'From: a@b.pl'
    >>> raw_header_block(b"bez pustej linii")
    'bez pustej linii'
    """
    for sep in (b"\r\n\r\n", b"\n\n"):
        head, found, _ = raw.partition(sep)
        if found:
            return head.decode("utf-8", "replace")
    return raw.decode("utf-8", "replace")


def line_endings(raw: bytes) -> str:
    """Rodzaj zakończeń linii w pliku źródłowym.

    Spójne CRLF w całym pliku to ślad, że wiadomość nie przeszła przez narzędzie
    normalizujące — fakt tani do zebrania i istotny dla wartości dowodowej kopii.

    >>> line_endings(b"a\\r\\nb\\r\\nc")
    'CRLF w całym pliku (2)'
    >>> line_endings(b"a\\nb\\nc")
    'LF w całym pliku (2)'
    >>> line_endings(b"a\\r\\nb\\nc")
    'mieszane: CRLF 1, samotny LF 1'
    >>> line_endings(b"bez zakonczen")
    'brak zakończeń linii'
    """
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and not lf:
        return f"CRLF w całym pliku ({crlf})"
    if lf and not crlf:
        return f"LF w całym pliku ({lf})"
    if crlf and lf:
        return f"mieszane: CRLF {crlf}, samotny LF {lf}"
    return "brak zakończeń linii"


def raw_header_value(raw_headers: str, name: str) -> str | None:
    """Dosłowna wartość nagłówka z surowego bloku, bez normalizacji przez parser.

    `msg.get("Date")` zwraca wartość po sparsowaniu i ponownym sformatowaniu —
    `Mon, 1 Jun 2026` staje się `Mon, 01 Jun 2026`. Raport podawał tę wartość
    z etykietą „dosłownie z nagłówka”, choć dosłowna nie była.

    >>> blok = "Date: Mon, 1 Jun 2026 10:34:21 +0000\\nSubject: =?utf-8?b?T2Rk?="
    >>> raw_header_value(blok, "Date")
    'Mon, 1 Jun 2026 10:34:21 +0000'
    >>> raw_header_value(blok, "subject")
    '=?utf-8?b?T2Rk?='
    >>> raw_header_value(blok, "From") is None
    True

    Zwinięcia są rozwijane, ale bez zmiany treści — spacja kontynuacji zostaje:

    >>> raw_header_value("Subject: dlugi\\n kawalek", "Subject")
    'dlugi kawalek'
    """
    lines = raw_headers.replace("\r\n", "\n").split("\n")
    collected: list[str] = []
    for index, line in enumerate(lines):
        if not line.lower().startswith(name.lower() + ":"):
            continue
        collected.append(line.split(":", 1)[1].strip())
        for continuation in lines[index + 1 :]:
            if continuation[:1] in (" ", "\t"):
                collected.append(continuation.strip())
            else:
                break
        return " ".join(collected)
    return None


def extract_headers_text(msg: email.message.Message) -> str:
    """Nagłówki po parsowaniu — znormalizowane, do czytania, nie do cytowania.

    >>> from email import message_from_string, policy
    >>> msg = message_from_string("From: a@b\\nTo: c@d\\n\\ntest", policy=policy.default)
    >>> extract_headers_text(msg)
    'From: a@b\\nTo: c@d'
    >>> extract_headers_text(message_from_string("\\n\\ntest", policy=policy.default))
    ''
    """
    return "\n".join(f"{k}: {v}" for k, v in msg.items())


def header_names(msg: email.message.Message) -> tuple[str, ...]:
    """Nazwy wszystkich nagłówków w kolejności z pliku, z powtórzeniami.

    >>> from email import message_from_string, policy
    >>> msg = message_from_string("Received: a\\nReceived: b\\nFrom: c@d\\n\\nx", policy=policy.default)
    >>> header_names(msg)
    ('Received', 'Received', 'From')
    """
    return tuple(k for k, _ in msg.items())


def parse_date_header(value: str) -> datetime.datetime | None:
    """Parsuje datę z nagłówka; przyjmuje też warianty niestandardowe.

    SendGrid stempluje `Sat, 29 Aug 2026 06:40:50.368 +0000 (UTC)` — z ułamkiem
    sekundy, którego `parsedate_to_datetime` nie przyjmuje. Milczące pominięcie
    takiego skoku wycina połowę osi czasu z raportu.

    >>> parse_date_header("Wed, 12 Aug 2026 02:38:44 +0200").isoformat()
    '2026-08-12T02:38:44+02:00'
    >>> parse_date_header("Sat, 29 Aug 2026 06:40:50.368 +0000 (UTC)").isoformat()
    '2026-08-29T06:40:50.368000+00:00'
    >>> parse_date_header("Tue, 23 Jun 2026 09:00:02 GMT").isoformat()
    '2026-06-23T09:00:02+00:00'
    >>> parse_date_header("2026-08-29 06:40:50.390557031 +0000 UTC").isoformat()
    '2026-08-29T06:40:50.390557+00:00'
    >>> parse_date_header("nie data") is None
    True
    """
    text = str(value or "").strip()
    if not text:
        return None

    try:
        parsed = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None:
        return parsed

    frac = re.match(r"(.*?\d{2}:\d{2}:\d{2})\.(\d+)(\s*[+-]\d{4}.*)", text)
    if frac:
        try:
            base = email.utils.parsedate_to_datetime(frac.group(1) + frac.group(3))
        except (TypeError, ValueError):
            base = None
        if base is not None:
            micro = int(frac.group(2)[:6].ljust(6, "0"))
            return base.replace(microsecond=micro)

    go_style = re.match(
        r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?\s*([+-]\d{4})", text
    )
    if go_style:
        micro = int((go_style.group(3) or "0")[:6].ljust(6, "0"))
        aware = datetime.datetime.strptime(
            f"{go_style.group(1)} {go_style.group(2)}{go_style.group(4)}",
            "%Y-%m-%d %H:%M:%S%z",
        )
        return aware.replace(microsecond=micro)
    return None


def extract_addresses(msg: email.message.Message) -> dict[str, list[Address]]:
    """Adresy ze wszystkich nagłówków adresowych, z nazwami wyświetlanymi.

    Nazwa wyświetlana jest osobną daną: `From: Google <nadawca@inna-domena.pl>`
    to rozbieżność, której porównanie samych domen nie pokaże.

    >>> from email import message_from_string, policy
    >>> src = "From: Marka <nadawca@wysylka.pl>\\nTo: klient+tag@odbiorca.pl\\n\\nx"
    >>> msg = message_from_string(src, policy=policy.default)
    >>> addrs = extract_addresses(msg)
    >>> addrs["From"][0].display_name
    'Marka'
    >>> addrs["To"][0].addr_spec
    'klient+tag@odbiorca.pl'
    >>> addrs["To"][0].tag
    'tag'
    >>> "Cc" in extract_addresses(msg)
    False
    """
    out: dict[str, list[Address]] = {}
    fields = (
        "From",
        "To",
        "Cc",
        "Bcc",
        "Reply-To",
        "Return-Path",
        "Sender",
        "Delivered-To",
        "X-Original-To",
        "Envelope-To",
    )
    for name in fields:
        values = msg.get_all(name) or []
        parsed = [
            Address(display_name=n.strip(), addr_spec=a.strip())
            for n, a in email.utils.getaddresses([str(v) for v in values])
            if a.strip() or n.strip()
        ]
        if parsed:
            out[name] = parsed
    return out


def extract_domain(value: str | None) -> str | None:
    """Domena z pojedynczego adresu email (bez gubienia tagu w części lokalnej).

    >>> extract_domain("uzytkownik@przyklad.pl")
    'przyklad.pl'
    >>> extract_domain("Nazwa <uzytkownik+tag@przyklad.pl>")
    'przyklad.pl'
    >>> extract_domain("bounce+abc=klient.pl@dostawca.pl")
    'dostawca.pl'
    >>> extract_domain(None) is None
    True
    >>> extract_domain("") is None
    True
    """
    addr = Address.parse(str(value or ""))
    if addr.domain:
        return addr.domain
    m = re.search(r"@([A-Za-z0-9.-]+)", str(value or ""))
    return m.group(1).lower().rstrip(".>") if m else None


# ──────────────────────────── trasa i czas ────────────────────────────


def extract_hops(msg: email.message.Message) -> list[ReceivedHop]:
    """Nagłówki Received rozłożone na pola, w kolejności od najstarszego.

    >>> from email import message_from_string, policy
    >>> src = ("Received: from b.pl by mx.pl with ESMTP; Tue, 11 Aug 2026 10:00:01 +0000\\n"
    ...        "Received: from a.pl by b.pl with ESMTPA; Tue, 11 Aug 2026 10:00:00 +0000\\n\\nx")
    >>> hops = extract_hops(message_from_string(src, policy=policy.default))
    >>> [h.helo for h in hops]
    ['a.pl', 'b.pl']
    >>> hops[0].protocol
    'ESMTPA'
    >>> extract_hops(message_from_string("\\n\\nx", policy=policy.default))
    []
    """
    received = msg.get_all("Received") or []
    return [ReceivedHop.parse(str(r), i) for i, r in enumerate(reversed(received), 1)]


def received_chain_continuity(
    hops: list[ReceivedHop],
) -> list[tuple[int, str, str, bool]]:
    """Czy `by` skoku N zgadza się z nazwą, od której zaczyna się skok N+1.

    Test ciągłości łańcucha: host, który przyjął wiadomość, powinien być tym
    samym, który ją dalej nadaje. Raport liczył skoki i orzekał, że nazwy są
    składniowo poprawne, ale tego zestawienia nie robił — a w jednym z plików
    między `by` a następnym `from` stoi host niewystępujący nigdzie indziej,
    czyli odcinek drogi bez żadnego nagłówka.

    Zwraca krotki `(numer skoku, by, from następnego, czy zgodne)`.

    >>> h1 = ReceivedHop(1, "", helo=None, rdns=None, ip=None, by="mx1.przyklad.pl",
    ...                  by_ip=None, protocol=None, tls=None, queue_id=None,
    ...                  for_address=None, timestamp=None)
    >>> h2 = ReceivedHop(2, "", helo="mx1.przyklad.pl", rdns=None, ip=None,
    ...                  by="mx2.przyklad.pl", by_ip=None, protocol=None, tls=None,
    ...                  queue_id=None, for_address=None, timestamp=None)
    >>> received_chain_continuity([h1, h2])
    [(1, 'mx1.przyklad.pl', 'mx1.przyklad.pl', True)]

    Przerwa jest zwracana jako `False` — to ustalenie, nie brak danych:

    >>> h2b = ReceivedHop(2, "", helo="obcy.przyklad.pl", rdns=None, ip=None,
    ...                   by="mx2.przyklad.pl", by_ip=None, protocol=None, tls=None,
    ...                   queue_id=None, for_address=None, timestamp=None)
    >>> received_chain_continuity([h1, h2b])
    [(1, 'mx1.przyklad.pl', 'obcy.przyklad.pl', False)]
    >>> received_chain_continuity([h1])
    []
    """
    out: list[tuple[int, str, str, bool]] = []
    for earlier, later in itertools.pairwise(hops):
        receiver = (earlier.by or "").rstrip(".").lower()
        sender = (later.helo or later.rdns or "").rstrip(".").lower()
        if not receiver or not sender:
            continue
        out.append(
            (
                earlier.index,
                earlier.by or "",
                later.helo or later.rdns or "",
                receiver == sender,
            )
        )
    return out


def collect_net_addresses(
    msg: email.message.Message, hops: list[ReceivedHop]
) -> list[NetAddress]:
    """Adresy sieciowe z całej wiadomości, z rolą i kategorią — bez spłaszczania.

    >>> from email import message_from_string, policy
    >>> src = ("Received: by 2002:a05:7109:c30a:b0:579:5199:ff53 with SMTP id x\\n"
    ...        "Received: from a.pl (a.pl. [203.0.113.9]) by mx.pl with ESMTPS\\n"
    ...        "X-CLIENT-IP: 198.51.100.7\\n\\nbody")
    >>> msg = message_from_string(src, policy=policy.default)
    >>> addrs = collect_net_addresses(msg, extract_hops(msg))
    >>> [(a.value, a.role) for a in addrs if a.category == 'dokumentacyjny (RFC 5737)']
    [('203.0.113.9', 'Received skok 1 (from)'), ('198.51.100.7', 'X-CLIENT-IP')]
    >>> [a.category for a in addrs if a.value.startswith('2002:')]
    ['prefiks 2002::/16 z osadzonym 10.5.113.9 (adres prywatny — nie spełnia RFC 3056 dla 6to4)']
    """
    out: list[NetAddress] = []
    seen: set[tuple[str, str]] = set()

    def add(value: str, role: str) -> None:
        value = value.strip().strip("[]").rstrip(".")
        category = NetAddress.classify(value)
        if category == "nie jest adresem IP":
            return
        key = (value, role)
        if key in seen:
            return
        seen.add(key)
        out.append(NetAddress(value=value, role=role, category=category))

    for hop in hops:
        if hop.ip:
            add(hop.ip, f"Received skok {hop.index} (from)")
        if hop.by_ip:
            add(hop.by_ip, f"Received skok {hop.index} (by)")
        if hop.is_internal and re.fullmatch(r"[0-9a-fA-F:.]+", hop.by or ""):
            add(hop.by or "", f"Received skok {hop.index} (by, wewnętrzny)")
        elif hop.by and re.fullmatch(r"\[?[0-9a-fA-F:.]+\]?", hop.by):
            add(hop.by, f"Received skok {hop.index} (by)")
        if hop.helo and hop.helo.strip("[]") != (hop.ip or ""):
            helo_value = hop.helo.strip("[]")
            if NetAddress.classify(helo_value) != "nie jest adresem IP":
                add(
                    helo_value, f"Received skok {hop.index} (HELO — deklaracja klienta)"
                )

    for value in msg.get_all("X-SES-Outgoing") or []:
        for found in re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})", str(value)):
            add(found, "X-SES-Outgoing")

    for name in ("X-CLIENT-IP", "X-Originating-IP", "X-Sender-IP", "X-Real-IP"):
        for value in msg.get_all(name) or []:
            for found in re.findall(r"[0-9a-fA-F:.]{3,}", str(value)):
                add(found, name)

    for value in msg.get_all("X-Received") or []:
        for found in re.findall(r"\bby\s+([0-9a-fA-F:]{6,})", str(value)):
            add(found, "X-Received (wewnętrzny)")

    for header in msg.get_all("Received-SPF") or []:
        for found in re.findall(r"client-ip=([0-9a-fA-F:.]+)", str(header)):
            add(found, "Received-SPF client-ip")
    for name in ("Authentication-Results", "ARC-Authentication-Results"):
        for header in msg.get_all(name) or []:
            for found in re.findall(r"client-ip=([0-9a-fA-F:.]+)", str(header)):
                add(found, f"{name} client-ip")
            # `designates 45.92.16.114 as permitted sender` — ten sam adres w innej
            # roli; bez tego tabela „adresy występujące w wiadomości” pokazywała
            # 2 z 4 realnych wystąpień.
            for found in re.findall(r"designates\s+([0-9a-fA-F:.]+)", str(header)):
                add(found, f"{name} (designates)")

    return out


def extract_timestamps(
    msg: email.message.Message,
) -> list[tuple[str, datetime.datetime]]:
    """Wszystkie znaczniki czasu z nagłówków — Date, Received, DKIM t=, ARC t=, epoki.

    Zebranie ich razem pokazuje, czy `Date` zgadza się z momentem podpisania. To
    ustalenie da się zrobić wyłącznie z jednego pliku — i w żadnym z badanych
    raportów nie zostało zrobione.

    >>> from email import message_from_string, policy
    >>> src = ("Date: Fri, 07 Aug 2026 15:06:02 +0200\\n"
    ...        "DKIM-Signature: d=a.pl; h=From; t=1786107962;\\n\\nx")
    >>> ts = extract_timestamps(message_from_string(src, policy=policy.default))
    >>> [label for label, _ in ts]
    ['Date', 'DKIM-Signature t=']
    >>> ts[0][1] == ts[1][1]
    True
    >>> extract_timestamps(message_from_string("\\n\\nx", policy=policy.default))
    []
    """
    result: list[tuple[str, datetime.datetime]] = []

    date_value = msg.get("Date")
    if date_value:
        parsed = parse_date_header(str(date_value))
        if parsed:
            result.append(("Date", parsed))

    for hop in extract_hops(msg):
        if hop.timestamp:
            result.append((f"Received skok {hop.index}", hop.timestamp))

    def from_epoch(seconds: int) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)

    for header, label in (
        ("DKIM-Signature", "DKIM-Signature t="),
        ("ARC-Seal", "ARC-Seal t="),
        ("ARC-Message-Signature", "ARC-Message-Signature t="),
    ):
        for value in msg.get_all(header) or []:
            match = re.search(r"(?:^|;)\s*t=(\d{9,11})", re.sub(r"\s+", "", str(value)))
            if match:
                result.append((label, from_epoch(int(match.group(1)))))
        for value in msg.get_all(header) or []:
            match = re.search(r"(?:^|;)\s*x=(\d{9,11})", re.sub(r"\s+", "", str(value)))
            if match:
                result.append(
                    (f"{label[:-3]} x= (wygaśnięcie)", from_epoch(int(match.group(1))))
                )

    for value in msg.get_all("X-Received") or []:
        match = re.search(r"\b(\d{13})\b", str(value))
        if match:
            result.append(
                ("X-Received (epoka ms)", from_epoch(int(match.group(1)) // 1000))
            )

    # Znacznik czasu z Message-ID wiadomości, na którą to jest odpowiedź.
    # `message_id_parts` istniało, ale było wołane wyłącznie na własnym
    # `Message-ID` — przez co oś czasu miała jeden wiersz zamiast dwóch i nie
    # pokazywała odstępu między pismem a odpowiedzią.
    for name in ("In-Reply-To", "References"):
        for value in msg.get_all(name) or []:
            for identifier in re.findall(r"<[^>]+>", str(value)) or [str(value)]:
                for label, decoded in message_id_parts(identifier):
                    moment = re.search(r"→ (.+?)(?: UTC)?$", decoded)
                    if not moment:
                        continue
                    # Część lokalna Message-ID niesie same cyfry daty, BEZ strefy.
                    # Dopisywanie `+0000` bez śladu w etykiecie sprawiało, że
                    # kolumna „Strefa z nagłówka” pokazywała wartość pochodzącą
                    # z kodu, a cały policzony odstęp stał na niezasygnalizowanym
                    # założeniu. Założenie zostaje, ale jest widoczne.
                    parsed = parse_date_header(moment.group(1) + " +0000")
                    if parsed is None:
                        try:
                            parsed = datetime.datetime.strptime(
                                moment.group(1), "%Y-%m-%d %H:%M:%S"
                            ).replace(tzinfo=datetime.timezone.utc)
                        except ValueError:
                            continue
                    result.append(
                        (
                            f"{name} ({label}) [strefa nieustalona — przyjęto UTC]",
                            parsed,
                        )
                    )
                break

    # `X-SES-Outgoing: 2026.03.17-23.249.218.110` niesie **samą datę**, bez godziny.
    # Dopisanie jej północy i policzenie odstępu do `Date` dawało w raportach
    # „rozpiętość osi 15 h 7 min” tam, gdzie wszystkie realne znaczniki mieszczą
    # się w jednej sekundzie — czyli błąd rzędu 50 000×. Data bez godziny nie jest
    # punktem na osi czasu; trafia do faktów jako data, nie jako znacznik.

    for value in msg.get_all("X-MS-Exchange-CrossTenant-originalarrivaltime") or []:
        parsed = parse_date_header(re.sub(r"\.\d+\s*\(UTC\)", " +0000", str(value)))
        if parsed:
            result.append(("X-MS-Exchange-CrossTenant-OriginalArrivalTime", parsed))

    # `msg.get_all` jest niewrażliwe na wielkość liter, więc odpytanie o dwie
    # pisownie tego samego nagłówka zwracało tę samą wartość dwa razy — a raport
    # liczył z tego nieistniejący odstęp „0 s” między nagłówkiem a nim samym.
    # Ta sama zasada dotyczy `In-Reply-To` i `References` niosących ten sam
    # identyfikator: to jedno źródło, nie dwa niezależne potwierdzenia.
    unikalne: list[tuple[str, datetime.datetime]] = []
    seen: set[tuple[str, float]] = set()
    for label, moment in result:
        # Adnotację w nawiasach kwadratowych (np. o nieustalonej strefie) zdejmujemy
        # przed wyliczeniem rodziny — inaczej `In-Reply-To` i `References` niosące
        # ten sam identyfikator znów byłyby dwoma punktami osi zamiast jednym.
        rodzina = re.sub(r"\s*\[[^\]]*\]\s*$", "", label)
        rodzina = re.sub(r"\s*\(.*\)$", "", rodzina).lower()
        rodzina = (
            "in-reply-to/references"
            if rodzina in {"in-reply-to", "references"}
            else rodzina
        )
        klucz = (rodzina, moment.timestamp())
        if klucz in seen:
            continue
        seen.add(klucz)
        unikalne.append((label, moment))
    return unikalne


# ──────────────────────────── uwierzytelnienie ────────────────────────────


def extract_auth_headers(msg: email.message.Message) -> list[AuthHeader]:
    """Każdy nagłówek uwierzytelnienia osobno, z nazwą i numerem wystąpienia.

    >>> from email import message_from_string, policy
    >>> src = ("Authentication-Results: mx.a.pl; dkim=pass; spf=pass\\n"
    ...        "Received-SPF: pass (a.pl: autoryzacja) client-ip=203.0.113.9\\n\\nx")
    >>> headers = extract_auth_headers(message_from_string(src, policy=policy.default))
    >>> [(h.name, h.index) for h in headers]
    [('Authentication-Results', 1), ('Received-SPF', 1)]
    >>> headers[0].authserv_id
    'mx.a.pl'

    Podciąg `arc` w `dmarc` nie tworzy metody `arc` (błąd w 10 z 13 raportów):

    >>> src = "Authentication-Results: mx.a.pl; dmarc=pass (p=NONE) header.from=a.pl\\n\\nx"
    >>> headers = extract_auth_headers(message_from_string(src, policy=policy.default))
    >>> [m.method for m in headers[0].methods]
    ['dmarc']
    """
    out: list[AuthHeader] = []
    for name in (
        "Authentication-Results",
        "ARC-Authentication-Results",
        "Received-SPF",
        "X-Authentication-Results",
    ):
        for i, value in enumerate(msg.get_all(name) or [], 1):
            out.append(
                AuthHeader(
                    name=name, index=i, raw=re.sub(r"\s+", " ", str(value)).strip()
                )
            )
    return out


def auth_methods_by_name(
    headers: list[AuthHeader],
) -> dict[str, list[tuple[str, AuthMethod]]]:
    """Mapa metoda → [(nagłówek, wynik)] — z atrybucją do nagłówka, który ją podał.

    `dkim=none` z wewnętrznego Exchange'a i `dkim=pass` od bramy odbiorcy to dwa
    różne ustalenia z różnych etapów trasy. Bez atrybucji wyglądają jak sprzeczność.

    >>> h1 = AuthHeader(name="Authentication-Results", index=1, raw="mx.a.pl; dkim=pass")
    >>> h2 = AuthHeader(name="ARC-Authentication-Results", index=1, raw="i=1; mx.b.pl; dkim=none")
    >>> {k: [(n, m.result) for n, m in v] for k, v in auth_methods_by_name([h1, h2]).items()}
    {'dkim': [('Authentication-Results #1', 'pass'), ('ARC-Authentication-Results #1', 'none')]}
    >>> auth_methods_by_name([])
    {}
    """
    out: dict[str, list[tuple[str, AuthMethod]]] = {}
    for header in headers:
        for method in header.methods:
            out.setdefault(method.method, []).append(
                (f"{header.name} #{header.index}", method)
            )
    return out


def extract_dkim_signatures(msg: email.message.Message) -> list[DkimSignature]:
    """Wszystkie nagłówki DKIM-Signature — każdy sparsowany z własnych tagów.

    `msg.get("DKIM-Signature")` zwraca tylko pierwszy; iterowanie po liście przy
    czytaniu `d=`/`s=` z `get()` przypisywało drugiemu podpisowi domenę pierwszego
    (dwa raporty twierdziły, że nadawca podpisał wiadomość dwa razy — drugi podpis
    należał do infrastruktury dostawcy).

    >>> from email import message_from_string, policy
    >>> src = ("DKIM-Signature: d=nadawca.pl; s=sel1; h=From:Subject;\\n"
    ...        "DKIM-Signature: d=dostawca-ses.example; s=sel2; h=From:Feedback-ID;\\n\\nx")
    >>> sigs = extract_dkim_signatures(message_from_string(src, policy=policy.default))
    >>> [(s.domain, s.selector) for s in sigs]
    [('nadawca.pl', 'sel1'), ('dostawca-ses.example', 'sel2')]
    >>> sigs[1].signed_headers
    ('From', 'Feedback-ID')
    >>> extract_dkim_signatures(message_from_string("\\n\\nx", policy=policy.default))
    []
    """
    parsed = (
        DkimSignature.parse(str(raw)) for raw in (msg.get_all("DKIM-Signature") or [])
    )
    return [sig for sig in parsed if sig is not None]


#: Nagłówki dopisywane na trasie **po** podpisaniu wiadomości. Nie mogą być objęte
#: `h=`, więc wymienianie ich jako „niepodpisane” niczego nie ustala. Wykluczamy je,
#: ale raport podaje ich listę wprost — poprzedni opis mówił „różnica zbiorów, nie
#: lista szablonowa”, choć lista szablonowa istniała, tylko schowana w kodzie.
TRANSIT_HEADERS = frozenset(
    {
        "received",
        "x-received",
        "received-spf",
        "return-path",
        "delivered-to",
        "authentication-results",
        "x-google-smtp-source",
        "x-originating-ip",
    }
)

#: Nagłówki, których nie może objąć `h=`, bo powstają **razem z podpisem** albo
#: **są** podpisem. Wcześniej trafiały do worka „dopisane na trasie po podpisaniu”
#: — uzasadnienie nieprawdziwe: `DKIM-Signature` tworzy nadawca, nie pośrednik.
SIGNATURE_HEADERS = frozenset({"dkim-signature"})

#: Nagłówki dopisywane przez relay i filtry **po stronie nadawcy**, zanim
#: wiadomość opuści jego infrastrukturę. Nie są ani nagłówkami nadawcy,
#: ani dopisanymi przez odbiorcę — raport mylił je z pierwszą kategorią.
SENDER_RELAY_PREFIXES = (
    "x-client-",
    "x-vade-",
    "x-dcc",
    "x-sare",
    "x-ses-",
    "x-sg-",
    "x-alidm",
    "x-mail-from",
    "x-emailguid",
    "x-sid",
    "x-return-path",
)


def oversigned_headers(
    msg: email.message.Message, signed: tuple[str, ...]
) -> list[str]:
    """Nagłówki wymienione w `h=`, których w wiadomości nie ma.

    To celowa technika blokująca dopisanie nagłówka w tranzycie: podpis obejmuje
    pustą pozycję, więc dodanie jej unieważnia DKIM. Raport liczył różnicę zbiorów
    wyłącznie w drugą stronę, przez co ta obserwacja nie padała ani razu — a w
    jednym z plików `h=` wymieniało 13 nieistniejących nagłówków.

    >>> from email import message_from_string, policy
    >>> msg = message_from_string("From: a@b.pl\\nSubject: x\\n\\nx", policy=policy.default)
    >>> oversigned_headers(msg, ("From", "Subject", "Sender", "Cc", "List-Id"))
    ['Sender', 'Cc', 'List-Id']
    >>> oversigned_headers(msg, ("From", "Subject"))
    []
    """
    present = {name.lower() for name in header_names(msg)}
    out: list[str] = []
    for name in signed:
        if name.lower() not in present and name not in out:
            out.append(name)
    return out


def unsigned_headers(
    msg: email.message.Message, signed: tuple[str, ...]
) -> tuple[list[str], dict[str, list[str]]]:
    """Nagłówki spoza listy `h=`, rozdzielone na własne nadawcy i dopisane w tranzycie.

    Poprzednia wersja drukowała stałą listę (`To, Reply-To, List-Unsubscribe,
    Cc, Bcc`) niezależnie od zawartości pliku. Naprawa zamieniła ją na różnicę
    zbiorów, ale zostawiła w kodzie ukryty filtr — a raport zapewniał, że filtra
    nie ma. Teraz zwracamy obie listy, przy czym odjęte są rozbite na powody:
    `DKIM-Signature` nie jest „dopisany na trasie po podpisaniu” (tworzy go
    nadawca), a `X-VADE-*` czy `X-CLIENT-*` dokłada relay nadawcy, nie odbiorcy.

    >>> from email import message_from_string, policy
    >>> src = ("From: a@b.pl\\nSubject: x\\nMessage-ID: <1@b.pl>\\nPrecedence: bulk\\n"
    ...        "Received: from x by y\\nAuthentication-Results: mx; spf=pass\\n\\nx")
    >>> wlasne, tranzyt = unsigned_headers(msg := message_from_string(src, policy=policy.default),
    ...                                    ("From", "Subject"))
    >>> wlasne
    ['Message-ID', 'Precedence']
    >>> tranzyt["dopisane na trasie przez serwery pośredniczące"]
    ['Received', 'Authentication-Results']
    >>> unsigned_headers(msg, ("From", "Subject", "Message-ID", "Precedence"))[0]
    []
    """
    signed_lower = {h.lower() for h in signed}
    out: list[str] = []
    excluded: dict[str, list[str]] = {
        "dopisane na trasie przez serwery pośredniczące": [],
        "dopisane przez infrastrukturę po stronie nadawcy": [],
        "będące samym podpisem (nagłówek nie podpisuje sam siebie)": [],
    }
    for name in header_names(msg):
        low = name.lower()
        if low in signed_lower:
            continue
        if low in SIGNATURE_HEADERS or low.startswith("arc-"):
            kategoria = "będące samym podpisem (nagłówek nie podpisuje sam siebie)"
        elif low.startswith(SENDER_RELAY_PREFIXES):
            kategoria = "dopisane przez infrastrukturę po stronie nadawcy"
        elif low in TRANSIT_HEADERS:
            kategoria = "dopisane na trasie przez serwery pośredniczące"
        else:
            if name not in out:
                out.append(name)
            continue
        if name not in excluded[kategoria]:
            excluded[kategoria].append(name)
    return out, {k: v for k, v in excluded.items() if v}


def extract_arc_message_signatures(msg: email.message.Message) -> list[DkimSignature]:
    """Nagłówki ARC-Message-Signature — mają tę samą składnię, co DKIM-Signature.

    Sekcja ARC pokazywała wyłącznie `ARC-Seal`, przez co ginęła lista `h=`
    podpisu ARC — jedyny w pliku zapis tego, które nagłówki istniały w chwili
    odbioru, czyli jedyne narzędzie do wykrycia późniejszej modyfikacji pliku.

    >>> from email import message_from_string, policy
    >>> src = ("ARC-Message-Signature: i=1; a=rsa-sha256; d=posrednik.example; "
    ...        "s=arc-1; h=from:to:subject; bh=YWJj\\n\\nx")
    >>> sigs = extract_arc_message_signatures(message_from_string(src, policy=policy.default))
    >>> sigs[0].domain, sigs[0].signed_headers
    ('posrednik.example', ('from', 'to', 'subject'))
    >>> extract_arc_message_signatures(message_from_string("\\n\\nx", policy=policy.default))
    []
    """
    parsed = (
        DkimSignature.parse(str(raw))
        for raw in (msg.get_all("ARC-Message-Signature") or [])
    )
    return [sig for sig in parsed if sig is not None]


def extract_arc_seals(msg: email.message.Message) -> list[ArcSet]:
    """Wszystkie nagłówki ARC-Seal, posortowane po `i=`.

    >>> from email import message_from_string, policy
    >>> src = "ARC-Seal: i=1; d=przyklad.pl; cv=none; t=1787985652\\n\\nx"
    >>> seals = extract_arc_seals(message_from_string(src, policy=policy.default))
    >>> seals[0].index, seals[0].chain_validation
    (1, 'none')
    >>> extract_arc_seals(message_from_string("\\n\\nx", policy=policy.default))
    []
    """
    seals = [ArcSet.parse_seal(str(raw)) for raw in (msg.get_all("ARC-Seal") or [])]
    present = [s for s in seals if s is not None]
    return sorted(present, key=lambda s: (s.index is None, s.index or 0))


def extract_spam_headers(msg: email.message.Message) -> list[tuple[str, str]]:
    """Nagłówki filtrów antyspamowych — dowolnego producenta, nie tylko VADE/DCC.

    Twierdzenie „brak nagłówków filtrów” było nieprawdziwe dla wiadomości
    z Microsoft 365, bo skrypt szukał wyłącznie dwóch nazw.

    >>> from email import message_from_string, policy
    >>> src = ("x-microsoft-antispam: BCL:0\\nx-forefront-antispam-report: SCL:1;SFV:NSPM\\n"
    ...        "X-VADE-SPAMSTATE: clean\\n\\nx")
    >>> extract_spam_headers(message_from_string(src, policy=policy.default))
    [('x-microsoft-antispam', 'BCL:0'), ('x-forefront-antispam-report', 'SCL:1;SFV:NSPM'), ('X-VADE-SPAMSTATE', 'clean')]
    >>> extract_spam_headers(message_from_string("From: a@b\\n\\nx", policy=policy.default))
    []
    """
    out: list[tuple[str, str]] = []
    for name, value in msg.items():
        if name.lower().startswith(SPAM_HEADER_PREFIXES):
            out.append((name, re.sub(r"\s+", " ", str(value)).strip()))
    return out


def parse_dcc_metrics(value: str) -> list[tuple[str, int]]:
    """Liczniki z nagłówka X-DCC--Metrics — ile razy filtr widział daną sumę kontrolną.

    Raport pisał tylko „DCC to filtr, który analizuje metryki treści” i zostawiał
    liczby nierozłożone, mimo że to jedyny w pliku ślad skali wysyłki.

    >>> parse_dcc_metrics("host.przyklad.pl 1024; Body=1 Fuz1=1 Fuz2=29281")
    [('Body', 1), ('Fuz1', 1), ('Fuz2', 29281)]
    >>> parse_dcc_metrics("bez licznikow")
    []
    """
    return [
        (k, int(v))
        for k, v in re.findall(r"\b(Body|Fuz1|Fuz2|many|rep)=(\d+)\b", str(value))
    ]


# ──────────────────────────── MIME ────────────────────────────


def build_mime_tree(msg: email.message.Message) -> list[MimePart]:
    """Drzewo MIME z zagnieżdżeniem, rozmiarem i SHA-256 każdej części.

    >>> from email import message_from_string, policy
    >>> src = ('Content-Type: multipart/alternative; boundary="b"\\n\\n'
    ...        '--b\\nContent-Type: text/plain\\n\\ntekst\\n'
    ...        '--b\\nContent-Type: text/html\\n\\n<p>html</p>\\n--b--\\n')
    >>> parts = build_mime_tree(message_from_string(src, policy=policy.default))
    >>> [(p.depth, p.content_type) for p in parts]
    [(0, 'multipart/alternative'), (1, 'text/plain'), (1, 'text/html')]
    >>> parts[1].size
    5
    >>> len(parts[1].sha256)
    64
    """
    out: list[MimePart] = []

    def walk(part: email.message.Message, depth: int) -> None:
        payload: bytes | None = None
        if not part.is_multipart():
            try:
                decoded = part.get_payload(decode=True)
            except (AssertionError, TypeError, ValueError):
                decoded = None
            payload = decoded if isinstance(decoded, bytes) else None
        out.append(
            MimePart(
                depth=depth,
                content_type=part.get_content_type(),
                charset=part.get_content_charset(),
                encoding=(part.get("Content-Transfer-Encoding") or None)
                and str(part.get("Content-Transfer-Encoding")).strip(),
                filename=part.get_filename(),
                content_id=(part.get("Content-ID") or None)
                and str(part.get("Content-ID")).strip(),
                disposition=part.get_content_disposition(),
                size=len(payload) if payload is not None else None,
                sha256=hashlib.sha256(payload).hexdigest()
                if payload is not None
                else None,
            )
        )
        if part.is_multipart():
            children = part.get_payload()
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, email.message.Message):
                        walk(child, depth + 1)

    walk(msg, 0)
    return out


def extract_attachments(tree: list[MimePart]) -> list[MimePart]:
    """Części będące załącznikami albo zasobami osadzonymi (cid:).

    Stwierdzenie „brak załączników” jest ustaleniem i musi paść wprost —
    zwłaszcza gdy temat wiadomości brzmi „Faktura”.

    >>> parts = [MimePart(0, "multipart/mixed", None, None, None, None, None, None, None),
    ...          MimePart(1, "text/html", "utf-8", "base64", None, None, None, 10, "ab"),
    ...          MimePart(1, "image/png", None, "base64", "logo.png", "<cid1>", "inline", 99, "cd")]
    >>> [p.filename for p in extract_attachments(parts)]
    ['logo.png']
    >>> extract_attachments(parts[:2])
    []

    `Content-ID` na części `text/html` to ciało wiadomości, nie załącznik:

    >>> body = MimePart(1, "text/html", "utf-8", "base64", None,
    ...                 "<AD821DA8@eurprd04.prod.outlook.com>", None, 10, "ab")
    >>> extract_attachments([body])
    []
    """
    return [
        p
        for p in tree
        if p.disposition == "attachment"
        or p.filename
        or (
            (p.disposition == "inline" or p.content_id)
            # Część tekstowa bez nazwy pliku to ciało wiadomości, nie zasób
            # osadzony — nawet gdy niesie `Content-ID`.
            and p.content_type not in {"text/plain", "text/html"}
        )
    ]


def extract_bodies(msg: email.message.Message) -> tuple[str | None, str | None]:
    """Części text/html i text/plain zdekodowane z transfer-encoding.

    >>> from email import message_from_string, policy
    >>> msg = message_from_string("From: a@b\\n\\nHello", policy=policy.default)
    >>> extract_bodies(msg)
    (None, 'Hello')
    >>> msg = message_from_string("Content-Type: text/html\\n\\n<p>x</p>", policy=policy.default)
    >>> extract_bodies(msg)
    ('<p>x</p>', None)
    """
    html_body: str | None = None
    txt_body: str | None = None
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type not in {"text/html", "text/plain"}:
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        if content_type == "text/html" and html_body is None:
            html_body = text
        elif content_type == "text/plain" and txt_body is None:
            txt_body = text
    return html_body, txt_body


# ──────────────────────────── treść HTML ────────────────────────────


def strip_style_and_script(src: str) -> str:
    """Usuwa zawartość <style>, <script>, <head> i <title> — to nie jest treść.

    Sekcja „treść po usunięciu obfuskacji” liczyła w kilku raportach 700 linii,
    z czego ~500 to arkusz stylów szablonu. Prezentowała szum zamiast dowodu.

    >>> strip_style_and_script('<style>p{margin:0}</style>Tekst')
    'Tekst'
    >>> strip_style_and_script('<script src="/x"></script>Tekst')
    'Tekst'
    >>> strip_style_and_script('<head><title>T</title></head>Tekst')
    'Tekst'
    >>> strip_style_and_script('bez stylow')
    'bez stylow'
    """
    out = re.sub(r"<head\b[^>]*>.*?</head>", "", src, flags=re.DOTALL | re.IGNORECASE)
    out = re.sub(r"<style\b[^>]*>.*?</style>", "", out, flags=re.DOTALL | re.IGNORECASE)
    out = re.sub(
        r"<script\b[^>]*>.*?</script>", "", out, flags=re.DOTALL | re.IGNORECASE
    )
    return re.sub(
        r"<title\b[^>]*>.*?</title>", "", out, flags=re.DOTALL | re.IGNORECASE
    )


def deobfuscate(src: str) -> str:
    """Zwraca tekst widoczny: bez znaczników, stylów, skryptów i znaków zerowej szerokości.

    >>> deobfuscate("")
    ''
    >>> deobfuscate("Hello world")
    'Hello world'
    >>> deobfuscate("He<!--komentarz-->llo")
    'Hello'
    >>> deobfuscate('<span>rozbity</span>')
    'rozbity'
    >>> deobfuscate('<br/>linia1<br/>linia2')
    'linia1\\nlinia2'
    >>> deobfuscate('&amp; &lt;')
    '& <'
    >>> deobfuscate('a\\n\\n\\n\\nb')
    'a\\n\\nb'
    >>> deobfuscate('<style>p{margin:0px}</style>Tresc')
    'Tresc'
    >>> deobfuscate('<script>var a=1</script>Tresc')
    'Tresc'

    Tekst z deklaracjami ukrywającymi zostaje, ale z jawnym znacznikiem —
    usunięcie go skasowałoby dowód, przemilczenie podałoby go jako treść
    widoczną. Marker wymienia **zadeklarowane reguły**, nie orzeka o widoczności:

    >>> deobfuscate('<div style="display:none">ukryte</div>widoczne')
    '[DEKLARACJE: display:none] ukryte\\nwidoczne'

    Sam biały kolor tekstu nie jest deklaracją ukrywającą — o widoczności
    decyduje tło, więc tekst wchodzi do treści bez markera:

    >>> deobfuscate('<div style="background-color:#1965F7;color:#FFF">Zobacz</div>')
    'Zobacz'
    """
    text = strip_style_and_script(src)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    def mark_hidden(match: re.Match[str]) -> str:
        style = match.group("style")
        rules = _hidden_rules(style)
        inner = re.sub(r"<[^>]+>", "", match.group("inner"))
        inner = html.unescape(inner).strip()
        if not rules or not inner:
            return match.group(0)
        return f"\n[DEKLARACJE: {', '.join(rules)}] {inner}\n"

    text = re.sub(
        r"<(?P<tag>div|span|p|td|table)\b[^>]*style=[\"'](?P<style>[^\"']*)[\"'][^>]*>"
        r"(?P<inner>.*?)</(?P=tag)>",
        mark_hidden,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    text = html.unescape(text)
    text = "".join(c for c in text if ord(c) not in ZERO_WIDTH_CHARS)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</?(?:p|div|tr|table|h[1-6]|li)[^>]*>", "\n", text, flags=re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


QUOTE_MARKERS = (
    r"^\s*(?:W\s+dniu\s+.{0,80}?(?:pisze|napisał|napisała)\s*:)",
    r"^\s*(?:On\s+.{0,80}?wrote\s*:)",
    r"^\s*-{2,}\s*(?:Original Message|Wiadomość oryginalna|Forwarded message)\s*-{2,}",
    r"^\s*(?:Od|From)\s*:\s*.+@.+",
    r"^\s*_{5,}\s*$",
)


def split_quoted(text: str) -> tuple[str, str]:
    """Dzieli treść na część własną nadawcy i cytat wcześniejszej korespondencji.

    Bez tego podziału raport pokazuje 22 kB tekstu tam, gdzie nadawca napisał
    trzy zdania, a reszta to zacytowane pismo odbiorcy.

    >>> own, quoted = split_quoted("Dzien dobry.\\n\\nW dniu 17-08-2026 16:59, x@y.pl pisze:\\n> stare")
    >>> own
    'Dzien dobry.'
    >>> quoted.splitlines()[0]
    'W dniu 17-08-2026 16:59, x@y.pl pisze:'
    >>> split_quoted("Bez cytatu")
    ('Bez cytatu', '')
    >>> split_quoted("")
    ('', '')
    """
    lines = text.splitlines()
    patterns = [re.compile(p, re.IGNORECASE) for p in QUOTE_MARKERS]
    for i, line in enumerate(lines):
        if any(p.match(line) for p in patterns):
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
    return text.strip(), ""


#: Deklaracje, które wyjmują element z widoku **niezależnie od tła**. Tylko one
#: są samodzielnym ustaleniem; reszta wymaga wiedzy o kontekście renderowania.
HIDING_DECLARATIONS = (
    r"display:none",
    r"visibility:hidden",
    r"mso-hide:all",
    r"opacity:0(?:\.0*[0-9])?(?![\d.])",
    r"max-height:0(?:px)?(?![\d.])",
    r"max-width:0(?:px)?(?![\d.])",
    r"font-size:[01](?:px)?(?![\d.])",
    r"line-height:0(?:px)?(?![\d.])",
    r"(?<!-)\bheight:0(?:px)?(?![\d.])",
    r"(?<!-)\bwidth:0(?:px)?(?![\d.])",
    r"text-indent:-\d+",
    r"position:absolute;left:-\d+",
)

#: Deklaracje **koloru tekstu**. O widoczności przesądzają dopiero razem z tłem —
#: biały tekst na niebieskim przycisku jest w pełni widoczny. Dlatego zadeklarowane
#: tło, jeśli różni się od koloru tekstu, wyklucza je z ustalenia.
COLOR_CONTRAST_DECLARATIONS = (
    # `(?<![-a-z])` odcina `border-top-color`, `background-color` i podobne —
    # dopasowanie po podciągu `color:` produkowało fałszywy pozytyw na tabelach
    # z białą linią obramowania.
    r"(?<![-a-z])color:#f{3,6}\b",
    r"(?<![-a-z])color:white",
    r"(?<![-a-z])color:rgb\(255,255,255\)",
    # 8-cyfrowy hex niesie kanał alfa: `#00000050` to czerń z krycia 0x50 = 31 %.
    # Detektor znający tylko biel przepuszczał zmierzalne wygaszenie stopki.
    r"(?<![-a-z])color:#[0-9a-f]{6}(?:0[0-9a-f]|[0-7][0-9a-f])\b",
    r"(?<![-a-z])color:(?:grey|gray|silver|lightgr[ae]y|gainsboro)\b",
    r"(?<![-a-z])color:rgba\([^)]*,0?\.[0-4]\d*\)",
)

#: Deklaracje osłabiające widoczność **niezależnie od koloru tła**: częściowe
#: krycie i drobny rozmiar czcionki. Wcześniej leżały w jednym worku z kolorem
#: tekstu, więc zadeklarowane tło wykluczało je razem z nim — i element
#: `opacity:0.96` z własnym tłem znikał z raportu bez żadnego ustalenia.
DIMMING_DECLARATIONS = (
    r"opacity:0\.[0-9]+",
    r"font-size:[2-5](?:px)?(?![\d.])",
)

#: Suma obu zbiorów — używana tam, gdzie sekcja opisuje „kontrast/rozmiar”
#: łącznie, bez rozstrzygania, co zależy od tła.
LOW_CONTRAST_DECLARATIONS = COLOR_CONTRAST_DECLARATIONS + DIMMING_DECLARATIONS


def _match_declarations(style: str, patterns: tuple[str, ...]) -> list[str]:
    """Dopasowane deklaracje CSS, zwrócone dosłownie w kolejności wzorców."""
    normalized = re.sub(r"\s*:\s*", ":", style.lower())
    found = []
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            found.append(match.group(0))
    return found


def _hidden_rules(style: str) -> list[str]:
    """Deklaracje ukrywające element niezależnie od tła — zwracane dosłownie.

    >>> _hidden_rules("display:none; color:red")
    ['display:none']
    >>> sorted(_hidden_rules("opacity:0.01;max-height:0px;font-size:1px"))
    ['font-size:1px', 'max-height:0px', 'opacity:0.01']
    >>> _hidden_rules("color:#000000; font-size:14px")
    []
    >>> _hidden_rules("height:0px")
    ['height:0px']
    >>> _hidden_rules("line-height:1.5; font-size:16px")
    []

    Sam biały kolor tekstu **nie** jest tu liczony — o widoczności decyduje tło,
    którego wiadomość może w ogóle nie deklarować:

    >>> _hidden_rules("color:#FFFFFF")
    []
    """
    return _match_declarations(style, HIDING_DECLARATIONS)


def declared_background(style: str) -> str | None:
    """Tło zadeklarowane na tym samym elemencie, jeśli jest.

    Bez tego sprawdzenia biały tekst na kolorowym przycisku był oznaczany jako
    ukryty — fałszywy dowód wygenerowany przez samo narzędzie.

    >>> declared_background("background-color:#1965F7; color:#FFFFFF")
    'background-color:#1965f7'
    >>> declared_background("background:#000")
    'background:#000'
    >>> declared_background("color:#FFFFFF") is None
    True
    >>> declared_background("background-color:transparent")
    'background-color:transparent'
    """
    normalized = re.sub(r"\s*:\s*", ":", style.lower())
    match = re.search(r"background(?:-color)?:[^;\"']+", normalized)
    return match.group(0).strip() if match else None


def _low_contrast_rules(style: str) -> list[str]:
    """Deklaracje koloru/rozmiaru, które o widoczności same nie przesądzają.

    >>> _low_contrast_rules("color: white; font-size: 4px")
    ['color:white', 'font-size:4px']
    >>> _low_contrast_rules("color:#333; font-size:14px")
    []

    `border-top-color` i `background-color` to nie kolor tekstu:

    >>> _low_contrast_rules("border-top-width:2px;border-top-color: #FFFFFF")
    []
    >>> _low_contrast_rules("background-color:#FFFFFF")
    []

    Ósma i dziewiąta cyfra hex to kanał alfa — `#00000050` renderuje się jako
    jasna szarość, mimo że sam kolor jest czarny:

    >>> _low_contrast_rules("font-size:10px;color:#00000050")
    ['color:#00000050']
    >>> _low_contrast_rules("color:grey; text-decoration:none")
    ['color:grey']
    >>> _low_contrast_rules("opacity:0.96")
    ['opacity:0.96']
    >>> _low_contrast_rules("color:#000000")
    []
    """
    return _match_declarations(style, LOW_CONTRAST_DECLARATIONS)


def _color_contrast_rules(style: str) -> list[str]:
    """Deklaracje koloru tekstu — te, które zadeklarowane tło może wykluczyć.

    >>> _color_contrast_rules("color:white; font-size:4px")
    ['color:white']
    >>> _color_contrast_rules("opacity:0.96")
    []
    """
    return _match_declarations(style, COLOR_CONTRAST_DECLARATIONS)


def _dimming_rules(style: str) -> list[str]:
    """Deklaracje osłabiające widoczność niezależnie od tła: krycie i rozmiar.

    Krycie 0.96 obniża widoczność tak samo na białym i na czarnym tle, więc
    zadeklarowane tło nie może go wykluczyć. Wspólny worek z kolorem tekstu
    sprawiał, że przycisk `opacity:0.96` z własnym `background-color` wypadał
    z sekcji o widoczności w całości — razem z tekstem, który niósł.

    >>> _dimming_rules("opacity:0.96;background-color:#1965F7;color:#FFFFFF")
    ['opacity:0.96']
    >>> _dimming_rules("font-size:3px")
    ['font-size:3px']
    >>> _dimming_rules("color:white")
    []
    """
    return _match_declarations(style, DIMMING_DECLARATIONS)


def _element_inner(src: str, match: "re.Match[str]") -> str:
    """Treść elementu od znacznika otwierającego do najbliższego domykającego.

    Przybliżenie wystarczające do zacytowania tekstu: nie buduje drzewa DOM,
    tylko bierze fragment do pierwszego `</tag>` tego samego typu.

    >>> import re
    >>> src = '<td style="font-size:0px">tekst</td>'
    >>> m = re.search(r"<(?P<tag>td)\\b(?P<attrs>[^>]*)>", src)
    >>> _element_inner(src, m)
    'tekst'
    >>> src = '<td style="x">bez domkniecia'
    >>> m = re.search(r"<(?P<tag>td)\\b(?P<attrs>[^>]*)>", src)
    >>> _element_inner(src, m)
    'bez domkniecia'
    """
    tag = match.group("tag")
    rest = src[match.end() :]
    closing = re.search(rf"</{re.escape(tag)}\s*>", rest, re.IGNORECASE)
    return rest[: closing.start()] if closing else rest[:2000]


def _colour(declaration: str) -> str | None:
    """Znormalizowany kolor z deklaracji CSS — do porównań tekst ↔ tło.

    >>> _colour("color:#FFFFFF")
    '#ffffff'
    >>> _colour("background-color: white")
    '#ffffff'
    >>> _colour("background:#000")
    '#000000'
    >>> _colour("color:red") is None
    True
    """
    match = re.search(
        r"#([0-9a-fA-F]{3,8})\b|\b(white|black)\b", declaration, re.IGNORECASE
    )
    if not match:
        return None
    if match.group(2):
        return "#ffffff" if match.group(2).lower() == "white" else "#000000"
    hex_ = match.group(1).lower()
    if len(hex_) == 3:
        hex_ = "".join(c * 2 for c in hex_)
    return "#" + hex_[:6]


def text_blends_into_background(style: str, background: str | None) -> bool:
    """Czy zadeklarowany kolor tekstu jest identyczny z zadeklarowanym tłem.

    Samo istnienie tła nie wyklucza ukrycia — biały tekst na białym `body`
    to klasyczny przypadek, który przy regule „jest tło, więc pomijamy”
    wypadłby z raportu.

    >>> text_blends_into_background("color:#ffffff", "background-color:#ffffff (z <style>, body)")
    True
    >>> text_blends_into_background("color:#FFFFFF", "background-color:#1965F7")
    False
    >>> text_blends_into_background("color:#fff", None)
    False
    """
    if not background:
        return False
    text = _colour(re.sub(r"background[^;]*", "", style, flags=re.IGNORECASE))
    background = _colour(background)
    return bool(text and background and text == background)


def find_hidden_elements(src: str) -> list[HiddenElement]:
    """Elementy z deklaracjami CSS wpływającymi na widoczność, wraz z treścią.

    Rozdzielone na dwie klasy, bo mają różną wartość dowodową:

    * `ukrywające` — `display:none`, `opacity:0`, zerowa wysokość i podobne;
      działają niezależnie od kontekstu renderowania,
    * `kontrast/rozmiar` — biały kolor tekstu, czcionka 2–5 px; o widoczności
      przesądzają dopiero razem z tłem, więc zadeklarowane tło jest podane obok.

    >>> els = find_hidden_elements('<div style="opacity:0.01;max-height:0px">tajne</div>')
    >>> els[0].text, els[0].kind
    ('tajne', 'ukrywające')
    >>> sorted(els[0].rules)
    ['max-height:0px', 'opacity:0.01']
    >>> find_hidden_elements('<div style="color:#000">jawne</div>')
    []

    Biały tekst na zadeklarowanym kolorowym tle to element widoczny:

    >>> find_hidden_elements(
    ...     '<div style="background-color:#1965F7;color:#FFFFFF">Zobacz cennik</div>')
    []

    Tło zadeklarowane w bloku `<style>` liczy się tak samo jak w atrybucie:

    >>> find_hidden_elements(
    ...     '<style>#stopka{background-color:#000000}</style>'
    ...     '<td id="stopka" style="color:#FFFFFF">Firma sp. z o.o.</td>')
    []

    Tło zgodne z kolorem tekstu to ustalenie najmocniejsze w tej klasie:

    >>> el = find_hidden_elements(
    ...     '<style>body{background-color:#ffffff}</style>'
    ...     '<div style="color:#ffffff;font-size:1px">tekst pomocniczy</div>')[0]
    >>> el.kind, "kolor tekstu identyczny z tłem (#ffffff)" in el.rules
    ('ukrywające', True)

    Bez zadeklarowanego tła fakt zostaje odnotowany w klasie, która
    o widoczności nie przesądza:

    >>> el = find_hidden_elements('<span style="color: white; font-size: 4px">x</span>')[0]
    >>> el.kind, el.rules, el.background is None
    ('kontrast/rozmiar', ('color:white', 'font-size:4px'), True)

    Krycie nie zależy od tła, więc zadeklarowane tło go nie wyklucza:

    >>> el = find_hidden_elements(
    ...     '<div style="opacity:0.96;background-color:#1965F7;color:#FFFFFF">Zobacz</div>')[0]
    >>> el.kind, el.rules, el.text
    ('kontrast/rozmiar', ('opacity:0.96',), 'Zobacz')

    Element bez treści też jest ustaleniem:

    >>> el = find_hidden_elements('<span style="display:none;opacity:0"></span>')[0]
    >>> el.text, el.kind
    ('', 'ukrywające')
    """
    out: list[HiddenElement] = []
    # Skanujemy znaczniki OTWIERAJĄCE. Wzorzec wymagający pary `<tag>…</tag>`
    # konsumował zagnieżdżone elementy i przy 27 komórkach `<TD>` z regułą
    # ukrywającą raportował 9 — `finditer` nie zwraca dopasowań nakładających się.
    pattern = re.compile(
        r"<(?P<tag>div|span|p|td|tr|table|a|font)\b(?P<attrs>[^>]*)>",
        re.IGNORECASE,
    )
    stylesheet = stylesheet_declarations(src)
    for match in pattern.finditer(src):
        style = _attr(match.group("attrs"), "style")
        if not style:
            continue
        # Tło bierzemy najpierw z atrybutu elementu, a gdy go tam nie ma —
        # z reguł `<style>` dopasowanych po `id`/`class`. Bez drugiego kroku
        # biały tekst na czarnej stopce trafiał do sekcji o widoczności
        # z adnotacją „tło nieustalone”, choć plik zawierał odpowiedź.
        background = declared_background(style) or background_for_element(
            match.group("attrs"), stylesheet
        )
        hiding = _hidden_rules(style)
        # Tło wyklucza regułę kontrastu tylko wtedy, gdy RÓŻNI SIĘ od koloru
        # tekstu. Zgodność (biały na białym) jest odwrotnie — najmocniejszym
        # przypadkiem w tej klasie, więc trafia do reguł ukrywających.
        blends = text_blends_into_background(style, background)
        if blends:
            hiding = hiding + [
                f"kolor tekstu identyczny z tłem ({_colour(background)})"
            ]
        colour = [] if (background and not blends) else _color_contrast_rules(style)
        # Krycie i rozmiar czcionki NIE zależą od tła, więc zadeklarowane tło
        # ich nie wyklucza. Wspólne wykluczanie z kolorem tekstu kasowało cały
        # element `opacity:0.96; background-color:#1965F7` — razem z jego treścią.
        low_contrast = colour + _dimming_rules(style)
        if not hiding and not low_contrast:
            continue
        inner = html.unescape(re.sub(r"<[^>]+>", " ", _element_inner(src, match)))
        inner = re.sub(r"\s+", " ", inner).strip()
        out.append(
            HiddenElement(
                tag=match.group("tag").lower(),
                rules=tuple(hiding or low_contrast),
                text=inner,
                style=re.sub(r"\s+", " ", style).strip(),
                kind="ukrywające" if hiding else "kontrast/rozmiar",
                background=background,
            )
        )
    return out


def stylesheet_declarations(src: str) -> dict[str, dict[str, str]]:
    """Deklaracje z bloków `<style>` w podziale na selektor → właściwość → wartość.

    Bez tej mapy biały tekst stopki leżącej w `<td id="templateFooter">`
    z regułą `#templateFooter{background-color:#000000}` był raportowany jako
    „tło nieustalone”, choć plik zawiera odpowiedź.

    >>> mapa = stylesheet_declarations('<style>#stopka{background-color:#000000;color:#fff}</style>')
    >>> mapa["#stopka"]["background-color"]
    '#000000'
    >>> stylesheet_declarations("bez stylow")
    {}

    Reguły z `@media` nie wchodzą do mapy — obowiązują tylko przy spełnionym
    warunku, więc nie ustalają tła, na którym renderuje się wiadomość:

    >>> stylesheet_declarations('<style>@media print{body{background:#000}}</style>')
    {}
    """
    out: dict[str, dict[str, str]] = {}
    for block in re.findall(
        r"<style\b[^>]*>(.*?)</style>", src, re.DOTALL | re.IGNORECASE
    ):
        for selector, body, condition in _rules_with_conditions(block):
            if condition is not None:
                continue
            declarations = {
                k.strip().lower(): v.strip()
                for k, v in re.findall(r"([a-zA-Z-]+)\s*:\s*([^;]+)", body)
            }
            if not declarations:
                continue
            for single in selector.split(","):
                name = re.sub(r"\s+", " ", single).strip()
                if name:
                    out.setdefault(name, {}).update(declarations)
    return out


def background_for_element(
    attrs: str, stylesheet: dict[str, dict[str, str]]
) -> str | None:
    """Tło elementu ustalone z jego `id`/`class` wobec reguł z bloków `<style>`.

    >>> arkusz = {"#stopka": {"background-color": "#000000"}}
    >>> background_for_element('id="stopka"', arkusz)
    'background-color:#000000 (z <style>, selektor #stopka)'
    >>> background_for_element('class="tresc"', arkusz) is None
    True

    Gdy element nie pasuje do żadnego selektora, tło dziedziczy z `body`:

    >>> background_for_element('class="x"', {"body": {"background-color": "#ffffff"}})
    'background-color:#ffffff (z <style>, selektor body)'
    """
    element_id = _attr(attrs, "id")
    classes = (_attr(attrs, "class") or "").split()
    # `body` na końcu: gdy element nie deklaruje własnego tła ani nie pasuje do
    # żadnego selektora, tło dziedziczy z dokumentu. Bez tego kroku biały tekst
    # przy `body{background-color:#ffffff}` zostawał jako „tło nieustalone”.
    selectors = (
        ([f"#{element_id}"] if element_id else [])
        + [f".{k}" for k in classes]
        + ["body"]
    )
    for selector in selectors:
        declarations = stylesheet.get(selector, {})
        for prop in ("background-color", "background"):
            if prop in declarations:
                return f"{prop}:{declarations[prop]} (z <style>, selektor {selector})"
    return None


def _rules_with_conditions(block: str) -> list[tuple[str, str, str | None]]:
    """Reguły z bloku CSS jako `(selektor, deklaracje, warunek)`.

    Reguły zagnieżdżone w `@media`/`@supports` niosą swój warunek; pozostałe
    mają `None`. Wcześniejszy parser dopasowywał `([^{}]+)\\{([^{}]*)\\}`, więc
    nagłówek `@media …` traktował jak zwykły selektor, a jego zawartość jako
    reguły bezwarunkowe.

    >>> _rules_with_conditions('.a{display:none}')
    [('.a', 'display:none', None)]
    >>> _rules_with_conditions('@media (max-width:600px){.b{display:none}}')
    [('.b', 'display:none', '@media (max-width:600px)')]
    >>> _rules_with_conditions('.a{color:red}@media print{.b{display:none}}.c{margin:0}')
    [('.a', 'color:red', None), ('.b', 'display:none', '@media print'), ('.c', 'margin:0', None)]
    >>> _rules_with_conditions('')
    []
    """
    out: list[tuple[str, str, str | None]] = []
    pos = 0
    while pos < len(block):
        opening = block.find("{", pos)
        if opening < 0:
            break
        prelude = block[pos:opening].strip()
        if prelude.startswith("@") and re.match(
            r"@(media|supports|container)\b", prelude
        ):
            # Reguła warunkowa: jej ciało zawiera kolejne reguły. Szukamy
            # domykającej klamry pary, żeby nie uciąć bloku na pierwszym `}`.
            depth, index = 1, opening + 1
            while index < len(block) and depth:
                if block[index] == "{":
                    depth += 1
                elif block[index] == "}":
                    depth -= 1
                index += 1
            condition = re.sub(r"\s+", " ", prelude)
            for selector, body, nested in _rules_with_conditions(
                block[opening + 1 : index - 1]
            ):
                out.append((selector, body, nested or condition))
            pos = index
            continue
        closing = block.find("}", opening)
        if closing < 0:
            break
        selector = prelude
        if selector:
            out.append((selector, block[opening + 1 : closing].strip(), None))
        pos = closing + 1
    return out


def stylesheet_hiding_rules(src: str) -> list[StylesheetRule]:
    """Reguły ukrywające z bloków `<style>` — selektor, deklaracje, użycie i warunek.

    Sekcja o elementach ukrytych skanowała wyłącznie atrybut `style`, a bloki
    `<style>` były wcześniej usuwane z treści. Ustalenie „0 elementów” było więc
    prawdziwe tylko dla stylów inline — i nie mówiło o tym zakresie.

    Reguła w `@media` obowiązuje **tylko** przy spełnionym warunku — bez niego
    blok responsywny czytałby się jak dowód ukrywania treści:

    >>> r = stylesheet_hiding_rules(
    ...     '<style>@media only screen and (max-width:714px){.hiddentds{display:none}}</style>'
    ...     '<td class="hiddentds">x</td>')[0]
    >>> r.selector, r.declarations, r.usage, r.condition
    ('.hiddentds', 'display:none', 1, '@media only screen and (max-width:714px)')

    Reguła bezwarunkowa ma `condition` równe `None` — tylko ona jest
    samodzielnym ustaleniem:

    >>> r = stylesheet_hiding_rules(
    ...     '<style>.ukryte{display:none}</style><td class="ukryte">x</td>')[0]
    >>> r.condition is None, r.unconditional
    (True, True)

    Atrybut bez cudzysłowów liczy się tak samo:

    >>> r = stylesheet_hiding_rules(
    ...     '<STYLE>.hiddentds{display:none}</STYLE><TR class=hiddentds><TR class=hiddentds>')[0]
    >>> r.selector, r.usage
    ('.hiddentds', 2)
    >>> stylesheet_hiding_rules('<style>p{margin:0}</style><p>x</p>')
    []
    >>> stylesheet_hiding_rules('bez stylow')
    []
    """
    out: list[StylesheetRule] = []
    for block in re.findall(
        r"<style\b[^>]*>(.*?)</style>", src, re.DOTALL | re.IGNORECASE
    ):
        for selector, body, condition in _rules_with_conditions(block):
            declarations = _hidden_rules(body)
            if not declarations:
                continue
            name = re.sub(r"\s+", " ", selector).strip().split(",")[0].strip()
            if not name:
                continue
            usage = 0
            class_match = re.search(r"\.([A-Za-z0-9_-]+)", name)
            if class_match:
                # `class=hiddentds` bez cudzysłowów jest równie legalne co
                # `class="hiddentds"` — wymaganie cudzysłowów dawało licznik 0
                # przy 17 elementach faktycznie noszących tę klasę.
                usage = len(
                    re.findall(
                        rf'class\s*=\s*["\']?[^"\'>]*\b{re.escape(class_match.group(1))}\b',
                        src,
                        re.IGNORECASE,
                    )
                )
            out.append(
                StylesheetRule(
                    selector=name,
                    declarations=", ".join(declarations),
                    usage=usage,
                    condition=condition,
                )
            )
    return out


def classify_comments(src: str) -> list[HtmlComment]:
    """Komentarze HTML z klasyfikacją i sprawdzeniem, czy faktycznie dzielą wyraz.

    >>> [c.kind for c in classify_comments('<!--[if gte mso 9]>tekst<![endif]-->')]
    ['warunkowy MSO/Outlook']
    >>> [c.kind for c in classify_comments('<div><!--[if mso]><![endif]--></div>')]
    ['warunkowy MSO/Outlook']
    >>> [c.kind for c in classify_comments('<!-- NAME: SELL PRODUCTS -->')]
    ['znacznik szablonu/generatora']
    >>> c = classify_comments('sło<!--x-->wo')[0]
    >>> c.splits_word, c.kind
    (True, 'wewnątrz wyrazu')
    >>> classify_comments('bez komentarzy')
    []
    """
    out: list[HtmlComment] = []
    for match in re.finditer(r"<!--.*?-->|<!\[endif\]-->", src, flags=re.DOTALL):
        text = match.group(0)
        before = src[max(0, match.start() - 1) : match.start()]
        after = src[match.end() : match.end() + 1]
        splits = bool(before and after and before[-1].isalnum() and after[0].isalnum())
        if re.search(r"\[if\b|\[endif\]", text, re.IGNORECASE):
            kind = "warunkowy MSO/Outlook"
        elif splits:
            kind = "wewnątrz wyrazu"
        elif re.search(
            r"\*\|.*\|\*|blockId|BEGIN|END|NAME:|Preheader|Created with",
            text,
            re.IGNORECASE,
        ):
            kind = "znacznik szablonu/generatora"
        else:
            kind = "zwykły"
        out.append(
            HtmlComment(
                text=re.sub(r"\s+", " ", text)[:120], kind=kind, splits_word=splits
            )
        )
    return out


def find_word_splitting_spans(src: str) -> list[str]:
    """Znaczniki <span> stojące wewnątrz wyrazu — sprawdzone przez sąsiedztwo.

    Poprzednia wersja liczyła każdy `<span>...</span>` bez atrybutów jako
    „pusty span rozbijający wyrazy”. Trafiała w komórki układu (`<td><span></span></td>`)
    i w spany z treścią, których nic nie rozbijały.

    >>> find_word_splitting_spans('sło<span></span>wo')
    ['sło<span></span>wo']
    >>> find_word_splitting_spans('sł<span>ańst</span>wo')
    ['sł<span>ańst</span>wo']
    >>> find_word_splitting_spans('<td> <span></span> </td>')
    []
    >>> find_word_splitting_spans('<span>Ochrona do 36 miesiecy</span>')
    []
    >>> find_word_splitting_spans('tekst <span>samodzielny</span> tekst')
    []
    """
    out: list[str] = []
    for match in re.finditer(
        r"<span[^>]*>.*?</span>", src, flags=re.DOTALL | re.IGNORECASE
    ):
        before = re.search(r"\w{0,12}$", src[: match.start()])
        after = re.match(r"\w{0,12}", src[match.end() :])
        left = before.group(0) if before else ""
        right = after.group(0) if after else ""
        if left and right:
            out.append(left + match.group(0) + right)
    return out


def _attr(attrs: str, name: str) -> str | None:
    """Wartość atrybutu HTML — w cudzysłowach albo bez nich.

    Składnia bez cudzysłowów jest legalna w HTML i występuje w wiadomościach
    generowanych przez starsze edytory (`alt=dell_9020 title=dell_9020`).
    Regex wymagający cudzysłowów pokazywał „brak danych” tam, gdzie dane były.

    >>> _attr('src="https://a.pl/x.png" alt="Logo"', "alt")
    'Logo'
    >>> _attr('SRC=cid:1 ALT=dell_9020 WIDTH=308', "alt")
    'dell_9020'
    >>> _attr("alt=''", "alt") is None
    True
    >>> _attr('src="x"', "alt") is None
    True
    """
    match = re.search(
        rf"""\b{re.escape(name)}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""",
        attrs,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = next((g for g in match.groups() if g), None)
    return value or None


#: Który zapis wygrywa, gdy ten sam URL występuje w treści na kilka sposobów.
#: Niższa liczba = zapis niosący więcej informacji o tym, jak zasób jest pobierany.
RESOURCE_KIND_PRIORITY = {
    "img": 0,
    "beacon-css": 1,
    "script": 2,
    "iframe": 3,
    "link": 4,
    "v:fill": 5,
    "a": 6,
    "css-url": 7,
}


def extract_html_resources(src: str) -> list[HtmlResource]:
    """Wszystkie zasoby odwoływane z HTML — nie tylko <a href>.

    `<a href="...">tekst<span>…</span></a>` gubił się na regexie `>([^<]+)</a>`,
    a `<img>`, `<script src>`, `<link rel=stylesheet>` i tła CSS nie były zbierane
    w ogóle — przez co raporty twierdziły „nie znaleziono linków” w wiadomościach
    z pikselem śledzącym i przyciskiem CTA.

    >>> res = extract_html_resources('<a href="https://a.pl/x?id=1"><span>Kliknij</span></a>')
    >>> res[0].kind, res[0].host, res[0].text
    ('a', 'a.pl', 'Kliknij')
    >>> px = extract_html_resources('<img height="1" width="1" src="https://t.pl/o.gif" alt=""/>')
    >>> px[0].kind, px[0].is_pixel
    ('img', True)
    >>> extract_html_resources('<script src="/bot/x.js"></script>')[0].kind
    'script'
    >>> extract_html_resources('<link rel="stylesheet" href="https://a.pl/s.css">')[0].kind
    'link'
    >>> extract_html_resources('<div style="background-image:url(https://a.pl/p.gif)">x</div>')[0].kind
    'css-url'
    >>> extract_html_resources('<a href="mailto:kontakt@a.pl">napisz</a>')[0].scheme
    'mailto'

    Beacon zapisany jako element 1×1 z obrazem w tle nie jest znacznikiem `<img>`,
    ale jest zasobem pobieranym z sieci:

    >>> zrodlo = '<div style="width:1px;height:1px;background:url(https://t.example/o)"></div>'
    >>> b = [r for r in extract_html_resources(zrodlo) if r.kind == "beacon-css"]
    >>> b[0].host
    't.example'

    Deklaracja przestrzeni nazw nie jest linkiem nadawcy:

    >>> extract_html_resources('<html xmlns="http://www.w3.org/1999/xhtml">tresc</html>')
    []

    Powtórzone odwołanie to jedna pozycja, ale z licznikiem wystąpień:

    >>> dwa = extract_html_resources('<a href="https://a.pl/x">raz</a><a href="https://a.pl/x">dwa</a>')
    >>> len(dwa), dwa[0].occurrences
    (1, 2)

    Ten sam URL zapisany na dwa sposoby to **jeden** pobierany zasób:

    >>> jeden = extract_html_resources(
    ...     '<div style="width:1px;height:1px;background:url(https://t.pl/p.gif)"></div>')
    >>> len(jeden), jeden[0].kind, jeden[0].also_as
    (1, 'beacon-css', ('css-url',))
    """
    out: list[HtmlResource] = []

    def add(kind: str, url: str, text: str | None = None, attrs: str = "") -> None:
        alt_present = bool(re.search(r"\balt\s*=", attrs, re.IGNORECASE))
        url = html.unescape(url.strip())
        # `cid:` zostaje — to odwołanie do części osadzonej w samej wiadomości,
        # czyli fakt o strukturze, a nie do zasobu pobieranego z sieci.
        if (not url or url.startswith("#")) and not url.lower().startswith("cid:"):
            return
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if host and host.lower() in BOILERPLATE_URL_HOSTS:
            return
        width = re.search(r'\bwidth\s*=\s*["\']?(\d+)', attrs, re.IGNORECASE)
        height = re.search(r'\bheight\s*=\s*["\']?(\d+)', attrs, re.IGNORECASE)
        out.append(
            HtmlResource(
                kind=kind,
                url=url,
                text=text,
                scheme=(parsed.scheme or "względny").lower(),
                host=host,
                width=width.group(1) if width else None,
                height=height.group(1) if height else None,
                attrs=re.sub(r"\s+", " ", attrs).strip()[:200],
                alt_present=alt_present,
            )
        )

    for match in re.finditer(
        # `attrs` musi objąć CAŁY znacznik, nie tylko część przed `href`.
        # Wcześniej atrybuty stojące za `href` — w tym `title` i `style` —
        # były dla ekstraktora niewidoczne, więc kotwica z pustym tekstem
        # i opisem wyłącznie w `title` trafiała do raportu jako „—”.
        r"<a\b(?P<attrs>[^>]*?)href=[\"'](?P<url>[^\"']+)[\"'](?P<rest>[^>]*)>"
        r"(?P<text>.*?)</a>",
        src,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        text = html.unescape(re.sub(r"<[^>]+>", " ", match.group("text")))
        label = re.sub(r"\s+", " ", text).strip()
        attrs_all = match.group("attrs") + match.group("rest")
        title = _attr(attrs_all, "title")
        if title:
            label = f"{label} (title: {title})" if label else f"(title: {title})"
        add("a", match.group("url"), label, attrs_all)

    for match in re.finditer(r"<img\b(?P<attrs>[^>]*)>", src, flags=re.IGNORECASE):
        attrs = match.group("attrs")
        url = _attr(attrs, "src")
        if url:
            # `alt=dell_9020` bez cudzysłowów jest równie legalne co `alt="…"`.
            # Regex wymagający cudzysłowów pokazywał „—” w kolumnie tekstu przy
            # czternastu obrazach, z których każdy miał `alt` i `title`.
            label = _attr(attrs, "alt")
            title = _attr(attrs, "title")
            if title and title != label:
                label = f"{label or ''} (title: {title})".strip()
            add("img", url, label, attrs)

    for tag, kind in (("script", "script"), ("iframe", "iframe"), ("link", "link")):
        for match in re.finditer(rf"<{tag}\b([^>]*)>", src, flags=re.IGNORECASE):
            attrs = match.group(1)
            url = _attr(attrs, "src") or _attr(attrs, "href")
            if url:
                add(kind, url, None, attrs)

    for match in re.finditer(
        r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", src, flags=re.IGNORECASE
    ):
        add("css-url", match.group(1))

    # Beacon bywa elementem 1×1 z obrazem w tle, nie znacznikiem `<img>` —
    # taki nie trafiał do raportu w żadnej sekcji: detektor pikseli patrzył
    # wyłącznie na `<img>`, a detektor ukryć wyłącznie na reguły ukrywające.
    for match in re.finditer(
        r"<(?:div|td|span|table)\b([^>]*)>", src, flags=re.IGNORECASE
    ):
        style = _attr(match.group(1), "style") or ""
        normalized = re.sub(r"\s+", "", style.lower())
        if not re.search(r"(?<![-a-z])width:[01](?:px|pt)", normalized):
            continue
        if not re.search(r"(?<![-a-z])height:[01](?:px|pt)", normalized):
            continue
        background = re.search(r"url\(\s*[\"']?([^\"')]+)", style, re.IGNORECASE)
        if background:
            add("beacon-css", background.group(1), None, match.group(1))

    # Outlook VML: <v:fill src="..."> to ten sam zasób co tło CSS, innym zapisem.
    for match in re.finditer(r"<v:fill\b([^>]*)>", src, flags=re.IGNORECASE):
        url_match = re.search(r"src=[\"']([^\"']+)[\"']", match.group(1), re.IGNORECASE)
        if url_match:
            add("v:fill", url_match.group(1), None, match.group(1))

    counts: dict[tuple[str, str], int] = {}
    # Deduplikacja po URL-u, nie po parze (rodzaj, URL). Ten sam piksel zapisany
    # jako `background:url(…)` na elemencie 1×1 trafiał do wyniku dwa razy —
    # jako `css-url` i jako `beacon-css` — więc licznik zasobów pobieranych
    # z sieci podawał 5 tam, gdzie pobierane są 3, a sekcja jednocześnie
    # twierdziła, że żadne odwołanie się nie powtarza.
    unique: list[HtmlResource] = []
    kinds: dict[str, list[str]] = {}
    for resource in out:
        counts[resource.url] = counts.get(resource.url, 0) + 1
        kinds.setdefault(resource.url, [])
        if resource.kind not in kinds[resource.url]:
            kinds[resource.url].append(resource.kind)
        if any(r.url == resource.url for r in unique):
            # Zapis niosący więcej informacji wygrywa: `beacon-css` mówi
            # o elemencie 1×1, `css-url` tylko o tym, że URL jest w CSS.
            index = next(i for i, r in enumerate(unique) if r.url == resource.url)
            if RESOURCE_KIND_PRIORITY.get(
                resource.kind, 99
            ) < RESOURCE_KIND_PRIORITY.get(unique[index].kind, 99):
                unique[index] = resource
            continue
        unique.append(resource)
    # Krotność wystąpień zostaje w wyniku — inaczej „5 linków” po deduplikacji
    # czytałoby się jak „w wiadomości jest 5 znaczników”, a bywa ich więcej.
    return [
        replace(
            r,
            occurrences=counts[r.url],
            also_as=tuple(k for k in kinds[r.url] if k != r.kind),
        )
        for r in unique
    ]


def unusual_characters(text: str) -> list[tuple[str, int, str, str]]:
    """Znaki zerowej szerokości i homoglify ASCII — z kodem, nazwą i liczbą wystąpień.

    U+2024 (ONE DOT LEADER) w miejscu kropki przeszedł przez detektor, który znał
    tylko znaki zerowej szerokości.

    >>> unusual_characters("m\\u2024in. tekst")
    [('U+2024', 1, 'ONE DOT LEADER', 'wygląda jak "."')]
    >>> unusual_characters("a\\u200bb")
    [('U+200B', 1, 'ZERO WIDTH SPACE', 'zerowa szerokość')]
    >>> unusual_characters("zwykly tekst")
    []

    Myślnik półpauzowy to poprawna typografia, nie próba podszycia:

    >>> unusual_characters("słowo \u2013 drugie")
    [('U+2013', 1, 'EN DASH', 'typografia spoza ASCII (nie homoglif)')]
    """
    counter = collections.Counter(
        ch
        for ch in text
        if ord(ch) in ZERO_WIDTH_CHARS
        or ch in HOMOGLYPHS
        or ord(ch) in TYPOGRAPHY_CHARS
    )
    out: list[tuple[str, int, str, str]] = []
    for char, count in sorted(counter.items(), key=lambda kv: ord(kv[0])):
        code = ord(char)
        try:
            name = unicodedata.name(char)
        except ValueError:
            name = ZERO_WIDTH_CHARS.get(code, "?")
        if code in ZERO_WIDTH_CHARS:
            note = "zerowa szerokość"
        elif char in HOMOGLYPHS:
            note = f'wygląda jak "{HOMOGLYPHS[char]}"'
        else:
            note = "typografia spoza ASCII (nie homoglif)"
        out.append((f"U+{code:04X}", count, name, note))
    return out


def named_entities(src: str) -> list[tuple[str, int]]:
    """Nazwane encje HTML użyte w treści, z liczbą wystąpień.

    Sekcja sprawdzała wyłącznie encje numeryczne i orzekała ich brak — a w pliku
    było sześć encji nazwanych, w tym `&oacute;` obok tego samego znaku zapisanego
    surowym UTF-8.

    >>> named_entities("&nbsp;tekst&oacute;&oacute;&hellip;")
    [('&oacute;', 2), ('&nbsp;', 1), ('&hellip;', 1)]
    >>> named_entities("bez encji")
    []
    """
    return collections.Counter(
        re.findall(r"&[a-zA-Z][a-zA-Z0-9]{1,31};", src)
    ).most_common()


def mixed_character_encodings(src: str) -> list[tuple[str, str, int, int]]:
    """Znaki zapisane w tym samym dokumencie dwoma sposobami: encją i wprost.

    Dwa zapisy tego samego znaku to obserwowalna niespójność kodowania,
    a raport widział tylko jedną z tych postaci.

    >>> mixed_character_encodings("kt&oacute;ry i który")
    [('ó', '&oacute;', 1, 1)]
    >>> mixed_character_encodings("&nbsp; sam")
    []

    Cudzysłów ograniczający atrybut nie jest znakiem treści:

    >>> mixed_character_encodings('<div dir="ltr">&quot;cytat&quot;</div>')
    []

    Encje **numeryczne** liczą się tak samo jak nazwane:

    >>> mixed_character_encodings("Maj&#99;hrowicz i c")
    [('c', '&#99;', 1, 2)]
    """
    # Znaki wprost liczymy w tekście, nie w znacznikach: cudzysłowy ograniczające
    # atrybut `dir="ltr"` były zliczane jako „ten sam znak zapisany wprost”,
    # co dawało niespójność kodowania tam, gdzie jej nie ma.
    text_only = re.sub(r"<[^>]*>", "", strip_style_and_script(src))
    # `&` rozpoczynające encję nie jest tym samym znakiem „zapisanym wprost” —
    # liczenie go po obu stronach dawało tabelę niespójności tam, gdzie
    # wszystkie ampersandy otwierają encje.
    text_only = re.sub(r"&[a-zA-Z][a-zA-Z0-9]{1,31};|&#\d+;", " ", text_only)
    out: list[tuple[str, str, int, int]] = []
    # Encje numeryczne (`&#99;`) są tym samym zjawiskiem co nazwane. Sprawdzanie
    # wyłącznie nazwanych dawało ustalenie negatywne w wiadomości, w której
    # dokładnie ten mechanizm rozbijał nazwisko na `Maj&#99;hrowicz` — jedno `c`
    # jako encja, drugie wprost, w tym samym wyrazie.
    for entity, count in list(named_entities(src)) + list(numeric_entities(src)):
        decoded = html.unescape(entity)
        if len(decoded) != 1 or decoded == entity:
            continue
        literal = text_only.count(decoded)
        if literal:
            out.append((decoded, entity, count, literal))
    return out


def glued_tag_boundaries(src: str) -> list[str]:
    """Miejsca, w których tekst przechodzi przez granicę znaczników bez separatora.

    Detektor pytał o znacznik **wewnątrz** wyrazu; tu wyraz powstaje ze sklejenia
    dwóch sąsiednich elementów (`…będą</span><strong>zawieszone…`). Sekcja
    drukowała ustalenie negatywne dla zjawiska, którego artefakt raport
    reprodukował dosłownie w sekcji treści.

    >>> glued_tag_boundaries("<span>bedą</span><strong>zawieszone</strong>")
    ['bedą</span><strong>zawieszone']
    >>> glued_tag_boundaries("<span>slowo </span><strong>drugie</strong>")
    []
    >>> glued_tag_boundaries("<p>akapit</p><p>drugi</p>")
    []
    >>> glued_tag_boundaries("<strong>630041</strong> <strong>17</strong>")
    []
    >>> glued_tag_boundaries("zwykly tekst")
    []
    """
    # Znaczniki blokowe wprowadzają własny odstęp przy renderowaniu — sklejenie
    # dotyczy wyłącznie elementów liniowych.
    inline = r"span|strong|b|i|em|u|font|a|small|sup|sub|mark"
    # BEZ `\s*` między znacznikami: `630041</strong> <strong>17` ma spację, więc
    # wyrazy się nie sklejają — dopuszczanie białych znaków dawało fałszywy pozytyw.
    # Wariant `w<span>w</span>w` (znacznik wewnątrz wyrazu) łapie osobna funkcja
    # `find_word_splitting_spans`; tutaj chodzi o granicę DWÓCH sąsiednich elementów.
    pattern = re.compile(
        rf"(\w{{1,20}})</(?:{inline})><(?:{inline})\b[^>]*>(\w{{1,20}})",
        re.IGNORECASE,
    )
    return [match.group(0) for match in pattern.finditer(src)]


def document_metadata(src: str) -> list[tuple[str, str]]:
    """Metadane dokumentu HTML: tytuł i deklaracje języka.

    `<title>` był wycinany razem z `<head>` przed analizą treści i nie czytała
    go żadna sekcja — mimo że bywa trzecią, inną nazwą produktu w pliku.
    Atrybut `lang` nie występował w raportach ani razu.

    >>> document_metadata('<title>Kod weryfikacyjny</title><html lang="en">')
    [('<title>', 'Kod weryfikacyjny'), ('lang w <html>', 'en')]
    >>> document_metadata('<span lang="DE">Dzień dobry</span>')
    [('lang w elementach', 'DE (1×)')]
    >>> document_metadata("bez metadanych")
    []
    """
    out: list[tuple[str, str]] = []
    tytul = re.search(r"<title\b[^>]*>(.*?)</title>", src, re.DOTALL | re.IGNORECASE)
    if tytul:
        out.append(
            ("<title>", re.sub(r"\s+", " ", html.unescape(tytul.group(1))).strip())
        )

    html_tag = re.search(r"<html\b([^>]*)>", src, re.IGNORECASE)
    if html_tag:
        jezyk = _attr(html_tag.group(1), "lang")
        if jezyk:
            out.append(("lang w <html>", jezyk))

    pozostale = collections.Counter(
        m.group(1)
        for m in re.finditer(
            r"<(?!html)[a-z]+\b[^>]*\blang\s*=\s*[\"']([^\"']+)", src, re.IGNORECASE
        )
    )
    for jezyk, count in pozostale.most_common():
        out.append(("lang w elementach", f"{jezyk} ({count}×)"))
    return out


def html_document_structure(src: str) -> list[tuple[str, str]]:
    """Obecność znaczników strukturalnych dokumentu HTML i ich kolejność.

    Dokument bez `<html>`, `<head>` i `<body>`, w którym `<meta>` i `<style>`
    stoją po pierwszych akapitach, to obserwowalna cecha sposobu wytworzenia —
    raport nie miał sekcji, która by ją zapisywała.

    >>> html_document_structure("<!DOCTYPE html><html><head></head><body><p>x</p></body></html>")
    [('<!DOCTYPE>', 'obecny'), ('<html>', 'obecny'), ('<head>', 'obecny'), ('<body>', 'obecny')]
    >>> html_document_structure("<p>tekst</p><meta charset='utf-8'><style>p{}</style>")
    [('<!DOCTYPE>', 'brak'), ('<html>', 'brak'), ('<head>', 'brak'), ('<body>', 'brak'), ('<meta> / <style>', 'poza <head>, po pierwszej treści')]
    >>> html_document_structure("")
    []
    """
    if not src.strip():
        return []
    out: list[tuple[str, str]] = []
    for label, pattern in (
        ("<!DOCTYPE>", r"<!DOCTYPE\b"),
        ("<html>", r"<html\b"),
        ("<head>", r"<head\b"),
        ("<body>", r"<body\b"),
    ):
        out.append(
            (label, "obecny" if re.search(pattern, src, re.IGNORECASE) else "brak")
        )

    has_head = re.search(r"<head\b", src, re.IGNORECASE)
    head_like = re.search(r"<(?:meta|style|title)\b", src, re.IGNORECASE)
    first_text = re.search(r"<(?:p|div|table|h[1-6])\b", src, re.IGNORECASE)
    if (
        not has_head
        and head_like
        and first_text
        and head_like.start() > first_text.start()
    ):
        out.append(("<meta> / <style>", "poza <head>, po pierwszej treści"))
    return out


def numeric_entities(src: str) -> list[tuple[str, int]]:
    """Numeryczne encje HTML użyte zamiast liter, posortowane po liczbie wystąpień.

    >>> numeric_entities("&#107;&#107;&#111;")
    [('&#107;', 2), ('&#111;', 1)]
    >>> numeric_entities("zwykly tekst")
    []
    """
    return collections.Counter(re.findall(r"&#\d+;", src)).most_common()


# ──────────────────────────── tokeny ────────────────────────────


def _sendgrid_unescape(value: str) -> str:
    """Odwraca escaping SendGrida w parametrze `upn=` (`-2B`→`+`, `-2F`→`/`, `-3D`→`=`).

    >>> _sendgrid_unescape("u001.abc-2Bdef-3D")
    'u001.abc+def='
    >>> _sendgrid_unescape("bez escapowania")
    'bez escapowania'
    """
    for escaped, plain in (("-2B", "+"), ("-2F", "/"), ("-3D", "="), ("-5F", "_")):
        value = value.replace(escaped, plain)
    return value


def _try_base64(raw: str) -> tuple[bytes | None, str]:
    """Próbuje zdekodować ciąg jako base64 albo base64url; zwraca (bajty, wariant).

    >>> _try_base64("amFuIGtvd2Fsc2tp")[0]
    b'jan kowalski'
    >>> _try_base64("YWJjZGVm")[1]
    'base64'
    >>> _try_base64("nie-jest!")[0] is None
    True
    """
    candidate = raw.strip()
    if len(candidate) < 8 or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", candidate):
        return None, ""
    # Alfabety base64 i base64url wykluczają się wzajemnie (RFC 4648 §4–5).
    # Ciąg z `+` **i** `_` — jak lokalna część adresu VERP
    # `newsletter+bounce_6a75…` — nie jest żadnym z nich; oznaczanie go jako
    # base64url produkowało wiersz dowodowy z wymyślonymi „30 B” danych.
    standard = bool(re.search(r"[+/]", candidate))
    url_safe = bool(re.search(r"[-_]", candidate))
    if standard and url_safe:
        return None, ""
    variant = "base64url" if url_safe else "base64"
    normalized = candidate.replace("-", "+").replace("_", "/").rstrip("=")
    for padding in ("", "=", "=="):
        padded = normalized + padding
        if len(padded) % 4:
            continue
        try:
            return base64.b64decode(padded, validate=True), variant
        except (binascii.Error, ValueError):
            continue
    return None, ""


UUID_RE = re.compile(
    r"\A([0-9a-f]{8})-([0-9a-f]{4})-([1-8])([0-9a-f]{3})-([89ab])([0-9a-f]{3})-([0-9a-f]{12})\Z",
    re.IGNORECASE,
)

#: Kształt 8-4-4-4-12 bez poprawnego pola wariantu — losowy hex, nie UUID.
HEX_GROUPS_RE = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.IGNORECASE
)


#: Kształt UUID-a 8-4-4-4-12. Skaner powtórzeń musi rozpoznać go w całości,
#: zanim rozetnie ciąg na myślnikach — inaczej jeden identyfikator wchodzi do
#: tabeli jako cztery niezależne pozycje, z których żadna nie jest identyfikatorem.
UUID_PATTERN = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"


def describe_uuid(value: str) -> str | None:
    """Opis identyfikatora UUID: wersja, a dla wersji 1 — czas i adres węzła.

    Segment ścieżki w formacie UUID nie jest tokenem base64; opisany jako
    „dane binarne, 27 B" był szumem zamiast faktu. UUID wersji 1 niesie
    znacznik czasu i adres sprzętowy węzła, który go wygenerował.

    >>> describe_uuid("7038b650-63af-11f0-ab4f-40a6b73c97e4")
    'UUID wersja 1, znacznik czasu 2025-07-18 08:16:00 UTC, węzeł 40:a6:b7:3c:97:e4'
    >>> describe_uuid("9d1821a1-bdae-4c7b-9196-e7f1bf4deebd")
    'UUID wersja 4'
    >>> describe_uuid("nie-uuid") is None
    True

    Kształt 8-4-4-4-12 bez poprawnego pola wariantu (`8`/`9`/`a`/`b`) to nie UUID.
    Czytanie samego pola wersji dawało trzem jednorodnym identyfikatorom obrazów
    trzy różne „wersje UUID”, a czwartemu — zupełnie inną klasę:

    >>> describe_uuid("6d0bb530-a3dc-826c-4d83-0b039daab294")
    'hex w formacie 8-4-4-4-12 (pole wariantu spoza RFC 4122 — nie UUID)'
    >>> describe_uuid("df7620c0-09a6-7fea-7188-58299f973a0b")
    'hex w formacie 8-4-4-4-12 (pole wariantu spoza RFC 4122 — nie UUID)'

    Gdy wariant jest poprawny, a poza zakresem stoi pole wersji, uzasadnienie
    musi wskazać właściwe pole:

    >>> describe_uuid("7d20815d-6c66-c3e1-8e55-3896f9864c45")
    'hex w formacie 8-4-4-4-12 (pole wersji `c` spoza zakresu 1–8 — nie UUID)'
    """
    match = UUID_RE.match(value)
    if not match:
        shape = HEX_GROUPS_RE.match(value)
        if not shape:
            return None
        # Rozróżniamy, KTÓRE pole jest niepoprawne — wcześniej każdy przypadek
        # dostawał uzasadnienie „pole wariantu”, także gdy wariant był w porządku,
        # a poza zakresem stało pole wersji.
        version_ok = value[14].lower() in "12345678"
        variant_ok = value[19].lower() in "89ab"
        if version_ok and not variant_ok:
            reason = "pole wariantu spoza RFC 4122"
        elif variant_ok and not version_ok:
            reason = f"pole wersji `{value[14]}` spoza zakresu 1–8"
        else:
            reason = "pola wersji i wariantu spoza RFC 4122"
        return f"hex w formacie 8-4-4-4-12 ({reason} — nie UUID)"
    version = int(match.group(3))
    if version != 1:
        return f"UUID wersja {version}"
    # RFC 4122 §4.1.2: 60-bitowy licznik 100-nanosekundowych interwałów od 1582-10-15.
    ticks = int(match.group(4) + match.group(2) + match.group(1), 16)
    seconds = ticks / 1e7 - 12219292800
    moment = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    node = match.group(7)
    mac = ":".join(node[i : i + 2] for i in range(0, 12, 2))
    return (
        f"UUID wersja 1, znacznik czasu {moment.strftime('%Y-%m-%d %H:%M:%S')} UTC, "
        f"węzeł {mac}"
    )


def _looks_like_word(value: str) -> bool:
    """Czy ciąg to zwykłe słowo ze ścieżki, a nie token.

    `unsubscribe` dekoduje się formalnie jako base64 do 8 bajtów śmieci —
    wpisanie tego do tabeli tokenów zaszumia dowód wpisami bez treści.

    >>> _looks_like_word("unsubscribe")
    True
    >>> _looks_like_word("polityka-prywatnosci")
    True
    >>> _looks_like_word("openai-logo-email-header-2")
    True
    >>> _looks_like_word("YTo1OntzOjY6InNvdXJjZSI7")
    False
    >>> _looks_like_word("6a75d83a7b8c0129001949")
    False
    """
    return bool(re.fullmatch(r"[a-z]+(?:[-_][a-z0-9]+)*", value))


#: Kształty identyfikatorów, które wyglądają jak base64, ale nim nie są.
#: Każdy z nich trafił do tabeli dowodowej z wymyślonym „po zdekodowaniu”.
NIE_TOKENY = (
    (
        r"\AE?[0-9A-Za-z]{6,7}-[0-9A-Za-z]{10,12}-[0-9A-Za-z]{2,4}\Z",
        "identyfikator kolejki Exima",
    ),
    (
        r"\A[A-Za-z][A-Za-z]+(?:_[A-Za-z0-9]+)*_\d+(?:_\d+)+\Z",
        "nazwa i wersja programu",
    ),
    (r"\A[A-Z]{2,}_[a-z]{2,}_[a-z]{2,}\d*\Z", "nazwa kampanii"),
    (r"\A\d+\Z", "liczba dziesiętna"),
)


def falszywy_ksztalt(value: str) -> str | None:
    """Rozpoznaje ciągi, które mieszczą się w alfabecie base64, ale nim nie są.

    Sam fakt, że ciąg da się przepuścić przez dekoder, nie jest dowodem, że
    cokolwiek koduje. `Smart_Send_3_1_6`, `RZEM_tot_wzn19` i identyfikator
    kolejki Exima dostawały w raporcie wiersz z sumą SHA-256 policzoną
    z przypadkowo zdekodowanych śmieci.

    >>> falszywy_ksztalt("E1wzgyG-00000002Ly9-309c")
    'identyfikator kolejki Exima'
    >>> falszywy_ksztalt("Smart_Send_3_1_6")
    'nazwa i wersja programu'
    >>> falszywy_ksztalt("RZEM_tot_wzn19")
    'nazwa kampanii'
    >>> falszywy_ksztalt("7363754514882711723180")
    'liczba dziesiętna'
    >>> falszywy_ksztalt("YTo1OntzOjY6InNvdXJjZSI7") is None
    True
    """
    for pattern, description in NIE_TOKENY:
        if re.fullmatch(pattern, value):
            return description
    return None


def _plausible_opaque_token(value: str) -> bool:
    """Czy ciąg dekodujący się do danych binarnych wygląda na token, a nie na nazwę.

    Dekoder base64 przyjmie każdy ciąg o właściwej długości — `ExternalDevices`
    i `openai-logo-email-header-2` „zdekodowały się” do szumu, a raport nadawał
    im SHA-256, czyli rangę materiału dowodowego. Dla wyniku nieczytelnego
    wymagamy więc cech zapisu maszynowego: mieszanej wielkości liter **i** cyfry.

    >>> _plausible_opaque_token("kf0LaY8LJ9ceWLx7YbKumw")
    True
    >>> _plausible_opaque_token("ExternalDevices")
    False
    >>> _plausible_opaque_token("Newsletter")
    False
    >>> _plausible_opaque_token("YTo1OntzOjY2Iu==")
    True
    """
    if "=" in value or "+" in value or "/" in value:
        return True
    has_upper = any(c.isupper() for c in value)
    has_lower = any(c.islower() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_upper and has_lower and has_digit


def _as_text(data: bytes) -> str | None:
    """Zwraca tekst, jeśli bajty są czytelne; inaczej None (dane binarne).

    >>> _as_text(b"jan kowalski")
    'jan kowalski'
    >>> _as_text(b"adres@przyklad.pl\\n")
    'adres@przyklad.pl\\n'
    >>> _as_text(b"\\x00\\x01\\x02\\xff") is None
    True
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in text) / len(text)
    if printable > 0.9 and re.search(r"[A-Za-z0-9]", text):
        return text
    return None


def _digest_of(data: bytes) -> str:
    """Skrót SHA-256 (12 znaków) tego, co faktycznie zostało zdekodowane.

    Kolumna „po zdekodowaniu” podawała wcześniej skrót **surowego ciągu ASCII**,
    czyli opisywała inną wartość niż etykieta obok niej.

    >>> _digest_of(b"abc")
    'ba7816bf8f01'
    >>> _digest_of(b"")
    'e3b0c44298fc'
    """
    return hashlib.sha256(data).hexdigest()[:12]


def _token_candidates(src: str) -> list[tuple[str, str]]:
    """Kandydaci na token wraz z opisem miejsca, w którym stoją.

    Poprzednia wersja patrzyła wyłącznie na query-string. Identyfikatory bywają
    w ścieżce (`/r/hBngrJl9N9/8ak6/28130/`), w nazwie pliku (`so41634_KEY.gif`)
    i w nagłówkach (`X-AliDM-Trace`) — pomijanie ich dawało „nie wykryto tokenów”
    przy wiadomościach naszpikowanych identyfikatorami.

    >>> sorted({place for _, place in _token_candidates("https://a.pl/r?t=YWJjZGVmZ2g=")})
    ['parametr t=']
    >>> [tok for tok, place in _token_candidates("https://a.pl/YWJjZGVmZ2hpams/x")]
    ['YWJjZGVmZ2hpams']

    Query bez klucza (`?bWF0ZWU=`) jest kandydatem w całości — samo `=` w środku
    to padding base64, nie separator klucza:

    >>> _token_candidates("https://a.pl/?bWF0ZWVhY2Q")
    [('bWF0ZWVhY2Q', 'query bez klucza')]

    Rozszerzenie pliku nie jest częścią tokenu:

    >>> _token_candidates("https://a.pl/e/6a75d83a7b8c0129001949.gif")
    [('6a75d83a7b8c0129001949', 'segment ścieżki w a.pl')]
    """
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(value: str, place: str) -> None:
        value = value.strip()
        # Krótsze ciągi to prawie zawsze słowa ze ścieżki (`/email/`, `/gif`), nie tokeny.
        if len(value) < 8 or (value, place) in seen:
            return
        seen.add((value, place))
        out.append((value, place))

    for match in re.finditer(r"https?://[^\s\"'<>)]+", src):
        url = match.group(0).rstrip(".,;")
        parsed = urllib.parse.urlparse(url)
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        for key, value in pairs:
            add(value, f"parametr {key}=")
            if key.lower() == "upn":
                add(_sendgrid_unescape(value), f"parametr {key}= (po odescapowaniu)")
        if parsed.query and not any(len(v) >= 8 for _, v in pairs):
            # `?bWF0ZWU=` — cały query bywa tokenem, a `=` w środku to padding
            # base64, nie separator klucza od wartości. `parse_qsl` rozcina to
            # w złym miejscu, więc pełny ciąg dokładamy jako osobnego kandydata.
            add(parsed.query, "query bez klucza")
        for segment in parsed.path.split("/"):
            if not segment:
                continue
            stem = segment.rsplit(".", 1)[0] if "." in segment else segment
            add(stem, f"segment ścieżki w {parsed.netloc}")
    return out


def _alphabet_of(candidate: str) -> str:
    """Nazwa alfabetu, w którym zapisany jest ciąg — fakt odczytany, nie przypisany.

    >>> _alphabet_of("abc123")
    'alfanumeryczny ASCII'
    >>> _alphabet_of("ab-c_1")
    'base64url (z `-` i `_`)'
    >>> _alphabet_of("ab+c/1")
    'base64 (z `+` i `/`)'
    """
    if "-" in candidate or "_" in candidate:
        return "base64url (z `-` i `_`)"
    if "+" in candidate or "/" in candidate:
        return "base64 (z `+` i `/`)"
    return "alfanumeryczny ASCII"


def _shape_token(source_label: str, place: str, candidate: str, variant: str) -> Token:
    """Token bez ustalonego kodowania — opisany kształtem zamiast zmyśloną zawartością.

    Ciąg zapisany alfabetem base64, ale bez wypełnienia `=`, nie jest dowodem
    na to, że coś w nim zakodowano: identyfikator Gmaila i numer zgłoszenia
    z UUID-em wyglądają tak samo. Wymuszone dekodowanie dawało „dane binarne,
    34 B” i sha256 z przypadkowych bajtów — liczbę bez wartości dowodowej,
    podaną w kolumnie „Po zdekodowaniu” jak ustalenie.

    >>> t = _shape_token("treść", "parametr q=", "CAHYL8ScaKb5hjAuJ1yW", "base64")
    >>> t.encoding
    'nie ustalono — kształt: 20 znaków, alfabet alfanumeryczny ASCII'
    >>> t.decoded_text is None, t.byte_length
    (True, 0)
    >>> "bez wypełnienia" in t.note
    True
    """
    return Token(
        source=f"{source_label}: {place}",
        raw=candidate,
        encoding=(
            f"nie ustalono — kształt: {len(candidate)} znaków, "
            f"alfabet {_alphabet_of(candidate)}"
        ),
        decoded_text=None,
        byte_length=0,
        sha256_prefix=_digest_of(candidate.encode()),
        note=(
            "nie zdekodowano — ciąg mieści się w alfabecie base64, ale jest "
            "bez wypełnienia `=`, więc plik nie ustala, że cokolwiek w nim "
            "zakodowano; skrót policzono z samego ciągu"
        ),
    )


def decode_tokens(src: str, source_label: str = "treść") -> list[Token]:
    """Tokeny zakodowane (base64/base64url/hex) znalezione w URL-ach danego tekstu.

    Wynik nieczytelny nie jest odrzucany — „token istnieje, dekoduje się do 16
    bajtów binarnych" to inny fakt niż „tokenu nie ma”.

    >>> toks = decode_tokens("https://a.pl/r?t=amFuIGtvd2Fsc2tp")
    >>> toks[0].decoded_text, toks[0].encoding
    ('jan kowalski', 'base64')
    >>> decode_tokens("https://a.pl/sciezka")
    []
    >>> decode_tokens("zaden url")
    []

    Końcowy znak nowej linii zostaje w wyniku — jest cechą sposobu wytworzenia
    tokenu, a ciche znormalizowanie go usuwało ślad z materiału:

    >>> decode_tokens("https://a.pl/?a2xpZW50YWNkQHByenlrbGFkLnBsCg==")[0].decoded_text
    'klientacd@przyklad.pl\\n'

    Token szesnastkowy jest odnotowany, choć nie jest base64:

    >>> t = decode_tokens("https://a.pl/email/6a75d83a7b8c0129001949.gif")[0]
    >>> t.encoding, t.byte_length
    ('hex (11 B)', 11)
    """
    out: list[Token] = []
    seen: set[str] = set()
    for raw, place in _token_candidates(src):
        candidate = raw.strip()
        if len(candidate) < 8 or candidate in seen or _looks_like_word(candidate):
            continue

        uuid_note = describe_uuid(candidate)
        if uuid_note:
            seen.add(candidate)
            out.append(
                Token(
                    source=f"{source_label}: {place}",
                    raw=candidate,
                    encoding="UUID"
                    if uuid_note.startswith("UUID")
                    else "hex 8-4-4-4-12",
                    decoded_text=None,
                    note=uuid_note,
                    byte_length=16,
                    sha256_prefix=_digest_of(bytes.fromhex(candidate.replace("-", ""))),
                )
            )
            continue

        # Każda cyfra dziesiętna jest legalną cyfrą hex, więc licznik dziesiętny
        # przechodził jako „hex (11 B)”. Wymagamy przynajmniej jednej litery a–f.
        if re.fullmatch(r"[0-9a-fA-F]{16,}", candidate) and re.search(
            r"[a-fA-F]", candidate
        ):
            seen.add(candidate)
            # Nieparzysta długość nie przekłada się na całkowitą liczbę bajtów,
            # ale ciąg nadal jest identyfikatorem — pomijanie go gubiło m.in.
            # 25-znakowe identyfikatory kont u dostawców CDN.
            if len(candidate) % 2 == 0:
                data = bytes.fromhex(candidate)
                out.append(
                    Token(
                        source=f"{source_label}: {place}",
                        raw=candidate,
                        encoding=f"hex ({len(data)} B)",
                        decoded_text=_as_text(data),
                        byte_length=len(data),
                        sha256_prefix=_digest_of(data),
                    )
                )
            else:
                out.append(
                    Token(
                        source=f"{source_label}: {place}",
                        raw=candidate,
                        encoding=f"hex ({len(candidate)} znaków, długość nieparzysta)",
                        decoded_text=None,
                        note=(
                            "nie zdekodowano — nieparzysta liczba znaków hex "
                            "nie przekłada się na całkowitą liczbę bajtów; "
                            "skrót policzono z samego ciągu"
                        ),
                        byte_length=0,
                        sha256_prefix=_digest_of(candidate.encode()),
                    )
                )
            continue

        if falszywy_ksztalt(candidate):
            continue
        data, variant = _try_base64(candidate)
        if data is None:
            continue
        text = _as_text(data)
        if text is None and (len(data) < 8 or not _plausible_opaque_token(candidate)):
            continue
        seen.add(candidate)
        if text is None and "=" not in candidate:
            # Bez wypełnienia `=` nic w pliku nie mówi, że ten ciąg JEST base64 —
            # alfabet sam z siebie tego nie ustala. Identyfikator Gmaila i numer
            # zgłoszenia z UUID-em przechodziły przez wymuszone dekodowanie, po
            # czym raport publikował sha256 z przypadkowych bajtów jako ustalenie.
            # Podajemy kształt, który jest faktem, zamiast wyniku, który nim nie jest.
            out.append(_shape_token(source_label, place, candidate, variant))
            continue
        out.append(
            Token(
                source=f"{source_label}: {place}",
                raw=candidate,
                encoding=variant,
                decoded_text=text,
                byte_length=len(data),
                sha256_prefix=_digest_of(data),
                note=None if text is not None else "dane binarne",
            )
        )
    return out


def decode_header_tokens(msg: email.message.Message) -> list[Token]:
    """Tokeny zakodowane w wartościach nagłówków (poza URL-ami).

    `X-AliDM-Trace: eyJPcGVuVHJhY2UiOiIxIn0=` dekoduje się do konfiguracji
    śledzenia otwarć — nagłówek nie pojawił się w raporcie ani razu, mimo że
    sekcja „tokeny” deklarowała szukanie base64.

    >>> from email import message_from_string, policy
    >>> src = "X-AliDM-Trace: eyJPcGVuVHJhY2UiOiIxIn0=\\n\\nx"
    >>> toks = decode_header_tokens(message_from_string(src, policy=policy.default))
    >>> toks[0].source, toks[0].decoded_text
    ('nagłówek X-AliDM-Trace', '{"OpenTrace":"1"}')
    >>> decode_header_tokens(message_from_string("From: a@b.pl\\n\\nx", policy=policy.default))
    []

    Fragment składni URL-a nie jest tokenem — ogólny skaner wycinał
    `//googlerecenzja` z `https://googlerecenzja.pl` i podawał jako dowód:

    >>> src = "List-Unsubscribe: <https://googlerecenzja.pl?unsubscribe=YWJjZGVmZ2hpams=>\\n\\nx"
    >>> toks = decode_header_tokens(message_from_string(src, policy=policy.default))
    >>> [t.raw for t in toks]
    ['YWJjZGVmZ2hpams=']
    >>> toks[0].source
    'nagłówek List-Unsubscribe: parametr unsubscribe='
    """
    out: list[Token] = []
    for name, value in msg.items():
        text = str(value).strip()
        if name.lower() in {
            "dkim-signature",
            "arc-seal",
            "arc-message-signature",
            "received",
        }:
            continue
        # URL-e w nagłówku obsługuje skaner URL-owy — ogólny regex wycinał
        # z nich fragmenty składni (`//googlerecenzja`, `pl/email/unsubscribe/…`)
        # i wpisywał je do tabeli dowodowej jako „tokeny base64”, obok tokenów
        # prawdziwych. Poza tym gubił token z nazwą parametru (`?unsubscribe=…`).
        out.extend(decode_tokens(text, f"nagłówek {name}"))
        bez_url = re.sub(r"https?://\S+", " ", text)

        for candidate in re.findall(r"[A-Za-z0-9+/=_-]{16,}", bez_url):
            # Ścieżka hex istniała wyłącznie dla treści; identyfikator kolejki
            # w `In-Reply-To` (16 znaków hex) był w efekcie pomijany, mimo że
            # sekcja deklaruje szukanie hexa także w nagłówkach.
            if re.fullmatch(r"[0-9a-fA-F]{16,}", candidate) and len(candidate) % 2 == 0:
                data = bytes.fromhex(candidate)
                out.append(
                    Token(
                        source=f"nagłówek {name}",
                        raw=candidate,
                        encoding=f"hex ({len(data)} B)",
                        decoded_text=_as_text(data),
                        byte_length=len(data),
                        sha256_prefix=_digest_of(data),
                    )
                )
                continue
            # Ten sam filtr kształtów co dla treści — bez niego identyfikator
            # kolejki Exima z `Message-Id` wracał jako „base64url, 18 B”.
            if falszywy_ksztalt(candidate):
                continue
            data, variant = _try_base64(candidate)
            if data is None:
                continue
            decoded = _as_text(data)
            # Wynik nieczytelny też jest faktem — tokeny z `List-Unsubscribe`
            # i `Feedback-ID` dekodują się do bajtów binarnych i były pomijane.
            if decoded is None:
                if len(data) < 8 or not _plausible_opaque_token(candidate):
                    continue
            elif len(decoded) < 4 or decoded.strip() == candidate.strip():
                continue
            out.append(
                Token(
                    source=f"nagłówek {name}",
                    raw=candidate,
                    encoding=variant,
                    decoded_text=decoded,
                    byte_length=len(data),
                    sha256_prefix=_digest_of(data),
                )
            )

    seen: set[tuple[str, str]] = set()
    unikalne: list[Token] = []
    for token in out:
        key = (token.source, token.raw)
        if key not in seen:
            seen.add(key)
            unikalne.append(token)
    return unikalne


def decode_hop_tokens(hops: list["ReceivedHop"]) -> list[Token]:
    """Zakodowane wartości w polach nagłówka Received (HELO, identyfikator kolejki).

    `from NTU5MjcwMDQ` w skoku 1 to base64 numeru konta nadawczego u dostawcy,
    a nie nazwa hosta. Raport podawał surowy ciąg jako nazwę i go nie dekodował,
    mimo że sekcja tokenów deklarowała szukanie base64.

    >>> hop = ReceivedHop.parse("from NTU5MjcwMDQ by mta.example with HTTP id X", 1)
    >>> toks = decode_hop_tokens([hop])
    >>> toks[0].decoded_text, toks[0].source
    ('55927004', 'Received skok 1: HELO')
    >>> decode_hop_tokens([ReceivedHop.parse("from mta.przyklad.pl by b.pl", 1)])
    []
    """
    out: list[Token] = []
    for hop in hops:
        for value, label in ((hop.helo, "HELO"), (hop.queue_id, "id")):
            if not value or "." in value or _looks_like_word(value):
                continue
            data, variant = _try_base64(value)
            if data is None:
                continue
            text = _as_text(data)
            if text is None or len(text) < 4 or text == value:
                continue
            out.append(
                Token(
                    source=f"Received skok {hop.index}: {label}",
                    raw=value,
                    encoding=variant,
                    decoded_text=text,
                    byte_length=len(data),
                    sha256_prefix=hashlib.sha256(value.encode()).hexdigest()[:12],
                )
            )
    return out


def repeated_identifiers(
    values: dict[str, str],
    min_length: int = 8,
    seeds: tuple[str, ...] = (),
    seed_only: frozenset[str] = frozenset(),
    substring_seeds: tuple[str, ...] = (),
) -> list[tuple[str, list[str]]]:
    """Identyfikatory powtarzające się w więcej niż jednym miejscu wiadomości.

    Ten sam token w `Return-Path`, w linku wypisu, w pikselu i w polu `stat`
    tokenu CTA to dowód, że każdy kanał identyfikuje tego samego odbiorcę.
    Żaden z badanych raportów nie łączył tych wystąpień.

    >>> vals = {"Return-Path": "bounce_6a75d83a@x.pl", "piksel": "https://x.pl/6a75d83a.gif",
    ...         "inne": "nic"}
    >>> repeated_identifiers(vals)
    [('6a75d83a', ['Return-Path', 'piksel'])]
    >>> repeated_identifiers({"a": "krotkie", "b": "inne"})
    []

    Krótki identyfikator podany jako ziarno jest szukany mimo progu długości:

    >>> repeated_identifiers({"X-EMAIL-ID": "4494", "token": 'email";i:4494;'},
    ...                      seeds=("4494",))
    [('4494', ['X-EMAIL-ID', 'token'])]
    >>> repeated_identifiers({"a": "id 44941", "b": "inne"}, seeds=("4494",))
    []

    Źródło oznaczone jako `seed_only` nie jest skanowane ogólnym wzorcem —
    inaczej wartość `bh=` rozpadłaby się na przypadkowe fragmenty rozdzielone
    znakami `+` i `/`:

    >>> repeated_identifiers(
    ...     {"DKIM": "bh=aa/bb+cc=", "ARC": "bh=aa/bb+cc="},
    ...     seeds=("aa/bb+cc=",), seed_only=frozenset({"DKIM", "ARC"}))
    [('aa/bb+cc=', ['DKIM', 'ARC'])]

    UUID liczy się jako **jeden** identyfikator, nie cztery fragmenty:

    >>> u = "9d1821a1-bdae-4c7b-9196-e7f1bf4deebd"
    >>> repeated_identifiers({"Message-ID": u, "link": f"https://a.pl/?c={u}"})
    [('9d1821a1-bdae-4c7b-9196-e7f1bf4deebd', ['Message-ID', 'link'])]

    Etykieta domeny to nie identyfikator — nazwy opisuje inwentarz domen:

    >>> repeated_identifiers({"From": "a@newsletter.przyklad.pl",
    ...                       "Return-Path": "b@newsletter.przyklad.pl"})
    []

    Identyfikator z `List-Id` bywa wtopiony w VERP i w nazwę pliku piksela,
    więc szukamy go jako podciągu:

    >>> repeated_identifiers(
    ...     {"List-Id": "<41634.z.przyklad.pl>",
    ...      "Return-Path": "sare0416342-klient=odbiorca.pl@z.przyklad.pl",
    ...      "treść: img": "https://41634-2.n.przyklad.pl/so41634_9f.gif"},
    ...     substring_seeds=("41634",))
    [('41634', ['List-Id', 'Return-Path', 'treść: img'])]
    """
    tokens: dict[str, list[str]] = collections.OrderedDict()

    def note(found: str, label: str) -> None:
        tokens.setdefault(found, [])
        if label not in tokens[found]:
            tokens[found].append(label)

    for label, text in values.items():
        haystack = str(text or "")
        # Wartości podpisów są base64 z `+` i `/`, więc ogólny skaner tnie je na
        # przypadkowe fragmenty. Dla tych źródeł szukamy wyłącznie ziaren, czyli
        # całych wartości tagów wyciągniętych wcześniej.
        if label not in seed_only:
            # UUID najpierw i w całości. Skaner `[A-Za-z0-9]{8,}` rozcinał go na
            # myślnikach i wpisywał do tabeli cztery „niezależne identyfikatory”
            # zamiast jednego — a każdy fragment z osobna nie jest identyfikatorem.
            rest = haystack
            for uuid_match in re.finditer(UUID_PATTERN, haystack, re.IGNORECASE):
                note(uuid_match.group(0), label)
                rest = rest.replace(uuid_match.group(0), " ")
            for found in set(re.findall(rf"[A-Za-z0-9]{{{min_length},}}", rest)):
                # Etykieta domeny (`newsletter`, `marketing`, `powiadomienia`)
                # to nie identyfikator odbiorcy ani kampanii — powiązania między
                # nazwami opisuje inwentarz domen. Skaner wpisywał je do tabeli
                # korelatorów, gdzie zajmowały większość wierszy.
                if _looks_like_word(found.lower()) and found.lower() == found:
                    continue
                note(found, label)
        # Krótkie identyfikatory (np. `X-EMAIL-ID: 4494`) nie przejdą przez próg
        # długości, a to właśnie one wiążą nagłówek ze zdekodowanym ładunkiem
        # linku. Szukamy ich wprost, z granicą słowa, żeby nie łapać fragmentów.
        for seed in seeds:
            if seed and re.search(
                rf"(?<![A-Za-z0-9]){re.escape(seed)}(?![A-Za-z0-9])", haystack
            ):
                note(seed, label)
        # Identyfikatory zadeklarowane wprost przez nadawcę (`List-Id`,
        # `Feedback-ID`) bywają **wtopione** w dłuższe ciągi: w adres zwrotny
        # VERP, w nazwę pliku piksela, w nazwę hosta. Skaner szukający całych
        # tokenów nie widział ich ani razu, więc korelator spinający kopertę,
        # nagłówki listy i treść nie trafiał do sekcji, dla której istnieje.
        # Szukamy ich jako podciągu — wolno, bo pochodzą z deklaracji w pliku,
        # a nie z dowolnego dopasowania.
        for seed in substring_seeds:
            if seed and seed in haystack:
                note(seed, label)
    return [(tok, places) for tok, places in tokens.items() if len(places) > 1]


# ──────────────────────────── domeny ────────────────────────────


def collect_domains(
    msg: email.message.Message,
    hops: list[ReceivedHop],
    resources: list[HtmlResource],
    dkim: list[DkimSignature],
) -> list[DomainRef]:
    """Wszystkie domeny/hosty w wiadomości z etykietą roli, bez pomijania nagłówków.

    Poprzednia wersja liczyła wyłącznie `From`/`Reply-To`/`Return-Path` i hosty
    z linków HTTP — pomijając hosty z `Received`, `Message-ID`, `d=` podpisu DKIM
    i adresów `mailto:`, a licząc `www.w3.org` z deklaracji przestrzeni nazw.

    >>> from email import message_from_string, policy
    >>> src = ("From: a@nadawca.pl\\nReply-To: b@inna.pl\\n"
    ...        "Message-ID: <1@serwer.host.pl>\\n"
    ...        "Received: from mta.dostawca.pl by mx.odbiorca.pl with ESMTP\\n"
    ...        "DKIM-Signature: d=podpisujaca.pl; h=From;\\n\\nx")
    >>> msg = message_from_string(src, policy=policy.default)
    >>> refs = collect_domains(msg, extract_hops(msg), [], extract_dkim_signatures(msg))
    >>> sorted({r.domain for r in refs})
    ['inna.pl', 'mta.dostawca.pl', 'mx.odbiorca.pl', 'nadawca.pl', 'podpisujaca.pl', 'serwer.host.pl']
    >>> [r.role for r in refs if r.domain == 'podpisujaca.pl']
    ['DKIM d=']
    """
    out: list[DomainRef] = []
    seen: set[tuple[str, str]] = set()

    def add(domain: str | None, role: str) -> None:
        if not domain:
            return
        domain = domain.strip().strip("<>[]").rstrip(".").lower()
        if not domain or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
            return
        key = (domain, role)
        if key not in seen:
            seen.add(key)
            out.append(DomainRef(domain=domain, role=role))

    for name, addresses in extract_addresses(msg).items():
        for address in addresses:
            add(address.domain, name)

    for hop in hops:
        add(hop.helo, f"Received skok {hop.index} HELO")
        add(hop.rdns, f"Received skok {hop.index} rDNS")
        add(hop.by, f"Received skok {hop.index} by")

    message_id = msg.get("Message-ID") or msg.get("Message-Id")
    if message_id:
        match = re.search(r"@([A-Za-z0-9.-]+)>?\s*$", str(message_id).strip())
        if match:
            add(match.group(1), "Message-ID (część po @)")

    for signature in dkim:
        add(signature.domain, "DKIM d=")

    for header in msg.get_all("ARC-Seal") or []:
        seal = ArcSet.parse_seal(str(header))
        if seal:
            add(seal.domain, f"ARC-Seal i={seal.index} d=")

    for header in extract_auth_headers(msg):
        add(header.authserv_id, f"{header.name} (wystawca)")
        for method in header.methods:
            for key in ("smtp.mailfrom", "header.from", "header.d", "header.i"):
                if key in method.props:
                    add(
                        extract_domain(method.props[key]) or method.props[key], f"{key}"
                    )

    for name in (
        "List-Unsubscribe",
        "Feedback-ID",
        "X-Mail-From",
        "X-Return-Path",
        "X-Abuse",
    ):
        for value in msg.get_all(name) or []:
            for found in re.findall(r"https?://([A-Za-z0-9.-]+)", str(value)):
                add(found, f"{name} (URL)")
            for found in re.findall(r"@([A-Za-z0-9.-]+)", str(value)):
                add(found, f"{name} (adres)")

    for resource in resources:
        if resource.host:
            add(resource.host, f"treść: {resource.kind}")
        elif resource.scheme == "mailto":
            # `mailto:a@x.pl,%20b@y.pl?subject=…` — wszyscy adresaci, nie tylko
            # pierwszy; drugi adresat rezygnacji był widoczny w tabeli zasobów,
            # ale nie trafiał do inwentarza domen.
            for found in re.findall(
                r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})",
                urllib.parse.unquote(resource.url),
            ):
                add(found, "treść: mailto")

    return out


# ──────────────────────────── porównanie części ────────────────────────────


def rfc8058_compliance(msg: email.message.Message) -> str | None:
    """Sprawdza wymóg RFC 8058 §3: `List-Unsubscribe-Post` wymaga podpisu DKIM.

    Raport miał oba fakty w osobnych sekcjach („brak DKIM-Signature" i
    „zadeklarowana obsługa one-click") i nigdy ich nie zestawiał, mimo że
    to sprawdzalne, normatywne ustalenie o wiadomości.

    >>> from email import message_from_string, policy
    >>> src = ("List-Unsubscribe: <https://a.pl/u>\\n"
    ...        "List-Unsubscribe-Post: List-Unsubscribe=One-Click\\n\\nx")
    >>> rfc8058_compliance(message_from_string(src, policy=policy.default))
    'nagłówek obecny, brak podpisu DKIM w wiadomości'

    >>> src = ("List-Unsubscribe: <https://a.pl/u>\\n"
    ...        "List-Unsubscribe-Post: List-Unsubscribe=One-Click\\n"
    ...        "DKIM-Signature: v=1; d=a.pl; s=s; h=From:Subject; bh=AAAA\\n\\nx")
    >>> rfc8058_compliance(message_from_string(src, policy=policy.default))
    'nagłówek obecny, podpis DKIM nie obejmuje: List-Unsubscribe, List-Unsubscribe-Post'

    >>> src = ("List-Unsubscribe: <https://a.pl/u>\\n"
    ...        "List-Unsubscribe-Post: List-Unsubscribe=One-Click\\n"
    ...        "DKIM-Signature: v=1; d=a.pl; s=s; bh=AAAA; "
    ...        "h=From:List-Unsubscribe:List-Unsubscribe-Post\\n\\nx")
    >>> rfc8058_compliance(message_from_string(src, policy=policy.default))
    'nagłówek obecny, oba nagłówki listy objęte podpisem DKIM'

    >>> rfc8058_compliance(message_from_string("From: a@b.pl\\n\\nx", policy=policy.default)) is None
    True
    """
    if msg.get("List-Unsubscribe-Post") is None:
        return None
    signatures = extract_dkim_signatures(msg)
    if not signatures:
        return "nagłówek obecny, brak podpisu DKIM w wiadomości"
    signed = {h.lower() for sig in signatures for h in sig.signed_headers}
    required = ["List-Unsubscribe", "List-Unsubscribe-Post"]
    missing = [name for name in required if name.lower() not in signed]
    if missing:
        return "nagłówek obecny, podpis DKIM nie obejmuje: " + ", ".join(missing)
    return "nagłówek obecny, oba nagłówki listy objęte podpisem DKIM"


#: Rozwinięcia sufiksów protokołu z RFC 3848. `A` = sesja uwierzytelniona
#: (SMTP AUTH), `S` = połączenie szyfrowane TLS. Raport podawał surowy token
#: bez rozwinięcia, przez co najsilniejszy fakt atrybucyjny w pliku — że
#: nadawca zalogował się na konto pocztowe — nie był zapisany.
PROTOCOL_NOTES = {
    "ESMTPA": "ESMTP, sufiks `A` = sesja uwierzytelniona (SMTP AUTH), RFC 3848",
    "ESMTPSA": "ESMTP, sufiksy `S` = TLS i `A` = SMTP AUTH, RFC 3848",
    "ESMTPS": "ESMTP, sufiks `S` = połączenie szyfrowane TLS, RFC 3848",
    "ESMTP": "ESMTP, token bez sufiksów `S`/`A` (RFC 3848 definiuje je jako opcjonalne)",
    "SMTP": "SMTP, token bez rozszerzeń",
    "LMTPA": "LMTP + sesja uwierzytelniona",
    "LMTPSA": "LMTP + TLS + sesja uwierzytelniona",
    "UTF8SMTPA": "SMTPUTF8 + sesja uwierzytelniona",
    "UTF8SMTPSA": "SMTPUTF8 + TLS + sesja uwierzytelniona",
    "HTTP": "wstrzyknięcie przez API dostawcy, nie przez klienta SMTP",
}


def describe_protocol(protocol: str | None) -> str | None:
    """Rozwinięcie tokenu protokołu z klauzuli `with` nagłówka Received.

    >>> describe_protocol("ESMTPA")
    'ESMTP, sufiks `A` = sesja uwierzytelniona (SMTP AUTH), RFC 3848'
    >>> describe_protocol("HTTP")
    'wstrzyknięcie przez API dostawcy, nie przez klienta SMTP'
    >>> describe_protocol("Microsoft SMTP Server") is None
    True
    >>> describe_protocol(None) is None
    True
    """
    return PROTOCOL_NOTES.get((protocol or "").upper())


def invalid_hostnames(hops: list["ReceivedHop"]) -> list[tuple[str, str, str]]:
    """Nazwy hostów z nagłówków Received niezgodne ze składnią RFC 1035.

    `DESKTOP-QD51OAL..home` ma pustą etykietę DNS. Raport przepisywał tę nazwę
    trzykrotnie i ani razu nie odnotowywał anomalii, choć miał całą sekcję na
    konstrukcje nietypowe — tyle że wyłącznie dla HTML.

    >>> hop = ReceivedHop.parse("from DESKTOP-QD51OAL..home by mx.example with ESMTPA", 1)
    >>> invalid_hostnames([hop])
    [('Received skok 1 HELO', 'DESKTOP-QD51OAL..home', 'pusta etykieta DNS (dwie kropki pod rząd)')]
    >>> invalid_hostnames([ReceivedHop.parse("from mta.przyklad.pl by b.pl", 1)])
    []
    >>> hop = ReceivedHop.parse("from WIN7-02 by mx.example with SMTP", 1)
    >>> invalid_hostnames([hop])
    [('Received skok 1 HELO', 'WIN7-02', 'brak kropki — nazwa nie jest FQDN')]
    """
    out: list[tuple[str, str, str]] = []
    for hop in hops:
        for value, role in ((hop.helo, "HELO"), (hop.rdns, "rDNS")):
            if not value or value.startswith("["):
                continue
            if NetAddress.classify(value.strip("[]")) != "nie jest adresem IP":
                continue
            if value.lower() == "unknown":
                continue
            label = f"Received skok {hop.index} {role}"
            if ".." in value:
                out.append((label, value, "pusta etykieta DNS (dwie kropki pod rząd)"))
            elif "." not in value:
                out.append((label, value, "brak kropki — nazwa nie jest FQDN"))
            elif not re.fullmatch(r"[A-Za-z0-9._-]+", value):
                out.append(
                    (label, value, "znaki spoza zbioru dopuszczalnego w nazwie DNS")
                )
    return out


def message_id_parts(message_id: str | None) -> list[tuple[str, str]]:
    """Rozbiór części lokalnej Message-ID na rozpoznawalne składniki.

    `20260721113602.3AA011B7B5F` niesie znacznik czasu i identyfikator kolejki.
    Raport rozbijał Message-ID na część lokalną i domenową, po czym nie dekodował
    żadnej z nich.

    >>> message_id_parts("<20260721113602.3AA011B7B5F@serwer.example>")
    [('znacznik czasu YYYYMMDDHHMMSS', '20260721113602 → 2026-07-21 11:36:02')]
    >>> message_id_parts("<1786107962.abc@serwer.example>")
    [('epoka uniksowa', '1786107962 → 2026-08-07 13:06:02 UTC')]
    >>> message_id_parts("<zwykly-identyfikator@serwer.example>")
    []
    >>> message_id_parts(None)
    []
    """
    if not message_id:
        return []
    local = str(message_id).strip().strip("<>").rsplit("@", 1)[0]
    out: list[tuple[str, str]] = []
    stamp = re.search(
        r"(?<!\d)(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?!\d)", local
    )
    if stamp:
        year, month, day, hour, minute, second = stamp.groups()
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31 and int(hour) <= 23:
            out.append(
                (
                    "znacznik czasu YYYYMMDDHHMMSS",
                    f"{stamp.group(0)} → {year}-{month}-{day} {hour}:{minute}:{second}",
                )
            )
    if not out:
        epoch = re.search(r"(?<!\d)(1[6-9]\d{8})(?!\d)", local)
        if epoch:
            moment = datetime.datetime.fromtimestamp(
                int(epoch.group(1)), tz=datetime.timezone.utc
            )
            out.append(
                (
                    "epoka uniksowa",
                    f"{epoch.group(1)} → {moment.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                )
            )
    return out


def software_fingerprints(
    msg: email.message.Message, html_body: str | None
) -> list[tuple[str, str]]:
    """Ślady oprogramowania, które wiadomość wytworzyło — obecne i nieobecne.

    Nieobecność `X-Mailer` i `User-Agent` jest obserwacją tak samo jak ich wartość;
    tak samo format `boundary` i `<meta name="Generator">`. Raporty odnotowywały
    to sporadycznie i tylko w prozie sekcji 8.

    >>> from email import message_from_string, policy
    >>> src = 'X-Mailer: Sendy (https://sendy.co)\\nContent-Type: multipart/mixed; boundary="b1"\\n\\nx'
    >>> software_fingerprints(message_from_string(src, policy=policy.default), None)
    [('X-Mailer', 'Sendy (https://sendy.co)'), ('MIME boundary', 'b1'), ('User-Agent', '(nagłówek nieobecny)')]

    Boundary w formacie `email.generator._make_boundary()` z Pythona ma stałą
    postać (15 znaków `=`, cyfry, `==`) — odnotowujemy sam format, bez wniosku:

    >>> src = 'Content-Type: multipart/mixed; boundary="===============4403652449191023895=="\\n\\nx'
    >>> [v for k, v in software_fingerprints(message_from_string(src, policy=policy.default), None)
    ...  if k == "Format boundary"]
    ['15× "=" + 19 cyfr + "==" — postać generowana przez email.generator._make_boundary() (Python)']

    >>> src = 'From: a@b.pl\\n\\nx'
    >>> software_fingerprints(message_from_string(src, policy=policy.default), None)
    [('X-Mailer', '(nagłówek nieobecny)'), ('User-Agent', '(nagłówek nieobecny)')]

    >>> software_fingerprints(message_from_string(src, policy=policy.default),
    ...                       '<meta name="Generator" content="Cocoa HTML Writer">')[-1]
    ('meta Generator', 'Cocoa HTML Writer')

    Ślady z treści też się liczą — szablon i niepodstawione znaczniki merge
    identyfikują narzędzie równie jednoznacznie, co nagłówek `X-Mailer`:

    >>> tresc = "<!-- NAME: SELL PRODUCTS --><title>*|MC:SUBJECT|*</title>"
    >>> [v for k, v in software_fingerprints(
    ...     message_from_string(src, policy=policy.default), tresc)
    ...  if k in {"Nazwa szablonu", "Niepodstawiony znacznik merge"}]
    ['NAME: SELL PRODUCTS', '*|MC:SUBJECT|*']

    Wszystkie znaczniki merge, nie tylko pierwszy:

    >>> wiele = "<title>*|MC:SUBJECT|*</title><!--*|IF:MC_PREVIEW_TEXT|*--><!--*|END:IF|*-->"
    >>> [v for k, v in software_fingerprints(
    ...     message_from_string(src, policy=policy.default), wiele)
    ...  if k == "Niepodstawiony znacznik merge"]
    ['*|MC:SUBJECT|*, *|IF:MC_PREVIEW_TEXT|*, *|END:IF|*']
    """
    out: list[tuple[str, str]] = []
    for name in ("X-Mailer", "User-Agent", "X-Originating-Client", "X-MimeOLE"):
        value = msg.get(name)
        if value is not None:
            text = str(value).strip()
            out.append((name, text if text else "(nagłówek obecny, wartość pusta)"))

    boundary = msg.get_param("boundary")
    if boundary:
        out.append(("MIME boundary", str(boundary)))
        match = re.fullmatch(r"(={10,})(\d+)(==)", str(boundary))
        if match:
            out.append(
                (
                    "Format boundary",
                    (
                        f'{len(match.group(1))}× "=" + {len(match.group(2))} cyfr + "==" '
                        "— postać generowana przez email.generator._make_boundary() (Python)"
                    ),
                )
            )

    # Nagłówki własne dostawcy wysyłki. Sekcja sprawdzała wyłącznie `X-Mailer`
    # i `User-Agent`, więc dla wiadomości z czterema nagłówkami `X-sare*`
    # nazywającymi system wprost drukowała „brak śladów oprogramowania” —
    # ustalenie sprzeczne z zawartością pliku.
    for name in msg:
        if re.match(
            r"(?i)^x-(sare|sg|ses|campaign|mailer-|esp|sendgrid|mailgun)", name
        ):
            value = str(msg.get(name) or "").strip()
            if value and (name, value) not in out:
                out.append((name, value[:200]))

    # Format części lokalnej `Message-ID` bywa sygnaturą oprogramowania: `E`
    # + długi identyfikator to kolejka Exima, `----=_Part_N_M.epoch` w boundary
    # to JavaMail. Raport pokazywał obie wartości, ale ich nie nazywał.
    message_id = str(msg.get("Message-ID") or "")
    if re.search(r"<E[0-9A-Za-z]{6,}-[0-9A-Za-z]{8,}-[0-9A-Za-z]{2,4}@", message_id):
        out.append(("Format Message-ID", "identyfikator kolejki Exim (`E` + id sesji)"))
    if boundary and re.fullmatch(r"----=_Part_\d+_\d+\.\d{10,13}", str(boundary)):
        out.append(
            (
                "Format boundary",
                "`----=_Part_N_M.epoch-ms` — postać generowana przez JavaMail/Jakarta Mail",
            )
        )

    # Nazwa MTA bywa jedyną identyfikacją oprogramowania w pliku, a stała
    # wyłącznie w surowym cytacie sekcji o trasie.
    for raw in msg.get_all("Received") or []:
        mta = re.search(
            r"\((Exim|Postfix|Sendmail|qmail|OpenSMTPD|MailEnable)\b[^)]*\)", str(raw)
        )
        if mta:
            value = mta.group(0).strip("()")
            if ("MTA z nagłówka Received", value) not in out:
                out.append(("MTA z nagłówka Received", value))

    for name in ("X-Mailer", "User-Agent"):
        if msg.get(name) is None:
            out.append((name, "(nagłówek nieobecny)"))

    if html_body:
        meta = re.search(
            r'<meta[^>]+name=["\']Generator["\'][^>]+content=["\']([^"\']+)["\']',
            html_body,
            re.IGNORECASE,
        )
        if meta:
            out.append(("meta Generator", meta.group(1)))
        comment = re.search(
            r"<!--\s*(Created with [^>]{0,60}?)\s*-->", html_body, re.IGNORECASE
        )
        if comment:
            out.append(("Komentarz generatora", comment.group(1)))

        # Pozostałe znaczniki `<meta>` i przestrzenie nazw. Raport wyłapywał
        # `Cocoa HTML Writer`, a gubił `CocoaVersion`, `MSHTML` i deklaracje
        # `xmlns:v`/`xmlns:o` — czyli resztę odcisku tego samego środowiska.
        for pattern, label in (
            (
                r'<meta[^>]+name=["\']?CocoaVersion["\']?[^>]+content=["\']?([^"\'>]+)',
                "meta CocoaVersion",
            ),
            (r'<meta[^>]+content=["\']?(MSHTML [0-9.]+)', "meta GENERATOR (MSHTML)"),
            (r'xmlns:(?:v|o|w|x)\s*=\s*["\']?([^"\'\s>]+)', "Przestrzeń nazw XML"),
            (r'(font-family\s*:\s*Aptos[^;"\']*)', "Deklaracja kroju"),
        ):
            found = list(dict.fromkeys(re.findall(pattern, html_body, re.IGNORECASE)))
            if found:
                out.append((label, ", ".join(found[:6])))

        # Dark Reader wstrzykuje swoje atrybuty w przeglądarce, po stronie
        # odbiorcy strony. Ich obecność w WYSŁANYM HTML-u to ślad autorski,
        # nie transportowy — raport liczył je, nie mówiąc, czym są.
        darkreader = len(re.findall(r"data-darkreader|--darkreader-", html_body))
        if darkreader:
            out.append(
                (
                    "Atrybuty Dark Reader",
                    (
                        f"{darkreader} wystąpień — atrybuty wstrzykiwane przez "
                        f"rozszerzenie przeglądarki do DOM po stronie klienta, "
                        f"obecne w wysłanej treści"
                    ),
                )
            )

        # Ślady zostawione w samej treści. Sekcja czytała wyłącznie `X-Mailer`
        # i `User-Agent`, przez co przy wiadomości z komentarzami szablonu,
        # prefiksowanymi klasami CSS i hostem CDN kończyła się „pusto”, choć
        # inna sekcja te same bajty liczyła.
        for pattern, label in (
            (r"<!--\s*(NAME:\s*[^>]{0,60}?)\s*-->", "Nazwa szablonu"),
            (r"<!--\s*(BEGIN TEMPLATE[^>]{0,40}?)\s*-->", "Znacznik szablonu"),
            (r"(\*\|[A-Z_:]{2,30}\|\*)", "Niepodstawiony znacznik merge"),
            (r"<!--\s*(blockId:[0-9a-f-]{8,})", "Identyfikator bloku edytora"),
        ):
            # `findall`, nie `search` — raport podawał 1 z 3 znaczników merge.
            found = list(dict.fromkeys(re.findall(pattern, html_body, re.IGNORECASE)))
            if found:
                out.append((label, ", ".join(found)))

        # Ucinanie do 4 znaków i lowercase robiło z jednej rodziny `mcn*` trzy
        # nieistniejące (`mcni`, `mcnd`, `mcnt`), a z sześciu różnych klas
        # Gmaila — jedną `gmai`. Wielkość liter jest częścią dowodu.
        classes = collections.Counter(
            name
            for atrybut in re.findall(r"""class\s*=\s*["']([^"']+)""", html_body)
            for name in atrybut.split()
        )
        most_common = [(n, c) for n, c in classes.most_common(8) if c >= 2]
        if most_common:
            out.append(
                (
                    "Najczęstsze klasy CSS",
                    ", ".join(f"{n} ({c}×)" for n, c in most_common),
                )
            )
        # Artefakty rozszerzeń przeglądarki i edytorów WYSIWYG obecne w wysłanym
        # źródle to ustalenie o pochodzeniu HTML-a; 64 takie atrybuty w jednym
        # pliku nie zostały odnotowane ani razu.
        for pattern, label in (
            (r"data-darkreader-[a-z-]+", "Atrybuty DarkReader"),
            (r"--darkreader-[a-z-]+", "Zmienne CSS DarkReader"),
            (r"contenteditable\s*=", "Atrybut contenteditable (edytor WYSIWYG)"),
            (r"data-template-container", "Atrybut data-template-container"),
        ):
            count = len(re.findall(pattern, html_body, re.IGNORECASE))
            if count:
                out.append((label, f"{count} wystąpień"))
    return out


def compare_parts(html_body: str | None, text_body: str | None) -> dict[str, object]:
    """Porównuje część text/plain z text/html — zgodność treści i zbiór URL-i.

    W `multipart/alternative` rozjazd między wersjami jest odrębnym ustaleniem;
    jego brak też. Żaden z badanych raportów nie porównywał części.

    >>> res = compare_parts("<p>Oferta https://a.pl/x</p>", "Oferta https://a.pl/x")
    >>> res["urls_only_in_html"], res["urls_only_in_text"]
    ([], [])
    >>> res["text_similar"]
    True
    >>> res = compare_parts('<a href="https://a.pl/tylko-html">x</a>', "bez linku")
    >>> res["urls_only_in_html"]
    ['https://a.pl/tylko-html']
    >>> compare_parts(None, "tekst")["status"]
    'brak części text/html'
    >>> compare_parts("<p>x</p>", None)["status"]
    'brak części text/plain'

    Notacja `[URL]` z wersji tekstowej nie tworzy różnicy między częściami:

    >>> res = compare_parts('<a href="https://a.pl/x">t</a>', "tekst [https://a.pl/x]")
    >>> res["urls_only_in_html"], res["urls_only_in_text"]
    ([], [])

    Deklaracja przestrzeni nazw XML nie jest URL-em treści — inaczej ta sekcja
    przeczyłaby inwentarzowi domen, który ją wyklucza:

    >>> compare_parts('<html xmlns="http://www.w3.org/1999/xhtml">x</html>',
    ...               "x")["urls_only_in_html"]
    []
    """
    if html_body is None:
        return {"status": "brak części text/html"}
    if text_body is None:
        return {"status": "brak części text/plain"}

    def urls(text: str) -> set[str]:
        # Wersja tekstowa zapisuje adresy jako `[https://…]` — bez obcięcia
        # nawiasu ten sam URL trafiał do „wyłącznie w text/plain” i „wyłącznie
        # w text/html” jednocześnie. Deklaracje przestrzeni nazw XML wykluczamy
        # tak samo jak w inwentarzu domen — inaczej sekcje przeczą sobie nawzajem.
        found = set()
        for raw in re.findall(r"https?://[^\s\"'<>)\]]+", text):
            candidate = raw.rstrip(".,;:!?\"')]}>")
            host = urllib.parse.urlparse(candidate).hostname
            if host and host.lower() in BOILERPLATE_URL_HOSTS:
                continue
            found.add(candidate)
        return found

    html_urls = urls(html_body) | {
        r.url
        for r in extract_html_resources(html_body)
        if r.scheme in {"http", "https"}
    }
    text_urls = urls(text_body)

    def words(text: str) -> set[str]:
        return set(re.findall(r"\w{4,}", text.lower()))

    html_words = words(deobfuscate(html_body))
    text_words = words(text_body)
    overlap = len(html_words & text_words) / max(1, len(html_words | text_words))

    return {
        "status": "obie części obecne",
        "urls_only_in_html": sorted(html_urls - text_urls),
        "urls_only_in_text": sorted(text_urls - html_urls),
        "text_similar": overlap > 0.5,
        "word_overlap": round(overlap, 3),
        # Sama liczba nie mówi, CO się różni — a to właśnie tam chowa się tekst
        # widoczny tylko w jednej wersji wiadomości. Raport podawał `0.985`
        # i zostawiał czytelnika bez możliwości sprawdzenia, czego dotyczy reszta.
        "words_only_in_html": sorted(html_words - text_words),
        "words_only_in_text": sorted(text_words - html_words),
        "urls_total": len(html_urls | text_urls),
    }


# ──────────────────────────── identyfikatory rejestrowe ────────────────────────────


def _iban_valid(iban: str) -> bool:
    """Suma kontrolna IBAN wg ISO 13616 (mod-97 = 1).

    >>> _iban_valid("PL17109028510000000130176424")
    True
    >>> _iban_valid("PL17109028510000000130176425")
    False
    """
    chars = re.sub(r"\s", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", chars):
        return False
    rotated = chars[4:] + chars[:4]
    digits = "".join(str(ord(z) - 55) if z.isalpha() else z for z in rotated)
    return int(digits) % 97 == 1


def _nip_valid(nip: str) -> bool:
    """Suma kontrolna NIP — wagi 6,5,7,2,3,4,5,6,7 modulo 11.

    >>> _nip_valid("836-167-65-10")
    True
    >>> _nip_valid("836-167-65-11")
    False
    >>> _nip_valid("123")
    False
    """
    digits = re.sub(r"\D", "", nip)
    if len(digits) != 10:
        return False
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    total = sum(w * int(c) for w, c in zip(weights, digits))
    return total % 11 == int(digits[9])


def _regon_valid(regon: str) -> bool:
    """Suma kontrolna REGON dla 9 i 14 cyfr.

    >>> _regon_valid("123456785")
    True
    >>> _regon_valid("123456789")
    False
    """
    digits = re.sub(r"\D", "", regon)
    weights = {9: (8, 9, 2, 3, 4, 5, 6, 7), 14: (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)}
    if len(digits) not in weights:
        return False
    total = sum(w * int(c) for w, c in zip(weights[len(digits)], digits))
    return total % 11 % 10 == int(digits[-1])


def _nrb_valid(nrb: str) -> bool:
    """Suma kontrolna polskiego NRB — IBAN po dopisaniu kodu kraju `PL`.

    >>> _nrb_valid("17 1090 2851 0000 0001 3017 6424")
    True
    >>> _nrb_valid("17 1090 2851 0000 0001 3017 6425")
    False
    """
    digits = re.sub(r"\s", "", nrb)
    return len(digits) == 26 and digits.isdigit() and _iban_valid("PL" + digits)


#: Wzorce identyfikatorów rejestrowych i finansowych spotykanych w treści.
#: Każdy z nich leżał w raportach wyłącznie jako proza w zrzucie treści — dla
#: wiadomości wzywającej do przelewu numer rachunku nie był daną w żadnej tabeli.
REGISTRY_PATTERNS = (
    ("IBAN", r"\b([A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){4,7})\b", _iban_valid),
    # Polski NRB bywa zapisany bez prefiksu `PL` — dokładnie tak stoi w treści
    # wezwania do zapłaty. Wzorzec wymagający kodu kraju nie znajdował go wcale.
    ("NRB (bez kodu kraju)", r"(?<![\dA-Z])(\d{2}(?:[ ]\d{4}){6})(?![\d])", _nrb_valid),
    (
        "NIP",
        r"\bNIP[:\s]*([0-9]{3}[-\s]?[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{2})",
        _nip_valid,
    ),
    ("KRS", r"\bKRS[:\s]*([0-9]{10})\b", None),
    ("REGON", r"\bREGON[:\s]*([0-9]{9}|[0-9]{14})\b", _regon_valid),
    ("BDO", r"\bBDO[:\s]*([0-9]{6,9})\b", None),
)


def registry_identifiers(text: str) -> list[tuple[str, str, str]]:
    """Identyfikatory rejestrowe i finansowe z treści, z policzoną sumą kontrolną.

    Suma kontrolna to **obliczenie na danej z pliku**, nie ocena wiadomości —
    ta sama klasa faktu co przeliczenie epoki na datę. Bez tej sekcji numer
    rachunku z wezwania do zapłaty istniał w raporcie wyłącznie jako fragment
    prozy w zrzucie treści.

    >>> registry_identifiers("Konto: PL17 1090 2851 0000 0001 3017 6424, NIP: 836-167-65-10")
    [('IBAN', 'PL17 1090 2851 0000 0001 3017 6424', 'suma kontrolna poprawna (mod-97)'), ('NIP', '836-167-65-10', 'suma kontrolna poprawna')]
    >>> registry_identifiers("KRS: 0000370919")
    [('KRS', '0000370919', 'brak sumy kontrolnej w standardzie')]
    >>> registry_identifiers("bez identyfikatorow")
    []

    Niepoprawna suma kontrolna jest ustaleniem, nie powodem pominięcia wpisu:

    >>> registry_identifiers("NIP: 836-167-65-11")
    [('NIP', '836-167-65-11', 'suma kontrolna **niepoprawna**')]
    """
    out: list[tuple[str, str, str]] = []
    for label, pattern, validator in REGISTRY_PATTERNS:
        for matched in dict.fromkeys(re.findall(pattern, text)):
            if validator is None:
                status = "brak sumy kontrolnej w standardzie"
            elif validator(matched):
                status = (
                    "suma kontrolna poprawna (mod-97)"
                    if "IBAN" in label or "NRB" in label
                    else "suma kontrolna poprawna"
                )
            elif "IBAN" in label or "NRB" in label:
                # Ciąg w kształcie IBAN-u z błędną sumą to inne ustalenie niż
                # brak numeru — pomijanie go po cichu kasowałoby dowód.
                status = "suma kontrolna **niepoprawna** (mod-97)"
            else:
                status = "suma kontrolna **niepoprawna**"
            out.append((label, matched, status))
    return out


def identity_layers(
    msg: email.message.Message,
    dkim: list[DkimSignature],
    resources: list[HtmlResource],
) -> list[tuple[str, str]]:
    """Warstwy deklarujące nadawcę — zestawione w jednym miejscu, bez oceny zgodności.

    Każda z tych wartości była w raporcie osobno, w innej sekcji. Zestawienia
    nie było, więc rozjazd typu „`From` podpisuje domena A, kopertę nadaje B,
    linki prowadzą do C” trzeba było składać ręcznie z pięciu tabel. To jest
    zestawienie faktów z pliku, nie ocena — sekcja 1 robi już analogiczne dla
    nazwy wyświetlanej i domeny adresu.

    >>> from email import message_from_string, policy
    >>> src = ("From: Marka <nadawca@marka.pl>\\nReply-To: kontakt@inna.pl\\n"
    ...        "Return-Path: <bounce@dostawca.pl>\\n\\nx")
    >>> msg = message_from_string(src, policy=policy.default)
    >>> identity_layers(msg, [], [])
    [('Nazwa wyświetlana `From`', 'Marka'), ('Domena `From`', 'marka.pl'), ('Domena `Reply-To`', 'inna.pl'), ('Domena koperty (`Return-Path`)', 'dostawca.pl')]

    >>> identity_layers(message_from_string("\\n\\nx", policy=policy.default), [], [])
    []
    """
    out: list[tuple[str, str]] = []

    def add(label: str, value: str | None) -> None:
        if value and (label, value) not in out:
            out.append((label, value))

    for naglowek, label in (
        ("From", "Domena `From`"),
        ("Reply-To", "Domena `Reply-To`"),
        ("Return-Path", "Domena koperty (`Return-Path`)"),
        ("Sender", "Domena `Sender`"),
    ):
        value = msg.get(naglowek)
        if not value:
            continue
        name, adres = email.utils.parseaddr(str(value))
        if naglowek == "From":
            add("Nazwa wyświetlana `From`", name.strip())
        if adres and "@" in adres:
            add(label, adres.rsplit("@", 1)[1].strip("> ").lower())

    for podpis in dkim:
        add("Domena podpisująca (DKIM `d=`)", podpis.domain)

    link_hosts = sorted({r.host.lower() for r in resources if r.kind == "a" and r.host})
    if link_hosts:
        add("Hosty odnośników w treści", ", ".join(link_hosts))
    resource_hosts = sorted(
        {r.host.lower() for r in resources if r.kind != "a" and r.host}
    )
    if resource_hosts:
        add("Hosty zasobów pobieranych w treści", ", ".join(resource_hosts))
    return out
