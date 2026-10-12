---
name: pismo
description: "Buduje pismo w sprawie — reklamację, wezwanie, odwołanie, skargę, żądanie z RODO — z argumentacją opartą na zweryfikowanych faktach i dosłownych cytatach przepisów, PDF-em z wdrukowanymi załącznikami, paczką dowodów i osobnym TL;DR dla użytkownika. Użyj, gdy w sprawie trzeba coś wysłać."
argument-hint: "[katalog sprawy] [rodzaj pisma]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/check-deps.sh) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/build_pismo.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kontrola_pisma.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh *) Bash(mkdir *) Bash(cp *) Bash(zip *) Bash(sha256sum *) Bash(date *) Read Write Edit AskUserQuestion
---

# Budowa pisma

Argumenty: `$ARGUMENTS`

Kolejność jest sztywna: **najpierw fakty, potem prawo, potem dopiero pismo.** Nie pisz ani jednego
zdania, zanim nie masz zweryfikowanego materiału — inaczej będziesz naginał fakty do wcześniej
napisanej tezy.

Konwencję redakcyjną (skład, numeracja, adresat, załączniki, podpis) masz w skillu
`redagowanie-pism`. Nie improwizuj formatowania.

---

## 0. Sprawdź zależności

```
${CLAUDE_PLUGIN_ROOT}/scripts/check-deps.sh
```

Rób to na starcie, nie w połowie roboty. Jeśli brak silnika PDF (weasyprint / Chrome
lub Chromium / wkhtmltopdf) — poinformuj użytkownika wprost, gotową komendą instalacji
z wyjścia skryptu, i przerwij zanim zaczniesz pisać pismo.

## 1. Wczytaj sprawę i dane nadawcy

Zapis do teczki idzie przez `teczka.py` — protokół w skillu `konwencje-teczki` („Zapis do teczki — teczka.py”). Jeśli sprawa jest w starym formacie (jest `index.md`, nie ma `sprawa.json`) — zatrzymaj się i zaproponuj `/kruczek:migruj <sprawa>`.

Przeczytaj `index.md` sprawy: bloki „Chronologia”, „Terminy” i „Zadania”, ustalenia, **sekcję `⚠ HIPOTEZY`**, dotychczasową
podstawę prawną, manifest. Przeczytaj wersje tekstowe kluczowych dowodów z `ARCHIWUM/`.

Sprawdź `_SZABLONY/dane-nadawcy.md` i status pól krytycznych w `CLAUDE.md` (sekcja
„Dane nadawcy" — ✓ / ⚠ BRAK). **Pola ✓ są gotowe — nie pytaj o nie ponownie.** Pola
⚠ BRAK dopytaj w kroku 2. Nigdy nie wpisuj do pisma tekstu zastępczego („[NAZWISKO —
UZUPEŁNIĆ]" i podobnych) zamiast prawdziwej wartości — to trafia do dokumentu, który
zostaje wysłany.

Jeśli `_SZABLONY/dane-nadawcy.md` nie istnieje, skopiuj szablon:
```
cp ${CLAUDE_PLUGIN_ROOT}/templates/dane-nadawcy.md <projekt>/_SZABLONY/
```

## 2. Dopytaj — raz, o to, czego naprawdę nie wiesz

**Jednym** wywołaniem AskUserQuestion (najwyżej 4 pytania), zanim zaczniesz research — nie pytaj
w treści odpowiedzi. Pytaj wyłącznie o rzeczy, których nie ma w teczce ani w `dane-nadawcy.md`:

- **rodzaj pisma** — reklamacja / wezwanie przedsądowe / odwołanie / żądanie z RODO / skarga do
  organu / zawiadomienie / odpowiedź na pismo
- **czego użytkownik chce osiągnąć** — pieniądze / naprawa / zaprzestanie / informacja / ukaranie.
  To determinuje całą konstrukcję pisma, a nie da się tego wywnioskować z dowodów
- **status nadawcy** — odczytaj z pola **Występuję jako** w nagłówku `index.md` sprawy (konsument /
  przedsiębiorca / w cudzym imieniu — inne podstawy prawne, inny katalog roszczeń). Dopytaj tylko,
  jeśli pole jest puste. Gdy sprawa jest prowadzona w cudzym imieniu, nadawcą pisma jest **osoba
  reprezentowana**, a pełnomocnictwo musi trafić do załączników
- brakujące dane twarde: kwota, numer rachunku, numer zgłoszenia, data zdarzenia
- pola oznaczone ⚠ BRAK w sekcji „Dane nadawcy" w CLAUDE.md (krok 1)

Odpowiedzi dotyczące danych stałych (adres, NIP, sposób wysyłki, podpis) **dopisz do
`dane-nadawcy.md`** — żeby przy następnym piśmie już nie pytać.

## 3. Fact-checking — przed pisaniem, nie po

To jest etap, którego nie wolno pominąć.

**Fakty.** Dla każdego twierdzenia, które ma trafić do pisma, wskaż plik w `ARCHIWUM/`, który je
potwierdza. Twierdzenie bez pliku nie wchodzi do pisma. Sprawdź daty i kwoty w dowodzie, nie
w chronologii — chronologia bywa przepisana z błędem.

**Adresat.** Zweryfikuj dane rejestrowe **teraz**, nie ufaj temu, co jest w teczce sprzed miesiąca:
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh pelny <NIP>
```
Adres z rejestru, nie ze strony WWW. Sprawdź formę prawną — spółka cywilna nie jest podmiotem,
adresatami są wspólnicy imiennie.

**Ustalenia techniczne**, jeśli sprawa je ma i mogły się zmienić (DNS, przekierowania, treść strony):
```
${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh raport <domena> > <sprawa>/ARCHIWUM/RRRR-MM-DD_dns_<domena>.md
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh strona <URL>
```

**Prawo.** Najpierw `BAZA_WIEDZY/przepisy/`. Czego tam nie ma:
```
${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh szukaj "<tytuł ustawy>"
${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh obowiazuje DU <rok> <poz>
${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh ujednolicony DU <rok> <poz>
```
Przy większym researchu zleć równolegle `pobierz-przepis` i `szukaj-orzeczen`.

**Sprawdź, czy przepis nadal obowiązuje.** Polskie prawo bywa uchylane hurtowo, a poradniki
w internecie zostają na lata. Przepis uchylony w piśmie kompromituje całość.

Nowo zweryfikowane przepisy zaproponuj użytkownikowi dopisać do bazy (`/kruczek:baza-wiedzy`).

Tekst każdego przepisu, który ma trafić do pisma, zapisz jako plik w `<wysylka>/ROBOCZE/przepisy/` (wynik
`eli.sh ujednolicony` / `eurlex.sh`) albo wskaż istniejący plik w `BAZA_WIEDZY/przepisy/`, i policz jego SHA-256
(`sha256sum`). Agent cytuje z pliku, nie z Twojego streszczenia.

## 4. Zasada, która rozstrzyga wszystkie wątpliwości

**Nie piszemy niczego, czego nie jesteśmy pewni na 100%.**

Nie piszemy niczego kontrowersyjnego ani takiego, co mogłoby zaszkodzić nadawcy: zarzutów bez
pokrycia, sugestii przestępstwa, ocen charakteru, hipotez w trybie oznajmującym.

Trzy udowodnione zarzuty biją dziesięć, z których dwa są do obalenia — bo obalenie dwóch podważa
pozostałe osiem. Gdy się wahasz, czy coś wpisać: nie wpisuj.

Hipotezy z `⚠ HIPOTEZY` albo zostają poza pismem, albo wchodzą **wyłącznie** jako żądanie
wyjaśnienia („wzywam do wskazania, czy…"), nigdy jako twierdzenie.

## 5. Napisz — zawsze przez agenta `napisz-pismo`

Treść pisma pisze agent `napisz-pismo` (opus) — **zawsze**, nie tylko przy trudnej kwalifikacji. Model tej
komendy obowiązuje tylko do pierwszej odpowiedzi użytkownika; agent pracuje na swoim modelu niezależnie od
modelu rozmowy.

1. Utwórz katalog wysyłki (`mkdir -p <sprawa>/<RRRR_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/ROBOCZE`, nazwa jak
   w kroku 6) i zapisz brief do `<wysylka>/ROBOCZE/BRIEF.md`:
   - **Fakty** — numerowane, jedno zdarzenie na punkt, data bezwzględna, przy każdym plik z `ARCHIWUM/`;
   - **Hipotezy** z `⚠ HIPOTEZY` — osobno, z adnotacją „tylko jako żądanie wyjaśnienia”;
   - **Przepisy** — akt, artykuł, publikator, ścieżka do pliku z tekstem i jego SHA-256 (krok 3), potwierdzenie,
     że obowiązywał w dacie zdarzenia;
   - **Orzeczenia** — sąd, data, sygnatura, teza, źródło;
   - **Decyzje użytkownika** — odpowiedzi z AskUserQuestion z kroku 2, dosłownie (rodzaj pisma, cel, status
     nadawcy, kwoty, numery);
   - **Adresat** z rejestru (krok 3) i **nadawca** z `dane-nadawcy.md`;
   - **Żądania i termin**, jeśli użytkownik je określił.
2. Zleć agentowi `napisz-pismo`: ścieżkę do `BRIEF.md` i katalogu sprawy. Agent zapisuje treść do
   `<wysylka>/ROBOCZE/tresc.html` i zwraca: ścieżkę, pola do uzupełnienia, „Gdzie jesteśmy słabi”,
   „Fakty z briefu nieużyte” i „Twierdzenia spoza briefu”.
3. „Twierdzenia spoza briefu” sprawdź przed krokiem 6: każde musi mieć plik w `ARCHIWUM/` albo wypada — odeślij
   agentowi konkretną uwagę. Treści pisma nie przepisuj sam; poprawki merytoryczne robi agent.

Konwencja redakcyjna (struktura, numeracja klasami szablonu, załączniki) — `redagowanie-pism`; agent ją stosuje.

## 6. Złóż PDF

```
mkdir -p <sprawa>/<RRRR_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/ROBOCZE
cp ${CLAUDE_PLUGIN_ROOT}/templates/pismo.html <wysylka>/ROBOCZE/pismo.html
# uzupełnij nagłówek (nadawca, adresat, meta, podpis; z wypełnionych pól USUŃ class="fill");
# treść między znacznikami KRUCZEK:TRESC wstawia --tresc
${CLAUDE_PLUGIN_ROOT}/scripts/build_pismo.py <wysylka>/ROBOCZE/pismo.html \
    --tresc <wysylka>/ROBOCZE/tresc.html \
    -o <wysylka>/<RRRR-MM-DD>_<Rodzaj>_<Adresat>.pdf \
    -z <sprawa>/ARCHIWUM/<dowod>.md:"Tytuł załącznika" \
    --stopka "<Rodzaj pisma> z <data>"
```

Marginesy (25/20/25/20 mm) i font ustawia skrypt — nie zmieniaj ich.

**Tytuł załącznika podany w `-z` musi być identyczny z tym, którym posługujesz się w treści pisma.**
Rozjazd nazw to klasyczny powód sporu o kompletność przesyłki.

Pól, których nie znasz, **nie zmyślaj** — zostaw `class="fill"` i wypisz je użytkownikowi jako
listę do uzupełnienia.

W `ROBOCZE/README.md` zostaw gotową komendę regeneracji.

## 7. Spakuj dowody

```
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sumy <sprawa>/ARCHIWUM
(cd <sprawa>/ARCHIWUM && zip -X ../<wysylka>/dowody.zip *)
```

## 8. Kontrola i recenzja — obowiązkowo, w tej kolejności

1. **Kontrola mechaniczna:** `/kruczek:kontrola` — numeracja, nazwy, sumy, wymogi druku.
2. **Recenzja merytoryczna:** zleć **równolegle, w jednej wiadomości** dwóm agentom, każdemu ze ścieżką do PDF-u,
   do `ROBOCZE/BRIEF.md` i do katalogu sprawy:
   - `weryfikuj-cytaty` — czy przepisy obowiązują (także w dacie zdarzenia), cytaty dosłowne, sygnatury istnieją,
     daty i sumy się zgadzają, linia obrony adresata;
   - `recenzuj` — fakty kontra dowody i brief, ryzyko dla nadawcy, język, siła argumentacji.

   Komendę `/kruczek:recenzja` (podpowiedź dla użytkownika) uruchamia tylko użytkownik — z wnętrza tej
   komendy model jej nie wywoła. Oba raporty złóż w jeden według sekcji Raport z
   `${CLAUDE_PLUGIN_ROOT}/skills/recenzja/SKILL.md` (🔴 → 🟠 → 🟡 → 🟢). Recenzja przechodzi, gdy nie ma 🔴
   w złożonym raporcie.
3. **Poprawki — najwyżej jedna runda automatyczna.** Pozycje 🔴 odeślij do `napisz-pismo` (poprawia `tresc.html`),
   złóż PDF ponownie (krok 6) i powtórz kontrolę mechaniczną. Ponowna recenzja tylko na zmienionych sekcjach:
   każdemu agentowi daj diff `tresc.html` (przed/po — kopię sprzed poprawki zachowaj jako
   `ROBOCZE/tresc.przed.html`) i poprzednią listę 🔴 do odhaczenia — bez pełnej recenzji od nowa.
4. Jeśli po tej rundzie zostaje cokolwiek 🔴 albo poprawka wymaga decyzji (usunąć zarzut, zmienić żądanie) —
   zapytaj użytkownika przez AskUserQuestion, co robimy; kolejna runda tylko po jego odpowiedzi.

**Nie melduj gotowości pisma, dopóki kontrola mechaniczna nie przechodzi albo w raportach zostaje
cokolwiek 🔴.**

## 9. Napisz TL;DR dla użytkownika

```
cp ${CLAUDE_PLUGIN_ROOT}/templates/tldr.md <wysylka>/TLDR.md
```

Wypełnij: co wysyłasz i czym, o co chodzi w trzech zdaniach, **co realnie można na tym ugrać**
(tabela scenariuszy z prawdopodobieństwem, korzyścią i kosztem), co trzeba uzupełnić przed wysyłką,
jaki podpis i dlaczego, mocne punkty sprawy i — najważniejsze — **gdzie jesteśmy słabi**.

Sekcję „gdzie jesteśmy słabi” weź z wyniku `napisz-pismo` i uzupełnij o pozycje 🟠/🟡 z recenzji (krok 8).

Wypełnij też **„Dane do wysyłki”** dla każdego kanału, którym pismo pójdzie — tak, żeby
użytkownik tylko przekleił: e-Doręczenia → adres ADE adresata, tytuł i krótki opis do formularza;
Envelo → tytuł roboczy i adresat; e-mail → Do, DW, temat i gotowa treść. Przy e-Doręczeniach
**nie każ podpisywać PDF-u** (skill `redagowanie-pism`, sekcja „Podpis”).

Bądź uczciwy co do tego, czego pismo nie osiągnie. Kara administracyjna trafia do budżetu państwa,
nie do nadawcy. Postępowanie potrafi trwać dwa lata. Jeśli koszt przewyższa stawkę i jedyną
korzyścią jest satysfakcja — napisz to wprost.

TLDR.md zostaje w katalogu wysyłki i **nie jest wysyłany**.

## 10. Zaktualizuj teczkę

- `manifest.py wstaw <sprawa>/index.md <sprawa>`. Jeśli to polecenie (albo `sumy` z kroku 7, albo odświeżenie
  `index.md` przez `teczka.py`) kończy się błędem lub ostrzeżeniem (np. „uszkodzone znaczniki manifestu — popraw
  ręcznie”, „index.md nie odświeżony”), pokaż komunikat użytkownikowi i nie edytuj `index.md` sam — w tym pliku
  są notatki użytkownika
- wątek adresata: odczytaj `watki` z `sprawa.json` (czytać wolno, edytować nie). Jeśli jest wątek z tym
  samym `adresat` — użyj go (wątek = korespondencja tam i z powrotem z jednym adresatem; kolejne pismo
  do tej samej firmy to ten sam wątek). Jeśli nie ma — `teczka.py watek <sprawa> <id> --adresat "<adresat>"`
- zadanie (uruchom; jego treść to podpowiedź dla użytkownika): `teczka.py zadanie <sprawa> "Nadaj <pismo> (<kanał>) i zarchiwizuj potwierdzenie nadania — potem /kruczek:chronologia nadanie" --watek <id>`;
  razem z nim oznacz jako `zrobione` otwarte zadania startowe „Przygotować pismo” i „Nadać i zarchiwizować
  potwierdzenie nadania” (`teczka.py zrobione <sprawa> <id>`, po jednym wywołaniu na zadanie; id z bloku „Zadania”)
- w `TLDR.md` pole „Termin, który wyznaczasz” wypełnione długością i podstawą — z niego
  `/kruczek:chronologia` (podpowiedź dla użytkownika) weźmie termin przy nadaniu. Termin wymaga `--termin` i `--podstawa` z treści pisma
  albo przepisu; nie znasz podstawy — zapytaj użytkownika, nie zgaduj
- sekcja „Ścieżka eskalacji”, jeśli pismo ją zapowiada (wolny tekst)

## 11. Zamelduj

Krótko: gdzie leży PDF i TLDR.md, ile stron, **co zostało do uzupełnienia**, jak i dokąd wysłać
(z danymi do wysyłki z TL;DR: tytuł/opis, Do/DW, temat), że po nadaniu użytkownikowi wystarczy `/kruczek:chronologia` (termin weźmie z TL;DR). Nie streszczaj treści pisma — użytkownik ma TL;DR.
