---
name: zrodla-prawa
description: Jak pobrać aktualne, dosłowne brzmienie polskiego przepisu z API ELI Sejmu (Dziennik Ustaw, Monitor Polski) i prawa UE z EUR-Lex. Użyj zawsze, gdy potrzebujesz treści artykułu, sprawdzenia czy przepis obowiązuje, albo publikatora do cytowania.
when_to_use: Pytania o treść ustawy, "czy art. X nadal obowiązuje", tekst jednolity, numer Dz.U., cytowanie przepisu w piśmie, RODO, dyrektywa unijna.
---

# Źródła tekstów prawnych

**Zasada:** przepisu nie cytujesz z pamięci ani z bloga kancelarii. Zawsze ze źródła urzędowego.
Modele mylą numery artykułów i reprodukują brzmienie sprzed nowelizacji — to najczęstsza przyczyna
kompromitacji pisma.

## Prawo polskie — API ELI Sejmu

Bez klucza, bez limitów. Wrapper: `${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh`

```bash
eli.sh szukaj "Kodeks cywilny"            # znajdź akt -> adres DU/rok/poz
eli.sh obowiazuje DU 2004 1800            # czy obowiązuje + czym uchylony + vacatio legis
eli.sh teksty DU 1964 93                  # jakie pliki są dostępne i co znaczą
eli.sh ujednolicony DU 1964 93            # POBIERZ aktualny tekst (PDF)
eli.sh referencje DU 2024 1221            # nowelizacje, teksty jednolite
eli.sh zmiany 2026-08-01                  # co się zmieniło od daty
```

### ⚠ Pułapka, która psuje najwięcej pism

`/text.pdf` i `/text.html` w API zwracają tekst **OGŁOSZONY** — pierwotny, sprzed wszystkich
nowelizacji. Dla Kodeksu cywilnego dostaniesz brzmienie z 1964 roku.

Tekst aktualny to **wyłącznie** plik o `type == "U"` w tablicy `texts[]`. `eli.sh ujednolicony`
wybiera go automatycznie.

Po pobraniu sprawdź nagłówek PDF-u „**Opracowano na podstawie:**" — mówi, do której nowelizacji
tekst jest zaktualizowany. Jeśli w `references["Nowelizacje po tekście jednolitym"]` są pozycje
nowsze, przepis mógł się zmienić po dacie tekstu jednolitego.

### Semantyka wyszukiwania

`title` działa jak `LIKE %fraza%` z ANDem po tokenach, **bez stemmingu**. `łączności` znajdzie 453
akty, `łączność` — zero. Jeśli nie trafiasz, sprawdź formę fleksyjną przez
`https://api.sejm.gov.pl/eli/titles?q=<początek słowa>`. Limit wyników to twarde 500, paginacja
przez `offset`. Parametr `address` jest ignorowany — nie używaj.

### Struktura odpowiedzi

`inForce`: `IN_FORCE` / `NOT_IN_FORCE` / `UNKNOWN`. `status`: polski opis („obowiązujący",
„uchylony", „akt posiada tekst jednolity"). `comments`: odroczone vacatio legis pojedynczych
artykułów — czytaj, gdy powołujesz świeżą ustawę. `references`: mapa relacji, m.in.
„Akty uchylające" z datą uchylenia, „Inf. o tekście jednolitym", „Przepisy wprowadzające".

Nie ma endpointu zwracającego pojedynczy artykuł — `/text.html/{treeId}` zwraca puste body.
Artykuł trzeba wyciąć z PDF-u tekstu ujednoliconego.

## Prawo UE — EUR-Lex

Wersja skonsolidowana (aktualna), polska wersja językowa:
```
https://eur-lex.europa.eu/legal-content/PL/TXT/HTML/?uri=CELEX:0<rok>R<numer>-<RRRRMMDD>
```
RODO: `CELEX:02016R0679-20160504`. Wiodące `0` = wersja skonsolidowana, `3` = akt bazowy.

**Pobieraj przez WebFetch, nie curl** — EUR-Lex odbija curla anty-botem (HTTP 202).
Alternatywa dla curla: `curl -L -H "Accept-Language: pol" https://publications.europa.eu/resource/celex/32016R0679`
(bez nagłówka `Accept-Language` zwraca HTTP 400).

### ⚠ Nie cytuj RODO z serwisów wtórnych

lexlege.pl, privacy-regulation.eu i odo24.pl reprodukują tekst **sprzed sprostowania z 2018 r.**
Potwierdzona rozbieżność: art. 15 ust. 3 — poprawnie jest „informacji udziela się **w powszechnie
stosowanej formie elektronicznej**". Jedyne wiarygodne źródło to EUR-Lex.

## Zanim zaczniesz szukać

Sprawdź `BAZA_WIEDZY/przepisy/` w projekcie. Jeśli przepis już tam jest — **nie zakładaj, że jest aktualny**.
Nawet gdy masz plik z Dz.U., sprawdź przez `eli.sh obowiazuje` czy to tekst jednolity, czy pierwotny
(ogłoszony). Tekst ogłoszony z roku uchwalenia jest **niezdatny do cytowania** — może być kilkadziesiąt
nowelizacji za sobą.

Procedura przy każdym przepisie, przed analizą i wnioskami:
1. `eli.sh obowiazuje DU <rok> <poz>` — status (`IN_FORCE` / `NOT_IN_FORCE`) + czy istnieje tekst jednolity
2. Jeśli `status` zawiera „akt posiada tekst jednolity" — pobierz go: `eli.sh ujednolicony`
3. Sprawdź nagłówek PDF „Opracowano na podstawie:" — do której nowelizacji sięga
4. `eli.sh referencje` — czy są nowelizacje **po** dacie tekstu jednolitego; jeśli tak, przepis mógł się zmienić
5. Dopiero po tych krokach zacznij analizę i wyciągaj wnioski

Po nowym researchu dopisz wynik do bazy (`/kruczek:baza-wiedzy`).

## Delegowanie

Przy większym researchu (kilka ustaw naraz) zleć subagentowi `pobierz-przepis` — pracuje na sonnecie,
nawiguje po API i długich PDF-ach, zwraca gotowe cytaty z publikatorami.
