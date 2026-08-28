# Dobór modeli w kruczku

Zasada: **model dobierany do rodzaju pracy, nie do ważności sprawy.** Liczenie sum kontrolnych jest
tak samo ważne jak pisanie wezwania, ale nie wymaga tego samego rozumowania.

Wartości dopuszczalne w Claude Code: `haiku`, `sonnet`, `opus`, `inherit`.
(`fable` jest opcją po stronie Cowork, nie polem `model` w definicji subagenta.)

## Mapa

| Komponent | Typ | Model | Effort | Uzasadnienie |
|---|---|---|---|---|
| `komendy` | skill | `haiku` | low | wypisanie statycznej tabeli |
| `dowod` | skill | `haiku` | low | kopiowanie, sumy, wywołanie skryptu — ustalona sekwencja |
| `chronologia` | skill | `haiku` | low | jeden wiersz w tabeli, znany format |
| `status` | skill | `haiku` | low | zebranie pól z plików i posortowanie |
| `analiza-eml` | skill | `haiku` | low | całą pracę wykonuje `eml_forensics.py` |
| `zrodla-dns-poczta` | skill | `haiku` | low | odpytanie DoH i przepisanie rekordów |
| `kontrola` | skill | `haiku` | low | porównywanie łańcuchów, zero uznaniowości |
| `analizuj-eml` | agent | `haiku` | — | uruchamia skrypt i zestawia wyniki |
| `archiwizuj` | agent | `haiku` | — | porównywanie sum, deterministyczne |
| `dopisz-chronologie` | agent | `haiku` | — | wstawianie wierszy, arytmetyka dat |
| `fakt` | skill | `haiku` | low | dopisanie jednego faktu do chronologii — ustalony format |
| `metadane` | skill | `haiku` | low | ekstrakcja metadanych pliku, wynik deterministyczny |
| `ustal-strone` | agent | `haiku` | — | wywołanie API i przepisanie pól JSON |
| `sprawdz-zalaczniki` | agent | `haiku` | — | numeracja i sumy kontrolne — wynik deterministyczny |
| `archiwa` | skill | `sonnet` | — | delegacja do `archiwizuj-strone`; trzeba ocenić, co warto archiwizować |
| `archiwizuj-strone` | agent | `sonnet` | — | CDX/Wayback/curl — nawigacja po kilku API, część zablokowana |
| `gmail` | skill | `sonnet` | — | wyszukiwanie i zestawianie wiadomości przez Gmail MCP |
| `nowy-projekt` | skill | `sonnet` | medium | rozmowa z użytkownikiem o kontekście projektu |
| `nowa-sprawa` | skill | `sonnet` | medium | ustalenie celu sprawy i wstępna kwalifikacja |
| `baza-wiedzy` | skill | `sonnet` | medium | streszczanie wniosków praktycznych z przepisu |
| `ocr-transkrypcja` | skill | `sonnet` | medium | odczyt obrazu, polskie diakrytyki |
| `sprawdz-klauzule` | agent | `sonnet` | — | analiza klauzul abuzywnych — wymaga oceny, nie tylko wykrycia |
| `transkrybuj` | agent | `sonnet` | — | haiku gubi „ą/ę/ł" i myli podobne litery w skanach |
| `pobierz-przepis` | agent | `sonnet` | — | nawigacja po API i wycinanie artykułu z 300-stronicowego PDF |
| `szukaj-orzeczen` | agent | `sonnet` | — | wiele źródeł, część zablokowana, trzeba obchodzić |
| `podsumowanie` | skill | `opus` | high | synteza sprawy — ocena stanu, kwalifikacja ryzyk |
| `pismo` | skill | `opus` | high | subsumpcja, dobór podstaw, konstrukcja wywodu |
| `weryfikuj` | skill | `opus` | high | najdroższe miejsce na błąd w całym procesie |
| `eskalacja` | skill | `opus` | high | ocena ryzyka i realnych szans, właściwość organów |
| `napisz-pismo` | agent | `opus` | — | przyporządkowanie faktów do przesłanek normy |
| `weryfikuj-cytaty` | agent | `opus` | — | adwersaryjne szukanie błędu, który zauważy druga strona |
| `recenzja` | skill | `opus` | high | ostatnia bramka: fakty, ryzyko, język, siła |
| `recenzuj` | agent | `opus` | — | ocena ryzyka prawnego dla nadawcy i skuteczności pisma |
| `konwencje-teczki` | skill | dziedziczy | — | wiedza tła, nie wykonuje zadania |
| `redagowanie-pism` | skill | dziedziczy | — | jw. |
| `zrodla-prawa`, `zrodla-orzecznictwa`, `zrodla-rejestry` | skille | dziedziczy | — | jw. |
| `fallback-przegladarka` | skill | dziedziczy | — | jw. |

## Dlaczego akurat tak

**Praca mechaniczna → `haiku`.** Wszędzie tam, gdzie właściwą robotę wykonuje skrypt
(`eml_forensics.py`, `manifest.py`, `podmiot.sh`), model tylko uruchamia go i formatuje wynik.
Wynik jest deterministyczny, więc mocniejszy model niczego nie poprawi — a analiza jednej
wiadomości `.eml` z pięcioma technikami obfuskacji kosztuje wtedy ułamek tego, co kosztowałaby
na opusie.

**Odczyt obrazu → `sonnet`, nie `haiku`.** To jedyne miejsce, gdzie zeszliśmy z oszczędności.
Polskie znaki diakrytyczne w skanach i zdjęciach to realny problem; błędny odczyt trafia potem
do pisma jako cytat i jest nie do wykrycia bez porównania z oryginałem.

**Research → `sonnet`.** Odpytanie API i wycięcie artykułu z PDF-u wymaga orientacji, ale nie
rozumowania prawniczego. Agenci researchowi zwracają surowy materiał; ocenia go dopiero opus.

**Rozumowanie prawne → `opus`.** Subsumpcja, ocena ciężaru dowodu, dobór trybu eskalacji
i adwersaryjna weryfikacja. Tu błąd kosztuje najwięcej: pismo z uchylonym przepisem albo
wymyśloną sygnaturą kompromituje całą sprawę i daje drugiej stronie darmowy argument.

**Dwie bramki przed wysyłką, dwa różne modele.** `/kruczek:kontrola` (haiku) sprawdza to, co ma
jednoznaczną odpowiedź: czy numer załącznika się zgadza, czy suma kontrolna pasuje, czy zostało
puste pole. `/kruczek:recenzja` (opus) sprawdza to, co wymaga oceny: czy fakt ma pokrycie w dowodzie,
czy zdanie nie zaszkodzi nadawcy, czy pismo w ogóle zadziała. Rozdzielenie ich jest celowe —
gdyby kontrolę mechaniczną robił opus, płacilibyśmy za rozumowanie tam, gdzie wystarczy porównanie
łańcuchów, a przy okazji ryzykowalibyśmy, że model „domyśli się" zamiast porównać.

## Jak to zmienić u siebie

Pole `model` w nagłówku YAML pliku skilla (`skills/<nazwa>/SKILL.md`) albo agenta
(`agents/<nazwa>.md`). `inherit` oznacza model bieżącej sesji.

Chcesz taniej — zejdź z `opus` na `sonnet` w `pismo` i `weryfikuj`, ale **zostaw `weryfikuj`
możliwie wysoko**: to ostatnia bramka przed wysyłką i jedyne miejsce, gdzie wyłapiesz uchylony
przepis albo hipotezę udającą fakt.
