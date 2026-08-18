---
name: metadane
description: Analizuje metadane plików od drugiej strony — PDF, DOCX, XLSX, zdjęcia. Generuje tabelę z trzema kolumnami dat (z nazwy, z metadanych, z treści) i oznacza rozbieżności jako gotowe zarzuty. Wywoływany automatycznie przez /kruczek:dowod dla plików od drugiej strony.
argument-hint: "[plik lub katalog sprawy]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh *) Bash(exiftool *) Bash(pdftotext *) Bash(unzip *) Bash(mdls *) Bash(xattr *) Read Write Edit
---

# Analiza metadanych dokumentów drugiej strony

Argumenty: `$ARGUMENTS`

## 1. Uruchom skrypt zbiorczy

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh <plik1> [plik2 ...]
```

Jeśli podano katalog sprawy — przeszukaj `ARCHIWUM/` pod kątem plików od drugiej strony:
`.pdf`, `.docx`, `.xlsx`, `.jpg`, `.jpeg`, `.png`.

## 2. Dla każdego pliku — ustal trzecią datę: z treści

Otwórz plik (Read lub pdftotext) i poszukaj:
- „obowiązuje od", „wchodzi w życie", „data wystawienia", „wystawiono dnia", „sporządzono"
- Data podpisania w stopce dokumentu
- Data faktury / umowy

Wpisz ją do tabeli jako „data z treści".

## 3. Oceń rozbieżności — gotowe zarzuty

| Rozbieżność | Gotowe sformułowanie do pisma |
|---|---|
| Data metadanych wcześniejsza niż „data wejścia w życie" z treści | „Metadane pliku wskazują datę utworzenia [X], podczas gdy dokument deklaruje wejście w życie [Y] — plik istniał co najmniej [X-Y] dni przed opublikowaniem." |
| Producer: Word + imię autora | „Dokument nie jest eksportem z systemu — nosi cechy pliku złożonego ręcznie przez [Author] w [Producer]." |
| Liczba rewizji ≤ 2 + czas edycji < 5 min | „Dokument zawiera [N] rewizji i czas edycji [T] — wskazuje na sporządzenie ad hoc, nie archiwizację systemową." |
| GPS w zdjęciu | „Zdjęcie zawiera dane lokalizacyjne GPS — serwis przetwarza współrzędne geograficzne użytkownika (art. 5 ust. 1 lit. c RODO)." |
| Data z nazwy ≠ data z metadanych | „Nazwa pliku sugeruje datę [X], metadane wskazują [Y] — nie należy ufać nazwie pliku." |

## 4. Higiena własnych plików — przypomnienie

Przed każdą wysyłką własnego pisma:
```bash
exiftool -all= pismo.pdf          # usuń Author, ścieżki, metadane edytora
pdftotext pismo.pdf -             # sprawdź ukryte warstwy tekstowe
```

## 5. Raport

Tabela ze skryptu + kolumna „data z treści" + kolumna „gotowy zarzut" (jeśli jest).
Wpisz ustalenia do sekcji „Ustalenia" w `index.md`.

## macOS — skąd pochodzi plik (opcjonalne)

```bash
xattr -p com.apple.metadata:kMDItemWhereFroms <plik> | xxd -r -p
mdls <plik> | grep kMDItemDateAdded
```
`kMDItemWhereFroms` = URL, z którego pobrano. `kMDItemDateAdded` = kiedy trafił na dysk.
Powiązuje plik ze źródłem, gdy brakuje zrzutu ekranu pobrania.
