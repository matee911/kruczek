---
name: dowod
description: Wciąga dowód do archiwum sprawy — kopiuje oryginał, liczy sumę kontrolną, robi OCR/transkrypcję dla plików nietekstowych, aktualizuje manifest i dopisuje zdarzenie do chronologii. Użyj przy każdym nowym mailu, skanie, zdjęciu, nagraniu, PDF-ie czy zrzucie ekranu w sprawie.
argument-hint: "[ścieżka do pliku] [katalog sprawy]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eml-forensics.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(cp *) Bash(mkdir *) Bash(sha256sum *) Bash(file *) Bash(ls *) Read Write Edit
---

# Wciągnięcie dowodu do archiwum

Argumenty: `$ARGUMENTS`

To zadanie jest **mechaniczne**. Trzymaj się kroków, nie interpretuj treści dowodu prawnie
i nie oceniaj sprawy — od tego są inne komendy.

## 1. Ustal plik i sprawę

Jeśli nie podano ścieżki, poszukaj załączników z bieżącej rozmowy i katalogów spraw obok
`index.md`. Przy niejednoznaczności zapytaj — krótko.

## 2. Nazwij zgodnie z konwencją

`RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`

Data to **data powstania dowodu** (nadania listu, wysłania maila, wykonania zdjęcia,
rozmowy), a nie dzisiejsza. Odczytaj ją z metadanych albo z treści; jeśli się nie da,
użyj daty otrzymania i zaznacz to w opisie.

Rodzaj: `email`, `list`, `umowa`, `faktura`, `zdjecie`, `skan`, `nagranie`, `zrzut`, `wydruk`, `zgloszenie`.

## 3. Skopiuj do ARCHIWUM — nigdy nie przenoś, nigdy nie edytuj

```
cp <źródło> <sprawa>/ARCHIWUM/<nazwa-wg-konwencji>
```

`ARCHIWUM/` jest append-only. Oryginał zostaje bitowo nietknięty. Każda obróbka tworzy **nowy**
plik obok.

## 4. Jeśli plik jest nietekstowy — zrób wersję tekstową OD RAZU

Sprawdź typ (`file <plik>`) i zastosuj właściwą ścieżkę:

| Typ dowodu | Co zrobić | Plik wynikowy |
|---|---|---|
| `.eml`, `.msg` | `${CLAUDE_PLUGIN_ROOT}/scripts/eml-forensics.py <plik> --outdir <sprawa>/ARCHIWUM` | `_naglowki.txt`, `_tresc.html`, `_analiza.md` |
| skan / zdjęcie / PDF bez warstwy tekstowej | zleć subagentowi `transkryber` (sonnet) | `<nazwa>_tekst.md` |
| PDF z warstwą tekstową | `pdftotext -layout` | `<nazwa>_tekst.md` |
| nagranie audio / wideo | zleć subagentowi `transkryber` (sonnet) | `<nazwa>_tekst.md` |
| zrzut ekranu | odczyt vision → `transkryber` | `<nazwa>_tekst.md` |

Wersja tekstowa **zawsze** zaczyna się nagłówkiem:

```markdown
> **Odczyt pomocniczy.** Metoda: <OCR tesseract -l pol / odczyt vision / transkrypcja>.
> Data: RRRR-MM-DD. Plik źródłowy: `<nazwa>`, SHA-256: `<suma>`.
> Wiążąca jest treść oryginału. Fragmenty nieczytelne oznaczono `[nieczytelne]`, niepewne `[?]`.
```

Nigdy nie uzupełniaj domysłem tego, czego nie widać.

## 5. Przelicz sumy i manifest

```
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sumy  <sprawa>
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py wstaw <sprawa>/index.md <sprawa>
```

W tabeli opisowej nad manifestem (sekcja 4 `index.md`) dopisz wiersz: nazwa pliku + jedno zdanie,
**co to jest i co dowodzi**.

## 6. Dopisz do chronologii

Jeden wiersz w tabeli chronologii `index.md`: data i godzina **zdarzenia** (nie dodania do teczki),
opis, odesłanie do pliku. Zachowaj porządek chronologiczny.

## 7. Zamelduj krótko

Trzy linie: co dodano, jaka suma kontrolna, czy powstała wersja tekstowa. Jeśli przy okazji
wyszło coś istotnego dla sprawy (np. `eml-forensics.py` wykrył techniki obfuskacji albo token
z adresem odbiorcy) — dopisz **jedno** zdanie i wskaż, żeby zajrzeć do raportu. Nie streszczaj raportu.
