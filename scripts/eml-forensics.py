#!/usr/bin/env python3
"""eml-forensics.py — mechaniczna analiza wiadomości .eml pod kątem dowodowym.

Wypluwa gotowy raport markdown: droga wiadomości, uwierzytelnienie (SPF/DKIM/DMARC),
rozbieżność domen, sfingowany wątek, tokeny śledzące, katalog technik obfuskacji,
treść po deobfuskacji, sumy kontrolne. Zero interpretacji prawnej — same fakty.

Użycie:
    eml-forensics.py wiadomosc.eml [--outdir KATALOG]

Zapisuje w --outdir (domyślnie obok pliku):
    <stem>_naglowki.txt      pełne nagłówki
    <stem>_tresc.html        część text/html po zdekodowaniu
    <stem>_tresc.txt         część text/plain (jeśli jest)
    <stem>_analiza.md        raport
Bez zależności zewnętrznych (tylko stdlib).
"""

import sys, os, re, base64, email, email.policy, html as H, unicodedata, collections, argparse, binascii
from utils import sha256_file as sha256

ZW = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE",
    0x00AD: "SOFT HYPHEN",
    0x2060: "WORD JOINER",
}


def deobfuscate(src):
    """Usuwa techniki obfuskacji HTML i zwraca czysty tekst.

    >>> deobfuscate("")
    ''
    >>> deobfuscate("Hello world")
    'Hello world'
    >>> deobfuscate("He<!--spam-->llo")
    'Hello'
    >>> deobfuscate('<span style="color: white">ukryty</span>widoczny')
    'widoczny'
    >>> deobfuscate('<span>rozbity</span>')
    'rozbity'
    >>> deobfuscate('<br/>linia1<br/>linia2')
    'linia1\\nlinia2'
    >>> deobfuscate('&amp; &lt;')
    '& <'
    >>> deobfuscate('a\\n\\n\\n\\nb')
    'a\\n\\nb'
    """
    t = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    t = re.sub(
        r'<span[^>]+style="[^"]*color:\s*(white|#fff{1,3}|rgb\(255,\s*255,\s*255\))[^"]*"[^>]*>.*?</span>',
        "",
        t,
        flags=re.S | re.I,
    )
    t = re.sub(r"<span>(.*?)</span>", r"\1", t, flags=re.S)
    t = H.unescape(t)
    t = "".join(c for c in t if ord(c) not in ZW)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?p[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def decode_tokens(src):
    """Wyciąga query-stringi z URL-i i próbuje zdekodować każdy fragment jako Base64.

    >>> decode_tokens("")
    []
    >>> decode_tokens("żaden url")
    []
    >>> decode_tokens("https://example.com/path")
    []
    >>> decode_tokens("https://example.com/r?t=amFuIGtvd2Fsc2tp")
    [('amFuIGtvd2Fsc2tp', 'jan kowalski')]
    >>> decode_tokens("https://example.com/r?id=amFuIGtvd2Fsc2tp&src=email")
    [('amFuIGtvd2Fsc2tp', 'jan kowalski')]
    """
    out = []
    cands = []
    for m in re.finditer(r"https?://[^\s\"'<>]+", src):
        url = m.group(0)
        if "?" not in url:
            continue
        qs = url.split("?", 1)[1].split("#", 1)[0]
        for pair in re.split(r"[&;]", qs):
            cands.append(pair)  # ?bWF0...== (bez klucza)
            if "=" in pair:
                cands.append(pair.split("=", 1)[1])  # ?k=bWF0...==
    for raw in cands:
        raw = raw.strip()
        if len(raw) < 12 or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", raw):
            continue
        norm = raw.replace("-", "+").replace("_", "/")
        for cand in (norm, norm + "=", norm + "=="):
            if len(cand) % 4:
                continue
            try:
                dec = base64.b64decode(cand, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            dec = dec.strip()
            if (
                dec
                and sum(ch.isprintable() for ch in dec) / len(dec) > 0.9
                and re.search(r"[A-Za-z0-9]", dec)
            ):
                out.append((raw, dec))
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eml")
    ap.add_argument("--outdir", default=None)
    a = ap.parse_args()
    outdir = a.outdir or os.path.dirname(os.path.abspath(a.eml)) or "."
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.eml))[0]

    raw = open(a.eml, "rb").read()
    msg = email.message_from_bytes(raw, policy=email.policy.default)

    # --- artefakty ---
    hdr = "\n".join(f"{k}: {v}" for k, v in msg.items())
    p_hdr = os.path.join(outdir, f"{stem}_naglowki.txt")
    open(p_hdr, "w", encoding="utf-8").write(hdr + "\n")

    html_body = txt_body = None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/html" and html_body is None:
            html_body = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", "replace"
            )
        elif ct == "text/plain" and txt_body is None:
            txt_body = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", "replace"
            )

    written = [
        (
            os.path.basename(a.eml),
            sha256(a.eml),
            "oryginał wiadomości RFC 822 — DOWÓD GŁÓWNY, nie modyfikować",
        ),
        (os.path.basename(p_hdr), sha256(p_hdr), "pełne nagłówki (wyciąg)"),
    ]
    if html_body is not None:
        p = os.path.join(outdir, f"{stem}_tresc.html")
        open(p, "w", encoding="utf-8").write(html_body)
        written.append(
            (
                os.path.basename(p),
                sha256(p),
                "część text/html po zdekodowaniu transfer-encoding",
            )
        )
    if txt_body is not None:
        p = os.path.join(outdir, f"{stem}_tresc.txt")
        open(p, "w", encoding="utf-8").write(txt_body)
        written.append((os.path.basename(p), sha256(p), "część text/plain"))

    src = html_body or txt_body or ""

    # --- analiza ---
    L = []
    W = L.append
    W(f"# Analiza techniczna wiadomości `{os.path.basename(a.eml)}`\n")
    W(
        f"Wygenerowano skryptem `eml-forensics.py`. SHA-256 pliku źródłowego: `{sha256(a.eml)}`\n"
    )

    W("## 1. Identyfikacja\n")
    W("| Nagłówek | Wartość |")
    W("|---|---|")
    _seen_h = set()
    for k in (
        "Message-Id",
        "Date",
        "From",
        "To",
        "Cc",
        "Reply-To",
        "Return-Path",
        "Subject",
        "List-Unsubscribe",
        "X-Mailer",
        "User-Agent",
    ):
        v = msg.get(k)
        if v and k.lower() not in _seen_h:
            _seen_h.add(k.lower())
            W("| `%s` | %s |" % (k, str(v).replace("|", "\\|")))
    W("")

    W("## 2. Droga wiadomości (Received, od najstarszego)\n")
    rec = msg.get_all("Received") or []
    if not rec:
        W("_Brak nagłówków Received._\n")
    for i, r in enumerate(reversed(rec), 1):
        W(f"{i}. `{' '.join(str(r).split())}`")
    W("")
    ips = collections.OrderedDict.fromkeys(
        re.findall(r"\[?((?:\d{1,3}\.){3}\d{1,3})\]?", " ".join(map(str, rec)))
    )
    if ips:
        W("Adresy IP w łańcuchu: " + ", ".join(f"`{i}`" for i in ips) + "\n")

    W("## 3. Uwierzytelnienie nadawcy\n")
    auth = " ".join(
        str(v)
        for v in (msg.get_all("Authentication-Results") or [])
        + (msg.get_all("Received-SPF") or [])
    )
    if auth:
        W("```")
        for tag in ("dkim=", "spf=", "dmarc=", "arc="):
            for m in re.finditer(tag + r"[a-z]+[^;]*", auth):
                W(m.group(0).strip())
        W("```")
        verdict = []
        if "dkim=pass" in auth:
            verdict.append("DKIM **pass**")
        if "dkim=fail" in auth:
            verdict.append("DKIM **fail**")
        if "spf=pass" in auth:
            verdict.append("SPF **pass**")
        if "spf=fail" in auth or "spf=softfail" in auth:
            verdict.append("SPF **fail/softfail**")
        if verdict:
            W("\n" + ", ".join(verdict) + ".")
            if "dkim=pass" in auth and "spf=pass" in auth:
                W(
                    "\n> Wysyłka jest uwierzytelniona przez domenę nadawczą — wiadomość wyszła "
                    "z infrastruktury autoryzowanej przez tę domenę. Jeżeli zgadza się ona "
                    'z domeną z `From`, osłabia to linię obrony „ktoś podszył się pod naszą '
                    'firmę"; nie wyklucza jednak wysyłki z przejętego konta ani z domeny '
                    "łudząco podobnej."
                )
    else:
        W("_Brak nagłówków Authentication-Results / Received-SPF._")
    W("")

    W("## 4. Rozbieżność domen\n")

    def dom(v):
        m = re.search(r"@([A-Za-z0-9.-]+)", str(v or ""))
        return m.group(1).lower() if m else None

    d_from, d_reply, d_ret = (
        dom(msg.get("From")),
        dom(msg.get("Reply-To")),
        dom(msg.get("Return-Path")),
    )
    links = collections.OrderedDict.fromkeys(
        re.findall(r"https?://([A-Za-z0-9.-]+)", src)
    )
    W("| Rola | Domena |")
    W("|---|---|")
    for lbl, d in (("From", d_from), ("Reply-To", d_reply), ("Return-Path", d_ret)):
        if d:
            W(f"| {lbl} | `{d}` |")
    for d in links:
        W(f"| link w treści | `{d}` |")
    W("")
    distinct = {d for d in (d_from, d_reply, d_ret) if d} | set(links)
    if len(distinct) > 1:
        _n = len(distinct)
        _f = "różne domeny" if 2 <= _n <= 4 else "różnych domen"
        W(
            f"> Wykryto **{_n} {_f}**. Rozbieżność domeny nadawczej i domeny marki "
            "to typowy zabieg rotacji domen służący omijaniu list blokujących. "
            "Sprawdź WHOIS/RDAP każdej z nich (`podmiot.sh domena <domena>`) i czy przekierowują.\n"
        )

    W("## 5. Wątek korespondencji\n")
    subj = str(msg.get("Subject") or "")
    has_thread = bool(msg.get("In-Reply-To") or msg.get("References"))
    if re.match(r"\s*(re|odp|fwd|fw)\s*:", subj, re.I) and not has_thread:
        W(
            f"> **Brak powiązania z wątkiem.** Temat `{subj}` sugeruje odpowiedź na wcześniejszą "
            "korespondencję, ale brak nagłówków `In-Reply-To` i `References` — technicznie nic "
            "nie łączy tej wiadomości z wcześniejszym wątkiem. Prefiks bywa też wpisany ręcznie "
            "albo zgubiony przez klienta pocztowego; poszlaką sfingowania staje się to dopiero, "
            "gdy odbiorca potwierdzi, że wcześniejszej korespondencji nie było.\n"
        )
    elif has_thread:
        W("Wiadomość należy do wątku (`In-Reply-To`/`References` obecne).\n")
    else:
        W("Temat bez prefiksu odpowiedzi; brak nagłówków wątku.\n")

    W("## 6. Tokeny śledzące\n")
    toks = decode_tokens(src) + decode_tokens(hdr)
    seen, uniq = set(), []
    for r, d in toks:
        if d not in seen:
            seen.add(d)
            uniq.append((r, d))
    if uniq:
        W("| Token w URL | Po zdekodowaniu Base64 |")
        W("|---|---|")
        for r, d in uniq:
            W(f"| `{r[:60]}` | `{d}` |")
        W(
            "\n> Zakodowany identyfikator w linku dowodzi, że wysyłka była **spersonalizowana per odbiorca**, "
            "i wskazuje, że nadawca dysponował adresem w formie umożliwiającej powiązanie wejścia "
            "na stronę z konkretnym adresem.\n"
        )
    else:
        W("_Nie wykryto tokenów Base64 w URL-ach._\n")
    for m in re.finditer(
        r"[?&](?:unsu|unsub|email|e|u|id)=([^\"'&\s>]+)", src + hdr, re.I
    ):
        W(f"Identyfikator jawny w URL: `{m.group(1)}`\n")

    W("## 7. Techniki ukrywania treści przed filtrami antyspamowymi\n")
    rows = []
    n = len(re.findall(r"<!--.*?-->", src, flags=re.S))
    if n:
        rows.append(
            (
                "Komentarze HTML wewnątrz wyrazów",
                n,
                (
                    re.search(r"\w<!--.*?-->\w", src, flags=re.S)
                    or re.search(r"<!--.*?-->", src, flags=re.S)
                ).group(0)[:70],
            )
        )
    zwc = collections.Counter(ord(c) for c in src if ord(c) in ZW)
    for cp, cnt in zwc.items():
        ctx = ""
        m = re.search(r"\w" + re.escape(chr(cp)) + r"\w", src)
        if m:
            ctx = repr(m.group(0))
        rows.append((f"Znaki niedrukowalne U+{cp:04X} ({ZW[cp]})", cnt, ctx))
    ent = collections.Counter(re.findall(r"&#\d+;", src))
    if ent:
        rows.append(
            (
                "Numeryczne encje HTML zamiast liter",
                sum(ent.values()),
                " ".join(f"{k}×{v}" for k, v in ent.most_common(6)),
            )
        )
    sp = re.findall(r"<span>(.*?)</span>", src, flags=re.S)
    if sp:
        rows.append(
            (
                "Puste znaczniki &lt;span&gt; rozbijające wyrazy",
                len(sp),
                " · ".join(f"<span>{x[:14]}</span>" for x in sp[:3]),
            )
        )
    white = re.findall(
        r'<span[^>]+style="[^"]*color:\s*(?:white|#fff{1,3}|rgb\(255,\s*255,\s*255\))[^"]*"[^>]*>(.*?)</span>',
        src,
        flags=re.S | re.I,
    )
    if white:
        rows.append(
            (
                "Tekst niewidoczny (biały na białym) — hash busting",
                f"{sum(len(w) for w in white)} znaków",
                white[0][:70].replace("\n", " "),
            )
        )
    inv = re.findall(
        r'style="[^"]*(?:display:\s*none|font-size:\s*0|visibility:\s*hidden)[^"]*"',
        src,
        re.I,
    )
    if inv:
        rows.append(
            (
                "Elementy ukryte przez CSS (display:none / font-size:0)",
                len(inv),
                inv[0][:70],
            )
        )
    if rows:
        W("| # | Technika | Liczba | Przykład ze źródła |")
        W("|---|---|---|---|")
        for i, (t, c, ex) in enumerate(rows, 1):
            W("| %d | %s | %s | `%s` |" % (i, t, c, str(ex).replace("|", "\\|")))
        W(
            f"\n> Wykryto **{len(rows)} niezależnych technik** zastosowanych jednocześnie. "
            "Żadna nie powstaje samoczynnie w programie pocztowym — każda wymaga celowej ingerencji w kod HTML. "
            "Ich współwystępowanie jest okolicznością obciążającą przy ocenie umyślności.\n"
        )
    else:
        W("_Nie wykryto technik obfuskacji._\n")
    dcc = (
        msg.get("X-DCC--Metrics") or msg.get("X-Spam-Status") or msg.get("X-Spam-Flag")
    )
    if dcc:
        W(f"Nagłówek filtra po stronie odbiorcy: `{dcc}`\n")

    W("## 8. Treść po usunięciu obfuskacji\n")
    W("```\n" + (deobfuscate(src) if src else "(brak treści tekstowej)") + "\n```\n")

    W("## 9. Wygenerowane artefakty i sumy kontrolne\n")
    W("| Plik | SHA-256 | Opis |")
    W("|---|---|---|")
    for name, h, desc in written:
        W(f"| `{name}` | `{h}` | {desc} |")
    W("")
    W(
        "---\n_Raport wygenerowany mechanicznie. Kwalifikację prawną przeprowadź osobno "
        "(zob. skill `kruczek:konwencje-pism` i bazę wiedzy projektu)._"
    )

    p_an = os.path.join(outdir, f"{stem}_analiza.md")
    open(p_an, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[zapisano] {p_an}", file=sys.stderr)


if __name__ == "__main__":
    main()
