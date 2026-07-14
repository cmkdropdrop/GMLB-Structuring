# Unabhängiger Produkt- und Regulatorikreview

## AGILE-Modelling-Fachpaper

**Prüfstand:** 11. Juli 2026  
**Geprüfte Hauptdateien:** `AGILE_Modelling_Fachpaper.md` (vollständig), `AGILE.md` (vollständig)  
**Ergänzend geprüft:** `AGILE_Modelling_references.bib`, relevante Stellen in `AGILE_Modelling_Engine/README.md`, `METHODOLOGY.md`, `AUDIT_REPORT.md`, `agile_engine/product.py` und `examples/run_insurer_analysis.py`  
**Scope:** Produkt- und Vertragsangaben sowie regulatorische Einordnung; keine Prüfung der übrigen Mathematik, Ergebnisreconciliation oder Literaturmetadaten.

## 1. Kurzurteil

Die zentralen Produktzahlen des Fachpapers sind überwiegend korrekt: Juli-2026-Maximum-Returns, Guaranteed Minimums, der Basisfall der Lifetime-Income-Rate (männlich, Alter 65, Single Fixed, fünf vollständige Growth-Jahre), Product Fee und Lifetime Income Premium stimmen mit den offiziellen Unterlagen überein. Auch Group-Policy-Grundstruktur, Investor/Life-Insured-Trennung, Statutory Fund No. 2, Total-/Partial-Protection-Payoffs, nachschüssige monatliche Zahlungen und die Grundidee von DVA, MVA, Spouse Insured und Age Pension+ sind im Kern richtig.

Es verbleiben jedoch materielle Präzisierungs- und Vollständigkeitsmängel:

- Der APRA-Abschnitt zitiert nur LPS 110 und LPS 114, obwohl seine Aussagen unmittelbar LPS 115, LPS 117 und LPS 118 betreffen. Die Schlussfolgerung „kein APRA/LAGIC“ ist richtig, die regulatorische Herleitung aber unvollständig.
- Die Hauptdarstellung des Annual-Return-Payoffs bildet nur den marktgebundenen Zweig ab. Der vertraglich mögliche garantierte Fixed Return wird erst später als Modelllücke erwähnt und muss bereits bei der Produktformel als Ausnahme genannt werden.
- Age Pension+ wird zu knapp dargestellt. Election-Zeitpunkt, Investoren-Eignung, funding-spezifischer Beginn, MVA-Lower-of-Test, besondere Withdrawal-Reduktion und der Vorbehalt einer Ratenänderung bei geänderter Capital Access Schedule fehlen in der Produktdarstellung.
- Die Produktdesign-Tabelle verschweigt, dass die Spouse-Varianten eine 63-jährige Frau als jüngeres Leben verwenden. Ohne diese Angabe sind die ausgewiesenen Raten 7,70 % und 4,55 % nicht unabhängig nachvollziehbar.
- Für gleich alte Ehepartner unterschiedlichen Geschlechts und für nicht ganzzahlige Eintrittsalter ist die öffentliche Produktdokumentation nicht eindeutig; die Engine trifft hierfür nicht verifizierte Annahmen.

**Schweregrade:** 0 KRITISCH, 1 HOCH, 10 MITTEL, 2 NIEDRIG, 2 OFFEN.  
Die Befunde rechtfertigen Produkt- und Quellenkorrekturen im Paper, ändern aber den dokumentierten Basisfall 65/männlich/Single Fixed nicht.

## 2. Verwendete offizielle Primärquellen

Seitenangaben zum PDS beziehen sich auf die im Dokument gedruckte Seitennummer; der technische PDF-Index ist um eins niedriger.

| Kürzel | Quelle, Gültigkeit und relevante Fundstellen | Exakte URL |
|---|---|---|
| PDS | Allianz Guaranteed Income for Life Product Disclosure Statement, ausgegeben 19.01.2026; insbesondere S. 2, 12–18, 19–25, 26–35, 38–42, 45–47, 58–63, 65–75, 83–85 und Glossar S. 89–93 | https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/pds-2026/AGILE_PDS_19%20Jan_2026_F1.pdf |
| Income Rates | Lifetime Income Rates, Commencement 01.07.2026–31.07.2026; männliche und weibliche Tabellen S. 1–2 | https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Lifetime_Income_Rates_Jul26.pdf |
| Guaranteed Minimums | Guaranteed Minimums, Commencement 01.07.2026–31.07.2026; aktuelle Werte S. 1 | https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Guaranteed_Minimums_Jul26.pdf |
| Maximum Returns | Maximum Returns, Commencement **oder Anniversary** 01.07.2026–31.07.2026; aktuelle Werte S. 1 | https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Maximum_Returns_Jul26.pdf |
| Rates Centre | Offizielle, datierte Übersicht zu Maximum Returns, Income Rates und Minimums | https://www.allianzretireplus.com.au/adviser-resources/agile-rates.html |
| Bonus Terms | Offizielle Bedingungen des zeitlich/kapazitätsmäßig begrenzten 2-%-Angebots | https://www.allianzretireplus.com.au/about-us/certainty.html |
| LPS 110 | APRA Prudential Standard LPS 110 Capital Adequacy, in Kraft seit 01.07.2023; insbesondere Abs. 28–35, Attachment A und Attachment B | https://www.apra.gov.au/standards/lps-110 |
| LPS 114 | APRA Prudential Standard LPS 114 Capital Adequacy: Asset Risk Charge, aktuelle Fassung in Kraft seit 01.07.2026; insbesondere Abs. 8–23 und 60–84 | https://www.apra.gov.au/standards/lps-114 |
| LPS 115 | APRA Prudential Standard LPS 115 Capital Adequacy: Insurance Risk Charge, Status „in force“ seit 29.03.2023; insbesondere Abs. 8–16 und Stressabschnitte | https://www.apra.gov.au/standards/lps-115 |
| LPS 117 | APRA Prudential Standard LPS 117 Capital Adequacy: Asset Concentration Risk Charge, in Kraft seit 01.10.2024; insbesondere Abs. 8–9 und Attachment A | https://www.apra.gov.au/standards/lps-117 |
| LPS 118 | APRA Prudential Standard LPS 118 Capital Adequacy: Operational Risk Charge, in Kraft seit 01.07.2023; insbesondere Abs. 8–14 | https://www.apra.gov.au/standards/lps-118 |

Alle Webquellen wurden am 11.07.2026 auf den offiziellen Domains `allianzretireplus.com.au` beziehungsweise `apra.gov.au` geöffnet. Sekundärquellen wurden nicht als Beleg für Produkt- oder Regulatorikclaims verwendet.

## 3. Claim-to-Evidence-Übersicht

| Thema | Paper-Fundstelle | Typ | Status | Kernevidenz |
|---|---:|---|---|---|
| Issuer, Group Policy, Investor | Z. 30–32, 196–201 | Produktfakt | BESTÄTIGT MIT PRÄZISIERUNG | PDS S. 2 und 83–84 |
| Statutory Fund No. 2 / Garantie | Z. 30–32, 196–201 | Produktfakt | BESTÄTIGT MIT QUALIFIKATION | PDS S. 2; verfügbare Assets, mögliche Top-up-Pflicht und begrenzte Cessation-Fälle |
| Growth-/Income-Phase | Z. 203–211 | Produktfakt | UNVOLLSTÄNDIG | PDS S. 12–18 und 75; automatische Transition fehlt |
| Vier Protected Investment Options | Z. 218–225 | Produktfakt | BESTÄTIGT | PDS S. 12–13 und 26–30 |
| Juli-2026-Maximum-Returns | Z. 224–232 | Produktfakt | ZAHLEN BESTÄTIGT; VINTAGE UNVOLLSTÄNDIG | Maximum-Returns-Sheet S. 1 nennt Commencement **oder Anniversary** |
| Guaranteed Minimums 0,25/0,50 % | Z. 229–232, 1002 | Produktfakt | BESTÄTIGT; BEGRIFF PRÄZISIEREN | Minimum-Sheet S. 1 und PDS S. 58: Untergrenze des Maximum Return, nicht Annual-Return-Floor |
| TP-/PP10-Payoffformeln | Z. 234–269 | Modellabbildung | KORREKT FÜR MARKT-LINKED BRANCH | PDS S. 26–28; Fixed-Return-Ausnahme fehlt in der Hauptdarstellung |
| Lifetime-Income-Rate | Z. 294–323 | Produktfakt | BASISFALL BESTÄTIGT | Ratecard S. 1: 7,05 % + 5 × 0,35 % = 8,80 % |
| Alter/Geschlecht/jüngeres Leben | Z. 309–312 | Produktfakt | BESTÄTIGT; TIE-/INTERPOLATIONSREGEL OFFEN | PDS S. 18–19, 89; Ratecard S. 1–2 |
| Fixed/Rising | Z. 325–340 | Produktfakt/Modell | BESTÄTIGT MIT FIXED-RETURN-QUALIFIKATION | PDS S. 20–22 und 73–75 |
| Fees 0,30/1,15 % | Z. 342–361 | Produktfakt | BESTÄTIGT | PDS S. 41–42; täglich accrued, eventbezogen deducted; variabel nach Notice |
| Withdrawals/MVA | Z. 363–383 | Produktfakt/Modell | TEILWEISE | PDS S. 31–35 und 60–61; Age-Pension+-Sonderregeln fehlen |
| DVA | Z. 385–396 | Produktfakt/Modell | KERN RICHTIG; QUELLE UND DETAILS KORRIGIEREN | PDS S. 62–63, nicht nur S. 33 |
| Death Benefit / Spouse | Z. 398–404 | Produktfakt/Modell | KERN RICHTIG; WAHL-/DEFAULTREGEL FEHLT | PDS S. 22, 24–25 und 38–40 |
| Age Pension+ / CAS | Z. 359–361, 406–419 | Produktfakt/Modell | UNVOLLSTÄNDIG | PDS S. 15–17, 33–35, 65–70 und Glossar S. 89 |
| Produktdesign-Raten | Z. 1245–1265 | Ergebnis + Produktinput | ZAHLEN REPRODUZIERBAR; INPUT FEHLT | Runner Z. 329–345; Ratecard weiblich, Alter 63 |
| APRA/LAGIC-Abgrenzung | Z. 875–890, 1529–1530 | Regulatorik/Interpretation | SCHLUSSFOLGERUNG RICHTIG; EVIDENZ UNVOLLSTÄNDIG | LPS 110/114/115/117/118 |

## 4. Befunde und direkt einsetzbare Korrekturtexte

### HOCH-REG-01 – APRA-Architektur unvollständig belegt

**Fundstelle:** `AGILE_Modelling_Fachpaper.md`, Z. 875–890; Bibliografie enthält nur `apra2023lps110` und `apra2026lps114`.

**Geprüfte Aussage:** LPS 110 verlange Fund-/Entity-Kapital mit Insurance, Asset, Asset Concentration und Operational Risk; LPS 114 behandle On- und Off-Balance-Sheet-Asset-Risk; der Engine fehlten zentrale APRA-Komponenten.

**Einstufung:** HOCH.

**Evidenz und Beurteilung:**

- LPS 110, Abs. 28–35, definiert den Prescribed Capital Amount als Insurance Risk Charge + Asset Risk Charge + Asset Concentration Risk Charge + Operational Risk Charge – Aggregation Benefit + Combined Stress Scenario Adjustment. Abs. 28 verlangt bei Variable-Annuity-Business eine Attachment-A-Berechnung; Attachment B regelt den kombinierten Stress. Quelle: https://www.apra.gov.au/standards/lps-110
- LPS 114, aktuelle Fassung ab 01.07.2026, Abs. 8–12, verlangt sieben Asset-Stresses: real interest rates, expected inflation, currency, equity, property, credit spreads und default. Effektive Exposures der Assets **und Liabilities**, einschließlich Off-Balance-Sheet-Exposures, sind einzubeziehen. Quelle: https://www.apra.gov.au/standards/lps-114
- LPS 115 erfasst Mortality, Morbidity, Longevity, Lapse, Servicing Expenses und sonstige Insurance Contingencies wie Option Take-up und verlangt stressed policy liabilities auf Statutory-Fund-Ebene. Quelle: https://www.apra.gov.au/standards/lps-115
- LPS 117 verlangt zusätzliches Kapital für Überschreitungen von Konzentrationslimits. Quelle: https://www.apra.gov.au/standards/lps-117
- LPS 118 verlangt eine eigenständige Operational Risk Charge. Quelle: https://www.apra.gov.au/standards/lps-118

Die Aussage „kein APRA/LAGIC“ ist sachlich richtig. Die derzeitige Herleitung ist aber nicht vollständig, weil drei unmittelbar einschlägige Standards weder zitiert noch bibliografiert sind und der Unterschied zwischen dem SII-Proxy und APRA-Stressed-Policy-Liabilities nicht erläutert wird.

**Empfohlener Ersatztext:**

> LPS 110 verlangt die Kapitalermittlung je Fund und für die Life Company insgesamt. Der Standard Method-PCA eines Funds umfasst Insurance Risk nach LPS 115, Asset Risk nach LPS 114, Asset Concentration Risk nach LPS 117 und Operational Risk nach LPS 118, abzüglich Aggregation Benefit und zuzüglich Combined Stress Scenario Adjustment. Die seit 1. Juli 2026 geltende Fassung von LPS 114 erfasst sieben Stresskomponenten auf effektive Asset- und Liability-Exposures einschließlich Off-Balance-Sheet-Positionen. LPS 115 bewertet demgegenüber stressed policy liabilities unter Mortality-, Morbidity-, Longevity-, Lapse-, Expense- und weiteren Insurance-Contingency-Stresses. Der vorliegende SII-artige Einzelpolicenproxy besitzt weder eine Statutory-Fund-Bilanz noch die LPS-115-Liability-Basis, LPS-114-Exposures, LPS-117-Konzentrationen, LPS-118-Operational-Risk-Charge oder die LPS-110-Aggregation und ist daher kein APRA-Prescribed-Capital-Amount.

**Erforderliche Folgeänderung:** Drei BibTeX-Einträge für LPS 115, 117 und 118 ergänzen und alle fünf Standards im Absatz zitieren.

### MITTEL-PROD-01 – Garantie- und Group-Policy-Wortlaut zu stark verkürzt

**Fundstelle:** Z. 30–32 und 196–201.

**Geprüfte Aussage:** Garantierte Leistungen seien Verpflichtungen von Allianz Australia Life „aus Statutory Fund No. 2“; der Investor habe ein wirtschaftliches Interesse.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 2 und 83–84. Allianz Australia Life ist Issuer; die Group Policy ist an Allianz Australia Life Policy Services Pty Limited ausgegeben. Der Investor erwirbt ein **interest under the Group Policy** und ist specified beneficiary; Allianz zahlt die Income Streams direkt an den Investor. Investments werden Statutory Fund No. 2 zugeordnet. „Guarantee“ bedeutet Erfüllung der Zusagen aus den verfügbaren Assets dieses Funds; Allianz kann bei Unterdeckung zu einem Top-up verpflichtet werden, darf das Produkt aber in begrenzten PDS-Fällen beenden. Die Allianz-Mutter garantiert nicht.

**Empfohlener Ersatztext:**

> AGILE wird von Allianz Australia Life Insurance Limited ausgegeben und als Group Policy an deren Tochter Allianz Australia Life Policy Services Pty Limited strukturiert. Der Investor erwirbt als specified beneficiary ein unmittelbares Interesse unter der Group Policy; das Investor Certificate dokumentiert dieses Interesse und die individuellen Parameter. Allianz Australia Life zahlt die Leistungen direkt an den Investor. Die AGILE-Investments werden Statutory Fund No. 2 zugeordnet. Die Garantie bezeichnet die vertraglichen Zusagen von Allianz Australia Life, die aus den verfügbaren Assets dieses Statutory Fund erfüllt werden; mögliche Top-up-Anforderungen und die im PDS genannten begrenzten Group-Policy-Cessation-Fälle sind zu beachten. Eine Garantie durch Allianz SE oder andere Konzernunternehmen besteht nicht.

### MITTEL-PROD-02 – Automatischer Phasenwechsel fehlt

**Fundstelle:** Z. 203–211.

**Geprüfte Aussage:** Nach frühestens einem Jahr könne Lifetime Income aktiviert werden.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 17–18 und 75. Das Wahlrecht nach einem Jahr ist richtig und der Wechsel ist irreversibel. Zusätzlich erfolgt eine automatische Transition am nächsten Anniversary nach Alter 100; bei bereits gewähltem Age Pension+ spätestens am nächsten Anniversary nach der bei Age-Pension+-Commencement bestimmten Life Expectancy. Ohne Rückmeldung ist der Default Fixed Income ohne Spouse Insured. Fehlen Kontakt-/Bankdaten, behält sich Allianz einen Full Withdrawal vor.

**Empfohlene Ergänzung:**

> Der freiwillige Start ist nach dem ersten Jahr möglich und irreversibel. Daneben kennt der Vertrag einen spätesten Start: ohne Age Pension+ automatisch am nächsten Anniversary nach Vollendung des 100. Lebensjahrs, mit Age Pension+ am nächsten Anniversary nach Erreichen der bei Age-Pension+-Commencement bestimmten Life Expectancy. Ohne Optionsinstruktion wird Fixed Income ohne Spouse Insured verwendet. Diese automatische Commencement-/Default-Logik ist in der Engine nicht als allgemeine Vertragsregel abgebildet und gehört in die Production-Blocker.

### MITTEL-PROD-03 – Maximum-Return-Vintage und Guaranteed-Minimum-Begriff

**Fundstelle:** Z. 143, 224–232 und 1002.

**Einstufung:** MITTEL.

**Evidenz:** Das offizielle Juli-2026-Maximum-Returns-Sheet, S. 1, sagt ausdrücklich „commencement **or anniversary date** between 01/07/2026 and 31/07/2026“. Die Werte 6,20/13,00/6,00/12,80 % sind korrekt. Das Minimum-Sheet bestätigt 0,25 % für Total und 0,50 % für Partial Protection. Diese Minimums begrenzen jedoch den künftig gesetzten **Maximum Return nach unten**; sie sind kein garantierter Annual Return und kein Schutz-Floor des Kundenpayoffs.

**Empfohlener Ersatztext:**

> Die Maximum Returns 6,20 %, 13,00 %, 6,00 % und 12,80 % gelten für AGILE-Investments mit Commencement **oder Anniversary Date** zwischen 1. und 31. Juli 2026. Für bestehende Investments ist zusätzlich der im Investor Certificate festgelegte Guaranteed Minimum maßgeblich. Die Werte 0,25 % (Total Protection) und 0,50 % (Partial Protection) sind garantierte Untergrenzen des jährlich neu gesetzten Maximum Return, nicht garantierte Mindestjahresrenditen. Der Rendite-Floor aus Total Protection ist davon begrifflich zu trennen.

**Quellen:** Maximum-Returns-Sheet und Guaranteed-Minimums-Sheet, jeweils S. 1, URLs in Abschnitt 2.

### MITTEL-PROD-04 – Fixed-Return-Zweig muss schon bei der Payoffformel stehen

**Fundstelle:** Z. 234–273 und 325–340; die Lücke wird erst Z. 394–396 und 1527–1528 offengelegt.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 58 und 60 sowie Glossar S. 90. Allianz darf für Total Protection einen garantierten einjährigen Fixed Return anwenden, wenn dieser bei der Rate-Setting-Entscheidung mindestens so hoch ist wie der relevante Maximum Return. In diesem Jahr ist der Annual Return nicht marktgebunden. PDS S. 62 bestimmt für diesen Fall eine zeitanteilige Fixed-Return-DVA.

Die Formeln `c_TP` und `c_PP10` sind als Engineformeln für den marktgebundenen Zweig korrekt. Die Sätze „Die Kundenrendite liegt damit …“ und die Rising-Formel können aber als vollständige Vertragsformel gelesen werden.

**Empfohlene Korrektur:**

> Unter der in der Engine modellierten marktgebundenen Branch und sofern Allianz keinen garantierten Fixed Return anwendet, lauten die Payoffs … . Das PDS erlaubt bei Total Protection alternativ einen einjährigen garantierten Fixed Return, wenn dieser bei der Rate-Festlegung einen mindestens gleich hohen Annual Return wie der Maximum Return liefern kann. Dieser nicht marktgebundene Zweig und seine pro-rata DVA sind im vorliegenden Modell nicht implementiert.

### MITTEL-PROD-05 – DVA-Quelle und vertragliche Mindestwerte

**Fundstelle:** Z. 385–396; derzeitiger Beleg „PDS S. 33“.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 62–63 ist die maßgebliche Detailfundstelle. Die DVA ist nicht die laufende tatsächliche Indexrendite, sondern der Wert der relevanten Derivatekontrakte. Sie ist Bestandteil des Investment Value, wird aber bei unterjährigen Transaktionen oder Off-anniversary-Income-Commencement credited/debited. Bei gestiegenem Index gilt mindestens der Indexreturn bis zum zeitanteiligen Cap; bei gefallenem Index mindestens der zeitanteilige Protection Level. Bei Fixed Return gilt dessen zeitanteiliger Anteil.

**Empfohlener Ersatztext:**

> Das PDS beschreibt die DVA als unterjährigen Wert der für das Investment relevanten Derivatekontrakte, nicht als realisierte Year-to-date-Indexrendite. Der DVA Amount ist im Investment Value enthalten und wird bei unterjährigen Transaktionen beziehungsweise Off-anniversary-Income-Commencement credited oder debited. Vertragliche Mindestwerte sind ein pro-rata Maximum Return beziehungsweise pro-rata Protection Level; bei angewandtem Fixed Return gilt dessen pro-rata Anteil (PDS S. 62–63). Der Engine-Hedgewertproxy bildet diese Mindestwert- und Fixed-Return-Zweige noch nicht vollständig ab.

**Zitationsänderung:** `[@allianz2026pds, S. 62--63]` statt nur S. 33.

### MITTEL-PROD-06 – Withdrawals/MVA nicht universell proportional

**Fundstelle:** Z. 365–370 und 400–419.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 31–35 und 64–70.

- Ohne Age Pension+ gilt in der Growth Phase 5 % des initial Investment Amount als jährlicher Free Withdrawal Amount, ohne Carry-forward. In den ersten zehn Jahren unterliegen darüber hinausgehende Beträge und Full Withdrawals der MVA. Excess Withdrawals in der Income Phase reduzieren IV und künftiges Income proportional zu Withdrawal plus MVA relativ zum IV.
- Mit Age Pension+ gibt es keinen Free Withdrawal Amount; alle Withdrawals sind excess. Verfügbar ist der niedrigere Wert aus `IV − anwendbarer MVA` und `Age Pension+ Maximum Withdrawal Value`. Die MVA wird nur wirksam, wenn der erste Zweig bindet, und nicht separat erhoben, wenn der MWV bindet. Bei bindendem MWV kann die IV-/Income-Reduktion prozentual größer sein als der ausgezahlte Dollarbetrag.
- Zusätzlich gelten unter anderem AUD 100 Minimum, 95-%-Einzel-/Jahreslimits in der Growth Phase und ein verbleibender Withdrawal Value von mindestens AUD 2.000.

**Empfohlener Ersatztext:**

> Die proportionale Reduktion mit dem Nenner Investment Value gilt für Excess Withdrawals ohne Age Pension+. Nach Age-Pension+-Election gilt eine separate Lower-of- und Reduktionslogik: Der Withdrawal Value ist auf den niedrigeren Wert aus Investment Value abzüglich anwendbarer MVA und Maximum Withdrawal Value begrenzt; bindet der MWV, wird keine MVA separat belastet und die prozentuale IV-/Income-Reduktion kann den ausgezahlten Anteil übersteigen. Die Engineabbildung dieser Sonderlogik ist als Modellregel und nicht als gewöhnliche Withdrawal-Proportionalität zu beschreiben.

### MITTEL-PROD-07 – Age Pension+: Election, Verfügbarkeit und Ratenvorbehalt fehlen

**Fundstelle:** Z. 359–361 und 406–419.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 15–17 und Glossar S. 89.

- Election muss zum frühesten der einschlägigen Ereignisse erfolgen: Income Commencement, bei Superannuation Relevant Condition of Release (einschließlich Alter 65), bei Non-super Pension Age. Entscheidung für oder gegen die Option ist dann unwiderruflich.
- Funding-spezifischer Beginn: Superannuation erst bei Condition of Release; Non-super am früheren von Income Start und Pension Age.
- Die Option steht Non-superannuation-Trustee-/Company-Investors grundsätzlich nicht offen, ausgenommen Non-super-Platform-Trustees.
- Die bei Commencement bestätigten Age-Pension+-Rates setzen eine unveränderte Capital Access Schedule bis zum tatsächlichen Beginn der Option voraus. Ändert sich die CAS, behält sich Allianz eine Änderung der Age-Based Rate und Escalator Rate für diese Option vor.

**Empfohlene Ergänzung:**

> Age Pension+ ist keine jederzeit frei aktivierbare Zusatzoption. Election und Commencement hängen von Funding Source, Condition of Release beziehungsweise Pension Age und Income Start ab; die Entscheidung am maßgeblichen Zeitpunkt ist unwiderruflich. Die bei Product Commencement gezeigten Age-Pension+-Rates stehen unter dem ausdrücklichen Vorbehalt einer unveränderten Capital Access Schedule bis zum Beginn der Option. Für modellierte Age-Pension+-Cashflows sind daher Funding Source, Election Date, Commencement Date, CAS-Vintage und die bestätigte Ratecard gemeinsam zu speichern.

### MITTEL-PROD-08 – Spouse-/Death-Election nicht nur „modellierte Election“

**Fundstelle:** Z. 400–404.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 22, 24–25 und 38–40. Nach Spouse-Insured-Election kann Income bei Tod des Life Insured weiterlaufen, sofern die Eligibility-/Beneficiary-Bedingungen erfüllt sind, oder ein Lump Sum gewählt werden. Wer anweisen darf, hängt vom Investor-Typ ab. Bei fehlender Instruktion ist der PDS-Default die Fortsetzung des Income. Life Insured oder Surviving Spouse haben keine eigenen Vertragsrechte, wenn sie nicht Investor sind.

**Empfohlener Ersatztext:**

> Mit wirksam gewählter Spouse Insured Option und erfüllten PDS-Bedingungen wird das Lifetime Income nach Tod des Life Insured für die Lebenszeit des Surviving Spouse fortgesetzt, sofern die nach Investor-/Beneficiary-Struktur berechtigte Partei nicht stattdessen den Lump Sum wählt. Ohne Instruktion setzt Allianz die Income-Zahlungen standardmäßig fort. `spouse_death_election` ist daher ein modellierter Szenarioinput für ein vertragliches Wahlrecht, dessen Inhaber und Default vom Ownership-Pfad abhängen.

### MITTEL-RESULT-09 – Spouse-Modellpunkt in Produktdesign-Tabelle fehlt

**Fundstelle:** Z. 1245–1265.

**Einstufung:** MITTEL.

**Evidenz:** `examples/run_insurer_analysis.py`, Z. 329–345, setzt für beide Spouse-Varianten `spouse_age=63` und `spouse_sex=FEMALE`. Die Juli-2026-Female-Ratecard ergibt bei Alter 63, Spouse, ohne Age Pension+: Fixed 6,20 % + 5 × 0,30 % = 7,70 %; Rising 3,30 % + 5 × 0,25 % = 4,55 %. Die Tabellenwerte sind damit richtig, aber ohne offengelegten Model Point nicht auditierbar.

**Erforderliche Ergänzung unmittelbar vor der Tabelle:**

> Für die Spouse-Varianten wird zusätzlich eine 63-jährige Frau am Product Commencement Date modelliert; sie ist gegenüber dem 65-jährigen männlichen Life Insured das jüngere und damit ratenbestimmende Leben. Die Age-Pension+-Varianten bleiben Single Life, männlich, Alter 65, und verwenden eine illustrative CAS-Lebenserwartung von 20 Jahren.

### MITTEL-PROD-10 – Gebühren sind aktuelle Sätze, nicht unveränderliche Vertragsparameter

**Fundstelle:** Z. 342–361 und Modellpunkt Z. 1030.

**Einstufung:** MITTEL.

**Evidenz:** PDS S. 41–42 bestätigt 0,30 % p. a. Product Fee und 1,15 % p. a. LIP, täglich accrued auf IV ohne DVA/aufgelaufene Fees/Premiums und bei festgelegten Events deducted. PDS S. 42 erlaubt eine Variation von Fees/Premiums beziehungsweise deren Frequenz mit mindestens 30 Tagen oder anderer angemessener Notice im Rahmen des Relevant Law.

**Empfohlene Korrektur:**

> Nach dem PDS vom 19. Januar 2026 betragen die aktuellen Sätze 0,30 % p. a. und 1,15 % p. a. Für den Modellpunkt werden sie über die gesamte Laufzeit konstant gehalten. Dies ist eine Modellannahme; das PDS enthält ein rechtlich begrenztes Änderungsrecht mit Notice.

### NIEDRIG-TERM-01 – „APS“ ist nicht als offizieller Produktbegriff definiert

**Fundstelle:** unter anderem Z. 429, 487, 740, 756, 825, 900, 1256–1264 und 1524.

**Einstufung:** NIEDRIG.

**Beurteilung:** Das PDS verwendet „Age Pension+ Option“ und „Capital Access Schedule (CAS)“. `aps` ist eine interne Codeabkürzung. Im Paper kann „APS“ zudem mit Allianz Australia Life Policy Services verwechselt werden.

**Korrektur:** In Fließtext, Tabellen und Abbildungen „Age Pension+“ verwenden. Falls Codefelder erläutert werden, einmal ausdrücklich definieren: „internes Engine-Kürzel `aps` für `AgePensionPlusSpec`; kein offizieller Produktbegriff“.

### NIEDRIG-PROD-02 – Produktdefinition von Gender dokumentieren

**Fundstelle:** Z. 305–312.

**Einstufung:** NIEDRIG.

**Evidenz:** PDS-Glossar S. 90 definiert `Gender` produktspezifisch als bei Geburt registriertes Geschlecht. Die Ratecard enthält Male-/Female-Tabellen; der Code verwendet `Sex.MALE/FEMALE`.

**Korrektur:** Beim ersten Auftreten ergänzen, dass „Geschlecht“ die PDS-Definition von `Gender` wiedergibt. Das ist eine Dokumentationspräzisierung, keine Aussage über eine allgemeine aktuarielle Geschlechtsdefinition.

### OFFEN-RATE-01 – Gleich alte Spouses und nicht ganzzahlige Alter

**Fundstelle:** Z. 309–312; Engine `agile_engine/product.py`, Z. 349–365.

**Einstufung:** OFFEN.

**Evidenz und Konflikt:** PDS S. 18–19 und Ratecard S. 1–2 verweisen bei Spouse Insured auf Alter und Gender des **jüngeren** Lebens. Sie regeln in den öffentlich geprüften Unterlagen nicht, welche Gender-Tabelle bei exakt gleichem Alter und unterschiedlichem Gender gilt. Die Ratecard weist nur ganzzahlige Alter 50–80 aus und beschreibt keine Interpolation. Die Engine wählt bei Gleichstand das Primary Life (`spouse_age < rating_age`, nicht `<=`) und interpoliert linear zwischen Alterszeilen (`np.interp`). Beides ist öffentlich nicht verifiziert.

**Erforderliche Behandlung:**

- Basisfall und aktuelle Ergebnisvarianten sind nicht betroffen, weil alle ratenbestimmenden Alter ganzzahlig und die Spouse-Variante eindeutig jünger ist.
- Für Production keine Interpolation oder Tie-Regel als Produktfakt ausgeben. Admin-Spezifikation/Investor Certificate beziehungsweise schriftliche Allianz-Regel einholen.
- Im Paper als offener Product-Sign-off-Punkt ergänzen.

### OFFEN-REG-02 – APRA-Klassifikation von AGILE als Variable-Annuity-Business

**Fundstelle:** Z. 27–32 und 877–882.

**Einstufung:** OFFEN.

**Evidenz:** LPS 110 Attachment A gilt für einen Statutory Fund „containing variable annuity business“ und verlangt dort gemeinsame Asset-/Insurance-Risk-Modellierung sowie APRA-Genehmigung der Methode vor Ausgabe solcher Policies. Das Paper bezeichnet AGILE ausdrücklich nur als **ökonomische** FIA-plus-GLWB-Analogie. Weder das geprüfte PDS noch eine öffentlich geprüfte APRA-Quelle bestätigt, wie Allianz/APRA AGILE für Attachment A tatsächlich klassifiziert.

**Korrektur:**

> LPS 110 Attachment A enthält Sonderregeln für Statutory Funds mit Variable-Annuity-Business. Die ökonomische FIA-/GLWB-Modellabstraktion dieses Papers belegt nicht, dass APRA AGILE rechtlich oder aufsichtlich dieser Kategorie zuordnet. Die konkrete APRA-Klassifikation und eine etwaige genehmigte Methode sind ohne nichtöffentliche Allianz-/APRA-Unterlagen offen.

Damit bleibt die allgemeine Aussage über Attachment A erhalten, ohne eine unbelegte AGILE-spezifische Klassifikation zu suggerieren.

## 5. Positiv bestätigte Kernclaims

Die folgenden Aussagen können nach dem offiziellen Quellenabgleich beibehalten werden, jeweils mit dem oben genannten Vintage:

1. **Issuer/Struktur:** Allianz Australia Life Insurance Limited ist Issuer; die Group Policy ist an Allianz Australia Life Policy Services Pty Limited ausgegeben; Investor und Life Insured können auseinanderfallen.
2. **Statutory Fund:** AGILE wird Statutory Fund No. 2 zugeordnet.
3. **Protected Investment Options:** Australian/Global × Total/Partial-10 sind die vier Growth-Phase-Optionen; in der Income Phase wird Australian Equity Index – Total Protection verwendet.
4. **Market-linked Payoffs:** Total Protection liefert im marktgebundenen Zweig `min(max(R,0),C)`; Partial-10 liefert für negative Returns `min(0,R+10%)`. Das −18-%-/−8-%-Beispiel stimmt.
5. **Juli-2026-Maximum-Returns:** 6,20 %, 13,00 %, 6,00 %, 12,80 %.
6. **Juli-2026-Guaranteed-Minimums:** 0,25 % für Total und 0,50 % für Partial Protection als Minimum des künftigen Maximum Return.
7. **Ratecard:** Alter und Gender am Product Commencement Date sind maßgeblich; bei eindeutig jüngerem Spouse dessen Alter/Gender; nur vollständige Growth-Jahre zählen.
8. **Basisrate:** Mann, 65, Single Fixed, kein Age Pension+, fünf Jahre Growth: `7,05 % + 5 × 0,35 % = 8,80 %`.
9. **Fixed/Rising:** Fixed ist nominal level vorbehaltlich reduzierender Ereignisse; Rising ratchetiert bei positivem Annual Return, ist aber nicht CPI-indexiert.
10. **Fees:** 0,30 % Product Fee und 1,15 % LIP nach PDS 19.01.2026; tägliches Accrual, eventbezogene Deduction.
11. **MVA:** nur in den ersten zehn Jahren; kein MVA auf Death Benefit.
12. **DVA:** anwendbar auf unterjährige Transaktionen/Off-anniversary-Income-Start und nicht identisch mit Year-to-date-Indexperformance.
13. **Death Benefit:** grundsätzlich positiver IV zum Zahlungszeitpunkt, vorbehaltlich Age-Pension+-Death-Cap und Spouse-Pfad.
14. **Age Pension+ MWV:** Start bei 100 % des IV am Age-Pension+-Commencement, straight-line bis null bei Life Expectancy, angepasst um Withdrawals. Die Paperformel ist als vereinfachte Modellgleichung sachgerecht bezeichnet.
15. **APRA-Grenze:** Ein Einzelpolicen-SII-Proxy ohne Fund-Bilanz, Assets/Hedges, LPS-115-Liability-Stresses, Konzentrationen, Operational Risk und LPS-110-Aggregation ist kein APRA/LAGIC-Ergebnis.
16. **2-%-Angebot:** Die Nichtverwendung als Produktdefault ist sachgerecht; die offizielle Kampagne ist zeitlich bis 31.07.2026 beziehungsweise früherer Kapazitätsausschöpfung begrenzt und steht unter Eligibility-/Änderungsvorbehalten.

## 6. Empfohlene neue Bibliografieeinträge

Die konkrete BibTeX-Syntax ist an den Stil der Hauptbibliografie anzupassen. Inhaltlich müssen mindestens folgende Primärquellen ergänzt werden:

```bibtex
@techreport{apra2023lps115,
  author      = {{Australian Prudential Regulation Authority}},
  title       = {Prudential Standard LPS 115: Capital Adequacy -- Insurance Risk Charge},
  institution = {APRA},
  year        = {2023},
  url         = {https://www.apra.gov.au/standards/lps-115},
  urldate     = {2026-07-11}
}

@techreport{apra2024lps117,
  author      = {{Australian Prudential Regulation Authority}},
  title       = {Prudential Standard LPS 117: Capital Adequacy -- Asset Concentration Risk Charge},
  institution = {APRA},
  year        = {2024},
  url         = {https://www.apra.gov.au/standards/lps-117},
  urldate     = {2026-07-11}
}

@techreport{apra2023lps118,
  author      = {{Australian Prudential Regulation Authority}},
  title       = {Prudential Standard LPS 118: Capital Adequacy -- Operational Risk Charge},
  institution = {APRA},
  year        = {2023},
  url         = {https://www.apra.gov.au/standards/lps-118},
  urldate     = {2026-07-11}
}

@techreport{allianz2026maximums,
  author      = {{Allianz Australia Life Insurance Limited}},
  title       = {AGILE Maximum Returns: Commencement or Anniversary 01/07/2026--31/07/2026},
  institution = {Allianz Retire+},
  year        = {2026},
  month       = jul,
  url         = {https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Maximum_Returns_Jul26.pdf},
  urldate     = {2026-07-11}
}
```

## 7. Priorisierte Übergabe an die Hauptrevision

1. Zuerst HOCH-REG-01 umsetzen und LPS 115/117/118 bibliografieren.
2. Im Produktkapitel die Ersatztexte zu Group Policy/Guarantee, Fixed Return, DVA und Age Pension+ einarbeiten.
3. Die Begriffe `Guaranteed Minimum`, `Annual-Return-Floor`, `Maximum Return` und `Protection Floor` strikt trennen.
4. Vor der Produktdesign-Tabelle den 63/Female-Spouse-Modellpunkt offenlegen und `APS` in sichtbaren Labels durch `Age Pension+` ersetzen.
5. Equal-age-/fractional-age-Rating sowie die tatsächliche APRA-Variable-Annuity-Klassifikation als **OFFEN** belassen; keine Regel erfinden.
6. Automatic Income Commencement als nicht modellierte Vertragsregel in die Production-Blocker aufnehmen.

## 8. Prüfnachweis

- `AGILE_Modelling_Fachpaper.md`: 1.772 Zeilen vollständig gelesen.
- `AGILE.md`: 616 Zeilen vollständig gelesen.
- Offizielle PDFs direkt geöffnet und deren Text-/Tabelleninhalte geprüft: PDS (96 PDF-Seiten), Income Rates (3), Guaranteed Minimums (3), Maximum Returns (3).
- APRA-Statusseiten und Standardtexte LPS 110, 114, 115, 117 und 118 direkt auf `apra.gov.au` geprüft.
- Keine Engine-, Paper-, Bibliografie- oder Ergebnisdatei geändert.
- Dieser Review ist eine neue Arbeitsdatei und enthält keine erfundenen Produkt- oder Adminregeln.
