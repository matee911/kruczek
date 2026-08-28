# kruczek

**Plugin do Claude Code / Cowork do prowadzenia spraw spornych z firmami i instytucjami — po polsku.**

Reklamacja, której nikt nie rozpatruje. Spam, który przychodzi trzeci miesiąc. Odmowa bez
uzasadnienia. Umowa, której druga strona nie wykonuje. Sprawy, które trzeba załatwić, choć nikomu
się nie chce — bo wymagają papierologii, chronologii i znajomości przepisu, którego akurat nie ma
się pod ręką.

`kruczek` robi z tego proces: teczkę sprawy z niezmiennym archiwum i sumami kontrolnymi, chronologię
zdarzeń, pisma z **dosłownymi cytatami przepisów pobranymi ze źródeł urzędowych**, i bazę wiedzy,
która rośnie z każdą sprawą, żeby nie szukać dwa razy tego samego.

> Znajdujemy kruczek, drukujemy druczek.

---

## Instalacja

```bash
/plugin marketplace add matee911/kruczek
/plugin install kruczek@kruczek
```

Lokalnie, do testów:
```bash
git clone https://github.com/matee911/kruczek && claude --plugin-dir ./kruczek
```

### Zależności

| Narzędzie | Do czego | Wymagane |
|---|---|---|
| `curl`, `jq` | API rejestrów i orzecznictwa | tak |
| `python3` (sam stdlib) | analiza `.eml`, manifest, budowa pism | tak |
| `weasyprint` **albo** Chrome/Chromium **albo** `wkhtmltopdf` | składanie pism do PDF (próbowane w tej kolejności) | do pism |
| `pandoc` | załączniki `.md` w PDF | do pism |
| `poppler-utils` (`pdftotext`, `pdfinfo`) | odczyt PDF, licznik stron | zalecane |
| `tesseract-ocr` + `tesseract-ocr-pol`, `ocrmypdf` | OCR skanów | do skanów |
| `exiftool` | metadane PDF i zdjęć (daty, autor, GPS) | zalecane |
| `unzip`, `qpdf`, `p7zip` | metadane plików Office, odszyfrowanie PDF/ZIP/7z chronionych hasłem | zalecane |
| `ggrep` (macOS) / `grep` (Linux) | PCRE w `metadane.sh` (pliki Office) | zalecane |

`scripts/check-deps.sh` sprawdza wszystko naraz i wypisuje gotową komendę instalacji brakujących
pakietów dla Twojego systemu. Skrypty działają tak samo na macOS (BSD, systemowy bash 3.2)
i na Linuksie — obie platformy są testowane w CI.

```bash
# Debian/Ubuntu
sudo apt install curl jq python3 weasyprint pandoc poppler-utils tesseract-ocr tesseract-ocr-pol ocrmypdf libimage-exiftool-perl unzip
# macOS
brew install curl jq python pandoc poppler tesseract tesseract-lang ocrmypdf exiftool grep unzip
pip install weasyprint
```

Bez narzędzi do PDF i OCR reszta pluginu działa normalnie — brakuje tylko składania pism
i odczytu skanów.

---

## Szybki start

```
/kruczek:nowy-projekt          # raz na repozytorium spraw
/kruczek:nowa-sprawa           # teczka na jeden podmiot
/kruczek:dowod                 # wciągnij mail, skan, nagranie — z sumą kontrolną i OCR
/kruczek:fakt                  # dopisz jeden fakt do chronologii
/kruczek:metadane              # sprawdź metadane pliku (data, autor, GPS, rozbieżności)
/kruczek:archiwa               # zabezpiecz stronę: własna kopia + snapshot w Wayback Machine
/kruczek:pismo                 # zbuduj pismo z cytatami, załącznikami i TL;DR
/kruczek:kontrola              # mechanicznie: numeracja, nazwy, sumy, wymogi druku
/kruczek:weryfikuj             # przepisy i sygnatury w źródłach urzędowych
/kruczek:recenzja              # fakty, ryzyko, język, siła — ostatnia bramka
/kruczek:chronologia           # dopisz nadanie i doręczenie
/kruczek:status                # co się dzieje we wszystkich sprawach
/kruczek:eskalacja             # co dalej, gdy termin minął
```

`/kruczek:komendy` wypisuje pełny spis w każdej chwili.

---

## Co powstaje na dysku

```
moje-sprawy/
├── index.md                       rejestr wszystkich spraw
├── KONWENCJE.md                   zasady prowadzenia teczek
├── BAZA_WIEDZY/                   wspólna dla wszystkich spraw
│   ├── przepisy/                  dosłowne cytaty + publikator + data weryfikacji
│   ├── orzecznictwo/              sygnatury, tezy, rozbieżne linie orzecznicze
│   ├── decyzje/                   decyzje UODO, UKE, UOKiK
│   ├── wzory/                     sprawdzone sformułowania
│   └── metodyka/                  checklisty, katalogi technik
├── _SZABLONY/
│   └── dane-nadawcy.md            tożsamości: Ty, Twoja działalność, osoby reprezentowane
└── nazwa-firmy/
    ├── index.md                   chronologia, ustalenia, hipotezy, manifest, TODO, eskalacja
    │                              oraz „Występuję jako" — rola w TEJ sprawie
    ├── ARCHIWUM/                  oryginały dowodów — append-only
    ├── ROBOCZE/
    └── 2026_08_18-WEZWANIE-FIRMA-DO_WYSYLKI/
        ├── ROBOCZE/               szablon + komenda regeneracji PDF
        ├── 2026-08-18_Wezwanie.pdf
        └── dowody.zip
```

---

## Zasady, na których to stoi

**Archiwum jest niezmienne.** `ARCHIWUM/` jest append-only. Oryginał dowodu nigdy nie jest
edytowany ani konwertowany w miejscu. Każda obróbka tworzy nowy plik obok.

**Każdy dowód ma sumę SHA-256.** Manifest w `index.md` jest generowany, nie pisany ręcznie.
`/kruczek:status` wykrywa, gdy plik zmienił się po zaewidencjonowaniu.

**Dowód nietekstowy dostaje wersję tekstową od razu.** Skan → OCR, nagranie → transkrypcja
ze znacznikami czasu, `.eml` → pełna analiza dowodowa. Zawsze z nagłówkiem, że wiążący jest
oryginał, i z `[nieczytelne]` tam, gdzie nie widać. Bez tego dowód jest martwy — nie da się go
zacytować ani znaleźć za pół roku.

**Fakt to nie hipoteza.** Zbieżność adresu czy branży trafia do sekcji `⚠ HIPOTEZY` z wyraźnie
wskazanym brakującym ogniwem. Hipoteza napisana w piśmie w trybie oznajmującym to najgorszy błąd
w całym procesie — druga strona obala jedno twierdzenie i podważa resztę. Ustalenia techniczne
opisujemy tym, co zmierzone („nagłówek zawiera X"), nie tym, co z tego wynika o czyimś zamiarze.

**Własna kopia jest fundamentem, archiwum zewnętrzne dodatkiem.** Każdy URL najpierw trafia na
dysk jako własny zrzut (treść, nagłówki, kod HTTP, adres końcowy po przekierowaniach, SHA-256,
data odczytu), a dopiero potem do Wayback Machine po niezależne poświadczenie strony trzeciej.
Cudza usługa bywa niedostępna, odmawia zapisu albo usuwa snapshot na żądanie właściciela domeny
— dowód nie może od niej zależeć.

**Przepisy pochodzą ze źródeł urzędowych, nie z pamięci modelu.** API ELI Sejmu dla prawa polskiego,
EUR-Lex dla unijnego. Przed każdym cytatem sprawdzane jest, czy przepis nadal obowiązuje —
w Polsce całe ustawy bywają uchylane, a poradniki w internecie zostają na lata.

**Nic nie wychodzi bez trzech bramek.** `/kruczek:kontrola` sprawdza mechanicznie numerację
załączników, zgodność ich nazw w treści i na stronach załączników, sumy kontrolne, niewypełnione
pola i wymogi druku. `/kruczek:weryfikuj` sprawdza każdy przepis w Dzienniku Ustaw i każdą
sygnaturę w bazie orzeczeń. `/kruczek:recenzja` pracuje przeciwko pismu: czy każdy fakt ma pokrycie
w dowodzie, czy któreś zdanie nie zaszkodzi nadawcy, czy nie ma literówek — i czy pismo w ogóle
zadziała.

**Nie piszemy niczego, czego nie jesteśmy pewni na 100%.** Trzy udowodnione zarzuty biją dziesięć,
z których dwa da się obalić — bo obalenie dwóch podważa pozostałe osiem. Hipotezy albo zostają poza
pismem, albo wchodzą jako żądanie wyjaśnienia, nigdy jako twierdzenie.

**Format jest sztywny.** A4, Liberation Serif 12 pt (metrycznie zgodny z Times New Roman),
marginesy 25/20/25/20 mm — spełniają jednocześnie wymogi Envelo (min. 8/15 mm), e-Doręczeń
(min. 10/8/15 mm) i zostawiają zapas na wpięcie akt. Numeracja generowana licznikami CSS wg
hierarchii `I.` → `1.` → `1)` → `a)` → `–`, z ciągłą numeracją ustępów przez całe pismo — więc
„pkt 14" zawsze znaczy jedno i nigdy nie powstanie mylące „1." wewnątrz „1.".

**Podpis dobierany świadomie.** Do firmy mailem podpis bywa zbędny (forma dokumentowa,
art. 77² k.c.), do sądu pocztą jest obowiązkowy (art. 126 § 1 pkt 6 k.p.c., brak = zwrot pisma),
do urzędu elektronicznie potrzebny jest kwalifikowany, zaufany albo osobisty. Plugin mówi, który
wariant i dlaczego, i zostawia w PDF wyraźne miejsce na podpis odręczny, gdy jest potrzebny.

**Osobny TL;DR dla Ciebie.** Obok pisma powstaje `TLDR.md`, którego się nie wysyła: co wysyłasz
i czym, o co chodzi w trzech zdaniach, **co realnie możesz na tym ugrać** i — najważniejsze —
gdzie jesteśmy słabi.

---

## Źródła, z których plugin korzysta

Wszystkie publicznie dostępne. Klucza wymaga wyłącznie CEIDG (darmowy token, jednorazowa
rejestracja przez Profil Zaufany) — reszta działa bez rejestracji.

| Źródło | Co daje | Dostęp |
|---|---|---|
| [API ELI Sejmu](https://api.sejm.gov.pl/eli/) | Dz.U. i M.P., teksty ujednolicone, status aktu, nowelizacje | pełne API |
| [EUR-Lex](https://eur-lex.europa.eu) | prawo UE, wersje skonsolidowane PL | HTTP |
| [SAOS](https://www.saos.org.pl) | orzeczenia sądów powszechnych, SN, NSA, TK | pełne API |
| [Portal Orzeczeń UODO](https://orzeczenia.uodo.gov.pl) | decyzje Prezesa UODO, pełnotekstowo | pełne API |
| [CBOSA](https://orzeczenia.nsa.gov.pl) | orzeczenia NSA i WSA | dokument po ID |
| [SN](https://www.sn.pl) | orzeczenia Sądu Najwyższego | PDF po sygnaturze |
| [e-Dziennik UKE](https://edziennik.uke.gov.pl) | Dziennik Urzędowy UKE | API |
| [decyzje UOKiK](https://decyzje.uokik.gov.pl) | decyzje Prezesa UOKiK | HTTP |
| [Biała lista VAT](https://wl-api.mf.gov.pl) | NIP → nazwa, REGON, KRS, adres, rachunki | pełne API |
| [API KRS](https://api-krs.ms.gov.pl) | odpis aktualny | pełne API |
| [CEIDG API v3](https://dane.biznes.gov.pl) | dane JDG: imię, nazwisko, NIP/REGON, adres działalności i korespondencyjny, status, historia (bez adresu zamieszkania) | token Bearer (jednorazowa rejestracja przez Profil Zaufany) |
| [RDAP NASK](https://rdap.dns.pl) | dane i data rejestracji domeny `.pl` | pełne API |
| dns.google, cloudflare-dns.com | rekordy DNS, SPF, DKIM, DMARC (DNS-over-HTTPS) | pełne API |
| [CRBR](https://crbr.podatki.gov.pl) | beneficjenci rzeczywiści spółek | przeglądarka |
| [Rejestr.io](https://rejestr.io) | powiązania kapitałowe, wspólnicy, zarządy | przeglądarka |
| [imsig.pl / MSiG](https://imsig.pl) | ogłoszenia obowiązkowe: likwidacja, upadłość, zmiany KRS | przeglądarka |
| [Repozytorium dokumentów KRS](https://przegladarka.ms.gov.pl) | sprawozdania finansowe, bilanse | przeglądarka |

Skille `zrodla-prawa`, `zrodla-orzecznictwa`, `zrodla-rejestry` i `zrodla-dns-poczta` opisują też,
**czego nie da się pobrać automatycznie** i jak to obejść — wyszukiwarki CBOSA, Portalu Orzeczeń SP
i UOKiK są dla automatów zamknięte. Skill `fallback-przegladarka` podaje drabinkę obejść: zmiana
narzędzia, boczne API, **Claude in Chrome** z sesją użytkownika, **Playwright** dla stron
renderowanych JS-em, computer use, a na końcu przekazanie zadania użytkownikowi z gotową instrukcją.
Obchodzimy ograniczenia techniczne, nie obchodzimy captcha, logowania ani zakazów w regulaminie.

---

## Dobór modeli

Zadania mechaniczne idą na `haiku`, research na `sonnet`, rozumowanie prawne na `opus`.
Pełna mapa: [`docs/MODELE.md`](docs/MODELE.md).

| Warstwa | Model | Dlaczego |
|---|---|---|
| sumy kontrolne, manifest, chronologia, analiza `.eml`, DNS, rejestry, kontrola załączników | `haiku` | robotę robi skrypt, model tylko czyta wynik i formatuje |
| OCR i transkrypcja | `sonnet` | polskie znaki diakrytyczne — haiku je gubi |
| research przepisów i orzecznictwa | `sonnet` | nawigacja po API i długich PDF-ach |
| pisanie pism, weryfikacja cytatów, recenzja, eskalacja | `opus` | subsumpcja i najdroższe miejsce na błąd |

---

## Zastrzeżenie

`kruczek` nie jest kancelarią i nie świadczy pomocy prawnej. Jest narzędziem do porządkowania
dokumentów, pobierania tekstów aktów prawnych ze źródeł urzędowych i przygotowywania pism.
Za treść wysłanego pisma odpowiada osoba, która je podpisuje.

Przy wysokiej stawce, skomplikowanym stanie faktycznym albo krótkim terminie zawitym skonsultuj
się z radcą prawnym lub adwokatem. Plugin sam o tym przypomina, gdy sprawa na to wygląda.

Teczki spraw zawierają dane osobowe. Jeżeli trzymasz je w repozytorium git — zadbaj o `.gitignore`.

## Licencja

MIT. Zob. [LICENSE](LICENSE).

## Wkład

Zgłoszenia i PR-y mile widziane — zwłaszcza nowe źródła urzędowe i wzory pism do `BAZA_WIEDZY/wzory/`.
Przed PR-em uruchom `claude plugin validate .`.
