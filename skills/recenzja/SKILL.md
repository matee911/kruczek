---
name: recenzja
description: "Recenzja gotowego pisma i załączników przed wysyłką — czy wszystko zgadza się z faktami, dowodami i prawem, czy nie ma literówek i błędów językowych, czy nie ma twierdzeń kontrowersyjnych lub niepewnych, i czy pismo ma maksymalny możliwy wpływ. Ostatni krok przed nadaniem."
argument-hint: "[katalog wysyłki lub pismo.pdf]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kontrola-pisma.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(pdftotext *) Read Grep Glob
---

# Recenzja pisma przed wysyłką

Cel: `$ARGUMENTS`

Jesteś ostatnią bramką. Po tobie pismo idzie do przeciwnika i nie da się go cofnąć.
Pracujesz **przeciwko** pismu: szukasz tego, co druga strona wykorzysta.

Zleć równolegle subagentom: `weryfikator-cytatow` (przepisy i sygnatury) oraz `recenzent`
(fakty, język, siła argumentacji), a sam zsyntetyzuj wyniki. Najpierw jednak upewnij się,
że przeszła kontrola mechaniczna (`/kruczek:kontrola`) — bez tego nie ma po co recenzować.

## 1. Fakty przeciw dowodom

Weź **każde** zdanie stanu faktycznego i znajdź dla niego pokrycie w `ARCHIWUM/`. Nie w pamięci,
nie w chronologii — w pliku dowodowym.

- Data w piśmie = data w dowodzie i w chronologii?
- Godzina, kwota, numer, identyfikator — przepisane wiernie?
- Cytat z korespondencji przeciwnika — dosłowny, nie sparafrazowany?
- Czy pismo twierdzi coś, czego dowód nie pokazuje, tylko sugeruje?

Fakt bez pokrycia w załączniku **wykreśl** albo przeformułuj na to, co dowód faktycznie pokazuje.

## 2. Hipotezy udające fakty

Porównaj sekcję `⚠ HIPOTEZY` w `index.md` z treścią pisma. To najgroźniejszy błąd w całym procesie:
przeciwnik obala jedno niepotwierdzone twierdzenie i podważa wszystko pozostałe, łącznie z tym,
co masz udowodnione.

Szukaj też hipotez, które nie trafiły do `index.md`, a wkradły się do pisma: „prawdopodobnie",
„najwyraźniej", „wszystko wskazuje", „to ta sama firma", „celowo". Każde takie sformułowanie
musi mieć twarde pokrycie albo wylatuje.

**Zasada:** nie piszemy niczego, czego nie jesteśmy pewni na 100%. Krótsze pismo z trzema
udowodnionymi zarzutami bije długie z dziesięcioma, z których dwa są do obalenia.

## 3. Prawo

Zleć `weryfikator-cytatow`. Sprawdzane jest: czy akt obowiązuje, czy publikator aktualny, czy cytat
dosłowny, czy przepis mówi to, co pismo twierdzi, czy sygnatura orzeczenia istnieje i czy teza
dotyczy tej sytuacji.

Dodatkowo sprawdź sam:
- czy nie powołano przepisu „dla powagi" — takiego, który tematycznie pasuje, ale nie ma
  zastosowania do tego stanu faktycznego,
- czy zapowiedziane kroki eskalacyjne są **realne**: właściwy organ, istniejący tryb, dotrzymywalny
  termin. Groźba, której nie wykonasz, kosztuje wiarygodność następnego pisma,
- czy nie pominięto przepisu **niekorzystnego**, który przeciwnik i tak podniesie.

## 4. Ryzyko — co może się obrócić przeciwko nadawcy

Przejrzyj pismo pod kątem zdań, które mogą zaszkodzić:

- **Przyznanie okoliczności niekorzystnej**, której nikt nie żądał.
- **Zarzut, którego nie udowodnisz** — zwłaszcza sugestia oszustwa, przestępstwa albo złej wiary.
  Formułuj przez fakty („zastosowano pięć technik ukrywania treści"), nie przez etykiety („oszukali").
- **Zniesławienie.** Zarzut postawiony publicznie i nieudowodniony to ryzyko z art. 212 k.k.
  W piśmie kierowanym wyłącznie do adresata ryzyko jest znikome, ale gdy pismo trafia do wiadomości
  osób trzecich albo ma być opublikowane — ostrzeż o tym użytkownika wprost.
- **Ujawnienie własnych danych**, które nie są potrzebne (PESEL w reklamacji, numer konta,
  dane innych osób).
- **Ton**, który da się zacytować jako nękanie albo groźbę.

## 5. Język

Czytaj zdanie po zdaniu:
- literówki, zwłaszcza w nazwach własnych, kwotach i numerach — literówka w NIP-ie adresata potrafi
  unieważnić doręczenie,
- błędy odmiany, zwłaszcza nazw firm i nazwisk,
- zdania, które można przeczytać na dwa sposoby — dwuznaczność zawsze zadziała na twoją niekorzyść,
- powtórzenia, watę słowną, zdania niewnoszące nic („Jak wiadomo…", „Pragnę zauważyć, że…"),
- spójność terminologii: raz „wiadomość", raz „mail", raz „korespondencja" — wybierz jedno,
- interpunkcja w wyliczeniach, spacje przed jednostkami (`14 dni`, `1 240,00 zł`),
- polskie cudzysłowy „…" zamiast "…".

## 6. Siła

Ostatnie pytanie: **czy to pismo maksymalizuje wpływ na nieuczciwego przedsiębiorcę?**

- Czy najmocniejszy argument stoi na początku, czy zginął w środku?
- Czy widać, że nadawca **udokumentował** sprawę — sumy kontrolne, chronologia, analiza techniczna?
  To sygnał: „ta osoba pójdzie dalej", i on działa mocniej niż groźby.
- Czy żądania są tak sformułowane, że spełnienie ich jest **tańsze niż ignorowanie**?
- Czy zapowiedź eskalacji trafia w to, co adresata naprawdę boli (kara administracyjna, koszt
  postępowania, ryzyko reputacyjne), czy jest ogólnikowa?
- Czy termin jest realny do dotrzymania? Termin niemożliwy zaprasza do zignorowania całości.
- Czy pismo daje adresatowi **wyjście** — konkretną, prostą czynność, po której sprawa się kończy?
  Pismo bez wyjścia zwykle trafia do prawnika, a nie do wykonania.

## Raport

**🔴 BLOKUJE WYSYŁKĘ** — fakt bez pokrycia w dowodzie, hipoteza w trybie oznajmującym, uchylony
przepis, niepotwierdzona sygnatura, twierdzenie, które może zaszkodzić nadawcy, błąd w danych
adresata. Przy każdym: co jest źle, gdzie dokładnie, i propozycja poprawki.

**🟠 OSŁABIA** — argument zapraszający kontrargument, żądanie bez terminu, groźba niewykonalna,
niezręczność językowa, zła kolejność argumentów.

**🟢 DO ROZWAŻENIA** — co jeszcze wzmocniłoby pismo, gdyby użytkownik chciał je jeszcze poprawić.

**Werdykt** — jedno zdanie: gotowe do wysyłki albo nie, i dlaczego.

Jeśli nie ma nic w 🔴, powiedz to wprost. **Nie dorabiaj zastrzeżeń, żeby raport wyglądał na
pracowity** — fałszywy alarm kosztuje tyle samo zaufania co przeoczenie.
