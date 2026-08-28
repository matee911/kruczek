---
name: pismo
description: "Buduje pismo w sprawie — reklamację, wezwanie, odwołanie, skargę, żądanie z RODO — z argumentacją opartą na zweryfikowanych faktach i dosłownych cytatach przepisów, PDF-em z wdrukowanymi załącznikami, paczką dowodów i osobnym TL;DR dla użytkownika. Użyj, gdy w sprawie trzeba coś wysłać."
argument-hint: "[katalog sprawy] [rodzaj pisma]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/check-deps.sh) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/build-pismo.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kontrola-pisma.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dns.sh *) Bash(mkdir *) Bash(cp *) Bash(zip *) Bash(sha256sum *) Bash(date *) Read Write Edit
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

Przeczytaj `index.md` sprawy: chronologię, ustalenia, **sekcję `⚠ HIPOTEZY`**, dotychczasową
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

**Jednym** wywołaniem AskUserQuestion, zanim zaczniesz research. Pytaj wyłącznie o rzeczy, których
nie ma w teczce ani w `dane-nadawcy.md`:

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

Nowo zweryfikowane przepisy dopisz do bazy (`/kruczek:baza-wiedzy`).

## 4. Zasada, która rozstrzyga wszystkie wątpliwości

**Nie piszemy niczego, czego nie jesteśmy pewni na 100%.**

Nie piszemy niczego kontrowersyjnego ani takiego, co mogłoby zaszkodzić nadawcy: zarzutów bez
pokrycia, sugestii przestępstwa, ocen charakteru, hipotez w trybie oznajmującym.

Trzy udowodnione zarzuty biją dziesięć, z których dwa są do obalenia — bo obalenie dwóch podważa
pozostałe osiem. Gdy się wahasz, czy coś wpisać: nie wpisuj.

Hipotezy z `⚠ HIPOTEZY` albo zostają poza pismem, albo wchodzą **wyłącznie** jako żądanie
wyjaśnienia („wzywam do wskazania, czy…"), nigdy jako twierdzenie.

## 5. Napisz

Przy złożonej subsumpcji zleć subagentowi `napisz-pismo` (opus).

Struktura i numeracja — wg `redagowanie-pism`. Skrót:
`I.` sekcje → `1.` ustępy z **numeracją ciągłą przez całe pismo** → `1)` punkty → `a)` litery → `–` tiret.
Nigdy dwa poziomy tym samym oznaczeniem. W szablonie numerację generują liczniki CSS —
**nie wpisuj cyfr ręcznie**.

Układ: stan faktyczny → ustalenia techniczne (opcjonalnie) → ocena prawna (cytat → subsumpcja →
orzecznictwo) → żądania → skutki bezskutecznego upływu terminu.

Podstawy wyliczaj **od najmocniejszej**. Żądania: co, w jakim terminie, w jakiej formie.
Skutki: tylko kroki, które naprawdę zostaną podjęte.

## 6. Złóż PDF

```
mkdir -p <sprawa>/<RRRR_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/ROBOCZE
cp ${CLAUDE_PLUGIN_ROOT}/templates/pismo.html <wysylka>/ROBOCZE/pismo.html
# uzupełnij treść; z wypełnionych pól USUŃ class="fill"
${CLAUDE_PLUGIN_ROOT}/scripts/build-pismo.py <wysylka>/ROBOCZE/pismo.html \
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

```
/kruczek:kontrola     # mechanicznie: numeracja, nazwy, sumy, wymogi druku
/kruczek:recenzja     # merytorycznie: fakty, prawo, ryzyko, język, siła
```

**Nie melduj gotowości pisma, zanim obie nie przejdą.** Poprawki nanieś i uruchom ponownie.

## 9. Napisz TL;DR dla użytkownika

```
cp ${CLAUDE_PLUGIN_ROOT}/templates/tldr.md <wysylka>/TLDR.md
```

Wypełnij: co wysyłasz i czym, o co chodzi w trzech zdaniach, **co realnie można na tym ugrać**
(tabela scenariuszy z prawdopodobieństwem, korzyścią i kosztem), co trzeba uzupełnić przed wysyłką,
jaki podpis i dlaczego, mocne punkty sprawy i — najważniejsze — **gdzie jesteśmy słabi**.

Bądź uczciwy co do tego, czego pismo nie osiągnie. Kara administracyjna trafia do budżetu państwa,
nie do nadawcy. Postępowanie potrafi trwać dwa lata. Jeśli koszt przewyższa stawkę i jedyną
korzyścią jest satysfakcja — napisz to wprost.

TLDR.md zostaje w katalogu wysyłki i **nie jest wysyłany**.

## 10. Zaktualizuj teczkę

- `manifest.py wstaw <sprawa>/index.md <sprawa>`
- chronologia: wiersz „sporządzenie pisma" + przyszły wiersz z upływem terminu
- TODO: nadanie, archiwizacja potwierdzenia, termin kontrolny
- sekcja „Ścieżka eskalacji", jeśli pismo ją zapowiada

## 11. Zamelduj

Krótko: gdzie leży PDF i TLDR.md, ile stron, **co zostało do uzupełnienia**, jak i dokąd wysłać,
jaki jest termin kontrolny. Nie streszczaj treści pisma — użytkownik ma TL;DR.
