---
name: dowod
description: Wciąga dowód do archiwum sprawy — kopiuje oryginał, liczy sumę kontrolną, robi OCR/transkrypcję dla plików nietekstowych, aktualizuje manifest i dopisuje zdarzenie do chronologii. Użyj przy każdym nowym mailu, skanie, zdjęciu, nagraniu, PDF-ie czy zrzucie ekranu w sprawie.
argument-hint: "[ścieżka do pliku] [katalog sprawy]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eml-forensics.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh *) Bash(cp *) Bash(mkdir *) Bash(sha256sum *) Bash(file *) Bash(ls *) Bash(qpdf *) Bash(unzip *) Bash(7z *) Read Write Edit
---

# Wciągnięcie dowodu do archiwum

Argumenty: `$ARGUMENTS`

To zadanie ma dwie warstwy: **mechaniczną** (kopia, hash, tekst) i **rozpoznawczą** (co to jest i co dalej).
Trzymaj się kolejności kroków.

## 0. Plik zaszyfrowany? Odszyfruj PRZED intake

Sprawdź typ pliku:
```bash
file <plik>
```

Jeśli PDF zaszyfrowany, .zip lub .7z:
- Zapytaj o hasło: „Plik jest zabezpieczony hasłem. Jakie hasło? (Przy plikach z urzędów/firm często PESEL lub data urodzenia.)"
- Odszyfruj:
  ```bash
  # PDF
  qpdf --password=<haslo> --decrypt <plik>.pdf <plik>_odszyfrowany.pdf
  # ZIP
  unzip -P <haslo> <plik>.zip -d <katalog>/
  # 7z
  7z x -p'<haslo>' <plik>.7z -o<katalog>/
  ```
- Do archiwum trafiają **oba**: oryginał jako `<nazwa>_ORYGINAŁ.<ext>` i odszyfrowany jako `<nazwa>.<ext>`
- **Hasło NIE trafia do `index.md` ani chronologii** — zapisz wyłącznie: „plik był zaszyfrowany, odszyfrowano RRRR-MM-DD"

## 1. Ustal plik i sprawę

Jeśli nie podano ścieżki — zapytaj krótko. Jeśli nie podano sprawy — sprawdź `index.md`
w bieżącym katalogu albo zapytaj.

## 2. Wykryj duplikat

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sumy <sprawa>
```
Sprawdź czy SHA-256 nowego pliku już istnieje w manifeście.
Jeśli duplikat: „Ten plik już jest w archiwum jako [nazwa]. Dodać mimo to?"

## 3. Nazwij zgodnie z konwencją

`RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`

Data to data **powstania** dowodu (nadania, wysłania, wykonania), nie dzisiejsza.
Rodzaj: `email`, `list`, `umowa`, `faktura`, `zdjecie`, `skan`, `nagranie`, `zrzut`, `wydruk`, `zgloszenie`.

## 4. Skopiuj do ARCHIWUM — nigdy nie przenoś, nigdy nie edytuj

```bash
cp <źródło> <sprawa>/ARCHIWUM/<nazwa-wg-konwencji>
```

## 5. Routing po typie pliku — wywołaj właściwe podsystemy

### `.eml` / `.msg`
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/eml-forensics.py <plik> --outdir <sprawa>/ARCHIWUM
```
Zleć subagentowi `analizuj-eml` (haiku).

Wyciągnij domeny z nagłówków (From, Reply-To, Return-Path, Received):
- Dla każdej **nowej** domeny (nie widzianej wcześniej w sprawie) → wywołaj `/kruczek:archiwa <domena>`
- Wygeneruj zapytania Gmail → zleć `/kruczek:gmail` z domenami z nagłówków

### `.pdf` / `.docx` / `.xlsx`

Zapytaj jeśli źródło nieznane: „Od kogo pochodzi ten plik?"

Jeśli od **drugiej strony**:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh <plik>
```
(lub zleć skill `/kruczek:metadane`)

Jeśli nazwa lub treść zawiera „regulamin", „OWU", „wzorzec", „ogólne warunki" — **niezależnie od źródła**:
zleć subagentowi `sprawdz-klauzule` (sonnet).

### Zrzut strony (`.html` / `.mhtml` / obraz z URL w nazwie)

Wyciągnij URL z nazwy pliku lub pytaj.
- Jeśli URL już był w sprawie → `/kruczek:archiwa diff <url>`
- Jeśli URL nowy w sprawie → `/kruczek:archiwa <url>` (pełne rozpoznanie + CDX)

### Obraz / skan bez URL

Zleć subagentowi `transkrybuj` (sonnet).

## 6. URL w treści pliku → natychmiast archiwizuj

Dla **każdego** nowego URL znalezionego w pliku (w .eml, w PDF, w fakturze):
```bash
# 1. WŁASNA kopia — fundament, zawsze:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh lokalnie "<url>" <sprawa>/ARCHIWUM
# 2. Niezależne poświadczenie IA — jeśli się uda:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh save "<url>" --kontakt "<e-mail nadawcy>"
```
Nie czekaj na analizę — najpierw zabezpiecz treść, potem czytaj.

**Kolejność jest istotna.** Wayback bywa niedostępny, zwraca błędy i może odmówić zapisu —
nie może być jedynym miejscem, w którym istnieje dowód. `lokalnie` nie wymaga `--kontakt`
ani żadnej konfiguracji i zapisuje treść, nagłówki, kod HTTP, łańcuch przekierowań i SHA-256.
Nieudany `save` **nie jest** porażką zabezpieczenia dowodu — odnotuj go i idź dalej.

`--kontakt` (tylko dla `save`) to e-mail w sprawach spornych z `_SZABLONY/dane-nadawcy.md`.
Gdy dane nadawcy są puste — zrób sam zrzut lokalny, a `save` dopisz do TODO.

## 7. Wersja tekstowa dla plików nietekstowych

| Typ | Co zrobić | Plik wynikowy |
|---|---|---|
| `.eml` / `.msg` | `eml-forensics.py` (krok 5) | `_naglowki.txt`, `_tresc.html`, `_analiza.md` |
| skan / zdjęcie / PDF bez tekstu | `transkrybuj` (sonnet) | `<nazwa>_tekst.md` |
| PDF z warstwą tekstową | `pdftotext -layout` | `<nazwa>_tekst.md` |
| nagranie audio / wideo | `transkrybuj` (sonnet) | `<nazwa>_tekst.md` |

Nagłówek wersji tekstowej (obowiązkowy):
```markdown
> **Odczyt pomocniczy.** Metoda: <OCR/vision/transkrypcja>. Data: RRRR-MM-DD.
> Plik źródłowy: `<nazwa>`, SHA-256: `<suma>`. Wiążąca jest treść oryginału.
> Fragmenty nieczytelne: `[nieczytelne]`, niepewne: `[?]`.
```

## 8. Sumy kontrolne i manifest

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sumy  <sprawa>
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py wstaw <sprawa>/index.md <sprawa>
```

W tabeli opisowej nad manifestem (`index.md` sekcja 4) dopisz: nazwa pliku + jedno zdanie co to jest i co dowodzi.

## 9. Pytanie o brakujący dowód kontekstowy

Przy każdym typie pliku — zaproponuj co mogłoby uzupełnić dowód:

| Typ pliku | Sugestia |
|---|---|
| `.eml` | „Czy masz autoresponder potwierdzający odbiór tej wiadomości?" |
| faktura / potwierdzenie płatności | „Czy masz wyciąg bankowy potwierdzający obciążenie?" |
| regulamin / OWU | „Czy masz poprzednią wersję tego dokumentu do porównania?" |
| zrzut ekranu | „Czy zrobiłeś zrzut 'przed' i 'po' zmianie?" |
| nagranie | „Czy masz potwierdzenie mailowe lub SMS nawiązujące do tej rozmowy?" |

## 10. Dopisz do chronologii

Jeden wiersz: data i godzina **zdarzenia** (nie dodania), opis, odesłanie do pliku. Porządek chronologiczny.

## 11. Raport końcowy

```
Plik:       <nazwa>
SHA-256:    <hash>
Wykryto:    <typ>
Wywołano:   <co uruchomiono — archiwa? metadane? forensyk? sprawdz-klauzule?>
Pewność:    dowód
⚠ Brakuje: <sugestia jeśli jest>
```
