---
name: konwencje-teczki
description: Zasady prowadzenia teczki sprawy (wskazują KONWENCJE.md) i protokół zapisu zdarzeń, terminów i zadań przez teczka.py. Obowiązują przy każdej pracy na plikach sprawy.
when_to_use: Praca na plikach w katalogu sprawy, dodawanie dowodów, edycja index.md, przygotowanie wysyłki, pytania o strukturę teczki.
user-invocable: false
---

# Konwencje teczki sprawy

Zasady teczki (archiwum, nazwy, sumy, wersje tekstowe, chronologia, wysyłka, hipotezy): przeczytaj
`${CLAUDE_PLUGIN_ROOT}/templates/KONWENCJE.md`. Ten wzorzec w pluginie ma pierwszeństwo: jeśli kopia
`KONWENCJE.md` w projekcie się od niego różni, obowiązuje wzorzec, a kopię odśwież (zaproponuj użytkownikowi `/kruczek:migruj`, krok 0).

## Zapis do teczki — teczka.py

Zdarzenia, terminy i zadania sprawy są w `sprawa.json`. Zapisuje je **wyłącznie**
`${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py`; po każdym zapisie sam odświeża tabele „Chronologia”,
„Terminy” i „Zadania” w `index.md`. Nie edytuj `sprawa.json` ani bloków `<!-- kruczek:… -->`.
Wolny tekst `index.md` (ustalenia, hipotezy, podstawa prawna, eskalacja) edytujesz jak dotąd.

**Stara sprawa** (jest `index.md`, nie ma `sprawa.json`): zatrzymaj się. Nie dopisuj do starej tabeli —
powiedz jednym zdaniem, że ta sprawa jest w starym formacie, i zaproponuj `/kruczek:migruj <sprawa>`.

**Typ zdarzenia = kierunek:**

| Typ | Kiedy |
|---|---|
| `nadanie` | Ty wysyłasz pismo (z `--termin` i `--podstawa`, jeśli pismo albo przepis wyznacza termin adresatowi) |
| `doreczenie` | Twoje pismo doszło do adresata (EPO, Envelo, potwierdzenie odbioru) |
| `odpowiedz` | adresat odpisał Tobie |
| `wplyw` | przyszło do Ciebie inne pismo, np. decyzja — z `--termin`, jeśli wyznacza **Tobie** termin (data = dzień doręczenia do Ciebie, także po awizo) |
| `fakt`, `telefon`, `inne` | notatka; przy fakcie bez pliku `--pewnosc` |

**Wątek** to korespondencja z jednym adresatem w tej sprawie, tam i z powrotem (pismo → odpowiedź →
kontra → …). Nie zakładaj nowego wątku na każde pismo. Nowy wątek tylko dla nowego adresata
(np. UODO obok firmy): `teczka.py watek <sprawa> <id> --adresat "<nazwa>"`.

**Termin:** tylko gdy wyznacza go pismo albo przepis — długość (`14d`, `2t`, `1m`, `1r`) i podstawa
(„art. 7a ust. 1 u.p.k.”, „wyznaczony w piśmie”). Nie znasz podstawy — zapytaj, nie zgaduj.

**Gdy teczka.py pyta o `--dotyczy`** (czeka naraz kilka Twoich pism w wątku): pokaż użytkownikowi
pisma z komunikatu jednym AskUserQuestion i powtórz polecenie z `--dotyczy <id>`.
**„Sprawdź datę doręczenia”** zamykasz wpisaniem doręczenia (`teczka.py zdarzenie <sprawa> --typ doreczenie
--data <data z EPO> --watek <w>`), nie przez `zrobione` — dopiero doręczenie przelicza termin adresata
z szacunku na datę od doręczenia. `zrobione` tylko wtedy, gdy daty doręczenia nie da się ustalić.
**Gdy po odpowiedzi wypisze „nadal otwarte …”**: zapytaj, czy ta odpowiedź dotyczy też tamtego pisma;
jeśli tak — `teczka.py zrobione <sprawa> <id>` dla wskazanych zadań, po jednym.

**Pomyłka:** `teczka.py popraw-zdarzenie <sprawa> <id> --data/--opis/--godzina/--pewnosc/--dowod`;
zły typ albo wątek ostatniego wpisu → `teczka.py cofnij-zdarzenie <sprawa> <id>` i wpis od nowa.

**Kod wyjścia 1 przy zapisie do jednej sprawy** (`nowa`, `zdarzenie`, `zadanie`, `watek`,
`zrobione`, `popraw-zdarzenie`, `cofnij-zdarzenie`, `zamknij`, `otworz`, `przelicz`, `migruj --zapisz`) = nic nie zapisano: pokaż komunikat
użytkownikowi, nie ponawiaj w ciemno. Przy `dzien-wolny` i `co-robic` kod 1 znaczy, że część spraw
zgłosiła błąd — czytaj sekcję BŁĘDY (reszta mogła się wykonać).
Kod 0 z linią `uwaga:` (np. „zapisano, ale index.md nie odświeżony”) = zapis jest, tylko `index.md`
się nie odświeżył: nie powtarzaj polecenia (zdublujesz zdarzenie), powiedz o tym użytkownikowi.

Daty względne zawsze zamieniaj na bezwzględne (`date +%F`). Przyszłe rzeczy (snapshot za 2 tygodnie)
to zadania: `teczka.py zadanie <sprawa> "<opis>" --aktywne-od <data>`.

**Twój termin (np. zawity na odwołanie, skargę) liczy kod, nie Ty.** Biegnie od pisma, które doszło do
Ciebie → `teczka.py zdarzenie <sprawa> --typ wplyw --data <dzień doręczenia> --watek <w> --termin <długość>
--podstawa "<przepis>"` (kod przesuwa koniec z soboty i święta i przelicza go po `dzien-wolny`). Pismo jest
już wpisane bez terminu: jeśli to ostatnie zdarzenie — `cofnij-zdarzenie` i wpisz je ponownie z `--termin`;
jeśli nie — powiedz to użytkownikowi i ustal z nim datę końca, zanim ją zapiszesz.
`zadanie <sprawa> "<opis z podstawą>" --termin <data>` tylko wtedy, gdy dokument podaje datę końca wprost
(np. „do 30.11.2026”) — z podstawą w opisie.
