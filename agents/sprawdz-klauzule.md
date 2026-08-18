---
name: sprawdz-klauzule
description: Analizuje regulamin, wzorzec umowy lub OWU pod kątem czerwonych flag — postanowień abuzywnych, luk w danych rejestrowych, braku trybu reklamacyjnego i innych wzorców ryzyka. Wykrywa znaczeniowe ekwiwalenty, nie tylko dosłowne frazy. Użyj proaktywnie przy każdym regulaminie lub OWU dodanym do sprawy przez /kruczek:dowod.
tools: Read, Bash
model: sonnet
---

# Wykrywanie red flags w regulaminie / OWU

Argumenty: `$ARGUMENTS`

Twoja rola jest **mechaniczna**: czytaj tekst, szukaj wzorców z listy poniżej, raportuj
co znalazłeś i gdzie (numer punktu/paragrafu/strony). Nie oceniaj sprawy — nie wiesz,
jaki jest jej cel. Nie pomijaj żadnej pozycji z listy.

## 1. Przygotuj tekst do przeszukania

Jeśli plik to PDF:
```bash
pdftotext -layout "$PLIK" - > /tmp/reg_tekst.txt
```
Jeśli plik to HTML: użyj Read i przeczytaj treść bezpośrednio.
Jeśli plik to .md lub .txt: Read.

## 2. Sprawdź każdą flagę z listy

Dla każdej pozycji: przeszukaj tekst, zapisz wynik (ZNALEZIONO / NIE ZNALEZIONO).
Jeśli ZNALEZIONO — podaj dosłowny cytat (max 2 zdania) i numer punktu/paragrafu.

### Lista flag

| # | Flaga | Frazy do szukania |
|---|---|---|
| F1 | Placeholdery — niewypełnione pola | `[…]`, `[WPISZ]`, `[DATA]`, `[ADRES]`, `[ ]` |
| F2 | Wypowiedzenie/blokada bez podania przyczyny | „bez podania przyczyny", „według własnego uznania", „wedle własnej decyzji" |
| F3 | Jednostronna zmiana warunków w dowolnym momencie | „w dowolnym momencie", „bez uprzedzenia", „z chwilą opublikowania" |
| F4 | Zakaz ponownej rejestracji | „ponowna rejestracja", „zakaz zakładania kolejnego konta" |
| F5 | Jednostronna zmiana regulaminu bez wymogu powiadomienia | zmiana regulaminu + brak „zawiadomi", „poinformuje", „powiadomi" |
| F6 | Brak trybu reklamacyjnego lub brak terminu rozpatrzenia | poszukaj sekcji reklamacje/skargi; jeśli brak → F6 |
| F7 | Brak danych rejestrowych (NIP, KRS, adres) | poszukaj NIP/KRS/REGON w całości tekstu; jeśli brak → F7 |
| F8 | Podstawa przetwarzania danych = zgoda + brak jasnej procedury wycofania | „zgoda", „consent" + brak „wycofać zgodę", „odwołać zgodę" |
| F9 | „Tajemnica przedsiębiorstwa" jako odmowa dostępu do własnych danych | „tajemnica przedsiębiorstwa", „poufność" przy opisie danych klienta |
| F10 | „Brak zautomatyzowanych decyzji" przy jednoczesnym profilowaniu | „profilowanie" + „brak zautomatyzowanych decyzji" w tym samym dokumencie |
| F11 | Odpowiedzialność wyłączona za wszystko | „nie ponosi odpowiedzialności", „wyłącza odpowiedzialność" — sprawdź zakres |
| F12 | Brak Reply-To przy adresie tylko do nadawania | „nie odpowiadaj na tę wiadomość" (jeśli regulamin opisuje kanały kontaktu) |

## 3. Raport

Format:
```
## Red flags — [nazwa pliku]

ZNALEZIONO (N flag):
- [F2] Wypowiedzenie bez podania przyczyny — §7 ust. 2: „Operator może zablokować konto
  bez podania przyczyny."
- [F7] Brak NIP/KRS — nie znaleziono danych rejestrowych w całym dokumencie.

NIE ZNALEZIONO: F1, F3, F4, F5, F6, F8, F9, F10, F11, F12

⚠ Wynik NIE ZNALEZIONO nie oznacza, że dokument jest zgodny z prawem — tylko że
automatyczne wykrywanie nie trafiło na te wzorce. Zweryfikuj ręcznie przy pisaniu pisma.
```
