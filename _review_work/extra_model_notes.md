# AGILE Engine 1.3.0 – genaue Modellabbildung

## 1. Zweck und Einordnung

Die Engine bildet AGILE als Kombination aus zwei ökonomischen Schichten ab:

1. einer **indexgebundenen Ansparphase** mit jährlicher Point-to-Point-
   Gutschrift und begrenzter Verlustbeteiligung; und
2. einer **lebenslangen Einkommensphase**, in der das Investment Value zunächst
   Zahlungen finanziert und der Versicherer nach dessen Erschöpfung die
   garantierte Zahlung übernimmt.

Das Modell ist pfadweise für die Kapitalmärkte, aber erwartungswertbasiert für
Tod und Storno. Es ist ein New-Business-Research-Modell ab Vertragsbeginn. Es
ist weder ein In-force-System noch ein bestätigtes Allianz-Administrationsmodell
oder ein APRA/LAGIC-Kapitalmodell.

Die Verarbeitungskette ist:

```text
Produkt + Model Point + Markt + Mortalität + Verhalten + Kosten
                              │
                              ▼
                    Q- oder P-Szenarien
                              │
                              ▼
                  monatliche State Machine
                              │
             ┌────────────────┼─────────────────┐
             ▼                ▼                 ▼
       Q-Bewertung       P-Projektion     Stressrevaluation
       BEL / VNB         Profit / PVFP    Kapitalproxy / RM
```

Das optimale Verhalten in `lsmc.py` ist ein separates Jahresmodell und nicht
in diese monatliche Standardkette integriert.

## 2. Eingaben und Ausgangszustand

### 2.1 Produktobjekt

`AgileProduct` bündelt:

- Gebühren (`FeeSpec`);
- Maximum-Return-Schedule und Guaranteed Minimums (`CapSchedule`);
- versionierte Lifetime-Income-Ratecard (`IncomeRateTable`);
- Withdrawal-Regeln (`WithdrawalRules`);
- MVA-Proxy (`MVASpec`);
- Capital Access Schedule für Age Pension+ (`AgePensionPlusSpec`);
- Eintritts- und Investmentgrenzen; und
- den Carry der beiden Return-Indizes.

Die Juli-2026-Defaults sind:

| Protected Investment Option | Maximum Return | Guaranteed Minimum des künftigen Maximum Return |
|---|---:|---:|
| Australian Equity Total Protection | 6,20 % | 0,25 % |
| Australian Equity Partial Protection 10 | 13,00 % | 0,50 % |
| Global Equity Total Protection | 6,00 % | 0,25 % |
| Global Equity Partial Protection 10 | 12,80 % | 0,50 % |

Das Guaranteed Minimum ist im Modell eine Untergrenze für die zukünftig
verwendete Cap-Schedule, kein jährlicher Mindestzins. Ohne explizite Schedule
wird der Juli-2026-Cap für alle späteren Jahre konstant fortgeschrieben.

### 2.2 Model Point

`PolicySpec` enthält insbesondere:

- Alter, Geschlecht und Commencement-Jahr;
- Initial Investment, Upfront Adviser Fee und optionalen Bonus;
- Allocation auf die vier Protected Investment Options;
- geplanten Income Start und Fixed/Rising;
- Single-/Spouse-Status, Spouse-Alter und -Geschlecht;
- bei Spouse die Death Election `continue_income` oder `lump_sum`;
- Funding Source, Age Pension+ und gegebenenfalls Condition of Release;
- optional die vertragliche CAS Life Expectancy.

Der investierte Startwert ist

\[
P_0=InitialInvestment\,(1-UpfrontAdviserFeePct)
    +InitialInvestment\,BonusPct.
\]

Ein Bonus erhöht also sämtliche folgenden Investment-, Fee- und Withdrawal-
Basen. Gleichzeitig wird sein Betrag bei Zeit null als Akquisitionsaufwand des
Versicherers erfasst. Der 2-%-Bonus ist wegen Angebots- und Kapazitätsgrenzen
nicht Default.

Die Engine prüft unter anderem die Investmentgrenzen AUD 20.000 bis AUD 5 Mio.,
das Eintrittsalter 50 bis 80, Allocation-Summe 100 %, Mindestwartezeit und das
Monatsraster. Jede Projektion startet bei Issue in der Growth Phase.

### 2.3 Lifetime-Income-Rate

Die Rate wird nicht aus dem Alter bei Income Start abgelesen, sondern aus
Alter und Geschlecht am **Product Commencement Date**. Für Spouse Income wird
das jüngere Leben verwendet. Danach werden vollständige Growth-Jahre addiert:

\[
LIPRate = BaseRate_{vintage,age,sex,type,spouse,APS}
          +n_{growth}\,Escalator_{age,sex,type}.
\]

Die Ratecard interpoliert nichtganzzahlige Alter linear. Bei exakt gleichem
Alter bleibt nach der implementierten `<`-Logik das Primary Life das Rating
Life. Weder diese Equal-age-Tie-Regel noch die lineare Interpolation sind gegen
eine Admin-Spezifikation bestätigt.

Beim Basis-Modellpunkt – Mann, Alter 65 bei Commencement, Single, Fixed,
fünf vollständige Growth-Jahre – ergibt sich:

\[
7{,}05\%+5\times0{,}35\%=8{,}80\%.
\]

## 3. Marktmodelle und Maße

### 3.1 Zero Curve

`YieldCurve` verwendet kontinuierlich verzinste Zero Rates. Zwischen den
Tenoren wird die Rate linear interpoliert, außerhalb flach extrapoliert:

\[
P(0,t)=\exp[-z(t)t].
\]

Die Basiskurve des Management-Runners ist illustrativ:

| Laufzeit | 1J | 2J | 5J | 10J | 20J | 30J |
|---|---:|---:|---:|---:|---:|---:|
| Zero Rate | 3,80 % | 3,90 % | 4,10 % | 4,30 % | 4,40 % | 4,40 % |

### 3.2 Risikoneutrales Maß Q

Unter \(Q\) werden replizierbare Cashflows mit risikoneutralem Drift erzeugt
und pfadweise mit dem Money-Market-Account diskontiert:

\[
PV_Q(CF)=E^Q\!\left[\sum_t D_tCF_t\right],\qquad
D_t=\exp\!\left(-\int_0^t r_sds\right).
\]

Q wird für Pricing, BEL, Fair LIP, Greeks und alle Stressrevaluationen des
Kapitalproxys verwendet.

### 3.3 Real-World-Maß P

Unter \(P\) wird nur dem Equity-Drift die `risk_premium` zugeschlagen. Im
Basisfall beträgt sie für beide Indizes 4,50 % p. a. P-Szenarien speisen die
Profit-Signature und Customer-Outcomes.

Heston-Varianzparameter, Hull–White-Zinsparameter und Korrelationen sind unter
P und Q identisch. Volatility Risk Premium, Bond Term Premium und weitere
Measure-Changes fehlen. P ist daher eine illustrative Expected-Experience-
Sicht, keine kalibrierte physische Verteilung.

### 3.4 Unterstützte ESGs

| Modell | Equity | Zins | numerisches Verfahren |
|---|---|---|---|
| `black_scholes` | zwei korrelierte GBMs | deterministische Kurve | exakte monatliche Lognormal-Schritte |
| `heston` | stochastische Varianz je Index | deterministische Kurve | Full-Truncation Euler für Varianz, Log-Euler für Equity, vier Substeps/Monat |
| `hull_white_bs` | BS-Equities | 1F Hull–White | gemeinsame exakte Gauß-Simulation von OU-Faktor, integrierter Rate und Equities |
| `heston_hull_white` | Heston je Index | 1F Hull–White | hybrides Substep-Schema: OU exakt, Rate trapezoidal, Varianz Full-Truncation, Equity Log-Euler |

Für Black–Scholes gilt unter Q:

\[
\frac{dS_{i,t}}{S_{i,t}}=(r_t-q_i)dt+\sigma_i dW^Q_{i,t}.
\]

Die beiden Vertragsindizes sind Return-Indizes. Deshalb ist der Default-Carry
\(q_i=0\); ein Cash-Dividend-Yield der Indexkonstituenten würde Dividenden
doppelt zählen. Basisvolatilitäten sind 16 % für AUS und 15 % für Global,
Equity-Korrelation 0,75.

Im Heston-Modell gilt zusätzlich:

\[
dv_t=\kappa(\theta-v_t)dt+\xi\sqrt{v_t}\,dW_t^v,
\qquad d\langle W^S,W^v\rangle_t=\rho_{Sv}dt.
\]

Die Default-Return-Variance-Korrelation ist −0,60 für AUS und −0,65 für
Global. Diese und alle weiteren Marktparameter sind nicht an eine datierte
Volatilitätsfläche kalibriert.

Hull–White wird als

\[
dx_t=-ax_tdt+\sigma_r dW_t^r,\qquad r_t=\phi(t)+x_t
\]

implementiert. Defaults sind \(a=0{,}03\), \(\sigma_r=0{,}008\) und
Equity-Rate-Korrelation −0,20. Die Parametrisierung von \(\phi(t)\) passt das
Modell an die Anfangskurve an.

### 3.5 Szenarioobjekt und Provenienz

`ScenarioSet` speichert auf Monatsraster:

- normalisierte Indexstände für AUS und Global;
- Short Rate und kumulierten Diskontfaktor;
- optional die Heston-Varianz je Index;
- Measure, Modellname, Seed und Heston-Substeps; und
- einen Fingerprint des Szenarioinhalts.

Die Arrays werden read-only gehalten. Fremde Szenarien werden im Pricing auf
ESG-Konfiguration, Modell, Seed, Pfadzahl, Heston-Substeps und Horizont geprüft.

## 4. Annual Crediting und Optionsreplikation

### 4.1 Vertraglicher Annual Return

Mit \(R=S_T/S_0-1\) lautet der modellierte Annual Return:

\[
c_{TP}(R)=\min(\max(R,0),Cap)
\]

für Total Protection und

\[
c_{PP10}(R)=
\begin{cases}
\min(R,Cap),&R\ge0,\\
\min(0,R+10\%),&R<0
\end{cases}
\]

für Partial Protection 10. Beispielsweise wird eine Indexrendite von −18 %
zu −8 % gutgeschrieben.

### 4.2 Statische Replikation

Pro Einheit Anniversary-Startwert wird der Credit als Optionspaket geschrieben:

\[
V_{TP}=Call(1)-Call(1+Cap),
\]

\[
V_{PP10}=Call(1)-Call(1+Cap)-Put(0{,}90).
\]

Im Black–Scholes-Zweig werden die Vanillas geschlossen bewertet. Im
Heston-Zweig nutzt die Engine einen COS-Pricer mit 128 Termen und einem breiten
Truncation-Intervall. Alle Strikes eines Pakets teilen dieselbe Auswertung der
Heston-Characteristic-Function.

### 4.3 DVA-Modellproxy

Innerhalb eines Crediting-Jahres wird eine Einheit `iv_frame` als Zero Bond
plus Optionspaket bewertet:

\[
p_z(t)=P(t,T_{anniv})+V_{package}(t).
\]

Der aktuelle DVA-konsistente Investment Value ist

\[
IV_t=IV_{frame,t}\,p_z(t).
\]

Am Anniversary konvergiert \(p_z\) zu \(1+c(R)\). Tod, Surrender, Income,
Fees und Withdrawals werden intra-year gegen diesen Wert abgewickelt. Wird ein
Teil des IV entfernt, wird `iv_frame` proportional reduziert, damit die
verbleibenden Einheiten denselben Hedgewert behalten.

Zu Beginn eines neuen Crediting-Zyklus bucht die Engine bei aktiviertem DVA:

\[
CreditingMargin_s=IV_{frame,s}[1-p_z(s)].
\]

Für die Basis-Caps ist diese Position positiv. \(p_z\le1\) ist aber keine
allgemeine Identität; bei teuren Caps oder anderen Marktparametern kann die
Position negativ, also ein Finanzierungsbedarf, sein.

Wenn DVA ausgeschaltet ist, wird eine näherungsweise Jahresendmarge verwendet:

\[
m=(1-V_{package})e^{r_{fwd}}-1.
\]

Die echte Allianz-DVA-Adminformel ist nicht bekannt. Insbesondere fehlen der
vertragliche zeitanteilige Protection Floor und der garantierte Fixed-Return-
Zweig. Das Modell bildet damit einen Hedgewertproxy, nicht den bestätigten
Transaktionswert.

### 4.4 Heston–Hull–White-COS-Einschränkung

Der COS-Zweig ergänzt die Heston-Characteristic-Function um

\[
w=Var\!\left(\int rdt\right)
  +2Cov\!\left(\int rdt,\int\sqrt v\,dW^S\right).
\]

Bei den Defaultparametern ist \(w\) für AUS über ein Jahr leicht negativ
(etwa −2,326×10⁻⁴). Der Code clippt den Term nur bei der Konstruktion des
Truncation-Intervalls, verwendet aber den rohen Wert im CF-Faktor. Er ist daher
keine positive „independent Gaussian variance“. Dieser Zweig ist eine hybride,
nicht gegen ein gemeinsames Heston–Hull–White-Monte-Carlo validierte
Näherung. Der Effekt war in einer Einzelprüfung klein; die mathematische
Qualifikation bleibt dennoch wesentlich.

## 5. Vertragszustände

### 5.1 Phasen

Die Vertragslogik kennt:

```text
GROWTH  ── Income Election ──►  INCOME  ──►  TERMINATED / OUT
```

`OUT` ist absorbierend. In der praktischen Monatsprojektion werden Tod und
Storno nicht als einzelne binäre Pfade simuliert. Stattdessen reduziert die
Engine das In-force-Gewicht `w`; der verbleibende Zustand ist der bedingte
Survivor-/Non-lapser-Zustand. `TERMINATED` wird pfadweise insbesondere bei
einem im Growth erschöpften IV verwendet. Diese Wahrscheinlichkeitsgewichtung
reduziert Monte-Carlo-Varianz.

### 5.2 Zentrale Pfadzustände

| Zustand | Bedeutung |
|---|---|
| `iv` | aktueller DVA-konsistenter Investment Value |
| `iv_frame` | Vertrags-/Hedgeeinheiten ohne den aktuellen DVA-Faktor; zugleich Fee-Basis |
| `phase` | Growth, Income oder Out |
| `income_annual` | aktuell garantiertes jährliches Fixed/Rising Income |
| `w` | In-force-Gewicht nach Tod und Storno |
| `anniv_index_level` | Indexfixings zu Beginn des aktuellen Crediting-Zyklus |
| `anniv_step` | Beginn des aktuellen, gegebenenfalls nach Election verschobenen Crediting-Jahres |
| `free_wd_used` | verbrauchte 5-%-Allowance im Anniversary Year |
| `partial_wd_used`, `wd_limit_base` | Nutzung und Basis der kumulativen 95-%-Grenze |
| `aps_active`, `cas_base`, `cas_start_t`, `cas_le`, `cas_wd` | Age-Pension+-/CAS-Zustand |
| `joint_surv_primary`, `joint_surv_spouse` | ab Income Election konditionierte Joint-Life-Survival-Zustände |

Optional zeichnet die Engine komplette Pfade für `iv`, `income` und `phase`
auf. Für normale Bewertungen ist `record_paths=False`, um Speicher zu sparen.

## 6. Monatliche Ereignisreihenfolge

Die Reihenfolge im Code ist materiell und lautet für jeden Monatsendpunkt:

1. **Marktstand übernehmen.** Index, Varianz, Short Rate und Discount stammen
   aus dem ESG-Schritt.
2. **Anniversary Credit.** Nur am Ende des aktuellen Crediting-Jahres wird die
   Point-to-Point-Rendite mit dem für dieses Jahr gültigen Cap gutgeschrieben.
   In der Income Phase wird ausschließlich Australian Equity Total Protection
   verwendet. Bei Rising Income wird das garantierte Income mit einem positiven
   AUS-TP-Credit erhöht und kann nicht sinken.
3. **Intra-year DVA aktualisieren.** Außerhalb des Anniversary wird `iv` aus
   `iv_frame × p_z(t)` neu bewertet.
4. **Gebühren abziehen.** Product Fee und LIP werden monatlich auf `iv_frame`
   approximiert. Die Entnahme ist auf den verfügbaren aktuellen `iv` begrenzt;
   `iv_frame` wird proportional reduziert.
5. **Age Pension+ aktivieren.** Am vertraglichen Monatsdatum werden Post-Fee-IV,
   CAS-Start und Life Expectancy fixiert.
6. **Income wählen.** Am Anniversary oder am geplanten Off-anniversary-
   Monatsdatum wird Income auf der Post-Fee-DVA-Basis fixiert. Bei
   Off-anniversary-Start wird der laufende Growth-DVA-Zyklus geschlossen und
   ein frischer AUS-TP-Zyklus ab Election gestartet.
7. **Neuen Crediting-Zyklus finanzieren.** Nach Anniversary/Election wird der
   neue DVA-Zyklus gestartet und die modellierte Crediting Margin aus dem
   Post-Fee-Wert gebucht. Am finalen Projektionspunkt wird kein neuer Zyklus
   eröffnet.
8. **Tod vor Zahlung.** Der Death Benefit basiert auf dem pre-payment IV. Nur
   Überlebende erhalten die nachschüssige Income-Zahlung. Age Pension+ kann den
   Death Benefit kappen; die Differenz wird als `aps_retained` erfasst.
9. **Income zahlen.** Die Monatsrate ist `income_annual/12`. Im Wahlmonat wird
   noch nicht gezahlt; die erste Rate folgt einen Monat nach Election. Soweit
   möglich kommt die Zahlung aus IV. Der Rest ist `guarantee_claim` des
   Versicherers. Income läuft nach IV-Erschöpfung weiter.
10. **Partial Withdrawals durchführen.** Je nach Behaviour-Schedule jährlich
    am Anniversary oder monatlich; zuerst Free Allowance, danach Excess/MVA.
11. **Maintenance Expenses buchen.** Fixkosten werden inflationsindiziert,
    variable Kosten auf das aktuelle IV erhoben und mit dem nach Tod
    verbleibenden In-force-Gewicht gebucht.
12. **Lapse/Full Withdrawal anwenden.** Der Surrender Value wird inklusive MVA
    und gegebenenfalls APS-Lower-of bestimmt. Das In-force-Gewicht wird um die
    statische oder dynamische Monatslapse reduziert.

Am Projektionshorizont wird ein verbleibendes IV als Residual-Closeout in der
Cashflow-Komponente `death_benefits` erfasst. Das ist eine technische
Closeout-Klassifikation und kein modellierter Tod genau am Horizont.

### 6.1 Anniversary-Sonderlogik

Am Anniversary wird zuerst der Return des abgelaufenen Jahres gutgeschrieben,
dann werden die bis zu diesem Datum approximierten Gebühren abgezogen und erst
danach werden Income und CAS-Basis fixiert. Damit verwendet die Income Base
den Post-Credit-, Post-Fee-Wert.

Für eine fällige nachschüssige Zahlung am Income Anniversary gilt noch das
vor dem Rising-Ratchet bestehende Income. Das erhöhte Income wirkt ab der
folgenden Monatszahlung.

Der PDS-Zwangsstart wird als erster Policy Anniversary nach Erreichen von Alter
100 modelliert. Für aktives APS in Growth wird der Start auf den ersten
ursprünglichen Policy Anniversary nach Ablauf der CAS Life Expectancy
vorgezogen.

## 7. Gebühren, MVA, Withdrawals und Age Pension+

### 7.1 Gebühren

Default sind:

- Product Fee: 0,30 % p. a.;
- Lifetime Income Premium: 1,15 % p. a.

Vertraglich tägliches Accrual und jährliche/eventgetriebene Deduction werden
als direkte monatliche Deduction approximiert. Die Basis ist `iv_frame`, also
Investment Value ohne den aktuellen DVA-Auf-/Abschlag.

Bei Age Pension+ wird der LIP in der Income Phase erst ab dem späteren von
Income Commencement und Pension-Age-/Condition-of-Release-Zeitpunkt erlassen.

### 7.2 MVA-Proxy

Innerhalb der ersten zehn Jahre lautet der modellierte Faktor:

\[
f_{MVA}(t)=1-
\left(\frac{1+z_{issue}+spread}{1+z_t+spread}\right)^\tau
+loading+loading_{py}\tau,
\]

wobei \(\tau\) die Restdauer des Zehnjahresfensters ist. Bei `only_reduces=True`
wird ein negativer Zinsanteil auf null gesetzt, sodass MVA keinen Kundengewinn
erzeugt. Die Basis-Loadings sind null. Die Parameter sind nicht gegen echte
Allianz-Quotes kalibriert.

Bei Full Surrender in Growth wird die verbleibende Free Allowance zuerst vom
MVA-exponierten Betrag abgezogen. In Income gibt es keine Free Allowance.

### 7.3 Partial Withdrawals

Growth-Regeln:

- Free Withdrawal Amount: 5 % des initialen Investment Amount pro Anniversary
  Year, ohne Carry-forward;
- Mindestentnahme AUD 100;
- maximal 95 % des IV je Transaktion;
- zusätzlich kumulativ maximal 95 % der Basis zu Beginn des Anniversary Year,
  jeweils inklusive MVA;
- mindestens AUD 2.000 Restwert.

Ein `excess_rate` wird als Anteil des aktuellen IV beantragt. Verbleibende Free
Allowance wird zuerst verbraucht; nur der darüberliegende Teil trägt MVA. In
der Income Phase reduziert eine Excess Withdrawal das Locked Income
proportional zur Bruttoreduktion des IV:

\[
Income_{new}=Income_{old}
\left(1-\frac{Withdrawal+MVA}{IV_{before}}\right).
\]

Der Basislauf setzt `free_utilisation=0` und `excess_rate=0`; Withdrawals sind
dort also ausgeschaltet.

### 7.4 Age Pension+ / CAS

Der Aktivierungszeitpunkt hängt von der Funding Source ab:

- Non-superannuation: früheres Datum aus Income Commencement und Pension Age;
- Superannuation: explizit gelieferte Relevant Condition of Release.

Bei Aktivierung werden `cas_base = IV`, CAS-Start und Life Expectancy fixiert.
Fehlt eine explizite CAS Life Expectancy, wird die illustrative
Mortalitätsbasis als nicht produktionsfähiger Fallback verwendet.

Der Maximum Withdrawal Value ist

\[
MWV_t=\max\left[0,
CASBase\left(1-\frac{elapsed}{LE}\right)-WithdrawalsSinceElection
\right].
\]

Der Death Cap bleibt bis zur halben Life Expectancy auf 100 % der CAS Base und
springt dann unmittelbar auf den zu diesem Zeitpunkt niedrigeren linearen
MWV-Pfad. Frühere Withdrawals reduzieren auch den Death Cap.

Bei Withdrawal oder Full Surrender gilt der vertragliche Lower-of-Test:

- bindet `IV − MVA`, wird MVA erhoben und die Reduktionsquote ist
  `(Cash + MVA)/IV`;
- bindet MWV, wird keine separate MVA erhoben und die Reduktionsquote ist
  `Cash/MWV`.

Die durch diese Reduktionsquote über den Kundencashflow hinaus entfernte
IV-Komponente wird als `aps_retained` gebucht.

## 8. Mortalität und Spouse

### 8.1 Defaultbasis

`MortalityTable.gompertz_makeham()` erzeugt eine synthetische Tabelle bis Alter
115:

\[
\mu(x)=A+Bc^x,
\qquad q_x=1-\exp\left(-\int_x^{x+1}\mu(u)du\right).
\]

Sie soll nur die Form einer australischen Lebenstafel annähern. Für Produktion
muss `MortalityTable.from_qx()` mit einer vollständigen Pricing-/Reserving-
Tabelle verwendet werden.

Die generational verbesserte Jahreswahrscheinlichkeit ist:

\[
q(x,y)=clip\{q_x[1-i(x)]^{\max(y-y_0,0)}s,0,1\}.
\]

Default sind Base Year 2022, 1,25 % Improvement bis Alter 90, linearer Taper
bis null bei Alter 110 und Stressmultiplikator 1. Monatlich wird konstante
Hazard innerhalb des Jahres unterstellt:

\[
q^{(m)}=1-(1-q)^{1/12}.
\]

Der First-Year-Catastrophe-Stress kann für die ersten zwölf
Projektionsmonate additiv auf q gelegt werden.

### 8.2 Wahrscheinlichkeitsgewichtung

Für jeden Marktpfad führt die Engine ein In-force-Gewicht. Bei Monatsmortalität
\(q_m\) wird der Death Benefit mit \(wq_m\) und alle nachfolgenden Cashflows
mit \(w(1-q_m)\) gewichtet. Analog wird später die Lapse-Wahrscheinlichkeit
angewendet. Marktpfade werden damit nicht um zusätzliche binäre
Mortalitäts-/Lapse-Zufallszahlen erweitert.

### 8.3 Joint Life

Bei `continue_income` wird in der Income Phase Last-Survivor-Survival unter
Unabhängigkeit verwendet:

\[
{}_tp_{LS}={}_tp_1+{}_tp_2-{}_tp_1{}_tp_2.
\]

Die Zustände beider Leben werden ab der tatsächlichen Income Election auf eins
konditioniert und von dort fortgeschrieben. Vor Election gilt Primary-Life-
Mortalität. Der Default-Horizont reicht bis zum terminalen Alter 115 des
jüngeren beziehungsweise länger laufenden gedeckten Lebens.

Bei `lump_sum` folgt auch die Income Phase der Primary-Life-Death-Decrement-
Logik und zahlt den Death Benefit bei dessen Tod. Die Engine bewertet diese
beiden Death Elections als getrennte Szenarioinputs, nicht als späteres
optimiertes Wahlrecht.

Systematisches Langlebigkeitsrisiko und Mortality Risk Premium werden nicht
stochastisch modelliert; im Kapitalproxy existieren nur deterministische
Mortalitätsstresse.

## 9. Verhalten

### 9.1 Statisches Storno

Default-Growth-Lapses sind jährlich 3,0 %, 3,5 %, 4,0 %, 4,0 %, 4,0 %, 3,5 %,
3,0 %, 3,0 %, 2,5 %, 2,0 %, 2,0 %; danach bleibt der letzte Satz konstant.
Income-Lapse ist 0,5 % p. a. Die Engine transformiert Jahresraten in
Monatswahrscheinlichkeiten.

### 9.2 Dynamisches Storno

Im Income-Zustand dient folgende Moneyness als Signal:

\[
M_t=\frac{Income_t\,AF_t}{SurrenderValue_t}.
\]

Der Lapse-Multiplikator ist

\[
m_t=clip[1-\beta(M_t-M_0),floor,cap].
\]

Defaults sind \(\beta=1{,}5\), \(M_0=1\), Floor 0,2 und Cap 2,5. Eine stärker
im Geld liegende Garantie storniert im Modell weniger. Der Annuitätenfaktor
ist ein heuristischer Mid-year-Proxy mit der pfadweisen flachen 10-Jahres-
Zero Rate; er ist kein vollständiger Tail-PV.

In Growth wird statt der Income-Moneyness das Verhältnis Surrender Value zu IV
verwendet. Eine bindende MVA reduziert damit die Lapse-Neigung. Growth wird
monatlich aktualisiert; der Income-Multiplikator wird grundsätzlich an
Anniversaries aktualisiert und innerhalb des Jahres gehalten.

Bei Off-anniversary Income Election berechnet die Helper-Funktion den ersten
Income-Multiplikator gegen IV statt gegen den MVA-/APS-bereinigten Surrender
Value. Erst am nächsten verschobenen Anniversary wird dies korrigiert. Das ist
eine bekannte Implementierungsvereinfachung.

### 9.3 Income Take-up

`IncomeTakeUp` unterstützt:

- `deterministic`: alle Pfade starten am `income_start_year`; oder
- `hazard`: jährliche, mit einem separaten Seed gezogene Take-up-
  Wahrscheinlichkeiten, spätestens `force_by_year`.

Im Management-Basislauf gilt deterministischer Start nach fünf Jahren. Die im
Objekt vorhandene Hazard-Kurve ist dann inaktiv.

### 9.4 Dynamische Withdrawal Utilisation

Optional skaliert ein analoger Multiplikator Free-/Excess-Withdrawals:

\[
u_t=clip[1-\gamma(M_t-M_0),floor,cap],
\]

ergänzt um MVA-Dämpfung

\[
u_t^{MVA}=clip(1-\gamma_{MVA}f_{MVA},0,1).
\]

Das Modul ist defaultmäßig deaktiviert. Auch diese Moneyness ist ein
Behaviour-Signal und keine separate Liability-Bewertung.

## 10. Cashflows und marktkonsistente Bewertung

### 10.1 Cashflow-Buckets

Die Projektion erzeugt je Marktpfad und Monatszeitpunkt bereits
in-force-gewichtete Arrays für:

| Gruppe | Cashflow-Buckets |
|---|---|
| Zufluss/Start | `premium` |
| Kundenleistung | `income_paid`, `death_benefits`, `surrender_benefits`, `partial_withdrawals` |
| Versichereraufwand | `guarantee_claims`, `expenses` |
| Finanzierung/Marge | `fees_product`, `fees_lip`, `crediting_margin`, `mva_retained`, `aps_retained` |

`income_paid` ist die volle Kundenzahlung. `guarantee_claims` ist nur der Teil,
der nach IV-Erschöpfung nicht mehr aus dem Konto finanziert werden kann.

### 10.2 Q-Barwerte

Für jede Komponente wird der Pfadbarwert summiert und dann über Pfade gemittelt.
Die zentrale Größen sind:

\[
BEL_{NU}=PV(Claims)+PV(Expenses)
-PV(ProductFees)-PV(LIP)-PV(CreditingMargin)
-PV(MVAretained)-PV(APSretained),
\]

\[
InsurerNetValue=-BEL_{NU},
\]

\[
BEL_{total}=P_0+BEL_{NU}.
\]

`bel_total` ist dabei eine interne Investment-Value-plus-Non-unit-Konvention,
kein regulatorischer Unit Reserve oder APRA/AASB/IFRS Policy Liability.

Der isolierte Garantiewert ist

\[
GuaranteeValue=PV(GuaranteeClaims)-PV(LIPFees).
\]

Er misst den modellierten Netto-Riderwert, nicht die Gesamtprofitabilität.

### 10.3 Fair LIP

`fair_lifetime_income_premium()` sucht per Brent-Verfahren den LIP-Satz mit

\[
GuaranteeValue(LIP^*)=target,
\]

defaultmäßig `target=0`. Eine gemeinsame feste Q-Szenariomenge wird für alle
Fee-Versuche wiederverwendet. Die Objective enthält die Rückwirkung der
geänderten Fee auf IV und Claims. Der Satz ist ein modellierter Rider-
Break-even, kein Gesamtprodukt-Break-even.

### 10.4 Marktwertidentität

Die Reconciliation lautet:

\[
\begin{aligned}
P_0={}&PV(Income+Death+Surrender+PartialWithdrawals)\\
&-PV(GuaranteeClaims)\\
&+PV(ProductFees+LIP+CreditingMargin+MVAretained+APSretained).
\end{aligned}
\]

Die Engine berichtet

\[
IdentityGap=\frac{PV(financed\ flows)-P_0}{P_0}.
\]

Ein kleiner Gap kontrolliert Cashflow-Leakage und interne
Martingal-/Buchungskonsistenz. Er validiert weder die echte DVA-/MVA-Formel
noch Mortalität, Verhalten, Kalibrierung oder Vertragsvollständigkeit.

### 10.5 Greeks

`greeks()` soll den Insurer Net Value per Common-Random-Numbers bump-and-revalue
ableiten:

- `equity_delta_pct`: zentraler ±1-%-Levelshock aller Indexpfade, normiert auf
  Premium;
- `vega_per_volpt`: additiver Volatilitätsshock, auf einen Volatilitätspunkt
  normiert;
- `rho_per_100bp`: zentraler Parallelshift der Zero Curve, auf 100 bp normiert.

Die Greek-Funktion ruft die Bewertung ohne `ExpenseAssumptions` auf und ist
daher eine Vor-Kosten-Sicht. In Version 1.3.0 ist ihr Equity-Shock außerdem
End-to-End defekt: Er weist einem Feld der frozen `ScenarioSet`-Dataclass einen
neuen Wert zu und wirft `FrozenInstanceError`. Das Kapitalmodul verwendet für
denselben Mechanismus korrekt `dataclasses.replace`; der reproduzierte
Management-Pack benötigte einen rein laufzeitlokalen Workaround.

## 11. Kapitalproxy

### 11.1 Standalone-Revaluation

Für jeden Stress gilt:

\[
SCR_i=\max(0,NAV_{base}-NAV_i^{stress}),
\]

wobei NAV der Q-Barwert des Versicherer-Netto-Cashflows ist. Marktstresse
werden mit gleichem Seed neu simuliert; Life-Stresse verwenden die unveränderte
Basisszenariomenge.

Default-Stresse:

| Modul | Umsetzung |
|---|---|
| Interest | tenorabhängige SII-artige relative Up-/Down-Shifts; Up mindestens +100 bp |
| Equity | −39 % Levelshock auf alle Indexstände nach Zeit null |
| Equity Vol | +25 % relativ, optionaler nicht-SF Add-on |
| Longevity | q × 0,80 |
| Mortality | q × 1,15 |
| Lapse Up/Down | Basislapses × 1,50 bzw. × 0,50 |
| Mass Lapse | Shortcut 40 % × positiver Basis-NAV, keine State-Revaluation |
| Expense | Maintenance Level +10 % und Inflation +1 %-Punkt |
| Cat | q + 0,0015 in den ersten zwölf Projektionsmonaten |

Der Expense-Stress erhöht nur Maintenance-Kosten, nicht Acquisition Expense.

Der bindende Interest-SCR ist das Maximum von Up und Down; der bindende Lapse-
SCR das Maximum von Up, Down und Mass. Markt und Life werden mit
Korrelationsmatrizen aggregiert:

\[
SCR=\sqrt{s^TCs}.
\]

Die Interest-Equity-Korrelation ist richtungsabhängig: 0,5, wenn Interest Down
bindet, sonst 0. Markt und Life haben Top-Level-Korrelation 0,25.

### 11.2 Risk Margin

Der Runoff-Treiber ist der Q-PV der verbleibenden Guarantee Claims plus
Expenses, auf den jeweiligen Runoff-Zeitpunkt aufgezinst und auf Zeit null
normiert. Falls dieser Treiber zu Beginn null ist, wird der erwartete
In-force-Runoff verwendet.

Der Cost-of-Capital-Proxy lautet:

\[
RM=6\%\sum_t SCR_{life}(t)P(0,t+1).
\]

Nur Life SCR gilt als nicht hedgebar. `with_risk_margin=False` setzt RM auf
null, lässt aber den SCR-Runoff für Profitability bestehen.

### 11.3 Was der Proxy nicht ist

Das Ergebnis trägt ausdrücklich `SII_RESEARCH_PROXY_NOT_APRA`. Es fehlen die
fund-level Architektur und Inputs für APRA LPS 110/114/115/117/118:

- Statutory-Fund-Bilanz und Portfolioaggregation;
- Assets, Derivate, Hedgepositionen und Off-Balance-Sheet-Exposures;
- Credit/Default, FX, Inflation und Konzentrationen;
- Operational Risk, Aggregation Benefit und Combined Stress; und
- genehmigte Management Actions sowie gegebenenfalls eine APRA-Methode für
  Variable-Annuity-Business.

Ein bloßer Austausch der `CapitalStresses` kann daraus kein APRA/LAGIC-Modell
machen.

## 12. Profitabilität

### 12.1 Zwei Projektionen

`analyse_profitability()` kombiniert:

1. eine Q-Bewertung für VNB und Certainty-Equivalent-Reserve; und
2. eine P-Projektion für erwartete operative Cashflows.

Die P-Projektion verwendet denselben Modelltyp und dieselbe Pfadzahl, aber
intern `seed + 1`. Ihre Equity-Drifts enthalten die Risk Premium.

### 12.2 Profit-Signature und BEL-Runoff

Die undiskontierte jährliche P-Signature ist

\[
Signature_y=Fees_y+CreditingMargin_y+MVA_y+APS_y
            -GuaranteeClaims_y-Expenses_y.
\]

Der Non-unit-BEL-Runoff wird ohne Nested Stochastics aus den verbleibenden
Q-Barwert-Cashflows abgeleitet. Diese PV(0)-Tails werden auf den jeweiligen
Jahreszeitpunkt aufgezinst. Ein Risk-Margin-Runoff wird als Liability zum BEL
addiert, nicht als Required Capital behandelt.

### 12.3 Distributable Earnings

Zeit null enthält Acquisition-/Reserve-Strain und die anfängliche
Kapitalbereitstellung:

\[
DE_0=(1-Tax)(Signature_0-BEL_0)-Capital_0.
\]

Für spätere Jahre gilt im Code:

\[
Profit_y=Signature_y+Interest(BEL_{y-1})-(BEL_y-BEL_{y-1}),
\]

\[
DE_y=(1-Tax)[Profit_y+CapitalIncome_y]
     +(Capital_{y-1}-Capital_y).
\]

Capital Income entspricht risikofreiem Forward-Ertrag plus optionalem Spread.
Default sind 8 % Hurdle Rate, 30 % Tax, null Capital Earning Spread und
Kapitalberücksichtigung eingeschaltet.

Die Steuerlogik multipliziert positive und negative Jahresergebnisse sofort
mit 70 %. Sie unterstellt also eine unmittelbar realisierbare Steuerentlastung
auf Verluste. Tax-Loss-Carry-Forward, Deferred Tax und Recoverability fehlen.

### 12.4 Kennzahlen

\[
VNB_{gross}=InsurerNetValue,
\qquad VNB=VNB_{gross}-RM,
\]

\[
NBM=VNB/P_0,
\qquad PVFP(h)=\sum_y DE_y(1+h)^{-y}.
\]

Zusätzlich werden berechnet:

- `pvfp_margin = PVFP/Premium`;
- die niedrigste gefundene reale IRR oberhalb −100 % auf einer breiten
  Log-Rate-Suche; und
- das erste Jahr, in dem die nominal kumulierten Distributable Earnings
  positiv sind.

Mehrfach-IRR-Cashflows bleiben grundsätzlich mehrdeutig. PVFP und VNB
beantworten verschiedene Fragen: PVFP diskontiert erwartete P-
Shareholdercashflows mit Hurdle Rate, VNB ist Q-Marktwert abzüglich RM.

## 13. Optimales Verhalten mit LSMC

### 13.1 Separater Jahresmotor

`value_optimal_behaviour()` ist kein Schalter der Monatsprojektion, sondern ein
eigenständiges jährliches Q-Modell. Es weist Age Pension+ und Off-anniversary
Starts ab. Gebühren werden einmal jährlich als Faktor `1 − total fee`
abgezogen; Income wird jährlich nachschüssig gezahlt; DVA innerhalb des Jahres
existiert nicht.

Default sind 30.000 Trainingspfade, 50.000 Evaluationspfade, Seed 4711 und ein
Horizont bis Alter 105, höchstens 40 Jahre. Der Monatsmotor reicht dagegen
grundsätzlich bis Alter 115.

### 13.2 Aktionen

Auf jedem Anniversary ab Jahr 1:

| Phase | Aktionen |
|---|---|
| Growth | Continue, Start Income, Surrender, Free Withdrawal, Free + Excess Withdrawal |
| Income | Continue, Surrender, Excess Withdrawal |

Die Excess-Fraktion ist defaultmäßig ein einzelner diskreter Wert von 10 % des
IV, kein kontinuierliches Optimierungsproblem.

### 13.3 Regression und adapted Policy

Die Features umfassen:

- Konstante;
- normalisiertes IV, IV² und IV³;
- normalisiertes Income und Income²;
- IV × Income; sowie
- bei entsprechenden ESGs Varianz, Varianz × IV, Short Rate, Rate × IV und
  Rate × Income.

Der Backward Pass zieht für jeden Zeitpunkt randomisierte IV-/Income-Zustände,
bewertet die Aktionskandidaten und schätzt Ridge-Regressionen. Zusätzlich werden
reine One-year-Continuation-Regressionsmodelle gespeichert.

Der unabhängige Forward Pass verwendet für die Entscheidung nur Zustand und
Regressionswert zum Zeitpunkt n. Die tatsächlich realisierte Folgejahresrendite
und Diskontierung fließen erst danach in die Bewertung ein; damit ist die
gelernte Policy adapted und frei vom früheren Look-ahead-Fehler.

### 13.4 Tod, Tail und Static-Fallback

Im Jahresmodell erhalten Todesfälle pre-payment IV, Überlebende die
nachschüssige Zahlung plus Continuation. Für Spouse Income wird eine
unbedingte Last-Survivor-Kurve ab Issue verwendet. Anders als im Monatsmotor
wird sie nicht konsistent auf die tatsächliche, pfadabhängige Election
konditioniert.

Am Horizont ist der Income-Closeout

\[
\max(IV,Income\times AF),
\]

wobei der Annuitätenfaktor pauschal mit der 30-jährigen Zero Rate berechnet
wird. Das vermeidet die frühere Doppelzählung von vollem IV und voller
Annuität, bleibt aber eine Tail-Näherung.

Die Static Policy startet zum vorgegebenen Jahr und enthält im LSMC-Forward-
Pass keine Storno-/Withdrawal-Entscheidungen. Sie ist nicht vollständig
like-for-like mit dem statischen oder dynamischen Monatsmotor.

Ist die gelernte Policy auf dem Evaluationssample schlechter als Static,
meldet die Engine den Static-Wert und dessen Exercise-Raten. Der Erwartungswert
einer festgelegten admissible Policy ist theoretisch ein Lower Bound auf den
wahren optimalen Kundenwert. Der ausgegebene Monte-Carlo-Wert ist wegen
Sampling, Regression und der Auswahl des Maximums aus learned/static auf
demselben Sample jedoch **kein strikter numerischer Lower Bound**. Die
Eigenschaft `optimal >= static` ist konstruktiv und kein unabhängiger
Validierungsnachweis.

## 14. Sensitivitäten

`standard_scenarios()` enthält folgende Einfaktor-Bumps:

1. Rates +100 bp;
2. Rates −100 bp;
3. Equity Vol +25 % relativ;
4. alle Caps −100 bp, aber nicht unter Guaranteed Minimum;
5. Longevity: q −10 %;
6. Mortality: q +10 %;
7. Lapse +50 %;
8. Lapse −50 %;
9. Dynamic Lapse aus;
10. Take-up zwei Jahre später;
11. Take-up zwei Jahre früher;
12. Free Withdrawals zu 100 % genutzt;
13. zusätzlich 2 % Excess Withdrawal p. a.;
14. Maintenance Expenses +10 %; und
15. Equity Risk Premium −100 bp, nur mit Wirkung unter P.

Jedes Szenario rechnet Q-Value und P-Profitability neu. Defaultmäßig wird im
Sensitivity-Runner Kapital aus Laufzeitgründen ausgelassen. Dann sind VNB und
PVFP **vor** Kapital und Risk Margin; Guarantee Value bleibt eine Q-Größe. Der
Expense-Bump betrifft nur Maintenance, nicht Acquisition. Die Tabellen liefern
keine gepaarten Standardfehler.

Der Equity-Level-Shock ist nicht Teil dieser Batterie; er liegt in Greeks und
Kapitalmodul.

## 15. Module und Schnittstellen

| Datei | wichtigste Inputs | wichtigste Outputs/Funktionen |
|---|---|---|
| `product.py` | kommerzielle Produktparameter, Ratecard, Model Point | `AgileProduct`, `PolicySpec`, Income-/Cap-/MVA-/APS-Funktionen |
| `curves.py` | Tenoren, kontinuierliche Zero Rates | Discount Factors, Forward Rates, Curve Shifts |
| `esg.py` | Curve, Equity/Heston/HW-Parameter, Measure, Seed | immutable `ScenarioSet` mit Marktpfaden |
| `crediting.py` | Indexratio, Protection, Cap, Markt-/Varianzzustand | Annual Credit, BS-/COS-Paketwert, DVA-Faktor, Fair Cap |
| `mortality.py` | qx oder GM-Parameter, Improvements/Stresse | monatliche q, Survival, Joint Life, LE, Annuitätenfaktor |
| `behavior.py` | Lapse-, Take-up- und Withdrawal-Annahmen | statische/dynamische Raten und Multiplikatoren |
| `projection.py` | Produkt, Policy, Szenarien, Behaviour, Mortality, Expenses | monatliche Zustände und Cashflow-Arrays, Identity Gap |
| `pricing.py` | Q-Inputs und Valuation Settings | PV-Komponenten, BEL, Insurer Value, Fair LIP, Greeks |
| `capital.py` | Q-Bewertung und Stressset | Standalone SCRs, Markt/Life/BSCR, RM und Runoff |
| `profitability.py` | Q-Value, P-Projektion, Kapital, Hurdle/Tax | Profit-Signature, BEL/Capital-Pattern, DE, VNB, PVFP, IRR |
| `sensitivities.py` | Scenario-Transformationen | tidy Szenariotabelle mit Leveln und Deltas |
| `lsmc.py` | jährliches Q-Modell und Aktionsset | Static-/Optimal-Wert und Exercise-Raten |

Der Assumptions-Fingerprint soll verhindern, dass Valuation- oder Capital-
Ergebnisse unter abweichenden Produkt-, Policy-, ESG-, Mortality-, Behaviour-,
Expense- oder Settings-Annahmen wiederverwendet werden.

## 16. Management-Runner: Basisannahmen und Outputs

### 16.1 Kanonischer Modellpunkt

`examples/run_insurer_analysis.py` baut:

- Commencement Mitte 2026;
- Mann 65, Non-superannuation;
- AUD 100.000 Initial Investment;
- 100 % Australian Equity Total Protection;
- Fixed Income ab Jahr 5;
- kein Spouse, kein Age Pension+, kein Adviser Fee, kein Bonus;
- dynamisches Lapse-Regime, aber keine geplanten Withdrawals;
- synthetische Gompertz–Makeham-Mortalität;
- 2 % Acquisition Expense, AUD 80 Maintenance p. a., 5 bp IV-Kosten,
  2,5 % Inflation; und
- Black–Scholes als Kernmodell.

Pfadzahlen des instrumentierten Packs:

| Analyse | Pfade |
|---|---:|
| Basispricing/Kapital/Profitability | 4.000 |
| Sensitivitäten | 1.200 |
| Product Designs und Timing | 1.500 |
| Behaviour Surfaces | 600 |
| Customer Outcomes | 2.500 |
| Modellvergleich | 600 je Modell |
| Seed-Stabilität | 800 je Seed, fünf Seeds |

### 16.2 CSV-Ausgaben

Der Runner erzeugt:

- `pv_components.csv`: Q-PV je Cashflow-Bucket;
- `executive_kpis.csv`: Premium, VNB, Fair/Charged LIP, BEL, Guarantee Value,
  BSCR/RM, PVFP, IRR, Payback, Identity Gap und Gross-VNB-SE;
- `reconciliations.csv`: Pricing-/Identity-Prüfungen;
- `market_greeks.csv`: Vor-Kosten-Greeks;
- `capital_proxy.csv`: Standalone- und bindende Kapitalmodule, BSCR, RM;
- `profit_runoff.csv`: Profit-Signature, DE, kumulierte DE, BEL/RM und Kapital;
- `sensitivities.csv`: Standard-Bumps;
- `customer_outcome_quantiles.csv` und `customer_annual_cashflows.csv`:
  P-Kundenoutcomes;
- `product_designs.csv`: Fixed/Rising/Spouse-Varianten;
- `income_start_timing.csv`: Timing-Varianten;
- `behaviour_takeup_lapse.csv` und `behaviour_withdrawals.csv`:
  Verhaltensflächen;
- `model_comparison.csv`: BS/Heston/HW/Heston-HW-Vergleich; und
- `mc_seed_stability.csv`: Seed-Diagnostik.

Hinzu kommen zehn PNG-Grafiken, ein Management-Report und
`run_manifest.json`.

### 16.3 Provenienzgrenzen

Das Manifest enthält Engine-Version, Python-/Library-Versionen, Inputs,
Settings sowie Valuation-/Capital-Fingerprints. Der `engine_source_sha256`
hasht aber nur `agile_engine/*.py`; Runner, Tests, Kommandozeile,
Runtime-Workaround und Outputs sind nicht umfasst. Die P-Projektion verwendet
intern `seed + 1`, dieser effektive Sub-Seed wird nicht separat attestiert.

Der unveränderte Runner bricht derzeit in `greeks()` ab. Der reproduzierte
vollständige Pack basiert deshalb auf einem dokumentierten, prozesslokalen
`dataclasses.replace`-Workaround. Das ändert keine fachliche Greek-Definition,
ist aber eine wesentliche Run-Provenienzinformation.

## 17. Wesentliche Modelllücken

### 17.1 Produkt und Administration

- kein In-force-Einstieg mit aktueller Phase, IV, Locked Income, laufendem
  Fixing, Certificate Cap, Issue Curve, CAS State und verbrauchter Allowance;
- Fixed/Rising, Spouse, APS, Death Election und Allocation sind Szenarioinputs,
  keine gemeinsam bewerteten späteren Wahlrechte;
- keine jährliche optimierte Reallocation und keine separaten Option-Balances;
- konstante Future Caps, sofern keine Schedule geliefert wird;
- fehlender Fixed-Return-Zweig und fehlender zeitanteiliger DVA-Protection-
  Floor;
- DVA/MVA nicht gegen Adminformeln oder Quotes reconciliert;
- tägliche Fee Accruals und eventgetriebene Deduction nur monatlich
  approximiert;
- Ongoing Adviser Fees, PAYG/Withholding, Cooling-off und Reinsurance fehlen;
- APS Life Expectancy ohne expliziten Input nur illustrativer Fallback;
- Investor-Eligibility und einzelne automatische Vertragsereignisse fehlen.

### 17.2 Finanz- und Versicherungsmathematik

- Marktparameter und Kurve sind nicht datiert/produktionskalibriert;
- P unterscheidet sich von Q nur durch Equity ERP;
- Heston/HW-Hybrid und insbesondere negativer COS-Cross-Term nicht durch einen
  gemeinsamen unabhängigen Benchmark validiert;
- kein systematisches stochastisches Langlebigkeitsmodell oder Mortality Risk
  Premium;
- Mortality, Lapse, Take-up, Withdrawals und Expenses sind illustrativ;
- Off-anniversary-Income-Lapse nutzt zunächst IV statt Surrender Value;
- LSMC-Horizont, Tail und Joint-Life-Conditioning weichen vom Monatsmotor ab;
- LSMC ist nicht in Pricing, Kapital oder Profitability integriert;
- keine Nested-Stochastic-Reserve- oder Capital-Verteilung.

### 17.3 Regulierung, Tax und Betrieb

- Kapital ist ein Solvency-II-artiger Einzelpolicenproxy, nicht APRA/LAGIC;
- keine Statutory-Fund-Assets, Hedges, Konzentrationen, Operational Risk oder
  Combined Stress;
- symmetrische Sofortsteuer statt Loss Carry/Deferred Tax/Recoverability;
- lange Szenarioarrays werden nicht gestreamt oder gechunked;
- keine Portfolioaggregation oder Experience-/Backtesting-Infrastruktur;
- fehlende Standardfehler für die meisten Ergebnisgrößen und Stresstdeltas;
- öffentliche Greek-API und Standard-End-to-End-Runner sind in 1.3.0 nicht
  regressionstestgedeckt und der Runner ist ohne Workaround nicht lauffähig.

## 18. Richtige Interpretation

Die Engine beantwortet belastbar die Frage:

> Wie verhalten sich die implementierten AGILE-ähnlichen Cashflows eines
> illustrativen New-Business-Modellpunkts unter den angegebenen Q-/P-,
> Mortality-, Behaviour-, Expense- und Cap-Annahmen?

Sie beantwortet ohne weitere Daten und Module nicht:

- welchen administrativen Transaction Value Allianz tatsächlich stellt;
- welche Price-, Reserve-, Hedge- oder Profitabilitätszahl für den realen
  Bestand gilt;
- wie hoch APRA/LAGIC-Prescribed Capital ist; oder
- wie ein konkreter Kunde handeln oder abschneiden wird.

Ein kleiner Identity Gap und grüne Unit Tests zeigen interne Konsistenz der
implementierten Buchungen. Sie können eine fehlende Vertragsfunktion oder
unkalibrierte Annahme nicht in ein valides Produktionsmodell verwandeln.
