---
name: fallback-przegladarka
description: "Co zrobić, gdy źródło jest zablokowane dla automatu — obejścia przez przeglądarkę: Claude in Chrome, Playwright, computer use, albo przekazanie zadania użytkownikowi z gotową instrukcją. Użyj, gdy WebFetch, curl albo API odbiją się od anty-bota, formularza POST lub logowania."
when_to_use: Strona zwraca 403, 202, captcha, wymaga logowania; wyszukiwarka to formularz POST; robots.txt blokuje; API wymaga tokenu; trzeba zrobić zrzut ekranu strony jako dowód.
---

# Gdy źródło jest zamknięte dla automatu

Część rejestrów i wyszukiwarek nie da się odpytać skryptem. Zanim odpuścisz, przejdź tę drabinkę
od góry — każdy szczebel kosztuje więcej niż poprzedni.

## 1. Zmień narzędzie

`WebFetch` respektuje `robots.txt`, `curl` nie — i odwrotnie, EUR-Lex odbija curla anty-botem,
a przez `WebFetch` przechodzi. Zanim uznasz źródło za zamknięte, spróbuj obu.

Sprawdź też, czy nie ma bocznego wejścia: SPA zwykle ma pod spodem API (`/api/…`), portal Domino
ma bezpośrednie `?OpenDocument`, a serwis z wyszukiwarką POST często wystawia dokumenty pod
przewidywalnym URL-em. Poszukaj przez wyszukiwarkę internetową z operatorem `site:`.

## 2. Claude in Chrome

Jeśli dostępne są narzędzia `mcp__claude-in-chrome__*`, użytkownik ma wtyczkę w swojej przeglądarce —
z jego sesją i zalogowaniem. To najlepsza droga do treści za logowaniem.

Kolejność: najpierw `tabs_context_mcp` (zobacz, co jest otwarte), potem `tabs_create_mcp` na nową
kartę, `navigate`, `get_page_text` albo `read_page`. Nie przejmuj kart, których użytkownik używa.

Zastrzeżenia:
- wtyczka wymaga zgody użytkownika na daną domenę — jeśli jej nie ma, poproś o nadanie,
- **nie klikaj niczego, co może otworzyć okno dialogowe** (`alert`, `confirm`, „Usuń") — modal
  blokuje wtyczkę i sesja przestaje odpowiadać,
- do dowodu rób zrzut ekranu i zapisz go do `ARCHIWUM/` razem z datą i URL-em.

## 3. Playwright — MCP albo CLI

Gdy przeglądarki użytkownika nie ma, a strona wymaga JavaScriptu. W tym środowisku Chromium jest
preinstalowany (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`) — **nie uruchamiaj `playwright install`**.

```bash
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="pl-PL")
    pg.goto("https://…", wait_until="networkidle")
    print(pg.inner_text("body")[:4000])
    pg.screenshot(path="dowod.png", full_page=True)
    b.close()
PY
```

Nadaje się do: formularzy POST (wypełnić i wysłać), stron renderowanych JS-em, zrzutów ekranu
jako dowodu. Nie nadaje się do omijania captcha i logowania — nie próbuj.

## 4. Computer use

Ostateczność, gdy trzeba obsłużyć aplikację desktopową albo interfejs, którego nie da się
zautomatyzować inaczej. Wolne i zawodne — sięgaj po to naprawdę na końcu.

## 5. Przekaż zadanie użytkownikowi

Często najtańsze. Nie pisz „nie udało się" — daj gotową instrukcję:

> Nie mam dostępu do wyszukiwarki CBOSA (odrzuca zapytania automatyczne).
> 1. Wejdź na https://orzeczenia.nsa.gov.pl
> 2. W polu „wszystkie słowa" wpisz: `niezamówiona informacja handlowa`
> 3. Skopiuj mi adres URL wyniku albo sam identyfikator z `/doc/<ID>` — resztę zrobię sam.

Przy dowodach, których nie da się pobrać automatycznie (np. dane domeny `.eu`), poproś o **zrzut
ekranu z widoczną datą** i wciągnij go przez `/kruczek:dowod`.

## Czego nie robisz — bezwzględnie

- **Nie omijasz captcha, logowania ani zabezpieczeń.** Jeśli serwis odgradza treść, to jest jego
  decyzja. Poproś użytkownika albo znajdź legalne źródło.
- **Nie podszywasz się** pod inną przeglądarkę po to, żeby obejść blokadę anty-botową, gdy regulamin
  serwisu tego zabrania.
- **Nie pobierasz treści, której `WebFetch` odmówił z powodów prawnych**, przez curl, Pythona ani
  przeglądarkę. Blokada jest blokadą niezależnie od narzędzia.

Granica jest prosta: obchodzimy ograniczenia **techniczne** (formularz POST, SPA, brak API),
nie obchodzimy ograniczeń **wolicjonalnych** (captcha, logowanie, zakaz w regulaminie).

## Zapisz, że próbowałeś

Gdy źródła nie da się sprawdzić, zapisz to w `index.md` sprawy jako lukę: czego nie udało się
ustalić, gdzie próbowałeś i co powinien zrobić człowiek. Luka odnotowana jest znacznie lepsza
niż luka przemilczana — bo w piśmie nie pojawi się twierdzenie bez pokrycia.
