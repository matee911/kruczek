---
name: nowa-sprawa
description: Zakłada teczkę nowej sprawy — katalog podmiotu, index.md z chronologią, ustaleniami, manifestem i ścieżką eskalacji. Użyj, gdy zaczynasz spór z konkretną firmą lub instytucją.
argument-hint: "[nazwa podmiotu] [przedmiot sprawy]"
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/nowa-sprawa.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh *) Read Write Edit
---

# Nowa sprawa

Argumenty: `$ARGUMENTS`

## 1. Ustal minimum

Potrzebujesz **nazwy podmiotu**, **jednozdaniowego przedmiotu sprawy** i **charakteru, w jakim
użytkownik występuje w tej sprawie**. Czego nie ma w argumentach ani w rozmowie — zapytaj
jednym wywołaniem AskUserQuestion.

Charakter jest cechą **sprawy**, nie projektu: ta sama osoba prowadzi jedną sprawę prywatnie,
drugą jako przedsiębiorca, a trzecią w cudzym imieniu. Nie odczytuj go z `dane-nadawcy.md`
i nie zakładaj, że jest taki sam jak w poprzedniej sprawie. Opcje:

- **osoba fizyczna / konsument** — silniejsza ochrona, inny katalog roszczeń
- **przedsiębiorca** — wymaga NIP i pełnego brzmienia firmy (sekcja „moja działalność
  gospodarcza" w `dane-nadawcy.md`)
- **w imieniu innej osoby** — nadawcą pisma jest ta osoba, nie użytkownik; potrzebne jej dane
  i **pełnomocnictwo** jako załącznik. Dopisz to do TODO sprawy.

Wybór wpisz do wiersza **Występuję jako** w nagłówku `index.md` sprawy (krok 2). Jeśli
odpowiednia tożsamość nie jest jeszcze wypełniona w `_SZABLONY/dane-nadawcy.md` — odeślij
do `/kruczek:dane-nadawcy`, nie zgaduj danych.

**Nie pytaj tu o cel sprawy** (co użytkownik chce osiągnąć — zaprzestanie / zwrot
pieniędzy / naprawa / informacja / ukaranie). Na tym etapie sprawa jeszcze nie jest
poznana ani przeanalizowana — to pytanie ma sens dopiero po zebraniu dowodów (`/kruczek:dowod`),
tuż przed pisaniem pisma, i tam już jest zadawane (skill `pismo`, krok 2).

Jeśli w rozmowie jest już materiał źródłowy (mail, umowa, zdjęcie) — **nie czytaj go teraz w całości**.
Załóż sprawę, a materiał wciągnij przez `/kruczek:dowod`.

## 2. Załóż katalog

```
${CLAUDE_PLUGIN_ROOT}/scripts/nowa-sprawa.sh "<nazwa>" "<przedmiot>" <katalog-projektu>
```

Skrypt tworzy `ARCHIWUM/`, `ROBOCZE/` i `index.md` ze szkieletem: chronologia, ustalenia,
hipotezy, podstawa prawna, manifest, TODO, eskalacja.

## 3. Ustal dane rejestrowe drugiej strony

Jeśli znasz NIP albo KRS — od razu:
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh pelny <NIP>
```
Jeśli masz tylko nazwę lub stronę WWW, zleć to subagentowi `ustal-strone` (haiku — to
mechaniczne odpytanie rejestrów). **W prompcie zawsze podaj cel ustalenia tożsamości**
(np. „ustalić czy to legalny podmiot, do którego można skierować wezwanie o zaprzestanie,
czy anonimowa wysyłka do zgłoszenia jako spam") — bez tego subagent nie wie, jak głęboko
kopać ani co odnotować jako szczególnie istotne. Wynik wpisz do tabeli nagłówkowej `index.md`.

**Nie zgaduj tożsamości podmiotu.** Jeśli powiązanie jest tylko prawdopodobne (zbieżny adres,
ta sama branża), wpisz je do sekcji `⚠ HIPOTEZY` z wyraźnym wskazaniem brakującego ogniwa.
Ustalenie tożsamości bywa samodzielnym celem pierwszego pisma.

## 4. Sprawdź bazę wiedzy

Zajrzyj do `BAZA_WIEDZY/index.md`. Jeśli są tam już przepisy pasujące do tego typu sprawy —
wypisz je w sekcji „Podstawa prawna" `index.md` sprawy jako punkt wyjścia. Jeśli baza jest pusta
w tym zakresie, zaznacz to w TODO. **Nie rób teraz researchu prawnego** — to zadanie na etapie pisma.

## 5. Kanały kontaktu — tabelka gotowa do pisma

Dla każdej domeny podmiotu:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh raport <domena>
```

**Nie wysyłaj tu żadnej testowej wiadomości** — na tym etapie nie wiadomo jeszcze, czy
sprawa jest sporem z ustalonym podmiotem czy zgłoszeniem typu spam/phishing, gdzie
wysyłka z prawdziwego adresu ujawnia użytkownika i potwierdza aktywność skrzynki.
Sprawdzanie realnej osiągalności kanału (np. wysyłka testowa) należy do etapu
weryfikacji danych kontaktowych, przed napisaniem pisma — nie do zakładania sprawy.

Wygeneruj tabelkę do wklejenia w pismo:

```
| kanał              | źródło   | stan                          |
|--------------------|----------|-------------------------------|
| e-mail z KRS       | rejestr  | nie istnieje, 550 5.1.10      |
| strona z KRS       | rejestr  | HTTP 404                      |
| adres do e-Doręczeń| BAE      | brak                          |
| formularz kontaktowy| serwis  | dostępny                      |
```

Kody SMTP warte opisania w piśmie:
- `550 5.1.10 RecipientNotFound` — skrzynka nie istnieje
- `550 5.0.1 Recipient rejected` — istnieje, ale odrzuca
- `4xx` — błąd przejściowy, nie nadaje się na zarzut

## 6. DSA Transparency Database (tylko platformy cyfrowe)

Jeśli podmiot to platforma cyfrowa (portal, aplikacja, marketplace, serwis społecznościowy):
- Sprawdź: https://transparency.dsa.ec.europa.eu (search po nazwie platformy)
- Szukaj `statements of reasons` — uzasadnień decyzji o ograniczeniu konta (art. 17 i 24 ust. 5 DSA)

Dwa wyniki, oba użyteczne:
- **Zgłosił** → mamy urzędową wersję powodu blokady do zestawienia z tym co napisał użytkownikowi
- **Nie zgłosił** → możliwe naruszenie obowiązku z art. 24 ust. 5 DSA. Zanim je postawisz, ustal,
  czy podmiot jest platformą internetową w rozumieniu DSA i czy jego działanie było decyzją
  moderacyjną wymagającą uzasadnienia — brak wpisu bywa też skutkiem opóźnienia publikacji.
  Organ właściwy w PL: koordynator ds. usług cyfrowych — UKE (uke.gov.pl)

Zapisz wynik w sekcji „Ustalenia" w `index.md`.

## 7. Gmail setup — filtry i zapytania startowe

Zleć `/kruczek:gmail` z domenami podmiotu. Wypisz użytkownikowi gotowe filtry do założenia.

## 8. Archiwa startowe

Dla każdego URL ze strony KRS/CEIDG podmiotu (adres strony, adres e-mail, formularz kontaktowy):
```bash
# 1. WŁASNA kopia — fundament, nie wymaga niczego poza siecią:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh lokalnie "<url>" <sprawa>/ARCHIWUM
# 2. Niezależne poświadczenie IA — jeśli się uda:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh save "<url>" --kontakt "<e-mail nadawcy>"
```
Szczególnie: strona kontaktowa, regulamin, polityka prywatności, cennik.
Zabezpiecz je przed wysłaniem pierwszego pisma.

Zrzut lokalny rób **zawsze** — Wayback bywa niedostępny albo odmawia zapisu, a dowód nie może
zależeć od cudzej usługi. `save` dokłada niezależne poświadczenie strony trzeciej; jeśli się nie
uda, odnotuj to w sprawie (kod odpowiedzi) i idź dalej. `--kontakt` to e-mail w sprawach spornych
z `_SZABLONY/dane-nadawcy.md`; gdy dane nadawcy są jeszcze puste, poprzestań na zrzucie lokalnym.

## 9. Dopisz sprawę do rejestru

Dodaj wiersz do tabeli „Sprawy" w `index.md` projektu.

## 10. Podsumuj

Pięć linii: gdzie jest teczka, co ustalono o podmiocie, jakie kanały działają / nie działają,
jaka jest następna komenda (zwykle `/kruczek:dowod`), oraz przypomnienie: dalszą pracę nad
tą sprawą prowadzić w osobnej sesji przypiętej do katalogu tej sprawy (w Cowork: razem z
`BAZA_WIEDZY/` jako drugim folderem, oba rw — izolacja dotyczy innych spraw, nie bazy
wiedzy, do której ta sesja ma dopisywać), nie w sesji obejmującej cały projekt —
zapobiega myleniu spraw przy pracy równoległej nad kilkoma naraz.
