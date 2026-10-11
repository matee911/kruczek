# /// script
# requires-python = ">=3.11"
# dependencies = ["pytailwindcss==0.3.1"]
# [tool.uv]
# exclude-newer = "2026-09-27T23:59:59Z"
# ///
"""budowa_css.py — buduje static/kruczek.css ze źródeł w css/ i klas użytych w components/.

Uruchamiaj przy zmianie CSS, tokenów albo komponentów (i przy wydaniu):
    uv run --script scripts/kruczek_strona/budowa_css.py            # buduje (pobiera Tailwind raz)
    uv run --script scripts/kruczek_strona/budowa_css.py --sprawdz  # tylko sprawdza, bez sieci
Użytkownik pluginu niczego nie buduje — kruczek.css jest w repozytorium.

Świeżość: pierwsza linia kruczek.css niesie sumę SHA-256 wszystkich źródeł (css/, components/)
i przypiętych wersji. Test porównuje ją z sumą liczoną na bieżąco — bez uruchamiania Tailwinda.
Na poziomie importu tylko stdlib; pytailwindcss ładuje się dopiero przy budowaniu.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

TAILWIND = "v4.3.3"
PYTAILWINDCSS = "0.3.1"
KATALOG = Path(__file__).resolve().parent
CSS = KATALOG / "css"
KOMPONENTY = KATALOG / "components"
WYNIK = KATALOG / "static" / "kruczek.css"
VENDOR = CSS / "vendor" / "basecoat-css-1.0.2"
_NAGLOWEK = re.compile(r"\A/\*! kruczek-css zrodla=([0-9a-f]{64}) \*/\n")


def tokens_css(tokens: dict) -> str:
    """tokens.json design systemu → zmienne CSS (motyw jasny na :root, ciemny pod [data-theme="dark"])
    i klasy stylów tekstu (.title, .body, .date …).

    >>> t = {"color": {"themes": [{"id": "light"}, {"id": "dark"}],
    ...      "tokens": [{"name": "ink", "value": {"light": "#111", "dark": "#eee"}}]},
    ...      "spacing": {"tokens": [{"name": "space-1", "value": "4px"}]},
    ...      "type": {"families": {"data": "monospace"}, "groups": [{"family": "data", "styles": [
    ...          {"name": "date", "fontSize": "15px", "lineHeight": "20px", "fontWeight": 500}]}]}}
    >>> print(tokens_css(t))
    :root, [data-theme="light"] {
      --ink: #111;
    }
    [data-theme="dark"] {
      --ink: #eee;
    }
    :root {
      --space-1: 4px;
      --font-data: monospace;
    }
    .date { font-family: var(--font-data); font-size: 15px; line-height: 20px; font-weight: 500; }
    <BLANKLINE>
    """
    motywy = [m["id"] for m in tokens["color"]["themes"]]
    pierwszy = motywy[0]

    def wartosc(v: str | dict, motyw: str) -> str:
        return v if isinstance(v, str) else v.get(motyw, v[pierwszy])

    def blok(selektor: str, motyw: str) -> str:
        linie = [f"{selektor} {{"]
        for rodzina in ("color", "shadow"):
            linie += [f"  --{t['name']}: {wartosc(t['value'], motyw)};" for t in tokens.get(rodzina, {}).get("tokens", [])]
        return "\n".join([*linie, "}"])

    css = [blok(f':root, [data-theme="{pierwszy}"]', pierwszy)]
    css += [blok(f'[data-theme="{m}"]', m) for m in motywy[1:]]
    inne = [":root {"]
    for rodzina, dane in tokens.items():
        if rodzina in ("color", "type", "shadow") or not isinstance(dane, dict) or "tokens" not in dane:
            continue
        inne += [f"  --{t['name']}: {t['value']};" for t in dane["tokens"]]
    inne += [f"  --font-{k}: {v};" for k, v in tokens["type"]["families"].items()]
    css.append("\n".join([*inne, "}"]))
    for grupa in tokens["type"]["groups"]:
        for s in grupa["styles"]:
            cechy = [f"font-family: var(--font-{s.get('family', grupa['family'])})", f"font-size: {s['fontSize']}",
                     f"line-height: {s['lineHeight']}", f"font-weight: {s['fontWeight']}"]
            if "letterSpacing" in s:
                cechy.append(f"letter-spacing: {s['letterSpacing']}")
            css.append(f".{s['name']} {{ {'; '.join(cechy)}; }}")
    return "\n".join(css) + "\n"


def pliki_zrodel() -> list[Path]:
    """Wszystko, od czego zależy wynik: źródła CSS (z vendorem i tokenami) i komponenty,
    w których Tailwind szuka klas. Pliki ukryte (.DS_Store itp.) są pomijane, żeby suma
    była taka sama na każdej maszynie."""
    pliki = [p for p in CSS.rglob("*") if p.is_file()] + list(KOMPONENTY.rglob("*.jinja"))
    jawne = [p for p in pliki if not any(c.startswith(".") for c in p.relative_to(KATALOG).parts)]
    return sorted(jawne, key=lambda p: p.relative_to(KATALOG).as_posix())


def suma_zrodel() -> str:
    h = hashlib.sha256(f"tailwind={TAILWIND};pytailwindcss={PYTAILWINDCSS}\n".encode())
    for p in pliki_zrodel():
        h.update(p.relative_to(KATALOG).as_posix().encode() + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def naglowek(suma: str) -> str:
    """
    >>> suma_z_naglowka(naglowek("a" * 64) + "body{}") == "a" * 64
    True
    """
    return f"/*! kruczek-css zrodla={suma} */\n"


def suma_z_naglowka(css: str) -> str | None:
    m = _NAGLOWEK.match(css)
    return m.group(1) if m else None


def niezgodne_z_sumami(katalog: Path, plik_sum: str) -> list[str]:
    """Pliki, których SHA-256 różni się od zapisanej w `plik_sum` (format `shasum -a 256`), albo których brak."""
    zle = []
    for linia in (katalog / plik_sum).read_text(encoding="utf-8").splitlines():
        if not linia.strip():
            continue
        suma, nazwa = linia.split(maxsplit=1)
        plik = katalog / nazwa.removeprefix("./")
        if not plik.is_file() or hashlib.sha256(plik.read_bytes()).hexdigest() != suma:
            zle.append(nazwa)
    return zle


def _tokens_z_json() -> str:
    return tokens_css(json.loads((CSS / "tokens.json").read_text(encoding="utf-8")))


def sprawdz() -> list[str]:
    """Co jest nieświeże albo zmienione — pusta lista = wszystko w porządku."""
    problemy = [f"vendor: {n}" for n in niezgodne_z_sumami(VENDOR, "FILES.sha256")]
    if (CSS / "tokens.css").read_text(encoding="utf-8") != _tokens_z_json():
        problemy.append("css/tokens.css nie odpowiada tokens.json")
    if not WYNIK.exists() or suma_z_naglowka(WYNIK.read_text(encoding="utf-8")) != suma_zrodel():
        problemy.append("static/kruczek.css nieaktualny")
    return problemy


def zbuduj() -> None:
    import pytailwindcss  # tylko przy budowaniu (zależność z nagłówka PEP 723)

    zle = niezgodne_z_sumami(VENDOR, "FILES.sha256")
    if zle:
        raise SystemExit(f"błąd: pliki Basecoat różnią się od sum: {', '.join(zle)}")
    (CSS / "tokens.css").write_text(_tokens_z_json(), encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        wyjscie = Path(tmp) / "kruczek.css"
        pytailwindcss.run(["-i", str(CSS / "input.css"), "-o", str(wyjscie), "--minify"],
                          cwd=CSS, auto_install=True, version=TAILWIND)
        css = wyjscie.read_text(encoding="utf-8")
    WYNIK.write_text(naglowek(suma_zrodel()) + css, encoding="utf-8")
    print(f"zbudowano {WYNIK} ({WYNIK.stat().st_size} B)")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--sprawdz"]:
        problemy = sprawdz()
        for p in problemy:
            print(f"błąd: {p} — uruchom: uv run --script scripts/kruczek_strona/budowa_css.py", file=sys.stderr)
        return 1 if problemy else 0
    if argv:
        print("użycie: budowa_css.py [--sprawdz]", file=sys.stderr)
        return 2
    zbuduj()
    return 0


if __name__ == "__main__":
    sys.exit(main())
