---
name: archiwa
description: Archiwizuje URL w Wayback Machine, pobiera historię snapshotów przez CDX API i porównuje dwie wersje strony akapit po akapicie. Użyj przy każdym nowym URL w sprawie i gdy chcesz sprawdzić, czy strona się zmieniła od ostatniego zapisu. Wywoływany automatycznie przez /kruczek:dowod.
argument-hint: "[url] lub diff [url] — wymaga e-maila nadawcy z dane-nadawcy.md (User-Agent)"
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(python3 *) Bash(diff *) Bash(sha256sum *) Bash(mkdir *) Bash(curl *) Read Write Edit
---

# Archiwa internetowe

Argumenty: `$ARGUMENTS`

## Wymóg wstępny: kontakt do User-Agenta

Internet Archive wymaga kontaktu do operatora bota w User-Agencie
(`archive.org/developers/bots.html`). **Nie każ użytkownikowi konfigurować środowiska** —
ten adres już jest w sprawie.

Przed pierwszym wywołaniem skryptu przeczytaj `_SZABLONY/dane-nadawcy.md` i weź **e-mail
w sprawach spornych** (a gdy pusty — e-mail główny). Przekazuj go każdemu wywołaniu jako
`--kontakt <e-mail>`.

Jeśli oba pola są puste — nie zgaduj adresu: powiedz użytkownikowi, że archiwizacja wymaga
e-maila nadawcy, i odeślij do `/kruczek:dane-nadawcy`.

Zlecaj subagentowi `archiwizuj-strone` (sonnet). Przekaż argumenty bez zmian, dokładając
ustalony `--kontakt`.

## Zasada: własna kopia jest fundamentem

Internet Archive to **dodatek, nie fundament**. Potrafi zwrócić błąd (520/503), odmówić zapisu
albo być niedostępny z sesji — a dowód musi istnieć niezależnie od cudzej usługi. Dlatego dla
każdego URL-a najpierw:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh lokalnie "<url>" <sprawa>/ARCHIWUM
```

Zapisuje treść, nagłówki, kod HTTP, URL końcowy po przekierowaniach, SHA-256 i metryczkę
z datą odczytu. Nie wymaga `--kontakt` ani żadnej konfiguracji.

Dopiero potem `save` — po niezależne poświadczenie strony trzeciej, którego własna kopia nie
daje. **Nieudany `save` nie unieważnia zabezpieczonego dowodu**; odnotuj kod odpowiedzi
w sprawie i pracuj dalej na kopii lokalnej.

## Tryby

**`/kruczek:archiwa <url>`** — nowy URL: zrzut lokalny + Save Page Now + pobierz kopię + historia CDX

**`/kruczek:archiwa diff <url>`** — URL już był w sprawie: porównaj digestem CDX z poprzednim zapisem,
pobierz obie wersje, diff akapit po akapicie, gotowe zdanie do pisma

## Skrypt pomocniczy

Wszystkie operacje curl korzystają z:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh <tryb> <argumenty> --kontakt <e-mail nadawcy>
```

Bez `--kontakt` skrypt odmówi startu (patrz „Wymóg wstępny" wyżej). `KRUCZEK_MODEL`
(opcjonalnie) to nazwa modelu, którym faktycznie pracuje bieżąca sesja — też trafia do UA.

## Sesja chmurowa (Cowork)

`web.archive.org` bywa zablokowany przez wymuszone proxy egress niezależnie od allowlisty
organizacji. `archiwa.sh` wykrywa to (`check_egress`) i kończy czytelnym błędem zamiast
timeoutu. W takiej sytuacji nie próbuj obejść blokady — przekaż użytkownikowi gotowe
wywołanie `${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh <tryb> <url>` (albo cel: URL/timestamp)
do uruchomienia lokalnie, wzorem `skills/fallback-przegladarka` (krok „Przekaż zadanie
użytkownikowi").

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
