---
name: eskalacja
description: Planuje kolejne kroki po bezskutecznym upływie terminu — który organ, jaki tryb, jaki koszt, jakie szanse, w jakiej kolejności. Użyj, gdy druga strona milczy, odmówił albo termin właśnie minął.
argument-hint: "[katalog sprawy]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(date *) Read Write Edit
---

# Plan eskalacji

Sprawa: `$ARGUMENTS`

## 1. Ustal, gdzie naprawdę jesteśmy

Z `index.md`: co wysłano, kiedy doręczono, jaki był termin, czy minął, co odpowiedziano.
Sprawdź dzisiejszą datę (`date +%F`) i policz. Jeśli termin **jeszcze nie minął** — powiedz to
i nie planuj eskalacji na zapas.

Jeśli druga strona odpowiedział — przeczytaj odpowiedź. Odmowa merytoryczna, milczenie i odpowiedź
wymijająca prowadzą do różnych ścieżek.

## 2. Dobierz ścieżki — konkretni adresaci, terminy, koszty

Wypisz **wszystkie** dostępne tryby. Nie wykluczają się nawzajem.

---

**PUODO — Prezes Urzędu Ochrony Danych Osobowych**
- Adres: ul. Stawki 2, 00-193 Warszawa
- E-mail / e-Doręczenia: kancelaria@uodo.gov.pl | adres ADE PUODO w bazie edoreczenia.gov.pl
- Formularz: uodo.gov.pl → Zgłoś naruszenie / Złóż skargę
- Termin rozpoznania: brak ustawowego (w praktyce 6–18 miesięcy)
- Koszt: bezpłatne
- Czego NIE osiągniesz: odszkodowania, zwrotu kosztów, wyroku nakazującego zapłatę
- Kiedy: naruszenie RODO przez administratora, odmowa realizacji praw (art. 15–22), wyciek danych

---

**UOKiK — Prezes Urzędu Ochrony Konkurencji i Konsumentów**
- Adres: pl. Powstańców Warszawy 1, 00-950 Warszawa
- Formularz: uokik.gov.pl → Złóż zawiadomienie
- Termin: brak ustawowego (w praktyce wiele miesięcy do lat)
- Koszt: bezpłatne
- Czego NIE osiągniesz: indywidualnego odszkodowania — postępowanie w interesie zbiorowym
- Kiedy: klauzule abuzywne (art. 385¹ KC), zmiana wzorca bez powiadomienia, praktyki naruszające zbiorowe interesy konsumentów (art. 24 u.o.k.k.)

---

**Miejski / Powiatowy Rzecznik Konsumentów**
- Adres: właściwy dla miejsca zamieszkania konsumenta (szukaj na stronie UOKiK)
- Kontakt: osobiście lub pismo
- Termin odpowiedzi do przedsiębiorcy: 30 dni (art. 42 u.o.k.k.)
- Koszt: bezpłatne
- Co osiągniesz: wystąpienie do przedsiębiorcy w imieniu konsumenta, bezpłatna porada prawna, mediacja
- Kiedy: pierwsza eskalacja w sprawach konsumenckich, zanim skierujesz do sądu

---

**UKE — Koordynator ds. usług cyfrowych (DSA)**
- Adres / formularz: uke.gov.pl
- Termin: brak ustawowego
- Koszt: bezpłatne
- Kiedy: naruszenie DSA przez platformę — brak statement of reasons (art. 17 DSA), brak zgłoszenia do rejestru, niereagowanie na zgłoszenia treści niezgodnych z prawem

---

**ADR — Inspekcja Handlowa (polubowne rozwiązywanie sporów)**
- Adres: właściwy Wojewódzki Inspektorat Inspekcji Handlowej (szukaj: ihik.gov.pl)
- Termin rozstrzygnięcia: 90 dni
- Koszt: bezpłatne dla konsumenta
- Czego NIE osiągniesz: wyroku sądowego, egzekucji komorniczej
- Kiedy: spór o świadczenie pieniężne z przedsiębiorcą, szybsza ścieżka niż sąd, gdy przedsiębiorca przystąpił do systemu ADR

---

**Chargeback — u wydawcy karty płatniczej**
- Gdzie: bank lub wydawca karty (Visa/Mastercard przez bank)
- ⚠ TERMIN KRÓTKI: zwykle 60–120 dni od daty obciążenia (sprawdź warunki swojej karty)
- Koszt: bezpłatne
- Kiedy: nieautoryzowane obciążenie, towar/usługa nie dostarczona lub niezgodna z opisem
- Działaj natychmiast po bezskutecznej reklamacji — termin nie czeka

---

**EPU / Pozew sądowy**
- E-sąd (EPU): e-sad.gov.pl — dla roszczeń pieniężnych, opłata 1/4 opłaty stałej
- Sąd rejonowy: właściwy dla pozwanego lub dla miejsca wykonania umowy
- Koszt: 5% wartości sporu (min. 30 zł), maksimum — sprawdź kksc
- Termin przedawnienia: 6 lat dla roszczeń majątkowych (art. 118 KC), 3 lata dla roszczeń z działalności gospodarczej
- Czego NIE osiągniesz bez prawnika przy stawce > 20 000 zł: realnej skuteczności bez profesjonalnego pełnomocnika
- Kiedy: ostateczność — wcześniej zebrany komplet dowodów decyduje

## 3. Oceń uczciwie

Dla każdej ścieżki podaj, **czego nie osiągnie**. Skarga do organu nie zwróci pieniędzy. Kara
administracyjna trafia do budżetu państwa, nie do poszkodowanego. Postępowanie potrafi trwać
dwa lata. Użytkownik ma prawo wiedzieć, w co wchodzi, zanim wejdzie.

Powiedz też wprost, kiedy **nie warto** — gdy koszt i czas przewyższają stawkę, a jedyną korzyścią
jest satysfakcja. To jest uczciwa odpowiedź, nie porażka.

Nie jesteś prawnikiem i tego nie ukrywaj: przy sprawach o wysokiej stawce, skomplikowanym stanie
faktycznym albo krótkim terminie zawitym — powiedz, że warto skonsultować się z radcą prawnym
lub adwokatem, i wskaż konkretnie dlaczego akurat tutaj.

## 4. Ułóż kolejność

Rekomendacja to **jedna** ścieżka jako następny krok plus uzasadnienie, dlaczego ta pierwsza.
Zwykle: najpierw tanie i szybkie, równolegle to, co ma krótki termin na wniesienie, na końcu sąd.
Pilnuj terminów zawitych — one nie czekają na resztę planu.

## 5. Zapisz w teczce

Uzupełnij sekcję „6. Ścieżka eskalacji" w `index.md`, dopisz terminy do chronologii jako przyszłe
wiersze, dopisz zadania do TODO. Zaproponuj `/kruczek:pismo` dla pierwszego kroku.
