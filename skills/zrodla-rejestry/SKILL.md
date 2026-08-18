---
name: zrodla-rejestry
description: Jak ustalić tożsamość drugiej strony z otwartych rejestrów — NIP przez białą listę VAT, KRS, dane domeny przez RDAP, łańcuch przekierowań stron. Użyj, gdy trzeba dowiedzieć się, kto naprawdę stoi za firmą, stroną albo wysyłką.
when_to_use: Ustalenie danych firmy, NIP, KRS, REGON, adres do doręczeń, kto jest właścicielem domeny, kiedy domenę zarejestrowano, dokąd przekierowuje strona.
---

# Ustalanie tożsamości drugiej strony

Wrapper: `${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh`

Pismo musi trafić do **właściwego podmiotu, pod właściwy adres**. Wezwanie wysłane do marki, która
nie jest osobą prawną, albo pod adres z reklamy, jest nieskuteczne i daje drugiej stronie zarzut
braku doręczenia.

## Kolejność ustaleń

```bash
podmiot.sh pelny 5252344078      # NIP -> biała lista VAT -> (jeśli jest KRS) odpis z KRS
podmiot.sh nip 5252344078        # sama biała lista
podmiot.sh krs 0000240611        # odpis aktualny (rejestr P = przedsiębiorcy, S = stowarzyszenia)
podmiot.sh domena example.pl     # RDAP: rejestrator, abonent, daty rejestracji, nameservery
podmiot.sh strona https://x.pl   # łańcuch przekierowań i nagłówki HTTP
```

**Biała lista VAT** (`wl-api.mf.gov.pl`) to najlepszy punkt startu po NIP-ie: jednym zapytaniem
dostajesz nazwę, REGON, KRS, adres siedziby i rachunki bankowe. Obejmuje też jednoosobowe
działalności. Bez klucza API.

**KRS** (`api-krs.ms.gov.pl`) działa tylko po numerze KRS — stąd sekwencja NIP → biała lista → KRS.
Odpis aktualny zawiera reprezentację i wspólników; przy spółce cywilnej wspólnicy są osobami
fizycznymi i to **ich** trzeba oznaczyć w piśmie.

**CEIDG API v3** daje pełne dane JDG: imię i nazwisko właściciela, adres zamieszkania (nie tylko
siedzibę), datę urodzenia, historię działalności i zawieszenia. Wymaga tokenu Bearer — jednorazowa
rejestracja przez Profil Zaufany: `biznes.gov.pl/pl/e-uslugi/00_9999_00`. Token przychodzi mailem
w ciągu kilku minut. Zapisz go w `~/.kruczek/ceidg_token` — `podmiot.sh pelny` użyje go
automatycznie gdy brak KRS. Bez tokenu poprzestań na białej liście VAT i zasugeruj użytkownikowi
rejestrację jeśli sprawa dotyczy JDG.

## Domeny

RDAP NASK obsługuje `.pl`. Zwraca datę rejestracji, rejestratora, nameservery. Dane abonenta
będącego osobą fizyczną są zanonimizowane, ale **data rejestracji bywa najmocniejszym dowodem**:
domena zarejestrowana kilka dni przed wysyłką to twardy ślad rotacji domen.

Dla `.eu` nie ma publicznego RDAP ani WHOIS po HTTP (EURid za anty-botem) — udokumentuj ręcznie
zrzutem ekranu i zarchiwizuj go jako dowód.

`podmiot.sh strona` pokazuje łańcuch przekierowań — dowód, że domena z reklamy prowadzi gdzie indziej.
Zapisz wynik do `ARCHIWUM/` jako dowód, bo przekierowanie może zniknąć.

## Powiązania kapitałowe i beneficjenci rzeczywiści

**CRBR** (Centralny Rejestr Beneficjentów Rzeczywistych, `crbr.podatki.gov.pl`) — kto faktycznie
kontroluje spółkę, nawet przez łańcuch udziałów. Brak publicznego API; użyj `fallback-przegladarka`
(Claude in Chrome) i wyszukaj po NIP. Ujawnienie beneficjenta to mocny dowód ukrytej struktury
własnościowej.

**Rejestr.io** (`rejestr.io/krs/<NIP>`) — wizualizacja powiązań między podmiotami (wspólnicy,
zarządy, spółki córki). Blokuje WebFetch; użyj `fallback-przegladarka`. Przydatne gdy druga strona
to sieć formalnie odrębnych spółek z tymi samymi właścicielami.

## Ogłoszenia i sprawozdania

**MSiG / imsig.pl** — publikacje obowiązkowe: zawieszenie, likwidacja, upadłość, zmiany KRS.
Wyszukiwanie po NIP lub KRS przez `fallback-przegladarka` (imsig.pl blokuje WebFetch).
Informacja o wszczętym postępowaniu restrukturyzacyjnym lub likwidacji zmienia strategię pisma.

**Sprawozdania finansowe z KRS** — `przegladarka.ms.gov.pl` (repozytorium dokumentów finansowych).
Bilans i rachunek zysków/strat zdradzają realną kondycję finansową drugiej strony. Użyj
`fallback-przegladarka`; pliki są w formacie XML lub PDF.

## Gdy nic nie działa

Zanim uznasz źródło za niedostępne, przejdź drabinkę obejść ze skillu **`fallback-przegladarka`**: zmiana narzędzia (WebFetch ↔ curl), boczne API, Claude in Chrome z sesją użytkownika, Playwright dla stron renderowanych JS-em, a na końcu przekazanie zadania użytkownikowi z gotową instrukcją krok po kroku. Nie omijamy captcha ani logowania.

## Gdy dane ze strony nie zgadzają się z rejestrem

To częsta sytuacja: serwis podaje nazwę handlową i adres, ale nie NIP-u ani formy prawnej.
Wtedy:

1. Zbieżność adresu lub branży to **hipoteza, nie ustalenie**. Wpisz ją do sekcji `⚠ HIPOTEZY`
   w `index.md` z wyraźnym wskazaniem brakującego ogniwa.
2. Ustalenie tożsamości administratora danych bywa **samodzielnym celem pierwszego pisma** —
   żądanie z art. 15 RODO zmusza do ujawnienia, kto jest administratorem.
3. Brak danych identyfikujących usługodawcę w serwisie to samodzielne naruszenie
   (art. 5 ustawy o świadczeniu usług drogą elektroniczną) — warto to w piśmie wytknąć.
4. Zaadresuj pismo na nazwę handlową i adres ze strony, ale dodaj zastrzeżenie: jeżeli adresat nie
   jest podmiotem odpowiedzialnym, ma wskazać ten podmiot w 7 dni, a brak wskazania będzie
   traktowany jako potwierdzenie odpowiedzialności adresata.

## Delegowanie

To zadanie mechaniczne — zleć subagentowi `ustal-strone` (haiku). Uruchamia skrypty
i przepisuje pola z JSON-a; nie potrzeba do tego mocnego modelu.
