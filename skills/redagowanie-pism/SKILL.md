---
name: redagowanie-pism
description: "Konwencja redakcyjna pism do firm, urzędów i sądów — układ nagłówka, tytuł, hierarchia numeracji, oznaczanie stron i załączników, dobór podpisu, skład i marginesy. Stosuj przy każdym piśmie: reklamacji, wezwaniu, odwołaniu, skardze, żądaniu z RODO."
when_to_use: Pisanie reklamacji, wezwania, odwołania, skargi do organu, pisma procesowego, żądania z RODO; pytania o formatowanie pisma, numerację punktów, jak podpisać, jak oznaczyć adresata i załączniki.
---

# Konwencja redakcyjna pism

Format jest sztywny. Nie improwizuj — spójność między pismami jest sama w sobie sygnałem, że po
drugiej stronie ktoś wie, co robi.

---

## 1. Skład

| Parametr | Wartość | Dlaczego tak |
|---|---|---|
| Format | A4 pionowo | wymóg Envelo i e-Doręczeń |
| Font | **Liberation Serif 12 pt** | metrycznie zgodny z Times New Roman — u odbiorcy złamie się identycznie |
| Interlinia | 1,4 | mieści się w praktyce 1,15–1,5 |
| Marginesy | **25 / 20 / 25 / 20 mm** (góra/dół/lewy/prawy) | Envelo min. 8/15 mm, PUH min. 10/8/15 mm, lewy 25 mm zostawia zapas na wpięcie akt (ISO 838: dziurki do ~16 mm od krawędzi) |
| Fonty w PDF | **osadzone** | Envelo i e-Doręczenia odrzucają pliki z nieosadzonymi fontami |
| Numeracja stron | „str. N z M" w stopce | odbiorca widzi, czy dostał całość |

Nie ma przepisu narzucającego krój ani stopień pisma w pismach procesowych — sprawdzone: art. 126
k.p.c. milczy, zarządzenie MS o sekretariatach sądowych też. Ale skoro Sąd UE wymaga min. 12 pt
i marginesów 2,5 cm, to jest dobry punkt odniesienia i trzymamy się go wszędzie.

Szablon: `${CLAUDE_PLUGIN_ROOT}/templates/pismo.html`. Składanie: `build_pismo.py` (ustawia
marginesy sam). Nie zmieniaj marginesów bez powodu.

---

## 2. Numeracja — jeden schemat, bez wyjątków

To najczęstszy błąd w pismach: „punkt 1." w sekcji, a pod nim „podpunkt 1." — czytelnik nie wie,
do którego odsyła późniejsze „jak wskazano w pkt 1".

**Obowiązująca hierarchia** (zgodna z Zasadami techniki prawodawczej, § 55–58):

```
I.        część pisma            rzymskie, wielkimi literami
1.        ustęp                  arabskie z kropką — NUMERACJA CIĄGŁA PRZEZ CAŁE PISMO
   1)     punkt                  arabskie z nawiasem
      a)  litera                 małe litery bez polskich znaków
         –  tiret
```

Zasady:

1. **Ustępy numerują się ciągle** przez całe pismo, przez wszystkie sekcje. Ustęp 14 jest jeden
   w całym dokumencie, więc „pkt 14" jest jednoznaczne.
2. **Nigdy dwa różne poziomy tym samym oznaczeniem.** Jeśli ustęp ma `1.`, to podpunkt ma `1)`,
   nie `1.`.
3. **Żądania i wnioski** numerujesz `1)`, `2)`, `3)` — bo siedzą wewnątrz ustępu. Odesłanie brzmi
   „żądanie 3)”, nie „punkt 3”.
4. W szablonie numeracja generuje się **licznikami CSS**. Klasy: `<h2>` → I., `<p class="ust">` → 1.,
   `<ol class="pkt">` → 1), `<ol class="lit">` → a), `<ul class="tir">` → –.
   **Nie wpisuj cyfr ręcznie** — model się myli, licznik nie.

---

## 3. Układ nagłówka

```
[20 mm odstępu na strefę okna koperty]

NADAWCA (lewa)                                    Miejscowość, dnia 18 sierpnia 2026 r.
imię i nazwisko / pełna firma
ulica i numer
kod i miejscowość
NIP (tylko jeśli występujesz jako przedsiębiorca)
e-mail

ADRESAT
Pełna firma z formą prawną
ulica i numer
kod i MIEJSCOWOŚĆ

Do wiadomości (drogą elektroniczną): adresy e-mail
Sygn. / znak sprawy: …            ← obowiązkowo w każdym dalszym piśmie w sprawie

                        TYTUŁ PISMA
                  dopełnienie tytułu
        dotyczy: czego, z datą i identyfikatorem
```

**Data** — zawsze pełna słowna: `Warszawa, dnia 18 sierpnia 2026 r.` Nie `18.08.2026`.

**Miejscowość w adresie** wielkimi literami, kod pocztowy przed nazwą — tak wymaga Poczta Polska
w zasadach adresowania.

**Znak sprawy adresata** cytuj zawsze, gdy go nadał. W administracji ma postać `ABC.123.77.2026`
(instrukcja kancelaryjna, § 5 ust. 4) i umieszcza się go w górnej części pierwszej strony (§ 19 ust. 4).
W piśmie do sądu sygnatura akt jest **obowiązkowa w każdym dalszym piśmie** (art. 126 § 2¹ k.p.c.).

**Tytuł** — wyśrodkowany, wielkimi literami, konstrukcja `RODZAJ PISMA` + dopełnienie:
`WEZWANIE do zaprzestania naruszeń`, `REKLAMACJA`, `SKARGA na bezczynność organu`,
`ODWOŁANIE od decyzji nr …`, `POZEW o zapłatę`.
W piśmie procesowym oznaczenie rodzaju pisma to **wymóg ustawowy** (art. 126 § 1 pkt 3 k.p.c.).

**„dotyczy:"** — tylko w korespondencji z firmą lub urzędem. **W piśmie procesowym do sądu się go
nie stosuje**, tak jak nie stosuje się zwrotów grzecznościowych („Szanowni Państwo", „Z poważaniem").

---

## 4. Oznaczenie stron

**Osoba fizyczna:** imię i nazwisko, adres zamieszkania, PESEL (gdy wymagany).

**Jednoosobowa działalność** — art. 43⁴ k.c.: firmą osoby fizycznej jest jej imię i nazwisko.
- POPRAWNIE: `Jan Nowak prowadzący działalność gospodarczą pod firmą „Nowak Serwis Jan Nowak", ul. …, NIP …`
- BŁĘDNIE: `Nowak Serwis` — sama nazwa handlowa nie jest podmiotem prawa
- BŁĘDNIE: `Nowak Serwis reprezentowany przez Jana Nowaka` — sugeruje odrębny podmiot

Adres przedsiębiorcy CEIDG: **adres do doręczeń wpisany do CEIDG** (art. 126 § 2 pkt 1 k.p.c.),
nie adres zamieszkania.

**Spółka:** pełna firma z formą prawną, siedziba, adres, KRS.
`„ABC" spółka z ograniczoną odpowiedzialnością z siedzibą w Warszawie, ul. …, KRS 0000123456`

**Spółka cywilna nie jest podmiotem** — stronami są wszyscy wspólnicy imiennie. To częsty błąd
przy małych firmach; sprawdź formę prawną, zanim zaadresujesz pismo.

**PESEL / NIP / KRS** podaje się **tylko własne** i **tylko w pierwszym piśmie w sprawie sądowej**
(art. 126 § 2 pkt 2 i 3 k.p.c.). Nie żądaj ich od siebie w reklamacji.

---

## 5. Fakty, dowody, żądania

**Stan faktyczny** — jedno zdarzenie na ustęp, daty bezwzględne, godziny jeśli znane,
identyfikatory (numer zgłoszenia, Message-Id, numer faktury). Każdy fakt z odesłaniem `(zał. N)`.

**Parowanie faktu z dowodem** jest wymogiem ustawowym w piśmie procesowym (art. 126 § 1 pkt 5 k.p.c.:
„wskazanie faktów (…) oraz wskazanie dowodu na wykazanie **każdego** z tych faktów"). Stosuj to
wszędzie — porządkuje pismo i pokazuje, że masz pokrycie.

**Wnioski dowodowe w piśmie do sądu wyodrębnij w osobnej sekcji** — art. 128¹ k.p.c.: wnioski
dowodowe zgłoszone tylko w uzasadnieniu **nie wywołują skutków**. Formalnie wiąże to pełnomocników
zawodowych, ale nic nie ryzykujesz, stosując to zawsze:

```
II. WNIOSKI DOWODOWE
Wnoszę o przeprowadzenie dowodu z:
1) umowy z 1.01.2026 r. (zał. 1) — na fakt zawarcia umowy i wysokości wynagrodzenia;
2) wezwania z 15.03.2026 r. (zał. 2) — na fakt wezwania i jego bezskuteczności.
```

**Żądania** — konkretne, wykonalne, sprawdzalne. Każde ma **co**, **w jakim terminie**, **w jakiej formie**.
> „Zwrotu kwoty 1 240,00 zł na rachunek nr … w terminie 14 dni od dnia doręczenia niniejszego pisma."

„Proszę o wyjaśnienie sytuacji" nie jest żądaniem — nie da się go spełnić ani wyegzekwować.

**Terminy** liczone **od doręczenia**, nie od nadania. Ustawowe cytuj z podstawą (np. miesiąc
z art. 12 ust. 3 RODO). Umowne: 7 dni na czynności proste, 14 na wymagające ustaleń.

---

## 6. Załączniki

Lista **po podpisie**, na końcu pisma, pod nagłówkiem `Załączniki:`. Numeracja ciągła `1., 2., 3.`
W treści odsyłasz `(zał. 3)`. Na samej stronie załącznika nagłówek `Załącznik nr 3 — <tytuł>`.

**Tytuł na liście i tytuł na stronie załącznika muszą być identyczne.** Rozjazd tych dwóch to
klasyczny błąd, przez który odbiorca twierdzi, że czegoś nie dostał. `kontrola_pisma.py` to sprawdza.

Wymienienie załączników jest obowiązkowe w piśmie procesowym (art. 126 § 1 pkt 7 k.p.c.), a same
załączniki trzeba dołączyć (§ 1¹). Do sądu dołącza się też **odpisy dla stron przeciwnych**
(art. 128 § 1 k.p.c.) — pamiętaj o tym przy liczeniu egzemplarzy.

Przy wysyłce papierowej **załączniki wdrukuj w PDF** (`build_pismo.py -z`), żeby wydruk był
kompletny bez dokładania czegokolwiek. Równolegle `dowody.zip` do wysyłki elektronicznej,
z `SHA256SUMS.txt` w środku.

Odesłania „k. 15" (karta akt) używa się **tylko w dalszych pismach**, gdy dokument już jest
w aktach sądu i ma nadaną kartę. W pierwszym piśmie nie występuje. Nie generuj go automatycznie.

---

## 7. Podpis — dobierz świadomie i powiedz użytkownikowi, co ma zrobić

To pytanie zadaj sobie **przy każdym piśmie**, bo odpowiedź zależy od kanału i adresata.

| Sytuacja | Czego trzeba | Podstawa |
|---|---|---|
| E-mail do przedsiębiorcy: reklamacja, wezwanie, odstąpienie, sprzeciw RODO | **Podpis niepotrzebny.** Wystarczy forma dokumentowa — dokument pozwalający ustalić osobę składającą oświadczenie | art. 77² k.c. |
| Papier do przedsiębiorcy | **Podpis własnoręczny** długopisem. Prawnie zwykle niekonieczny, ale wzmacnia i utrudnia kwestionowanie | art. 78 § 1 k.c. |
| Pismo procesowe do sądu wysłane pocztą | **Podpis własnoręczny OBOWIĄZKOWY** | art. 126 § 1 pkt 6 k.p.c. |
| Pismo do sądu przez system teleinformatyczny / Portal Informacyjny | podpis kwalifikowany, zaufany albo osobisty | art. 126 § 5 k.p.c. |
| Podanie / skarga do organu (UODO, UKE, UOKiK) — papier | **podpis własnoręczny** | art. 63 § 3 k.p.a. |
| Skarga do organu elektronicznie | podpis **kwalifikowany, zaufany albo osobisty** | art. 63 k.p.a. |
| Umowa wymagająca formy pisemnej pod rygorem nieważności | podpis własnoręczny **albo kwalifikowany** | art. 78 i 78¹ k.c. |

**Skan podpisu wklejony w PDF:** wystarcza dla formy dokumentowej (e-mail do firmy), **nie wystarcza**
dla formy pisemnej ani dla pisma procesowego. Wydruk ze wklejonym skanem to nie jest podpis
własnoręczny — sąd potraktuje to jako brak formalny.

**Podpis zaufany działa wobec urzędów, nie w obrocie prywatnym.** Art. 20ae ust. 2 ustawy
o informatyzacji: równoważny podpisowi własnoręcznemu — ale zakres ustawy to relacje z podmiotami
realizującymi zadania publiczne. W umowie z firmą podpis zaufany nie spełnia formy pisemnej.

**Podpis kwalifikowany działa wszędzie** — art. 25 ust. 2 eIDAS, równoważny podpisowi własnoręcznemu;
jedyny, który spełnia formę elektroniczną z art. 78¹ k.c.

**Skutek braku podpisu tam, gdzie jest wymagany:** wezwanie do uzupełnienia w 7 dni pod rygorem
zwrotu pisma (art. 130 § 1 k.p.c.); pismo zwrócone **nie wywołuje żadnych skutków** (§ 2).
W administracji — pozostawienie bez rozpoznania (art. 64 § 2 k.p.a.). Jeśli w międzyczasie upłynie
termin materialny, sprawa przepada. Uprzedź o tym użytkownika, gdy pismo idzie do sądu lub organu.

**W PDF zawsze zostaw wyraźne miejsce na podpis odręczny**, gdy jest potrzebny: pozioma linia
szerokości ok. 75 mm, nad nią minimum 20 mm wolnej przestrzeni, pod nią imię i nazwisko.
Szablon ma to w klasie `.podpis-pole`. Podpis idzie **pod treścią pisma, przed listą załączników** —
SN, postanowienie z 30.03.2017, V CZ 23/17: podpis zatwierdza treść, więc musi być pod nią.

---

## 8. Kanał wysyłki

| Adresat | Kanał | Uwaga |
|---|---|---|
| Przedsiębiorca | list polecony **za potwierdzeniem odbioru** + równolegle e-mail | data doręczenia rozpoczyna bieg terminu i trzeba ją umieć wykazać |
| Sąd | biuro podawcze, poczta albo dedykowany system | **e-mail i ePUAP są bezskuteczne** — SN, postanowienie z 29.03.2023, III CZ 427/22 |
| Organ administracji | e-Doręczenia, ePUAP, papier | **e-mail zostawia się bez rozpoznania** (art. 63 § 1 zd. 3 k.p.a.) |
| UODO | papier na ul. Moniuszki 1A, 00-014 Warszawa, albo adres do e-Doręczeń UODO | e-mail nie służy do składania skarg |

e-Doręczenia do przedsiębiorcy traktuj jako **kanał opcjonalny, nie domyślny** — baza adresów nie
jest publicznie przeszukiwalna, a korespondencja prywatna–prywatna jest płatna. Domyślnie:
polecony za potwierdzeniem odbioru na adres z CEIDG/KRS plus e-mail.

Doręczenie oceniasz przez art. 61 § 1 k.c.: oświadczenie jest złożone, gdy doszło do adresata
w taki sposób, że mógł zapoznać się z treścią.

---

## 9. Ton

Rzeczowy, bezosobowy, chłodny. Siła pisma bierze się z precyzji, nie z emocji.

Nie ma w piśmie: wykrzykników, sarkazmu, ocen charakteru („skandaliczne", „bezczelne"), gróźb
pozaprawnych, opisu własnych uczuć, wielkich liter dla podkreślenia, emotikonów.

Jest: konkretna data, konkretna kwota, konkretny przepis, konkretny termin, konkretny załącznik.

Nie stylizuj pisma osoby prywatnej na kancelaryjne i nie sugeruj, że pisał je prawnik. Nie powołuj
przepisów „dla powagi" — niepasujący przepis to pierwsza rzecz, którą wytknie druga strona.

---

## 10. Formuły, które warto znać

- „Niniejsze pismo stanowi próbę pozasądowego rozwiązania sporu w rozumieniu art. 187 § 1 pkt 3 k.p.c.
  oraz wezwanie do spełnienia świadczenia w rozumieniu art. 455 k.c."
  ⚠ Art. 187 § 1 pkt 3 k.p.c. **nie** definiuje „wezwania do zapłaty" — to przepis o informacji
  o próbie mediacji w pozwie. Częsty błąd w szablonach z internetu.
- Zastrzeżenie o niewłaściwym adresacie (wzór w szablonie) — zamyka drogę do zabawy w „to nie my".
- Suma SHA-256 kluczowego dowodu w treści pisma + oświadczenie o zachowaniu oryginału — utrudnia
  późniejsze kwestionowanie autentyczności.
