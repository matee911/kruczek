---
name: archiwa
description: Archiwizuje URL w Wayback Machine, pobiera historię snapshotów przez CDX API i porównuje dwie wersje strony akapit po akapicie. Użyj przy każdym nowym URL w sprawie i gdy chcesz sprawdzić, czy strona się zmieniła od ostatniego zapisu. Wywoływany automatycznie przez /kruczek:dowod.
argument-hint: "[url] lub diff [url]"
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(python3 *) Bash(diff *) Bash(sha256sum *) Bash(mkdir *) Bash(curl *) Read Write Edit
---

# Archiwa internetowe

Argumenty: `$ARGUMENTS`

Zlecaj subagentowi `archiwizuj-strone` (sonnet). Przekaż argumenty bez zmian.

## Tryby

**`/kruczek:archiwa <url>`** — nowy URL: Save Page Now + pobierz kopię + historia CDX + TimeTravel

**`/kruczek:archiwa diff <url>`** — URL już był w sprawie: porównaj digestem CDX z poprzednim zapisem,
pobierz obie wersje, diff akapit po akapicie, gotowe zdanie do pisma

## Skrypt pomocniczy

Wszystkie operacje curl korzystają z:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh <tryb> <argumenty>
```

## Po zakończeniu

Sprawdź czy `archiwizuj-strone` dopisał do `index.md`:
- URL z timestampem Wayback
- SHA-256 lokalnej kopii
- Liczbę unikalnych wersji z CDX

Dopisz wpis do chronologii sprawy: „Zarchiwizowano URL: <url>, <N> wersji w Wayback, SHA-256: <hash>".

## Ograniczenia — pamiętaj przy pisaniu pisma

- Brak snapshotu ≠ strona nie istniała (Wayback nie archiwizuje za logowaniem ani JS-heavy)
- Snapshot = dowód z dokumentu osoby trzeciej (nie dokument urzędowy) — wzmacniaj lokalną kopią + SHA-256 + dokładnym URL w treści pisma
- Właściciel domeny może usunąć z Wayback → kopia lokalna jest obowiązkowa
- archive.today: brak API, ręcznie: https://archive.ph/<rok>/<url>
- Bing Cache: fallback na świeże strony (ostatnie dni) — dostępny przez przeglądarkę
