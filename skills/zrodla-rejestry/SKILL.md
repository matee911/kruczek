---
name: zrodla-rejestry
description: Jak ustalić tożsamość drugiej strony z otwartych rejestrów — NIP przez białą listę VAT, KRS i Portal Rejestrów Sądowych (akta rejestrowe, sprawozdania finansowe), dane domeny przez RDAP, łańcuch przekierowań stron. Użyj, gdy trzeba dowiedzieć się, kto naprawdę stoi za firmą, stroną albo wysyłką.
when_to_use: Ustalenie danych firmy, NIP, KRS, REGON, adres do doręczeń, skład zarządu, akta rejestrowe i sprawozdania finansowe spółki, PRS, kto jest właścicielem domeny, kiedy domenę zarejestrowano, dokąd przekierowuje strona.
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

**KRS** (`api-krs.ms.gov.pl`, otwarte API od 8.03.2022) działa tylko po numerze KRS — stąd sekwencja
NIP → biała lista → KRS. Dwa odpisy: `OdpisAktualny` i `OdpisPelny` (ten drugi zawiera też dane
wykreślone — poprzednie firmy, adresy i zarządy, przydatne przy podmiocie, który zmieniał szyld).
Odpis aktualny zawiera reprezentację i wspólników; przy spółce cywilnej wspólnicy są osobami
fizycznymi i to **ich** trzeba oznaczyć w piśmie.

⚠ **Otwarte API maskuje dane osobowe.** W dziale 2 nazwiska, imiona i PESEL wracają zagwiazdkowane:
`{"nazwisko": {"nazwiskoICzlon": "M******"}, "imiona": {"imie": "P***"}, "pesel": "7**********"}`.
Sposób reprezentacji, funkcje i forma prawna są pełne — **nazwiska nie**. Nie oznaczysz więc
imiennie członka zarządu na podstawie samego API. Pełne dane daje „Full API", ale wymaga decyzji
administracyjnej Ministra Sprawiedliwości i jest przeznaczone do zwalczania przestępczości
gospodarczej — dla nas niedostępne. Obejście: odpis przez wyszukiwarkę na PRS, patrz niżej.

**CEIDG API v3** (`/firma?nip=`) daje dane JDG: imię i nazwisko właściciela, NIP i REGON, adres
działalności i korespondencyjny, status, daty rozpoczęcia/zawieszenia/wznowienia/wykreślenia, PKD,
kontakt, zakazy i upadłości. **Nie zwraca adresu zamieszkania ani daty urodzenia** — nie obiecuj
ich użytkownikowi (specyfikacja OpenAPI „API HD v3", kwiecień 2026). Wymaga tokenu Bearer — jednorazowa
rejestracja przez Profil Zaufany: `biznes.gov.pl/pl/e-uslugi/00_9999_00`. Token przychodzi mailem
w ciągu kilku minut. Zapisz go w `~/.kruczek/ceidg_token` — `podmiot.sh pelny` użyje go
automatycznie gdy brak KRS. Bez tokenu poprzestań na białej liście VAT i zasugeruj użytkownikowi
rejestrację jeśli sprawa dotyczy JDG.

## Portal Rejestrów Sądowych (PRS)

`prs.ms.gov.pl` — front-end Ministerstwa Sprawiedliwości do KRS (od 1.07.2021). Nie jest osobnym
rejestrem: to kanał dostępu do tego samego KRS, ale daje rzeczy, których API nie ma.

| Moduł | Co daje | Dostęp |
|---|---|---|
| Wyszukiwarka KRS | odpis aktualny / pełny | też przez `api-krs.ms.gov.pl` |
| **Przeglądarka akt rejestrowych** | akta sądowe spółki (elektroniczne od 1.07.2021) | tylko przeglądarka |
| **RDF** — repozytorium dokumentów finansowych | sprawozdania finansowe, uchwały o zatwierdzeniu | tylko przeglądarka |
| e-formularze KRS / S24 | składanie wniosków | wymaga podpisu — nie nasze zadanie |

**Ograniczenie: PRS nie ma API i nie da się go pobrać WebFetchem.** To aplikacja JS — każdy URL
(`/krs`, `/krs/akta`, `/kartoteki`) zwraca ten sam `index.html`, więc WebFetch widzi pusty
dokument, a nie wyniki. Nie ma też bocznego API dla akt ani RDF.

**Obejście: przeglądarka.** Akta rejestrowe i sprawozdania bierz przez `fallback-przegladarka` —
Claude in Chrome albo Playwright, bo treść dorysowuje się JS-em. Pobrane pliki (PDF/XML) wrzuć
do `ARCHIWUM/` jako dowód. **Wyszukiwarka KRS na PRS jest obejściem na maskowanie nazwisk
w otwartym API** — w interfejsie widać pełne imię i nazwisko członka zarządu, więc to stąd
bierzesz oznaczenie osoby do pisma. Zrób zrzut ekranu odpisu i zarchiwizuj go, bo sam JSON
z API tego ustalenia nie udźwignie.

**Czego PRS nie zna:** jednoosobowych działalności i spółek cywilnych — te nie mają numeru KRS
i siedzą w CEIDG. Po białej liście VAT rozwidlenie jest twarde: **jest KRS → api-krs + PRS;
nie ma KRS → CEIDG**.

## Domeny

RDAP NASK obsługuje `.pl`. Zwraca datę rejestracji, rejestratora, nameservery. Dane abonenta
będącego osobą fizyczną są zanonimizowane, ale **data rejestracji bywa najmocniejszym ustaleniem
technicznym**: domena zarejestrowana kilka dni przed wysyłką to poszlaka rotacji domen. Sama
zbieżność dat niczego nie przesądza — dopóki nie ma drugiego ogniwa, trzymaj ją w `⚠ HIPOTEZY`.

Dla `.eu` nie ma publicznego RDAP ani WHOIS po HTTP (EURid za anty-botem) — udokumentuj ręcznie
zrzutem ekranu i zarchiwizuj go jako dowód.

`podmiot.sh strona` pokazuje łańcuch przekierowań — dowód, że domena z reklamy prowadzi gdzie indziej.
Zapisz wynik do `ARCHIWUM/` jako dowód, bo przekierowanie może zniknąć.

## Powiązania kapitałowe i beneficjenci rzeczywiści

**CRBR** (Centralny Rejestr Beneficjentów Rzeczywistych, `crbr.podatki.gov.pl`) — kto faktycznie
kontroluje spółkę, nawet przez łańcuch udziałów. Brak publicznego API; użyj `fallback-przegladarka`
(Claude in Chrome) i wyszukaj po NIP. Pozwala ustalić, kto faktycznie kontroluje spółkę, także
przez łańcuch udziałów. CRBR jest rejestrem jawnym i obowiązkowym — wpis dowodzi struktury
własnościowej, nie tego, że była ona „ukrywana".

**Rejestr.io** (`rejestr.io/krs/<NIP>`) — wizualizacja powiązań między podmiotami (wspólnicy,
zarządy, spółki córki). Blokuje WebFetch; użyj `fallback-przegladarka`. Przydatne gdy druga strona
to sieć formalnie odrębnych spółek z tymi samymi właścicielami.

## Ogłoszenia i sprawozdania

**MSiG / imsig.pl** — publikacje obowiązkowe: zawieszenie, likwidacja, upadłość, zmiany KRS.
Wyszukiwanie po NIP lub KRS przez `fallback-przegladarka` (imsig.pl blokuje WebFetch).
Informacja o wszczętym postępowaniu restrukturyzacyjnym lub likwidacji zmienia strategię pisma.

**Sprawozdania finansowe z KRS** — RDF w PRS (patrz sekcja wyżej). Bilans i rachunek zysków/strat
zdradzają realną kondycję finansową drugiej strony. Użyj `fallback-przegladarka`; pliki są
w formacie XML lub PDF. Stary adres `przegladarka.ms.gov.pl` **nie działa** (NXDOMAIN),
a `ekrs.ms.gov.pl` przekierowuje na `prs.ms.gov.pl/krs` — nie odsyłaj użytkownika pod te hosty.

## Gdy nic nie działa

Zanim uznasz źródło za niedostępne, przejdź drabinkę obejść ze skillu **`fallback-przegladarka`**: zmiana narzędzia (WebFetch ↔ curl), boczne API, Claude in Chrome z sesją użytkownika, Playwright dla stron renderowanych JS-em, a na końcu przekazanie zadania użytkownikowi z gotową instrukcją krok po kroku. Nie omijamy captcha ani logowania.

## Gdy masz tylko nazwę firmy (bez NIP/REGON)

API Białej listy VAT (`wl-api.mf.gov.pl`) **nie ma endpointu `/search/name`** — obsługuje wyłącznie
NIP, REGON i numer rachunku. Nie próbuj szukania po nazwie przez to API.

Kolejność:
1. WebFetch stopki/regulaminu/„O nas" na stronie firmy — szukaj `NIP:`, `REGON:`, `KRS:` (wzorce: 10/9/14/10 cyfr).
2. WebFetch `rejestr.io` lub wyników wyszukiwarki z nazwą + „NIP".
3. Jeśli REGON znaleziony zamiast NIP-u: `curl -s "https://wl-api.mf.gov.pl/api/search/regon/<REGON>?date=$(date +%F)" | jq '.result.subject | {name,nip,krs}'`
4. Gdy nic nie działa — powiedz użytkownikowi wprost i podaj gotowe linki:
   - `https://wyszukiwarce.gov.pl`
   - `https://ceidg.gov.pl` → Wyszukiwarka podmiotów
   - stopka / regulamin / faktura od firmy

## Gdy dane ze strony nie zgadzają się z rejestrem

To częsta sytuacja: serwis podaje nazwę handlową i adres, ale nie NIP-u ani formy prawnej.
Wtedy:

1. Zbieżność adresu lub branży to **hipoteza, nie ustalenie**. Wpisz ją do sekcji `⚠ HIPOTEZY`
   w `index.md` z wyraźnym wskazaniem brakującego ogniwa.
2. Ustalenie tożsamości administratora danych bywa **samodzielnym celem pierwszego pisma** —
   żądanie z art. 15 RODO zmusza do ujawnienia, kto jest administratorem.
3. Brak danych identyfikujących usługodawcę w serwisie to **prawdopodobne** naruszenie obowiązku
   informacyjnego z art. 5 ustawy o świadczeniu usług drogą elektroniczną. Zanim wejdzie do pisma:
   sprawdź regulamin i podstrony (ustawa wymaga „udostępnienia" danych, niekoniecznie na stronie
   głównej) i potwierdź, że podmiot jest usługodawcą w rozumieniu ustawy i podlega prawu polskiemu.
4. Zaadresuj pismo na nazwę handlową i adres ze strony, ale dodaj zastrzeżenie: jeżeli adresat nie
   jest podmiotem odpowiedzialnym, ma wskazać ten podmiot w 7 dni, a brak odpowiedzi w tym terminie
   będzie traktowany jako odmowa wskazania podmiotu odpowiedzialnego i uzasadni skierowanie sprawy
   do właściwego organu przeciwko adresatowi jako podmiotowi prowadzącemu serwis. **Nie pisz, że
   milczenie „potwierdza odpowiedzialność"** — takie domniemanie nie istnieje, a adresat zacytuje
   je jako dowód, że nadawca sam nie wie, kogo obwinia.

## Delegowanie

To zadanie mechaniczne — zleć subagentowi `ustal-strone` (haiku). Uruchamia skrypty
i przepisuje pola z JSON-a; nie potrzeba do tego mocnego modelu.
