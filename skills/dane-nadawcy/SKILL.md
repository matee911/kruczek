---
name: dane-nadawcy
description: Wypełnia lub aktualizuje _SZABLONY/dane-nadawcy.md z danymi nadawcy (NIP, adres, e-mail). Dla przedsiębiorców weryfikuje dane z rejestrem (CEIDG dla JDG, KRS dla spółek). Użyj przy zakładaniu projektu lub gdy dane się zmieniły. Na końcu odświeża CLAUDE.md.
argument-hint: "[katalog projektu]"
model: sonnet
effort: low
allowed-tools: Read Write Edit Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh *)
---

# Aktualizacja danych nadawcy

Katalog projektu: `$1` (jeśli pusty — bieżący katalog roboczy).

## 1. Sprawdź czy plik istnieje

Jeśli `_SZABLONY/dane-nadawcy.md` nie istnieje — skopiuj szablon:

```
cp ${CLAUDE_PLUGIN_ROOT}/templates/dane-nadawcy.md <katalog>/_SZABLONY/dane-nadawcy.md
```

## 2. Odczytaj co już jest wypełnione

Read `<katalog>/_SZABLONY/dane-nadawcy.md`. Wypisz użytkownikowi **jedną** tabelę z bieżącymi
wartościami — zaznacz które pola są puste lub mają placeholder (`<...>`).

## 3. Zapytaj o brakujące dane

**Nie pytaj, w jakim charakterze użytkownik występuje** — to cecha pojedynczej sprawy
(pole `Występuję jako` w jej `index.md`), nie projektu. Ta sama osoba prowadzi jedną sprawę
prywatnie, drugą jako przedsiębiorca, a trzecią w cudzym imieniu. Ten plik trzyma **tożsamości**,
z których sprawy korzystają.

**AskUserQuestion tylko dla pól z prawdziwym, zamkniętym wyborem** (2–4 rozłączne
opcje) — to jego kontrakt, wywołanie z polem otwartym (imię, adres, e-mail...) kończy
się błędem walidacji, bo nie ma tam żadnego wyboru do zaproponowania. Na tym etapie takim
pytaniem jest **które tożsamości wypełniamy teraz** (multiSelect): dane osobiste / działalność
gospodarcza / osoba reprezentowana. Pytaj o nie tylko wtedy, gdy nie wiadomo z rozmowy —
sekcje działalności i reprezentacji zostaw puste, jeśli użytkownik ich nie potrzebuje.

Resztę brakujących pól — bo są otwarte (imię i nazwisko, adres, e-mail, telefon,
sposób wysyłki, podpisy, preferencje) — zapytaj **zwykłą wiadomością tekstową**,
jednym zestawem, nie AskUserQuestion. Nie pytaj o pola już wypełnione — szanuj to
co użytkownik już wpisał.

**Format pytania**: każde odrębne pole to osobny numerowany punkt — nie zlepiaj kilku
pól w jeden punkt (np. "sposób wysyłki + podpis kwalifikowany + Profil Zaufany" to
**trzy** punkty, nie jeden — inaczej odpowiedź w jednym zdaniu jest niejednoznaczna,
patrz incydent 2026-08-28 z "podpis zaufany"). Wyjątek: adres do korespondencji i
miejscowość w nagłówku pism pytaj **razem, w jednym punkcie** — to w praktyce to samo
miasto, osobne pytanie jest zbędne.

Szkielet pytania (pomiń punkty, na które już masz odpowiedź):
```
1. Imię i nazwisko
2. Adres do korespondencji, razem z miejscowością w nagłówku pism (zwykle to samo
   miasto — powiedz, jeśli mają się różnić)
3. E-mail do spraw spornych
4. Telefon (opcjonalnie)
5. Sposób wysyłki listów: sam z poczty / Envelo / e-Doręczenia
6. Podpis kwalifikowany — masz? (tak/nie)
7. Profil Zaufany — masz? (tak/nie)
8. Podpis zaufany przez Profil Zaufany — masz? (tak/nie; ważny tylko wobec
   administracji publicznej, nie w pismach do firm prywatnych)
9. Preferowany ton pism (rzeczowy / bardzo formalny; bez zdania — rzeczowy)
10. Domyślny termin w wezwaniach (bez zdania — 14 dni)
```

Dla sekcji **działalność gospodarcza** (tylko jeśli użytkownik jej potrzebuje): pełne brzmienie
firmy, forma prawna, NIP; REGON i KRS jeśli są.

Dla sekcji **osoby, które reprezentuję** (tylko jeśli użytkownik prowadzi sprawy w cudzym
imieniu): imię i nazwisko tej osoby, kim jest dla użytkownika, jej adres i e-mail, oraz czy
jest już pełnomocnictwo na piśmie. Zaznacz, że bez pełnomocnictwa jako załącznika adresat może
odmówić rozpatrzenia pisma.

Minimum potrzebne do pisania pism (dla tożsamości „ja"):
- imię i nazwisko
- adres do korespondencji
- miejscowość w nagłówku
- e-mail do spraw spornych

Dodatkowo, gdy sprawa ma być prowadzona jako przedsiębiorca: pełne brzmienie firmy, forma
prawna i NIP. Gdy w cudzym imieniu: komplet danych tej osoby + pełnomocnictwo.

## 4. Zapisz odpowiedzi

Edit `<katalog>/_SZABLONY/dane-nadawcy.md` — wpisz podane wartości w odpowiednie wiersze tabeli.
Nie zmieniaj struktury pliku ani innych pól.

## 5. Weryfikacja rejestrowa (tylko sekcja działalności gospodarczej)

Pomiń ten krok, jeśli sekcja „Tożsamość — moja działalność gospodarcza" jest pusta.
Danych osoby prywatnej **nie da się** zweryfikować w rejestrach — biała lista VAT, CEIDG i KRS
obejmują wyłącznie działalność gospodarczą. To ograniczenie, nie błąd.

Jeśli NIP jest wypełniony, odpytaj rejestr i porównaj z tym co użytkownik podał:

**JDG** (brak KRS lub forma prawna = JDG):
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh ceidg <NIP>
```
Sprawdź i zaraportuj rozbieżności w:
- adres do doręczeń w CEIDG vs adres podany przez użytkownika
- e-mail w CEIDG vs e-mail podany przez użytkownika
- status działalności (czy aktywna, czy zawieszona/wykreślona)
- pełne brzmienie firmy (imię i nazwisko + nazwa handlowa)

**Spółka** (jest KRS):
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh nip <NIP>
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh krs <KRS> P
```
Sprawdź i zaraportuj rozbieżności w:
- adres siedziby z KRS vs adres podany przez użytkownika
- pełne brzmienie firmy z formą prawną
- reprezentacja (kto może podpisywać pisma w imieniu spółki)
- status (czy aktywna, czy w likwidacji/upadłości)

Raport rozbieżności:
- **zgodne** — jedna linia, nie rozpisuj
- **niezgodne** — wypisz: pole, wartość z rejestru, wartość podana przez użytkownika, zapytaj które użyć
- **brak w rejestrze** (np. e-mail) — informacja, nie błąd

Jeśli CEIDG zwróci błąd braku tokenu — poinformuj użytkownika, że weryfikacja danych z CEIDG
wymaga tokenu (`~/.kruczek/ceidg_token`), ale biała lista VAT działa bez niego i podaj z niej
co się dało. Kod 204 z CEIDG nie jest błędem — oznacza, że NIP nie figuruje w tym rejestrze
(np. to spółka, nie JDG).

## 6. Odśwież CLAUDE.md

```
${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh <katalog>
```

Przelicza status pól krytycznych na podstawie tego, co właśnie zapisałeś — bez tego
CLAUDE.md pokazywałby stary, sprzed edycji, status.

## 7. Potwierdź

Pokaż użytkownikowi wypełnione pola. Powiedz które nadal są puste — jeśli są krytyczne
(imię i nazwisko, adres do korespondencji, miejscowość, e-mail, NIP dla przedsiębiorcy)
— wskaż to wprost.
