---
name: weryfikuj
description: Adwersaryjny cross-check pisma przed wysyłką — czy przepisy obowiązują, czy cytaty są dosłowne, czy sygnatury istnieją, czy daty i sumy się zgadzają, czy hipotezy nie awansowały na fakty, i gdzie są słabe punkty, które druga strona może wykorzystać. Użyj zawsze przed nadaniem czegokolwiek.
argument-hint: "[ścieżka do pisma lub katalogu wysyłki]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(pdftotext *) Bash(sha256sum *) Read
---

# Weryfikacja pisma przed wysyłką

Cel: `$ARGUMENTS`

Czytasz pismo jak przeciwnik. Twoim zadaniem nie jest je pochwalić, tylko znaleźć w nim to,
co druga strona wykorzysta. Zakładaj, że coś jest nie tak, i szukaj tego.

## 1. Wyciągnij tekst

Jeśli to PDF — `pdftotext -layout <plik> -`. Jeśli HTML — przeczytaj plik.

## 2. Sprawdź każdy powołany przepis — osobno

Dla każdego artykułu w piśmie:

```
${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh obowiazuje DU <rok> <poz>
```

Weryfikuj cztery rzeczy:
- **Czy akt obowiązuje?** `inForce: NOT_IN_FORCE` albo status „uchylony" = pismo do przepisania.
- **Czy publikator jest aktualny?** Tekst jednolity mógł się zmienić; stary numer Dz.U. w piśmie
  to sygnał, że cytat pochodzi z nieaktualnego źródła.
- **Czy cytat jest dosłowny?** Porównaj słowo w słowo z tekstem ujednoliconym (typ `U`).
  Uwaga na przepisy o zmienionej redakcji — w internecie krąży stare brzmienie.
- **Czy przepis mówi to, co pismo twierdzi, że mówi?** Najczęstszy błąd to powołanie artykułu
  o zbliżonym temacie, który reguluje coś innego.

## 3. Sprawdź każdą sygnaturę orzeczenia

```
${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh saos "<fraza z tezy>"
${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh uodo "<fraza>"
```

Orzeczenia, którego nie potwierdzisz w źródle — **wykreśl z pisma**. Sygnatura wymyślona lub
przekręcona jest gorsza niż jej brak. Sprawdź też, czy teza faktycznie dotyczy tego, do czego
jest przywołana, i czy orzeczenie nie zapadło na tle **uchylonego** stanu prawnego.

## 4. Sprawdź fakty i daty

- Każda data w piśmie musi zgadzać się z chronologią w `index.md` i z dowodem w `ARCHIWUM/`.
- Policz terminy: czy „14 dni od doręczenia" wypada tam, gdzie pismo twierdzi.
- Czy dni tygodnia i daty się zgadzają (jeśli pismo je podaje).

## 5. Sprawdź sumy kontrolne

```
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz <sprawa>
```
Każda suma SHA-256 podana w treści pisma musi odpowiadać faktycznemu plikowi. Sprawdź ręcznie
(`sha256sum`) — to zdanie w piśmie jest zobowiązaniem.

## 6. Sprawdź, czy hipotezy nie awansowały na fakty

Porównaj sekcję `⚠ HIPOTEZY` w `index.md` z treścią pisma. Jeśli coś, co jest hipotezą,
zostało w piśmie napisane w trybie oznajmującym — to najpoważniejszy błąd, jaki tu znajdziesz.
Przeciwnik obali jedno niepotwierdzone twierdzenie i podważy całą resztę.

## 7. Linia obrony drugiej strony

Wejdź w rolę pełnomocnika adresata. Przeczytaj pismo jeszcze raz i odpowiedz:

- **Co zaneguje.** Które twierdzenia są najłatwiejsze do podważenia — zbyt ogólne, niepoparte
  konkretnym dowodem, oparte na jednym źródle, albo sformułowane tak, że wystarczy jedno „nie"?
- **Co przemilczy.** Które żądania adresat może zignorować bez prawnych konsekwencji — bo termin
  odpowiedzi nie wynika z przepisu, bo sankcja jest niepewna, bo brak wskazania podstawy dochodzenia
  roszczeń?
- **Co obróci.** Czy jakieś zdanie w piśmie można przytoczyć przeciwko nadawcy — przyznanie faktu,
  rezygnacja z zarzutu, żądanie, które wygląda na nieadekwatne?
- **Czego brakuje w dowodach.** Luka w chronologii, dowód tylko pośredni, dokument bez podpisu,
  OCR który może być kwestionowany jako wierny zapis.
- **Zarzuty procesowe.** Czy adresat może kwestionować formę pisma, właściwość organu, termin
  przedawnienia albo brak wezwania przedsądowego?

Każdy punkt tej analizy idzie do raportu jako osobna sekcja — nawet jeśli nie blokuje wysyłki.
Nadawca musi wiedzieć, na co się przygotować po drugiej stronie.

## 8. Sprawdź kompletność

- Czy zostały niewypełnione pola `class="fill"` / `[nawiasy kwadratowe]`?
- Czy każdy załącznik z listy istnieje i jest wdrukowany albo dołączony?
- Czy każde żądanie ma termin?
- Czy adresat, adres i sposób doręczenia są kompletne?
- Czy zapowiedziane kroki eskalacyjne są realne i mają podstawę prawną?

## 9. Raport

Wypisz ustalenia w kolejności wagi:

**🔴 BLOKUJE WYSYŁKĘ** — uchylony przepis, niedosłowny cytat, niepotwierdzona sygnatura,
hipoteza jako fakt, niezgodna data lub suma kontrolna, puste pole.

**🟠 OSŁABIA PISMO** — cytat prawidłowy, ale nie na temat; żądanie bez terminu; groźba
eskalacji, której nie da się zrealizować.

**🟡 LINIA OBRONY ADRESATA** — po jednym punkcie na każdy ze scenariuszy z kroku 7:
co zaneguje, co przemilczy, co obróci, luki dowodowe, możliwe zarzuty procesowe.
Każdy punkt z krótką rekomendacją: czy wzmocnić pismo, czy zaakceptować ryzyko.

**🟢 SPRAWDZONE** — jedna linia zbiorcza: ile przepisów i sygnatur potwierdzono w źródłach.

Jeśli nie ma nic w kategorii 🔴 — powiedz wprost, że pismo jest gotowe do wysyłki.
Nie dorabiaj zastrzeżeń na siłę.
