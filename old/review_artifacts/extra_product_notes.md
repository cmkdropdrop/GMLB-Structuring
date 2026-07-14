---
title: "AGILE im Detail: Produktmechanik und Modellabbildung"
lang: de-DE
bibliography: ../AGILE_Modelling_references_reviewed.bib
link-citations: true
---

# AGILE im Detail: Produktmechanik und Modellabbildung

## Zweck und Leseschlüssel

Dieses Dokument erklärt zwei Dinge getrennt:

1. **wie AGILE laut den öffentlich verfügbaren Produktunterlagen funktioniert**; und
2. **wie die lokale AGILE Modelling Engine diese Mechanik in Rechenregeln, Zustände und Cashflows übersetzt**.

Diese Trennung ist wichtig. Ein Produktmerkmal ist nicht schon deshalb vollständig modelliert, weil die Engine dafür ein gleichnamiges Feld besitzt. Umgekehrt sind Marktmodelle, Mortalitätsannahmen, Verhaltensfunktionen und Bewertungsmaße keine Vertragsbestandteile. Im Folgenden werden deshalb vier Kennzeichnungen verwendet:

| Kennzeichnung | Bedeutung |
|---|---|
| **Produktfakt** | durch PDS oder offizielles Rate Sheet belegt |
| **Modellabbildung** | konkrete Rechenregel der lokalen Engine |
| **Modellannahme** | für die Rechnung benötigte, aber nicht vertraglich vorgegebene Setzung |
| **Offen / Produktionslücke** | aus öffentlichen Quellen nicht eindeutig oder in der Engine nicht vollständig umgesetzt |

Der Produktstand ist das PDS vom 19. Januar 2026. Die konkret genannten Maximum Returns, Guaranteed Minimums und Lifetime Income Rates gehören zum Juli-2026-Vintage. Für eine bestehende Police sind stets Investor Certificate und der für Commencement beziehungsweise Anniversary geltende Rate-Sheet-Vintage maßgeblich [@allianz2026pds; @allianz2026maximums; @allianz2026minimums; @allianz2026rates]. Dieses Dokument ist eine fachliche Modellbeschreibung, keine individuelle Produkt-, Rechts-, Steuer- oder Sozialversicherungsberatung.

## 1. Das Produkt in einem Ablaufbild

AGILE kombiniert einen indexbezogenen Ansparwert mit einer später aktivierbaren lebenslangen Einkommenszusage:

```text
Einzahlung / Product Commencement
              |
              v
      Growth Phase
      - geschützte jährliche Indexgutschrift
      - Maximum Return wird jährlich neu gesetzt
      - Gebühren, DVA und gegebenenfalls MVA
              |
              | freiwilliger, unwiderruflicher Income Start
              | frühestens nach einem vollständigen Jahr
              v
      Lifetime Income Phase
      - Fixed oder Rising Income
      - monatliche Zahlung nachschüssig
      - Zahlungen zunächst aus dem Investment Value
      - nach dessen Erschöpfung aus der Garantie
              |
              v
      Tod / Full Withdrawal / Ende des gedeckten Lebens
```

Die ökonomische Kernaussage lautet: In der Growth Phase wird keine direkte Fondsbeteiligung gehalten, sondern eine vertragliche, nichtlineare Rendite gutgeschrieben. In der Income Phase wird ein jährlicher Zahlungsbetrag festgeschrieben. Solange Investment Value vorhanden ist, finanziert dieser die Auszahlung. Ist er auf null gefallen, läuft das geschützte Einkommen bei fortbestehendem Anspruch weiter; dieser Teil ist der eigentliche Versicherungsclaim.

Die in der Fachliteratur gebräuchlichen Begriffe *Fixed Indexed Annuity* und *Guaranteed Lifetime Withdrawal Benefit* sind dafür nützliche Funktionsanalogien. Sie sind jedoch weder die rechtliche Produktbezeichnung noch eine bestätigte APRA-Klassifikation [@bauer2008].

## 2. Beteiligte Rollen und rechtliche Zahlungsbeziehung

### 2.1 Issuer, Group Policy und Statutory Fund

**Produktfakt.** AGILE wird von Allianz Australia Life Insurance Limited ausgegeben. Die Group Policy ist an Allianz Australia Life Policy Services Pty Limited ausgegeben. Der einzelne Investor ist *specified beneficiary*, erwirbt ein Interesse unter der Group Policy und erhält ein Investor Certificate, in dem die individuellen Produktparameter dokumentiert werden. Die Leistungen werden von Allianz Australia Life direkt an den Investor gezahlt [@allianz2026pds, S. 2 und 83--84].

Die AGILE-Investments sind Statutory Fund No. 2 zugeordnet. Die Garantie ist eine Verpflichtung von Allianz Australia Life, die grundsätzlich aus den verfügbaren Vermögenswerten dieses Funds erfüllt wird. Zu beachten sind mögliche Top-up-Anforderungen und die im PDS beschriebenen begrenzten Cessation-Fälle. Es besteht keine Garantie durch Allianz SE oder ein anderes Konzernunternehmen [@allianz2026pds, S. 2 und 83--85].

### 2.2 Investor, Life Insured und Surviving Spouse

Die folgenden Rollen dürfen nicht gleichgesetzt werden:

| Rolle | Funktion |
|---|---|
| **Investor** | hält das Interesse unter der Group Policy, erteilt die vertraglich zulässigen Weisungen und erhält grundsätzlich Leistungen |
| **Life Insured** | Leben, dessen Alter, Gender, Überleben und Tod für Rate und Leistungsdauer relevant sind |
| **Spouse Insured** | zusätzlich gedecktes Leben, wenn diese Option wirksam gewählt wurde |
| **Surviving Spouse** | überlebender Ehepartner im Spouse-Pfad; nicht automatisch selbst Vertragsinhaber |

Ist beispielsweise ein Trustee, eine Plattform oder eine Company Investor, hat die nominierte natürliche Person als Life Insured grundsätzlich nicht allein deshalb ein eigenes Interesse unter der Group Policy. Das gilt entsprechend für einen Surviving Spouse, sofern diese Person nicht selbst Investor oder sonst anspruchsberechtigt ist. Deshalb hängt auch die Weisung nach dem Tod des primären Life Insured vom konkreten Ownership- und Beneficiary-Pfad ab [@allianz2026pds, S. 22, 38--40 und 83--84].

**Modellabbildung.** Die Engine verdichtet diese Rollen in einem `PolicySpec`. Sie speichert insbesondere Alter, Gender, Funding Source, Spouse-Status sowie eine vorab gesetzte `spouse_death_election`. Die vollständige Eigentümer-, Trustee-, Plattform-, Beneficiary- und Weisungslogik wird nicht als eigener Rechtszustand geführt.

## 3. Product Commencement und Model Point

Beim Product Commencement werden unter anderem folgende Größen festgelegt oder als Eingaben benötigt:

- Initial Investment und gegebenenfalls Adviser Fee beziehungsweise ein separat berechtigter Bonus;
- Funding Source: Superannuation oder Non-superannuation;
- Alter und produktspezifisches `Gender` des Life Insured;
- bei Spouse Insured zusätzlich Alter und Gender des Ehepartners;
- Growth-Allocation auf die Protected Investment Options;
- Guaranteed Minimum des künftigen Maximum Return;
- Lifetime-Income-Ratecard-Vintage;
- Wahlmöglichkeiten für Fixed/Rising, Spouse und Age Pension+;
- bei Age Pension+ die für die Capital Access Schedule relevante Lebenserwartung und der maßgebliche Commencement-/Release-Pfad.

**Modellabbildung.** Die Engine prüft als Produktgrenzen insbesondere ein Base Investment Amount zwischen AUD 20.000 und AUD 5 Mio., Eintrittsalter 50 bis 80 und einen Income Start frühestens nach einem Jahr. Die Growth-Allocation wird als nichtnegative Gewichtung der vier Optionen gespeichert und muss sich zu 100 % summieren. Ein Upfront Adviser Fee reduziert die Ausgangsbasis; ein explizit gesetzter Bonus erhöht anschließend das Investment Value. Der Bonus ist kein Default.

Der geprüfte Basismodellpunkt ist:

| Merkmal | Basislauf |
|---|---:|
| Commencement | Mitte 2026 |
| Life Insured | männlich, Alter 65 |
| Funding | Non-superannuation |
| Initial Investment | AUD 100.000 |
| Growth-Allocation | 100 % Australian Equity Total Protection |
| Income Start | nach fünf vollständigen Jahren |
| Income | Single, Fixed |
| Spouse / Age Pension+ | nein / nein |
| geplante Partial Withdrawals | keine |

Diese Kombination ist nur ein illustrativer Model Point. Sie beschreibt weder einen durchschnittlichen Kunden noch das tatsächliche AGILE-Portfolio.

## 4. Growth Phase: Protected Investment Options

### 4.1 Vier Optionen

**Produktfakt.** In der Growth Phase stehen vier Kombinationen aus Indexregion und Schutzart zur Verfügung [@allianz2026pds, S. 12--13 und 26--30]:

| Indexregion | Total Protection | Partial Protection: Initial 10 % |
|---|---|---|
| Australian Equity | jährlicher Floor von 0 % im marktgebundenen Zweig, niedrigerer Cap | erster 10-%-Verlustpuffer, dafür höherer Cap |
| Global Equity | jährlicher Floor von 0 % im marktgebundenen Zweig, niedrigerer Cap | erster 10-%-Verlustpuffer, dafür höherer Cap |

Das Produkt ist *indexed*, nicht *unit-linked*: Der Kunde hält nicht einfach Fondsanteile, deren Wert jederzeit proportional zum Index schwankt. Stattdessen wird für jedes Crediting-Jahr eine vertragliche Rendite aus der Point-to-Point-Indexbewegung abgeleitet.

### 4.2 Maximum Return und Guaranteed Minimum

Für Commencement- **oder Anniversary Dates** zwischen 1. und 31. Juli 2026 gelten folgende Maximum Returns [@allianz2026maximums]:

| Option | Maximum Return Juli 2026 |
|---|---:|
| Australian Equity Total Protection | 6,20 % |
| Australian Equity Partial Protection 10 | 13,00 % |
| Global Equity Total Protection | 6,00 % |
| Global Equity Partial Protection 10 | 12,80 % |

Der Maximum Return wird an jedem Anniversary für die folgende Zwölfmonatsperiode neu festgesetzt. Die Werte sind vor Product Fee, Lifetime Income Premium und Steuern angegeben.

Die im Investor Certificate festgehaltenen Guaranteed Minimums des Juli-2026-Vintage betragen 0,25 % für Total Protection und 0,50 % für Partial Protection [@allianz2026minimums]. Das bedeutet:

- Der künftig neu gesetzte **Maximum Return** darf den relevanten Guaranteed Minimum grundsätzlich nicht unterschreiten.
- Der Guaranteed Minimum ist **keine** garantierte Mindestjahresrendite.
- Er ist auch **nicht** der Schutz-Floor des Kundenpayoffs.

Diese drei Begriffe sind daher auseinanderzuhalten:

| Begriff | Was er begrenzt |
|---|---|
| Maximum Return / Cap | positive jährliche Kundengutschrift nach oben |
| Guaranteed Minimum | den in Zukunft gesetzten Maximum Return nach unten |
| Protection Level / Buffer | negative jährliche Kundengutschrift |

**Modellabbildung.** `CapSchedule` kann einen konstanten Cap, einen expliziten Jahresvektor und additive Cap-Stresses verarbeiten. Jede modellierte Jahresrate wird am hinterlegten Guaranteed Minimum gefloort. Im Basislauf fehlt eine künftige Schedule; deshalb wird der Juli-2026-Cap in allen Jahren wiederholt. Das ist eine Modellannahme, keine Prognose der künftigen Allianz-Raten.

### 4.3 Jährlicher marktgebundener Payoff

Seien

\[
R=\frac{S_T}{S_0}-1
\]

die Indexrendite vom Beginn bis zum Ende eines Crediting-Jahrs und \(C\) der Maximum Return dieses Jahres.

Für **Total Protection** bildet die Engine den marktgebundenen Zweig als

\[
c_{\mathrm{TP}}(R)=\min\{\max(R,0),C\}
\]

ab. Negative Indexrenditen führen in diesem Zweig zu 0 %; positive Renditen werden bis zum Cap gutgeschrieben.

Für **Partial Protection mit 10-%-Buffer** gilt

\[
c_{\mathrm{PP10}}(R)=
\begin{cases}
\min(R,C), & R\ge 0,\\
\min(0,R+0{,}10), & R<0.
\end{cases}
\]

Die ersten 10 Prozentpunkte eines Jahresverlustes werden somit absorbiert. Erst der darüber hinausgehende Verlust reduziert das Investment Value.

| Indexrendite | Total Protection bei 6,20 % | Partial Protection bei 13,00 % |
|---:|---:|---:|
| +15 % | +6,20 % | +13,00 % |
| +6 % | +6,00 % | +6,00 % |
| −5 % | 0,00 % | 0,00 % |
| −10 % | 0,00 % | 0,00 % |
| −18 % | 0,00 % | −8,00 % |

Bei mehreren Growth-Optionen berechnet die Engine den Credit jeder Option getrennt und bildet anschließend die gewichtete Summe gemäß der bei Commencement gespeicherten Allocation. Am Anniversary wird das Investment Value vor den anschließend an diesem Datum verarbeiteten Gebühren und Events auf die Jahresgutschrift gestellt.

### 4.4 Optionsökonomische Replikation

Für den marktgebundenen Zweig kann der Credit mit normiertem Index \(X=S_T/S_0\) als Optionspaket geschrieben werden:

\[
V_{\mathrm{TP}}=Call(1)-Call(1+C),
\]

\[
V_{\mathrm{PP10}}=Call(1)-Call(1+C)-Put(0{,}90).
\]

Total Protection entspricht einem Bull Call Spread. Partial Protection enthält zusätzlich einen verkauften Put unterhalb des 10-%-Buffers. Diese Zerlegung ist die Brücke zwischen Kundengutschrift, Hedgekosten, unterjährigem DVA und Crediting Margin [@blackscholes1973; @merton1973].

**Modellabbildung.** Die Engine kann dieses Paket mit Black--Scholes oder, in Modellvergleichszweigen, mit einem Heston-COS-Pricer bewerten. Der Optionswert ist kein zusätzlicher Kundenposten, sondern eine Modellzerlegung des vertraglichen Credits.

### 4.5 Nicht modellierter Fixed-Return-Zweig

**Produktfakt.** Für Total Protection darf Allianz alternativ für ein einzelnes Jahr einen garantierten Fixed Return festlegen, wenn dieser bei der Rate-Setting-Entscheidung einen mindestens gleich hohen Annual Return wie der einschlägige Maximum Return liefern kann. In einem solchen Jahr ist der Credit nicht indexabhängig; auch der unterjährige DVA-Mindestwert folgt dann dem zeitanteiligen Fixed Return [@allianz2026pds, S. 58, 60 und 62].

**Offen / Produktionslücke.** Dieser Fixed-Return-Zweig ist in der Engine nicht implementiert. Die obigen Payoff- und Replikationsgleichungen sind daher präzise für den modellierten marktgebundenen Zweig, aber keine universelle Formel für jeden vertraglich möglichen AGILE-Jahrespfad.

## 5. Wechsel in die Lifetime Income Phase

### 5.1 Wann der Wechsel erfolgen kann

**Produktfakt.** Der Investor kann Lifetime Income frühestens nach einem vollständigen Jahr beginnen. Der freiwillige Wechsel ist unwiderruflich [@allianz2026pds, S. 17--18]. Ein Start kann auf einem Anniversary oder unterjährig erfolgen; beim unterjährigen Start wird der dann relevante DVA berücksichtigt und ein neuer Crediting-Zyklus begonnen.

**Modellabbildung.** Der Basislauf setzt einen deterministischen Start nach fünf Jahren. Alternativ kann die Engine eine jährliche Take-up-Hazard verwenden. Ein auf Monatsbruchteile gesetzter Start wird auf dem Monatsraster als Off-anniversary-Election behandelt. Die Engine setzt dann das aktuelle DVA-konsistente Investment Value als neue Basis und startet eine neue jährliche Australian-Equity-Total-Protection-Periode.

### 5.2 Berechnung des ersten Einkommens

Beim Beginn der Income Phase wird das jährliche Locked Income als

\[
I_0=IV_{\tau}^{\mathrm{post\ fee}}\,g
\]

festgelegt. \(IV_{\tau}^{\mathrm{post\ fee}}\) ist das Investment Value am Startdatum nach den bis dahin verarbeiteten Gebühren; bei Off-anniversary-Start enthält es den an diesem Datum wirksamen DVA.

Die Lifetime Income Rate lautet

\[
g=g_{\mathrm{base}}(x_0,\text{Gender},\text{Income Type},\text{Spouse},
\text{Age Pension+})+n_{\mathrm{Growth}}e(x_0,\text{Fixed/Rising}).
\]

Entscheidend sind:

- Alter und produktspezifisches `Gender` am **Product Commencement Date**, nicht das spätere Alter beim Income Start;
- die gewählte Kombination aus Fixed/Rising, Single/Spouse und mit/ohne Age Pension+;
- nur die **vollständigen** Jahre in der Growth Phase;
- bei Spouse Income das eindeutig jüngere Leben einschließlich dessen Gender am Product Commencement.

Für den Basismodellpunkt bestätigt das Juli-2026-Rate-Sheet [@allianz2026rates, S. 1]:

\[
g=7{,}05\%+5\times0{,}35\%=8{,}80\%.
\]

Wenn das Post-Fee-Investment-Value am Start beispielsweise \(IV_{\tau}=100.000\) AUD beträgt, ist das anfängliche Jahreseinkommen 8.800 AUD beziehungsweise 733,33 AUD je nachschüssigem Monat. Dieses Beispiel dient nur der Mechanikerklärung; das tatsächliche \(IV_{\tau}\) ist pfadabhängig.

**Offen.** Die öffentliche Ratecard enthält ganzzahlige Alterszeilen. Sie legt weder die Regel für zwei gleich alte Personen unterschiedlichen Genders noch eine Interpolation für nichtganzzahlige Commencement-Alter offen. Die Engine priorisiert bei Gleichstand das primäre Life Insured und interpoliert Alterszeilen linear. Beides sind nicht öffentlich bestätigte Modellannahmen.

### 5.3 Fixed Income

**Produktfakt.** Bei Fixed Income bleibt das nominale Locked Income grundsätzlich konstant. Es sinkt nicht wegen negativer Indexperformance. Eine Excess Withdrawal kann es jedoch reduzieren [@allianz2026pds, S. 20--22 und 73--75].

**Modellabbildung.** Die Engine hält `income_annual` konstant und zahlt monatlich \(I/12\). Bei einer relevanten Excess Withdrawal multipliziert sie das künftige Einkommen mit dem vertraglich beziehungsweise modellseitig bestimmten verbleibenden Prozentsatz.

### 5.4 Rising Income

**Produktfakt.** Rising Income beginnt mit einer niedrigeren Rate. An einem Income Anniversary wird das Locked Income um den positiven Annual Credit der Australian Equity Total Protection Option erhöht:

\[
I_{a+1}=I_a\,[1+c_{\mathrm{AUS,TP},a}].
\]

Eine negative Indexentwicklung senkt das bereits erreichte Einkommen nicht. Rising Income ist aber keine CPI-Indexierung: Die Erhöhung hängt von Australian-Equity-Indexperformance und dem jeweiligen Cap ab [@allianz2026pds, S. 21 und 73].

**Modellabbildung.** In der Income Phase verwendet die Engine für Investment Value und Ratchet Australian Equity Total Protection, unabhängig von der früheren Growth-Allocation. Die am Anniversary fällige nachschüssige Monatszahlung gehört noch zum abgelaufenen Einkommensjahr; der neue Ratchet wirkt daher erstmals auf die folgende Monatszahlung.

### 5.5 Was passiert, wenn das Investment Value auf null fällt?

Für jede fällige Monatszahlung \(I_m=I/12\) zerlegt die Engine:

\[
\text{aus IV}=\min(I_m,IV),
\qquad
\text{Garantieclaim}=\max(I_m-IV,0).
\]

Das Investment Value wird nur um den aus ihm finanzierten Teil reduziert. Der Garantieclaim ist der vom Versicherer zusätzlich zu finanzierende Betrag. Ein Investment Value von null beendet daher die Income Phase nicht. Bei fortbestehendem Lebens- und Vertragsanspruch wird das Locked Income weitergezahlt.

## 6. Gebühren

### 6.1 Vertragliche Sätze und Basis

**Produktfakt.** Nach dem PDS vom 19. Januar 2026 betragen die laufenden Sätze [@allianz2026pds, S. 41--42]:

- Product Fee: 0,30 % p. a.;
- Lifetime Income Premium (LIP): 1,15 % p. a.

Beide werden vertraglich täglich auf das Investment Value ohne DVA Amount und ohne bereits aufgelaufene Gebühren berechnet. Der tatsächliche Abzug erfolgt zu den im PDS definierten Events.

Die Sätze sind aktuelle Sätze, keine unabänderlichen Vertragskonstanten. Das PDS enthält ein rechtlich begrenztes Änderungsrecht für Satz oder Belastungsfrequenz mit vorheriger Notice.

### 6.2 Monatliche Engine-Näherung

Die Engine approximiert den täglichen Accrual monatlich:

\[
Fee_m\approx IV_{\mathrm{frame},m}\frac{f}{12}.
\]

`iv_frame` ist die DVA-bereinigte vertragliche Basis, also das Investment Value ohne den aktuellen DVA-Anteil. Product Fee und LIP werden separat als Cashflows gespeichert, gemeinsam aber höchstens bis zum vorhandenen aktuellen Investment Value abgezogen. Die Gebührenreduktion wird proportional auch auf den DVA-Frame übertragen.

**Modellannahme.** Im Basislauf bleiben 0,30 % und 1,15 % über die gesamte Projektion konstant. Eine Änderung nach Notice wird nicht simuliert. Die Monatsnäherung ist für Research-Zwecke nachvollziehbar, ersetzt aber keine taggenaue Admin-Reconciliation.

### 6.3 Besonderheit bei Age Pension+

Bei Age Pension+ entfällt die LIP nicht automatisch schon bei Wahl der Option. Sie wird erst ab dem späteren Zeitpunkt aus Income Commencement und Pension Age beziehungsweise relevanter Condition of Release erlassen [@allianz2026pds, S. 41]. Die Engine bildet dies funding-spezifisch ab: für Non-superannuation über das modellierte Pension Age, für Superannuation über das eingegebene Release-Datum.

## 7. Partial und Full Withdrawals ohne Age Pension+

### 7.1 Free Withdrawal Amount in der Growth Phase

**Produktfakt.** Ohne Age Pension+ steht in jedem Anniversary Year der Growth Phase ein Free Withdrawal Amount von 5 % des anfänglichen Investment Amount zur Verfügung. Ungenutzte Beträge werden nicht in das nächste Jahr übertragen [@allianz2026pds, S. 31--33].

Die Engine führt deshalb zwei Zustände:

- den im laufenden Anniversary Year bereits verbrauchten Free Withdrawal Amount; und
- den kumulierten Partial-Withdrawal-Verbrauch relativ zur Jahresanfangsbasis.

Am Anniversary werden diese Jahreszähler zurückgesetzt. Bei einer angeforderten Excess Withdrawal in der Growth Phase verbraucht die Engine zunächst einen noch verfügbaren freien Anteil; nur der darüber hinausgehende Teil ist MVA-pflichtiger Excess.

### 7.2 Mindest- und Höchstgrenzen

Das PDS enthält unter anderem folgende Grenzen [@allianz2026pds, S. 31--35]:

- eine Partial Withdrawal muss einschließlich MVA mindestens AUD 100 betragen;
- in der Growth Phase gilt eine 95-%-Grenze je einzelner Entnahme;
- zusätzlich gilt eine kumulierte 95-%-Grenze je Anniversary Year;
- nach einer Partial Withdrawal muss der relevante Withdrawal-/Investment Value mindestens AUD 2.000 betragen.

**Modellabbildung.** Die Engine begrenzt eine angeforderte Entnahme nacheinander durch Ereignislimit, verbleibendes Jahreslimit und Mindestrestwert. Unterschreitet der resultierende Betrag AUD 100, wird die Entnahme in diesem Rechenschritt auf null gesetzt.

### 7.3 Excess Withdrawal in der Income Phase

Ohne Age Pension+ reduziert eine Excess Withdrawal in der Income Phase nicht nur das Investment Value, sondern auch das künftige Locked Income. Im Modell ist bei Investment Value \(IV^-\) vor Entnahme und Bruttoabzug \(G=\text{Cash} + \text{MVA}\):

\[
IV^+=IV^- - G,
\qquad
I^+=I^-\left(1-\frac{G}{IV^-}\right).
\]

Der Abzug einschließlich MVA bestimmt also die prozentuale Garantieminderung. Ein Full Withdrawal beendet den Vertrag und damit die künftige Einkommensgarantie.

### 7.4 Basislauf versus Verhaltensszenarien

Im Basismodellpunkt sind geplante Free und Excess Withdrawals null. Die Engine kann jedoch jährliche oder monatliche Utilisation vorgeben. Im dynamischen Regime wird die Utilisation bei höherer Garantie-Moneyness und stärkerer MVA gedämpft. Diese Verhaltensfunktion ist eine Modellannahme, kein PDS-Mechanismus.

## 8. Market Value Adjustment (MVA)

### 8.1 Vertragliche Funktion

**Produktfakt.** Excess Withdrawals und Full Withdrawals können in den ersten zehn Jahren einer MVA unterliegen. Die MVA kann den Auszahlungswert reduzieren. Auf die Todesfallleistung fällt keine MVA an [@allianz2026pds, S. 31--33, 38--40 und 60--61].

Bei einem Full Withdrawal ohne Age Pension+ ermittelt die Engine zuerst den noch freien Betrag. Die MVA wirkt nur auf das darüber hinausgehende Investment Value. Der modellierte Surrender Value ist

\[
SV=IV-\text{MVA Amount}.
\]

### 8.2 Engine-Proxy

Da Allianz keine vollständige Produktionsformel veröffentlicht, verwendet die Engine einen Zinsproxy:

\[
f_{\mathrm{MVA}}(t)=
1-\left(\frac{1+z_{\mathrm{issue}}+s}{1+z_t+s}\right)^{\tau}
+\lambda_0+\lambda_1\tau,
\]

wobei \(\tau\) die verbleibende Zeit des Zehnjahresfensters, \(z_{\mathrm{issue}}\) der Issue-Zero-Rate für diese Restlaufzeit, \(z_t\) der aktuelle pfadweise Zero Rate, \(s\) ein Spread und \(\lambda_0,\lambda_1\) Termination-Loadings sind.

In der Default-Konfiguration gilt `only_reduces=True`; negative Faktoren werden auf null begrenzt. Die MVA darf dann keinen Auszahlungsgewinn erzeugen. Der Amount wird zusätzlich auf den betroffenen Excess-Betrag begrenzt.

**Modellannahme / Produktionslücke.** Die Default-Loadings sind null. Der Proxy reproduziert deshalb nicht automatisch den No-rate-move-Haircut der illustrativen PDS-Tabelle. Die Hilfsparametrisierung aus dieser Tabelle ist nur eine Illustration und keine bestätigte Allianz-Produktionskalibrierung. Für eine produktive Bewertung wären reale Transaktionsquotes, die Adminformel oder eine abgestimmte Kalibrierung erforderlich.

## 9. Daily Value Adjustment (DVA)

### 9.1 Was der DVA vertraglich bedeutet

**Produktfakt.** Der DVA ist der unterjährige Wert der für das Investment relevanten Derivatekontrakte. Er ist nicht einfach die bis heute realisierte Indexrendite. Der DVA Amount ist im Investment Value enthalten und wird bei unterjährigen Transaktionen beziehungsweise einem Off-anniversary-Income-Start gutgeschrieben oder belastet [@allianz2026pds, S. 62--63].

Das PDS beschreibt vertragliche Mindestwerte:

- bei gestiegenem Index mindestens die Year-to-date-Rendite bis zum zeitanteiligen Maximum Return;
- bei gefallenem Index mindestens das zeitanteilige Protection Level;
- bei einem angewandten Fixed Return dessen zeitanteiligen Anteil.

Der DVA sorgt damit dafür, dass eine unterjährige Transaktion nicht so behandelt wird, als sei das Crediting-Jahr entweder nie begonnen oder bereits regulär beendet worden.

### 9.2 Optionswertproxy der Engine

Die Engine hält neben dem aktuellen Investment Value einen `iv_frame`. Unterjährig wird der DVA-konsistente Faktor als

\[
p_z(t)=P(t,T_{\mathrm{anniv}})+V_{\mathrm{package}}(t)
\]

berechnet. \(P(t,T_{\mathrm{anniv}})\) ist der Zero-Bond-Wert bis zum nächsten Anniversary und \(V_{\mathrm{package}}\) der aktuelle Wert des für Total beziehungsweise Partial Protection erforderlichen Optionspakets. Dann gilt modellseitig

\[
IV_t=IV_{\mathrm{frame},t}\,p_z(t).
\]

Am Anniversary konvergiert der Faktor zu \(1+c(R)\); der unterjährige Optionswert wird damit zum finalen Annual Credit. Gebühren, Zahlungen und Entnahmen skalieren anschließend `iv_frame` proportional, damit keine fiktiven Optionsanteile im Vertrag verbleiben.

**Offen / Produktionslücke.** Der Proxy bildet weder die vertraglichen zeitanteiligen Protection-Floors noch den möglichen Fixed-Return-Zweig vollständig ab. Er ist eine marktkonsistente Hedgewertannahme, nicht die bestätigte Allianz-Adminformel. Außerdem ist \(p_z\le 1\) keine allgemeine mathematische Eigenschaft; bei einem sehr hohen oder nicht finanzierbaren Cap kann das Optionspaket den Bondabschlag übersteigen.

## 10. Tod und Spouse Insured

### 10.1 Standard-Death-Benefit

**Produktfakt.** Ohne die besonderen Age-Pension+-Grenzen entspricht der Death Benefit grundsätzlich dem positiven Investment Value zum Zahlungszeitpunkt. Eine MVA wird auf die Todesfallleistung nicht erhoben [@allianz2026pds, S. 24--25 und 38--40].

**Modellabbildung.** Im Monatsmotor wird Tod vor der an diesem Monatsende nachschüssig fälligen Income-Zahlung verarbeitet. Der Death Benefit basiert deshalb auf dem Pre-payment-Investment-Value. Nur bis zum Zahlungstermin Überlebende erhalten die Monatsrate. Die Engine simuliert nicht für jede Police einen binären Todeszeitpunkt; sie multipliziert Death Benefit und Folgecashflows mit monatlichen Todes- und In-force-Wahrscheinlichkeitsgewichten.

### 10.2 Spouse-Income-Pfad

**Produktfakt.** Ist die Spouse Insured Option wirksam gewählt und sind die Eligibility-/Beneficiary-Bedingungen erfüllt, kann das Lifetime Income nach dem Tod des primären Life Insured für das Leben des Surviving Spouse fortgesetzt werden. Die nach der Investorstruktur berechtigte Partei kann stattdessen den zulässigen Lump Sum wählen. Fehlt eine Instruktion, ist die Fortsetzung des Einkommens der PDS-Default [@allianz2026pds, S. 22 und 38--40].

Die Lifetime Income Rate basiert im Spouse-Fall auf dem eindeutig jüngeren Leben einschließlich dessen Gender am Product Commencement. Das ist von der späteren Frage zu trennen, wer nach einem Todesfall eine Weisung erteilen darf.

**Modellabbildung.** `spouse_death_election` wird bereits vor der Projektion als `continue_income` oder `lump_sum` gesetzt:

- Bei `continue_income` verwendet der Monatsmotor ab der tatsächlichen Income Election eine Last-Survivor-Wahrscheinlichkeit. Unter angenommener Mortalitätsunabhängigkeit gilt

  \[
  {}_tp_{LS}={}_tp_1+{}_tp_2-{}_tp_1{}_tp_2.
  \]

  Das Einkommen läuft im Erwartungswert bis zum Tod des letzten gedeckten Lebens.
- Bei `lump_sum` bleibt die primäre Todesfalllogik maßgeblich; der modellierte Death Benefit wird bei Tod ausgezahlt und der Income-Pfad endet.

Die Engine bildet damit zwei ökonomische Cashflowpfade ab, nicht jedoch die vollständige erst im Todesfall entstehende Wahl-, Informations- und Beneficiary-Logik. Das Vorziehen dieser Wahl in den Model Point ist eine Szenarioannahme.

## 11. Age Pension+

Age Pension+ ist keine kostenlose zusätzliche Garantie. Die Option tauscht Kapitalzugriff und gegebenenfalls Todesfallkapital gegen eine besondere Einkommens- und Social-Security-Struktur. Deshalb sind Election, Commencement, CAS und Withdrawal-Reduktion gemeinsam zu modellieren.

### 11.1 Election, Eligibility und Commencement

**Produktfakt.** Die Entscheidung muss beim frühesten für den Investor einschlägigen Ereignis getroffen werden: Income Commencement, bei Superannuation eine Relevant Condition of Release einschließlich Alter 65, bei Non-superannuation Pension Age. Die Entscheidung ist dann unwiderruflich [@allianz2026pds, S. 15--17].

Der tatsächliche Beginn ist funding-spezifisch:

- bei Superannuation bei Erfüllung der relevanten Condition of Release;
- bei Non-superannuation am früheren von Income Start und Pension Age.

Non-superannuation-Trustee- und Company-Investors sind grundsätzlich nicht berechtigt; eine Ausnahme besteht für Non-super-Platform-Trustees.

**Modellabbildung.** Ein boolesches Feld `age_pension_plus` legt den Pfad bereits im Model Point fest. Für Non-superannuation setzt die Engine den Beginn auf das frühere Monatsrasterdatum aus geplantem Income Start und modelliertem Pension Age 67. Für Superannuation muss ein `condition_of_release_year` vorgegeben werden. Die differenzierte Investor-/Trustee-/Company-Eligibility und der eigentliche Entscheidungsprozess werden nicht als Zustände modelliert.

### 11.2 Ratecard- und CAS-Vintage

Die beim Product Commencement gezeigten Age-Pension+-Rates und Escalators stehen unter dem Vorbehalt, dass sich die Capital Access Schedule bis zum tatsächlichen Beginn nicht ändert. Ändert sich die CAS, behält sich Allianz eine Änderung der Age-Based Rate und Escalator Rate vor [@allianz2026pds, S. 15; @allianz2026rates].

Ein Produktionsmodelpoint muss deshalb gemeinsam speichern:

- Ratecard-Vintage;
- CAS-Vintage;
- Election Date und tatsächliches Commencement Date;
- die im Investor Certificate bestätigten Parameter;
- die vertragliche CAS-Lebenserwartung.

Die Engine hat ein Ratecard-Vintage-Feld, modelliert aber keine spätere administrativ ausgelöste CAS-/Ratecard-Neufestsetzung.

### 11.3 Maximum Withdrawal Value

Bei Beginn der CAS wird eine Basis \(B\) aus dem relevanten Post-Fee-Investment-Value festgeschrieben. Mit verstrichener Zeit \(e_t\), CAS-Lebenserwartung \(LE\) und seit Beginn vorgenommenen Withdrawals \(W_t\) modelliert die Engine:

\[
MWV_t=\max\left\{B\left(1-\frac{e_t}{LE}\right)-W_t,0\right\}.
\]

Der Maximum Withdrawal Value läuft somit linear bis null bei Life Expectancy ab; Entnahmen reduzieren ihn zusätzlich Dollar für Dollar.

**Modellannahme.** Für Production muss \(LE\) aus dem Vertrag beziehungsweise Model Point kommen. Fehlt sie, leitet die Engine eine Lebenserwartung aus ihrer illustrativen Mortalitätsbasis ab. Dieser Fallback ist nicht als Vertragswert belastbar.

### 11.4 Maximum Benefit on Death

Der Todesfall-Cap folgt nicht derselben glatten Linie wie der MWV. Mit dem im Standardmodell verwendeten Half-Life-Expectation-Punkt gilt:

\[
MDB_t=
\begin{cases}
\max(B-W_t,0), & e_t<\tfrac12 LE,\\
\max\left(B\left(1-\frac{e_t}{LE}\right)-W_t,0\right),
& e_t\ge\tfrac12 LE.
\end{cases}
\]

Bis zur Hälfte der Life Expectancy bleibt die Ausgangsbasis vor Withdrawals als Obergrenze erhalten. Am Half-Life-Expectation-Punkt fällt der Cap unmittelbar auf den dann geltenden MWV und läuft danach linear aus [@allianz2026pds, S. 65--68]. Die Engine zahlt im Todesfall den niedrigeren Wert aus Investment Value und diesem Cap; die Differenz wird als `aps_retained` ausgewiesen.

### 11.5 Withdrawals mit Age Pension+

Nach Beginn von Age Pension+ gibt es keinen Free Withdrawal Amount. Jede Entnahme ist Excess. Der verfügbare Full-Withdrawal-Wert ist der niedrigere Wert aus

\[
IV-\text{anwendbare MVA}
\quad\text{und}\quad
MWV.
\]

Zwei Fälle sind zu unterscheiden [@allianz2026pds, S. 33--35 und 68--70]:

1. **Der IV-minus-MVA-Zweig bindet.** Die MVA wird belastet. Die prozentuale Reduktion von Investment Value und Locked Income ist

   \[
   q=\frac{\text{Cash}+\text{MVA}}{IV}.
   \]

2. **Der MWV-Zweig bindet.** Es wird keine MVA separat belastet. Die Reduktionsquote ist

   \[
   q=\frac{\text{Cash}}{MWV}.
   \]

   Investment Value und Locked Income werden um diesen Prozentsatz reduziert. Weil \(MWV<IV\) sein kann, kann die Reduktion des Investment Value in Dollar deutlich größer als die tatsächlich ausgezahlte Cash-Entnahme sein. Diese Differenz wird im Modell als Age-Pension+-Retained Amount erfasst.

Diese Lower-of-Logik ist der Grund, warum die gewöhnliche Proportionalität `Cash / IV` für Age Pension+ falsch wäre.

### 11.6 Automatischer Income Start mit Age Pension+

Ist Age Pension+ bereits aktiv und wurde Income noch nicht freiwillig begonnen, startet Lifetime Income spätestens am ersten ursprünglichen Policy Anniversary nach Erreichen der bei Age-Pension+-Beginn bestimmten Life Expectancy [@allianz2026pds, S. 17 und 75]. Die Engine berechnet bei Aktivierung einen entsprechenden `aps_auto_income_step` und nimmt das frühere Datum aus geplantem und erzwungenem Start.

## 12. Automatische und administrative Events

Neben einer freiwilligen Election enthält das Produkt späteste Start- und Default-Regeln:

| Event | Produktregel | Engineabbildung |
|---|---|---|
| freiwilliger Income Start | frühestens nach einem Jahr, unwiderruflich | deterministisches Jahr oder Hazard, auf Monatsraster |
| kein Age Pension+ und noch kein Income | nächster Anniversary nach Vollendung des 100. Lebensjahrs | Income-Step wird auf diesen Anniversary begrenzt |
| Age Pension+ aktiv und noch kein Income | nächster Anniversary nach CAS-Life-Expectancy | eigener Auto-Income-Step |
| keine Optionsinstruktion beim automatischen Start | Default Fixed Income ohne Spouse Insured | nicht als vollständiger administrativer Defaultpfad modelliert |
| fehlende Kontaktinformation oder Bankverbindung | Allianz behält sich Full Withdrawal statt Income Commencement vor | nicht als deterministischer Enginepfad modelliert |

Die Engine bildet somit die beiden zeitlichen Forced-Commencement-Grenzen ab, aber nicht den vollständigen Kommunikations-, Instruktions-, Bankdaten- und Ownership-Workflow.

## 13. Monatliche Zustandsmaschine der Engine

### 13.1 Zustände

Der Monatsmotor kennt drei Hauptzustände:

\[
\text{Growth}\longrightarrow\text{Income}\longrightarrow\text{Out}.
\]

`Out` ist absorbierend. Full Withdrawal oder der maßgebliche Tod führen aus Growth beziehungsweise Income in diesen Zustand. Ein auf null gefallenes Investment Value führt nur in Growth automatisch zu `Out`; in Income bleibt der Vertrag wegen des möglichen Garantieclaims aktiv.

Mortalität und Lapse werden im Standardprojektionsmotor nicht als binäre Einzelereignisse simuliert. Stattdessen wird ein In-force-Gewicht \(w_t\) fortgeschrieben. Dadurch sind Cashflows Erwartungswerte bedingt auf Marktpfade, und die Monte-Carlo-Varianz wird reduziert.

### 13.2 Ereignisreihenfolge je Monat

Die ausgeführte Reihenfolge ist materiell:

1. **Marktbewegung und DVA:** Index- und gegebenenfalls Zins-/Volatilitätszustände werden auf den neuen Monatszeitpunkt gebracht; unterjährig wird das DVA-konsistente Investment Value berechnet.
2. **Anniversary Credit:** Am Crediting Anniversary wird der Annual Credit je Growth-Option berechnet. In der Income Phase wird Australian Equity Total Protection verwendet.
3. **Rising Ratchet:** Am Income Anniversary wird das künftige Locked Income um den positiven Australian-TP-Credit erhöht.
4. **Gebühren:** Product Fee und LIP werden in monatlicher Näherung auf der DVA-freien Basis abgezogen.
5. **Age-Pension+-Aktivierung:** Der Post-Fee-Wert wird gegebenenfalls als CAS-Basis festgeschrieben.
6. **Income Election:** Das Post-Fee-Investment-Value wird mit der Rate \(g\) multipliziert. Bei Off-anniversary-Start wird der laufende DVA-Zyklus geschlossen und neu begonnen.
7. **Tod:** Death Benefit wird auf dem Wert vor der nachschüssigen Monatszahlung bestimmt; bei Age Pension+ greift der Death Cap.
8. **Income Payment:** Nur bis zum Zahlungstermin Überlebende erhalten die Rate. Im Election-Monat wird noch nichts gezahlt; die erste Rate fällt einen Monat später an.
9. **geplante Partial Withdrawals:** Free/Excess, MVA, Limits, CAS und Locked-Income-Reduktion werden angewandt.
10. **laufende Versichererkosten:** nur in der Profitabilitätssicht, nicht als Kundenabzug.
11. **Lapse / Full Withdrawal:** Surrender Value, MVA und gegebenenfalls Age-Pension+-Lower-of werden berechnet; anschließend sinkt das In-force-Gewicht.

Würde beispielsweise die Election vor den Gebühren verarbeitet, wäre die Income Base zu hoch. Würde die Monatszahlung vor dem Tod verarbeitet, erhielte auch der Todesfallpfad eine nicht mehr geschuldete nachschüssige Rate. Das Event Ordering ist deshalb Teil der Produktmodellierung und nicht nur eine Programmierkonvention [@agileaudit2026].

### 13.3 Wichtige Zustandsvariablen

Die Engine führt unter anderem:

- aktuelles Investment Value und DVA-Frame;
- jährliches Locked Income;
- Phase und In-force-Gewicht;
- Startindexstände des laufenden Crediting-Jahrs;
- Cap-Schedule beziehungsweise Policy-Year-Vintage;
- vollständige Growth-Jahre;
- verbrauchten Free Withdrawal Amount und kumuliertes 95-%-Jahreslimit;
- Age-Pension+-Aktivstatus, CAS-Basis, Startzeit, Life Expectancy, bisherige Withdrawals und MWV;
- Primary- und Spouse-Survival-Zustände; sowie
- Marktvariablen wie Index, gegebenenfalls stochastische Varianz und Zins.

Die Zustände können ab Issue aufgebaut werden. Eine beliebige bestehende Police kann aber noch nicht vollständig aus einem Admin-Snapshot mit bereits laufendem DVA-Jahr, historischem Cap-Vintage, Gebührenaccruals, Withdrawal-Zählern und CAS-Zustand initialisiert werden. Das ist eine Produktionslücke.

## 14. Welche Unsicherheiten zusätzlich modelliert werden

Die Vertragslogik allein liefert noch keinen heutigen Wert. Die Engine ergänzt sie daher um nichtvertragliche Annahmen:

### 14.1 Marktpfade

- Unter dem risikoneutralen Maß \(Q\) werden Cashflows für BEL, Garantie- und Hedgewert diskontiert.
- Unter dem Real-World-Maß \(P\) werden Profitabilitäts- und Kundenoutcomes projiziert.
- Der Basiszweig verwendet Black--Scholes-artige Equity-Pfade; Modellvergleiche verwenden Heston und Hull--White beziehungsweise hybride Kombinationen.
- Die zugrunde liegenden Return Indices erhalten im Default keinen zusätzlichen Dividend Carry, damit bereits im Index enthaltene Erträge nicht doppelt gezählt werden.

Diese Modelle bestimmen die Verteilung von Credits, DVA, MVA, Account Exhaustion und Garantieclaims. Sie ändern aber nicht die vertragliche Payoffformel.

### 14.2 Mortalität

Die Defaultbasis ist eine synthetische Gompertz--Makeham-Mortalität mit generational Improvement. Sie ist weder eine offizielle australische Pricing-Tafel noch eine Allianz-Erfahrungstafel. Monatswahrscheinlichkeiten werden aus jährlichen Sterbewahrscheinlichkeiten abgeleitet. Im Spouse-Continue-Pfad wird Mortalitätsunabhängigkeit angenommen.

### 14.3 Kundenverhalten

Der Basislauf verwendet vorgegebene Lapse-Raten, einen deterministischen Income Start und keine Partial Withdrawals. Optional kann die Engine Lapse und Withdrawal Utilisation mit Garantie-Moneyness und MVA skalieren. Diese Funktionen sind heuristisch und nicht auf AGILE-Kundendaten kalibriert.

Die Moneyness in der Income Phase wird näherungsweise als

\[
M_t=\frac{PV_t(\text{garantiertes Einkommen})}{SV_t}
\]

gebildet. Eine höhere Moneyness reduziert im dynamischen Modell Lapse und Entnahme. Der Zähler verwendet jedoch einen vereinfachten Annuitätenfaktor, keinen vollständigen marktkonsistenten Tail-PV. Bei einer Off-anniversary-Income-Election verwendet ein Helper bis zum nächsten Anniversary zudem Investment Value statt vollständig MVA-bereinigtem Surrender Value.

### 14.4 Optimales Verhalten

Ein separates jährliches LSMC-Modul kann Start-, Entnahme- und Surrender-Aktionen als stochastische Kontrolle bewerten. Dieses Modul ist keine identische Wiederholung des Monatsmotors: Horizon, Joint-Life-Konditionierung, Tailwert und Static-Policy-Vergleich sind vereinfacht. Es darf daher nicht als exakte Vertrags- oder Kundenverhaltensprognose gelesen werden.

## 15. Produktregel und Modellabbildung im direkten Vergleich

| Thema | Vertragliche Regel | Engineabbildung | Status |
|---|---|---|---|
| Rollen | Investor, Life Insured, Spouse und Beneficiary getrennt | verdichteter Model Point | Ownership-/Weisungsworkflow fehlt |
| Growth Allocation | vier Protected Investment Options | Gewichte über vier Optionen, Summe 100 % | umgesetzt |
| Maximum Return | jährlich neu, Vintage-spezifisch | konstante oder explizite Schedule | Basis wiederholt Juli-2026-Wert |
| Guaranteed Minimum | Floor des künftigen Maximum Return | Untergrenze jeder modellierten Cap-Rate | umgesetzt |
| Total Protection | 0-%-Floor bis Cap, sofern marktgebunden | `min(max(R,0),C)` | umgesetzt für Market-linked Branch |
| Partial Protection 10 | erster 10-%-Verlustpuffer, positiver Cap | stückweise Formel | umgesetzt |
| Fixed Return | möglicher alternativer TP-Jahreszweig | nicht vorhanden | Produktionslücke |
| DVA | Derivatewert mit pro-rata Mindestwerten | Bond plus Optionspaket | Floors/Fixed Branch fehlen |
| Income Rate | Commencement-Alter/Gender, Optionen, volle Growth-Jahre | versionierte Tabelle plus Escalator | Tie/Interpolation offen |
| Fixed Income | nominal konstant, außer Excess Withdrawal | konstantes `income_annual` | umgesetzt |
| Rising Income | AUS-TP-Ratchet, kein negativer Step-down | jährlicher Ratchet | umgesetzt im Market-linked Branch |
| Zahlung | monatlich nachschüssig | erste Rate einen Monat nach Election | umgesetzt |
| Garantieclaim | Income läuft nach IV-Erschöpfung weiter | `max(payment-IV,0)` | umgesetzt |
| Product Fee / LIP | täglich accrued, eventbezogen deducted | monatliche Näherung | Admin-Reconciliation fehlt |
| Fee-Änderung | begrenztes Änderungsrecht mit Notice | konstante Sätze | Modellannahme |
| Free Withdrawal | 5 % initial, Growth, kein Carry-forward | Jahreszähler | umgesetzt |
| Withdrawal Limits | AUD 100, 95 %, AUD 2.000 Restwert | sequenzielle Caps | umgesetzt auf Monatsraster |
| MVA | erste zehn Jahre, Excess/Full, nicht Death | unkalibrierter Zinsproxy | Produktionsformel unbekannt |
| Standard Death | positives IV, keine MVA | Death vor Monatszahlung | umgesetzt |
| Spouse Death | Continue oder Lump Sum, Default Continue | Pfad vorab gewählt | Wahl-/Beneficiary-Workflow fehlt |
| Age Pension+ Election | funding-/release-/age-spezifisch | boolescher Pfad plus Startregel | Eligibility nur teilweise |
| CAS-MWV | linearer Runoff minus Withdrawals | explizite Zustandsformel | umgesetzt |
| Age-Pension+-Death-Cap | volle Basis bis Half LE, dann Sprung auf MWV | stückweise Formel | umgesetzt |
| Age-Pension+-Withdrawal | Lower-of IV−MVA und MWV | beide Bindungsfälle | umgesetzt |
| automatischer Income Start | Alter 100 oder APS-Life-Expectancy | zeitliche Force Steps | Admin-Defaults fehlen |
| In-force-Police | historischer Vertragszustand maßgeblich | Aufbau nur ab Issue | Snapshot-Initialisierung fehlt |

## 16. Die wichtigsten offenen Punkte vor einer Produktionsverwendung

1. **Fixed-Return-Zweig:** Annual Credit und pro-rata DVA sind nicht implementiert.
2. **DVA-Adminformel:** Hedgewertproxy ohne alle vertraglichen Mindestwerte; keine bestätigte Allianz-Reconciliation.
3. **MVA-Kalibrierung:** Produktionsformel beziehungsweise reale Quotes fehlen; Default-Loadings sind null.
4. **Cap- und Rate-Vintages:** Der Basislauf wiederholt Juli-2026-Caps; echte zukünftige oder historische Schedules müssen pro Police geliefert werden.
5. **Equal-age-Spouse-Regel:** Die öffentliche Dokumentation entscheidet nicht, welches Gender bei exakt gleichem Alter ratebestimmend ist.
6. **Fractional-age-Rating:** Lineare Interpolation der Engine ist öffentlich nicht bestätigt.
7. **Age-Pension+-Daten:** CAS-Life-Expectancy, Election-/Commencement-Datum, Investor-Eligibility, Ratecard- und CAS-Vintage müssen administrativ verfügbar sein.
8. **Spouse-/Death-Workflow:** Wahlrechtsinhaber, Eligibility und PDS-Default sind nicht als vollständige Zustandsmaschine implementiert.
9. **Automatische Administration:** fehlende Instruktion, Kontakt- oder Bankdaten und der mögliche Full-Withdrawal-Pfad fehlen.
10. **Gebührenadministration:** täglicher Accrual, Event-Deduction und mögliche spätere Satzänderungen sind nur näherungsweise beziehungsweise gar nicht modelliert.
11. **In-force-Initialisierung:** DVA-Frame, Anniversary-Startindex, Cap-Vintage, Withdrawal-Zähler, Locked Income und CAS können nicht aus einem beliebigen Admin-Snapshot geladen werden.
12. **Erfahrungsbasen:** Mortalität, Lapse, Take-up, Partial Withdrawals und Kosten sind illustrativ, nicht auf AGILE-Bestandsdaten kalibriert.
13. **APRA-Klassifikation:** Aus öffentlichen Quellen ist nicht entscheidbar, ob AGILE als *variable annuity business* im Sinn von LPS 110 Attachment A behandelt wird.

## 17. Quellen- und Citekey-Übersicht

| Citekey | Verwendung in diesem Dokument |
|---|---|
| `allianz2026pds` | Rollen, Phasen, Payoffs, Income, Fees, Withdrawals, MVA, DVA, Death, Spouse, Age Pension+ und automatische Events |
| `allianz2026maximums` | Maximum Returns für Commencement/Anniversary im Juli 2026 |
| `allianz2026minimums` | Guaranteed Minimums des Juli-2026-Vintage |
| `allianz2026rates` | Lifetime Income Rates und Annual Income Escalators des Juli-2026-Vintage |
| `bauer2008` | GMxB-/GLWB-Modellanalogie, nicht rechtliche Klassifikation |
| `blackscholes1973`, `merton1973` | arbitragefreie Optionszerlegung des marktgebundenen Credits |
| `agileengine2026` | lokale Engine 1.3.0 und Modulabbildung |
| `agilemethodology2026` | lokale Methodenbeschreibung |
| `agileaudit2026` | auditierte Timing- und Implementierungsbefunde |

Die vier offiziellen Produktquellen sind für Produktfakten vorrangig. Lokaler Code und lokale Methodendokumente belegen ausschließlich, **was die Engine rechnet**; sie dürfen nicht als unabhängiger Nachweis dafür verwendet werden, dass die reale Allianz-Administration identisch arbeitet [@agileengine2026; @agilemethodology2026].
