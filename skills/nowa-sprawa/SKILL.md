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

Potrzebujesz **nazwy podmiotu** i **jednozdaniowego przedmiotu sprawy**. Jeśli ich nie ma
w argumentach ani w rozmowie, zapytaj — jednym wywołaniem AskUserQuestion, razem z pytaniem
o to, co użytkownik chce osiągnąć (zaprzestanie / zwrot pieniędzy / naprawa / informacja /
ukaranie), bo to determinuje całą dalszą ścieżkę.

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
mechaniczne odpytanie rejestrów). Wynik wpisz do tabeli nagłówkowej `index.md`.

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
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh <domena>
```
Wyślij realną wiadomość testową na adres e-mail z KRS i zachowaj `.eml` odbicia
(przez `/kruczek:dowod`).

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
- **Nie zgłosił** → osobne naruszenie DSA, do koordynatora ds. usług cyfrowych w PL: UKE (uke.gov.pl)

Zapisz wynik w sekcji „Ustalenia" w `index.md`.

## 7. Gmail setup — filtry i zapytania startowe

Zleć `/kruczek:gmail` z domenami podmiotu. Wypisz użytkownikowi gotowe filtry do założenia.

## 8. Archiwa startowe

Dla każdego URL ze strony KRS/CEIDG podmiotu (adres strony, adres e-mail, formularz kontaktowy):
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh save "<url>"
```
Szczególnie: strona kontaktowa, regulamin, polityka prywatności, cennik.
Zarchiwizuj przed wysłaniem pierwszego pisma.

## 9. Dopisz sprawę do rejestru

Dodaj wiersz do tabeli „Sprawy" w `index.md` projektu.

## 10. Podsumuj

Cztery linie: gdzie jest teczka, co ustalono o podmiocie, jakie kanały działają / nie działają,
jaka jest następna komenda (zwykle `/kruczek:dowod`).
