# Plan: obsługa danych meteorologicznych, pomiarowych i obywatelskich rejestrów odorowych

**Status:** dokument roboczy, lokalny. Nie commitować, nie wypychać.
**Data:** 2026-08-28
**Źródło materiału:** realna sprawa `uciazliwosci-odorowe-nn` (Warszawa-Bielany, sierpień 2026).
Wszystkie kontrakty API, pułapki i wnioski poniżej zostały empirycznie sprawdzone w tej sprawie —
to nie są założenia.

**Punkt wyjścia:** działający skill `dane-srodowiskowe` leży na dysku w
`SPORY/_NARZEDZIA/dane-srodowiskowe/` (`SKILL.md`, `reference.md`, `scripts/wiatr.py`, `gios.py`,
`azymut.py`, `tvoc-logger.py`). Można go rozebrać i wpiąć w plugin zamiast pisać od zera.

---

## 1. Zakres — co zbudować

### 1.1 Skrypty → `scripts/`

| Plik | Rola |
|---|---|
| `airqlab.py` | **nowy** — pobieranie zgłoszeń, czujników i pomiarów H₂S/NH₃ z otwartego API airqlab.pl |
| `wiatr.py` | obserwacje SYNOP z Ogimet: pobranie, róża wiatrów, okno wokół zdarzenia, częstość bazowa |
| `gios.py` | stacje i pomiary GIOŚ (API PJP v1), wyszukiwanie stacji w promieniu |
| `azymut.py` | odległości i azymuty do kandydatów + ostrzeżenie o nierozróżnialności kierunkowej |

Wymagania wspólne (zgodne z resztą `scripts/`):

- bez zależności poza biblioteką standardową Pythona 3,
- tryb jako pierwszy argument pozycyjny (`airqlab.py zgloszenia ...`),
- wyjście CSV/JSON do pliku albo na stdout,
- komunikaty po polsku.

### 1.2 Subagent → `agents/zbierz-dane-srodowiskowe.md`

```yaml
---
name: zbierz-dane-srodowiskowe
description: Pobiera dane meteorologiczne, pomiarowe i rejestry zgłoszeń odorowych do spraw
  o uciążliwości — wiatr z obserwacji SYNOP, stężenia GIOŚ, zgłoszenia i pomiary H2S/NH3
  z airqlab.pl, azymuty do podejrzewanych źródeł. Użyj, gdy trzeba ustalić skąd wiał wiatr
  w chwili zdarzenia albo zebrać dane o skali zjawiska.
tools: Bash, WebFetch, Read, Write
model: sonnet
---
```

**Model `sonnet`, nie `haiku`:** praca nie jest mechaniczna. Trzeba nawigować po kilku API,
z których część zwraca 410, część bywa zablokowana, część ma zduplikowane klucze w JSON,
a wyniki wymagają decyzji o oknach czasowych i deduplikacji.

**Granica odpowiedzialności:** subagent *pobiera i porządkuje*. Nie interpretuje —
interpretacja należy do skilla analitycznego, bo tam są pułapki wnioskowania.

### 1.3 Skille → `skills/`

**`zrodla-srodowiskowe/SKILL.md`** — skill referencyjny w rodzinie `zrodla-*`, obok
`zrodla-rejestry`, `zrodla-prawa`, `zrodla-dns-poczta`. Zawiera sekcje 2–4, 6 i 7 tego dokumentu:
endpointy, wykaz stacji, pułapki, kontekst prawny, dostępność sieciową.
Model `haiku`, effort `low` — to wykaz, nie rozumowanie.

**`analiza-emisyjna/SKILL.md`** — skill metodyczny. Zawiera sekcję 5: jak wnioskować z tych danych,
żeby nie postawić tezy, którą przeciwnik obali własnymi danymi sprawy.
Model `opus`, effort `high` — to jest miejsce, w którym błąd kosztuje najwięcej, na równi
z `weryfikuj`.

### 1.4 Rejestry do aktualizacji

- `skills/komendy/SKILL.md` — dopisać nowe pozycje do tabel skilli i subagentów.
- `docs/MODELE.md` — trzy wiersze:
  - `zrodla-srodowiskowe` | skill | `haiku` | low | wykaz endpointów i stacji, zero uznaniowości
  - `analiza-emisyjna` | skill | `opus` | high | analiza przyczynowa na danych obserwacyjnych, z aktywnym szukaniem kontrhipotez
  - `zbierz-dane-srodowiskowe` | agent | `sonnet` | — | kilka API, część zablokowana/410, decyzje o oknach czasowych i deduplikacji
- `docs/diagram-powiazan.md` — wpiąć nowy subagent w graf.

---

## 2. airqlab.pl — otwarte API, bez uwierzytelnienia

Obywatelski rejestr zgłoszeń odorowych. Operator komercyjny, wdraża sieci w wielu gminach;
instancja `/bielany/` obsługuje Warszawę-Bielany. **Ścieżka zawiera nazwę gminy** — przy innej
sprawie sprawdzić, czy istnieje instancja dla właściwego terenu.

Baza: `https://www.airqlab.pl/<gmina>/`
Parametry: `startDate`, `endDate` (RRRR-MM-DD), `deviceId`.

| Endpoint | Zwraca |
|---|---|
| `get_devices.php` | czujniki: `id`, nazwa, `lok_x` (lon), `lok_y` (lat) |
| `get_incidents.php` | zgłoszenia: `czas` (co do sekundy), `lok_x`, `lok_y`, `sila` (1–5), `typ`, `inny` |
| `get_incidents_chart.php` | zgłoszenia zagregowane po dniach — **tylko rozdzielczość dobowa** |
| `get_ato_chart.php` | `h2s`, `h2s_max`, `nh3`, `nh3_max`, `data_godzina` — godzinowo, na czujnik |
| `get_PM_chart.php` | PM godzinowo, na czujnik |
| `submit_incident.php` | POST — formularz zgłoszenia (**nie używać automatem**) |

**Słownik `typ`** (z `js/map2.js`, funkcja `mapujTypNaNazwe`):
`0` = opis własny w polu `inny` · `1` olej · `2` benzyna · `3` mocz · `4` zgniłe jajka ·
`5` gnijące warzywa · `6` gaz · `7` obornik/nawóz · `8` odór śmieci · `-1` nieokreślony

### 2.1 Pułapki — wszystkie napotkane realnie

- JSON ma **zduplikowane klucze numeryczne** (`"0"`, `"1"`, `"2"`…) obok nazwanych.
  Filtrować: `{k: v for k, v in r.items() if not k.isdigit()}`.
- Zakresy dłuższe niż ~30 dni **bywają ucinane**. Pobierać oknami po 30 dni i deduplikować
  po krotce `(czas, lok_x, lok_y, typ, sila, inny)`.
- Sporadyczne `Connection reset by peer` — ponawiać z odstępem, 3–4 próby.
  Przy jednym pobraniu 14 miesięcy trzy okna wymagały ponowienia.
- `get_incidents_chart.php` dla pojedynczego dnia zwraca `[]` — wymaga zakresu.
- Publiczne API zwraca tylko 6 pól z kilkunastu zbieranych — patrz niżej, to ma znaczenie dowodowe.

### 2.2 ⚑ Pola zbierane przez formularz, ale NIEUDOSTĘPNIANE przez API

`get_incidents.php` zwraca: `lok_x`, `lok_y`, `sila`, `typ`, `czas`, `inny`.

Formularz (`bielany/Index.html`) zbiera dodatkowo:

| Pole | Opcje |
|---|---|
| `ile` | poniżej 15 min · 15–30 min · 30 min–1 h · 1–2 h · 2–4 h · powyżej 4 h |
| `jak_czesto` | po raz pierwszy · powtarza się sporadycznie · powtarza się często |
| `rytm` | nieregularnie · dni robocze · dni wolne · zazwyczaj w dzień · zazwyczaj w nocy |
| `kierunek` | trudno określić · N · NE · E · SE · S · SW · W · NW · zmienny |
| `wiatr` | brak · słaby · umiarkowany · silny |
| `czy_fabryka`, `czy_wypadek`, `otoczenie`, `uwagi` | — |

To jest materiał do **wniosku o informację o środowisku**: pole `rytm` odpowiada wprost na pytanie
o porę występowania zjawiska, którego nie da się rozstrzygnąć z automatycznego znacznika czasu.
Skill ma podpowiadać, żeby o te pola wystąpić do gminy.

### 2.3 ⚑ `czas` to moment ZŁOŻENIA zgłoszenia, nie zdarzenia

`js/map2.js`, linia 128: `document.getElementById('czas').value = new Date().toISOString();`
— nadawany przy otwarciu formularza. Formularz **nie ma pola na czas wystąpienia odoru**.
Skill musi to sygnalizować przy każdej analizie godzinowej. Sposób obejścia — sekcja 5.5.

---

## 3. Wiatr — obserwacje SYNOP, nie model

**Zasada nadrzędna: do kierunku wiatru używać obserwacji, nigdy modelu reanalizy.**

Sprawdzone: Open-Meteo dał dla nocy 12.08.2026 kierunek 317–332° (NNW), obserwacja SYNOP z tej samej
doby i lokalizacji — 240–280°. Rozbieżność ~80°, dokładnie w godzinach epizodu. Przy prędkościach
1–2 m/s modele nie odwzorowują lokalnego przepływu, a właśnie wtedy zdarzają się epizody odorowe.

### 3.1 Ogimet — depesze SYNOP

```
https://www.ogimet.com/cgi-bin/getsynop?begin=RRRRMMDDHHMM&end=RRRRMMDDHHMM&block=<IIiii>
```

CSV: `block,rok,mies,dzień,godz,min,depesza`. Czas UTC — przeliczyć na `Europe/Warsaw`.

**Dekodowanie grupy `Nddff`** (druga grupa po numerze stacji):
`N` zachmurzenie (ignorować), `dd` kierunek w dziesiątkach stopni (26 → 260°), `ff` prędkość m/s.
`dd=00` cisza, `dd=99` zmienny — oba odrzucić. Kierunek to ten, **z którego** wieje.

⚠ `www.ogimet.com/cgi-bin/gsynres` (wersja HTML) zwraca **403** — używać `getsynop`.

### 3.2 Numery stacji SYNOP (IIiii)

`12375` Warszawa-Okęcie · `12360` Łódź · `12566` Kraków-Balice · `12424` Wrocław · `12330` Poznań ·
`12185` Gdańsk-Rębiechowo · `12295` Białystok · `12500` Rzeszów · `12495` Lublin-Radawiec ·
`12345` Bydgoszcz · `12235` Toruń · `12280` Olsztyn · `12435` Opole · `12560` Kielce ·
`12520` Katowice-Muchowiec · `12400` Zielona Góra · `12100` Kołobrzeg · `12105` Koszalin ·
`12195` Elbląg · `12205` Suwałki · `12469` Częstochowa · `12690` Zakopane

**Warszawa ma tylko jedną stację SYNOP — Okęcie, na południowym zachodzie.** Dla zdarzeń na północy
miasta to 12–15 km. Skill musi kazać zapisywać tę odległość jako ograniczenie.

### 3.3 IMGW

- bieżące: `danepubliczne.imgw.pl/api/data/synop/id/<id>` — tylko stan na teraz, bez historii
- archiwum: `danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/terminowe/synop/<rok>/<rok>_<mc>_s.zip`
  — opóźnienie publikacji ok. 1 miesiąca, bieżącego miesiąca nie ma.
  Do świeżych zdarzeń: Ogimet.

---

## 4. GIOŚ — API PJP v1

Stary endpoint `api.gios.gov.pl/pjp-api/rest/...` zwraca **410 Gone**. Aktualny:

```
https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll?size=500&page=<n>
https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors/<id_stacji>
https://api.gios.gov.pl/pjp-api/v1/rest/archivalData/getDataBySensor/<id_stanowiska>?dateFrom=&dateTo=
```

Pułapki:

- `getData/<id>` zwraca tylko ~3 ostatnie doby; do historii wyłącznie `archivalData`
- JSON-LD z polskimi kluczami („Lista stacji pomiarowych", „Wartość", „Data"), które **różnią się
  między endpointami** — wyciągać pierwszą wartość typu lista, nie po nazwie
- wyniki godzinowe w **CET (UTC+1), bez czasu letniego** — latem godzina mniej niż lokalny
- część stanowisk zwraca pustą listę mimo poprawnego id (manualne / nieczynne)

### 4.1 ⚑ GIOŚ nie mierzy żadnego markera odoru

Sprawdzone na wszystkich 27 stanowiskach mazowieckich: brak H₂S, NH₃, merkaptanów, LZO/TVOC.
Sieć mierzy wyłącznie substancje normowane: pyły, tlenki azotu, O₃, SO₂, CO, benzen, metale, WWA.

To jest **ustalenie samo w sobie i argument NA KORZYŚĆ skarżącego**: państwowa sieć z definicji nie
jest w stanie udokumentować uciążliwości zapachowej, bo odór nie jest normowany. Skill ma tak to
formułować, a nie jako słabość sprawy.

### 4.2 ⚠ Nie używać wskaźników zastępczych

Korelacja zgłoszeń ze stężeniem NO₂ na odległej stacji **nie wskazuje źródła odoru** — NO₂ z ruchu
drogowego kumuluje się w tych samych warunkach zastoju, w których kumuluje się odór. To wskaźnik
pogody, nie sprawcy. Stacja poza obszarem odczuwania uciążliwości nie wnosi nic i lepiej jej w ogóle
nie przywoływać.

Błąd popełniony i wycofany w tej sprawie: korelacja +0,62 dla NO₂ z Targówka, 8 km od miejsca
zdarzenia.

---

## 5. Metodyka wnioskowania — najważniejsza część

Skill `analiza-emisyjna` musi wymuszać poniższe. **Każdy punkt to błąd popełniony i naprawiony
w realnej sprawie.**

### 5.1 Emisja jest przerywana — wnioskuj asymetrycznie, nie korelacją

Zwykła korelacja kierunku wiatru z liczbą zgłoszeń dąży do zera niezależnie od tego, czy hipoteza
jest prawdziwa, bo dni z wiatrem „stamtąd" i bez odoru rozcieńczają wynik.

| Wiatr z sektora źródła? | Było czuć? | Wniosek |
|---|---|---|
| tak | tak | słaba przesłanka **za** — patrz częstość bazowa |
| nie | tak | przesłanka **PRZECIW** temu źródłu |
| tak | nie | nieinformatywne — źródło mogło nie emitować |
| nie | nie | nieinformatywne |

Właściwy test to **falsyfikacja**: ile dni z odorem miało zero godzin w sektorze kandydata.

### 5.2 Zawsze podawaj częstość bazową

Jeśli wiatr wieje z sektora kandydata przez 48 % czasu, to „w trakcie epizodu wiało stamtąd" ma
niską wartość rozróżniającą. Bez częstości bazowej analiza wygląda mocniej, niż jest.

### 5.3 Sprawdź rozróżnialność kandydatów, zanim cokolwiek policzysz

W tej sprawie: Radiowo 254°, ZUOK Kampinoska 259°, Orlen 277°, BYŚ 289° — rozpiętość 35°, kierunek
wiatru ich nie odróżnia. Skrypt `azymut.py` ostrzega przy różnicy < 40°.

Osobno: dla źródła bliżej niż ~1 km (tu ArcelorMittal, 0,89 km) wiatr mierzony na stacji oddalonej
o kilkanaście km nie ma mocy rozstrzygającej — ani wskazać, ani wykluczyć.

### 5.4 Gdy przeciwnik ma alternatywne wyjaśnienie — znajdź test, nie hedguj

Wzorzec do zakodowania w skillu: poszukaj warunku, w którym oba wyjaśnienia dają różne przewidywania,
i sprawdź go. Zamiast osłabiać tezę zastrzeżeniami albo ustępować.

Przykład z tej sprawy. Rozkład godzin zgłoszeń pokazywał szczyt wieczorny. Zarzut: to artefakt,
ludzie zgłaszają po powrocie z pracy. Test: gdyby tak było, szczyt powinien zanikać w dni wolne,
gdy wszyscy są w domu całą dobę. Wynik (n = 1582):

| przedział | dni robocze | weekend |
|---|---|---|
| 21:00–23:00 | 26,8 % | 32,7 % |
| 20:00–02:00 | 50,9 % | 59,9 % |
| 16:00–19:00 (powrót z pracy) | 17,8 % | 6,7 % |

Szczyt w weekend wyraźniejszy, godziny powrotu z pracy najcichsze w dobie. Hipoteza artefaktu
odrzucona — na danych, nie w dyskusji.

### 5.5 Szukaj statystyki odpornej na zarzut, którego nie da się usunąć

Znacznik czasu pozostaje momentem złożenia zgłoszenia i nic tego nie zmieni. Ale: 81,9 % zgłoszeń
powstaje poza godzinami urzędowania organu kontrolnego — to dotyczy **zgłoszeń**, nie emisji, więc
jest nie do podważenia, a uzasadnia dokładnie to samo żądanie kontroli wieczornej.

### 5.6 Szukaj momentu zmiany kierunku

Zamiast uśredniać dobę — znajdź godziny przełomu i **zapytaj użytkownika o dokładny czas zdarzenia**.
W tej sprawie wiatr skręcił z W na NE między 01:00 a 02:00; godzina powrotu użytkownika do domu
rozstrzygała między dwoma kandydatami. Jedno takie pytanie bywa warte więcej niż cała analiza
statystyczna.

### 5.7 Zmiana struktury bije zmianę wolumenu

Wzrost liczby zgłoszeń zawsze da się zbić zarzutem „przybyło użytkowników serwisu". Zmiany proporcji
między kategoriami ten zarzut nie tłumaczy. W tej sprawie udział kategorii „odór śmieci" wzrósł
z 4,6 % do 70,3 % — argument, którego nie da się zbić wolumenem.

### 5.8 Konkurencyjne wyjaśnienia do policzenia zawsze

- **stagnacja** — udział godzin ≤ 2 m/s; epizody korelują z bezwietrznością często silniej niż
  z kierunkiem (tu ρ = +0,43). To warunek **wzmacniający**, nie konkurencyjny: kierunek decyduje
  *skąd*, stagnacja *czy się utrzyma*.
- **dzień tygodnia** — liczba zgłoszeń bywa funkcją tego, kto jest w domu.
- **efekt kaskady** — jedna relacja w mediach lokalnych potrafi wywołać falę zgłoszeń.
- **luki w danych** — miesiąc z anomalnie niską liczbą to zwykle luka, nie brak zjawiska.

### 5.9 Status wyniku

Materiał z tych źródeł to **dane pomocnicze do analizy, nie dowód**. W repozytorium kruczka
zapisywać w `ROBOCZE/`, nigdy w `ARCHIWUM/`, z nagłówkiem o statusie i sekcją „Ograniczenia".
Do pisma nadaje się dopiero po zestawieniu z dokumentem urzędowym albo pomiarem organu.

### 5.10 Uważaj, co dajesz przeciwnikowi

Pismo do organu jest dokumentem, po który druga strona może sięgnąć własnym wnioskiem. W sprawie
odorowej **nie wolno wpisywać, że publiczne pomiary H₂S nie wykazują przekroczeń** — to gotowy cytat
do obrony operatora instalacji. Pytanie o metodykę tak, własna teza nie.

---

## 6. Kontekst prawny do wpięcia w `zrodla-srodowiskowe`

- **Wartość odniesienia H₂S: 20 µg/m³ (1 h) i 5 µg/m³ (rok)** — rozporządzenie Ministra Środowiska
  z 26.01.2010, Dz. U. Nr 16, poz. 87, tabela 1 zał. nr 1 poz. 140. Obowiązuje.
- ⚑ To **próg toksykologiczny, nie zapachowy**. Próg wyczuwalności zapachowej H₂S jest o rząd
  wielkości niższy. Dlatego „nie przekraczamy norm" nie wyklucza uciążliwości — to rozbraja
  standardową linię obrony operatora i musi być w skillu.
- **Brak rozporządzenia o wartościach odniesienia substancji zapachowych.** Delegacja z art. 222
  ust. 5 Prawa ochrony środowiska jest fakultatywna („może określić") i nie została wykonana.
  Stąd luka prawna w sprawach odorowych.
- **Ustawa o Inspekcji Ochrony Środowiska** (t.j. Dz. U. z 2024 r. poz. 425), art. 9 ust. 1c
  (kontrola interwencyjna) i art. 9 ust. 2 pkt 1 lit. a — „wstępu przez całą dobę".
  Likwiduje wymówkę „nie kontrolujemy w nocy".
- **Ustawa o udostępnianiu informacji o środowisku** (t.j. Dz. U. z 2026 r. poz. 670):
  art. 18 wyłącza tajemnicę przedsiębiorstwa dla danych o emisji do powietrza i o odpadach;
  art. 19 ust. 2 pkt 1 — przekazanie wniosku w 14 dni; art. 19 ust. 3 — przy wniosku „zbyt ogólnym"
  organ musi wezwać i pomóc, nie odmówić; art. 15 ust. 3 — pułapka formy.

---

## 7. Dostępność sieciowa — sprawdzone empirycznie

| Host | Status |
|---|---|
| `api.gios.gov.pl` | działa |
| `danepubliczne.imgw.pl` | działa |
| `www.ogimet.com/cgi-bin/getsynop` | działa |
| `www.airqlab.pl` | działa |
| `api.open-meteo.com` | działa (ale patrz sekcja 3 — **nie używać do kierunku**) |
| `nominatim.openstreetmap.org` | działa (1 zapytanie/s, wymaga User-Agent) |
| `archive-api.open-meteo.com` | **blokowany** |
| `overpass-api.de` | **blokowany** |
| `web.archive.org` | **blokowany** — `archiwa.sh save` nie działa, archiwizacja ręczna |
| `developer.electrolux.one` | robots.txt blokuje WebFetch |

**Geokodowanie:** pełny adres z numerem często nie trafia — szukać samej nazwy ulicy albo
miejscowości i wybierać z listy po `display_name`. Obiekty przemysłowe bywają w OSM pod nazwą
operatora, nie adresem.

---

## 8. Pomiar własny — opcjonalny czwarty skrypt

`tvoc-logger.py` (jest w `_NARZEDZIA/`) odpytuje API Grupy Electrolux (`developer.electrolux.one`,
apiKey + refreshToken) o stan bieżący czujników domowego oczyszczacza: TVOC, PM1/PM2.5/PM10, CO₂.
Aplikacja producenta daje 30 dni w rozdzielczości dobowej bez eksportu; API omija to ograniczenie,
ale **tylko na przyszłość** — historii nie odzyska.

Wartość dowodowa niska, ale niezerowa: czujnik konsumencki nie jest wzorcowany i nie odróżnia źródeł,
natomiast **datuje epizod co do minut**, co pozwala zestawić go z godzinową obserwacją wiatru.
Warunek: równoległa notatka o czynnościach domowych w godzinach pików.

Narzędzie o realnej wartości dowodowej to **pasywne próbniki dyfuzyjne H₂S/NH₃ z analizą
w akredytowanym laboratorium** — mierzą dokładnie to, czego GIOŚ nie mierzy, z protokołem
i łańcuchem kustodii. Skill powinien to podpowiadać, gdy sprawa zmierza do organu albo sądu.

---

## 9. Przy okazji do naprawy — `build-pismo.py` i `kontrola-pisma.py`

**`build-pismo.py`:** skrypt wstawia załączniki wyłącznie w miejsce komentarzy
`<!--KRUCZEK:ZALACZNIKI-->` i `<!--KRUCZEK:LISTA_ZALACZNIKOW-->`. Bez drugiego markera nadal raportuje
„Załączniki wdrukowane w PDF", ale stron załączników w PDF nie ma — a `kontrola-pisma.py` wykrywa to
dopiero jako błąd blokujący „Treść odsyła do załączników, których nie ma w piśmie". Build kończy się
sukcesem, więc łatwo to przeoczyć.
→ Dodać ostrzeżenie w `build-pismo.py`, gdy podano `-z`, a w szablonie brakuje markera.

**`kontrola-pisma.py`:** szuka placeholdera „TODO" bez granic słowa, więc słowo „METODOLOGICZNE"
wywołuje fałszywy alarm.
→ Dodać `\b` albo listę wyjątków.

---

## 10. Issue założone 2026-08-28 (matee911/kruczek)

Repo jest publiczne — w treści issue nie ma żadnych danych sprawy: lokalizacji, nazw
instalacji, azymutów ani wyników liczbowych. Same reguły.

**Fala 1 — niezależne quick winy:** #2 fałszywe alarmy w kontrolach · #3 `dns.sh abuse` ·
#4 `zagrozenia.sh` (NASK/CyberTarcza) · #5 zależność internet-archive-skills ·
#6 agent `wayback-fetch` · #7 skill `wiedza-webarchive` · #8 ostrzeżenie w `build-pismo.py`

**Fala 2 — rozstrzygnięcia przed budową:** #9 nazewnictwo skilli (blokuje #14) ·
#10 `zalaczniki.yaml` + `/kruczek:przenumeruj` (docelowa naprawa #8) · #11 świeżość pisma

**Fala 3 — nowa zdolność:** #12 `analiza-poszlakowa` (uogólniona sekcja 5) ·
#13 `podwaz-hipoteze` · #14 skill źródeł środowiskowych (sekcje 2–4, 6, 7) ·
#15 `airqlab.py` · #16 `wiatr.py` · #17 `gios.py` · #18 `triangulacja.py` (CPF/CBPF + MLE,
zastępuje `azymut.py`) · #19 `zbierz-dane-srodowiskowe` · #20 wzorce do `BAZA_WIEDZY/wzory/`

**Backlog z retrospektywy:** #21 eskalacja phishing/abuse · #22 mapa doręczeń ·
#23 adresat nieosiągalny · #24 `tempmail.sh` · #25 rosnąca baza wiedzy · #26 `_to_delete/` ·
#27 generowany plik startowy · #28 rejestr kanałów zgłoszeń · #29 `zrodla-osint` ·
#30 audyt zgodności modeli

Zrealizowane wcześniej, poza zakresem: P0.6 (`manifest.py` już używa ścieżek względnych),
P0.7 (`nowa-sprawa` nie pyta o cel na starcie), sekcja 8 retrospektywy (smoketest + CI),
usunięcie `timemap`. Nie na issue: P0.1 (weasyprint — do sprawdzenia, czy jest domyślny),
P5.25 i P2.13 (decyzje architektoniczne wymagające usera).

### Zmiany względem sekcji 1 tego dokumentu

- `analiza-emisyjna` → **`analiza-poszlakowa`**: metodyka z sekcji 5 jest domenowo
  neutralna i adresuje „tezę wyprzedzającą fakt" z retrospektywy, nie tylko sprawy odorowe.
- `azymut.py` → **`triangulacja.py`**: kalkulator azymutu był naiwny. CPF/CBPF
  (Uria-Tellaetxe & Carslaw 2014) normalizuje przez częstość bazową i rozdziela źródła
  bliskie od odległych przez prędkość wiatru; wielopunktowa estymacja wiarogodności
  (von Mises na siatce) zastępuje przecinanie prostych. Wyjście = iloraz wiarogodności,
  nie wskazanie sprawcy. Inwersja dyspersyjna świadomie poza zakresem — to praca biegłego.
- Reguły ogólne (obserwacja > model, brak normy ≠ brak naruszenia, pola formularza vs API,
  co dajesz przeciwnikowi) wyjęte do `BAZA_WIEDZY/wzory/`, zamiast powielać je w skillach.
