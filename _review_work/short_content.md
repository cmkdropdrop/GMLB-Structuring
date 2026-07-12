# Redaktionsvorlage: Kurzfassung des reviewed AGILE-Fachpapers (ca. 20 Seiten)

## 1. Redaktionsziel

Die Kurzfassung soll das 50-seitige reviewed Fachpaper auf eine selbständig
lesbare, fachlich belastbare Management-/Fachfassung von **ca. 20 A4-Seiten**
verdichten. Sie soll die Produktmechanik, die Bewertungslogik, den
Basismodellpunkt, die wesentlichen Ergebnisse und die entscheidenden
Modellrisiken erklären. Sie soll **kein Kurzlehrbuch**, kein vollständiger
Modellbericht und keine Produkt- oder Produktionsfreigabe sein.

Empfohlener Titel:

> **AGILE Modelling – Kurzfassung**  
> Produktmechanik, Bewertungsergebnisse und Model Risk der Research Engine
> 1.3.0

Empfohlener Umfang und Satz:

- 20 Seiten einschließlich Titel, kompakter Inhaltsübersicht und
  Literaturverzeichnis;
- etwa 6.000–6.800 Wörter Haupttext;
- A4, 10,5–11 pt, 1,05–1,10 Zeilenabstand, ca. 20 mm Seitenränder;
- höchstens fünf Abbildungen und acht Tabellen;
- Literaturverzeichnis auf höchstens zwei Seiten, nur tatsächlich zitierte
  Kernquellen;
- alle Ergebniswerte im Fließtext sinnvoll runden; technische
  Reconciliation-Werte nur in der zugehörigen Tabelle mit zwei Dezimalstellen.

Der Dokumentstatus muss auf der Titelseite oder unmittelbar danach sichtbar
bleiben:

> Diese Kurzfassung beschreibt einen unabhängig geprüften Research-Prototyp.
> Sie ist weder Produktberatung noch eine Preis-, Reserve-, Bilanz-, Hedge-
> oder Kapitalfreigabe. Sämtliche Ergebniszahlen gelten nur für den
> dokumentierten illustrativen New-Business-Modellpunkt und ausdrücklich
> bezeichnete Varianten. Sie erlauben keine Aussage über das reale
> AGILE-Portfolio.

## 2. Empfohlene 20-Seiten-Struktur

| Seiten | Abschnitt | Inhalt und Redaktionsziel | Elemente |
|---:|---|---|---|
| 1 | Titel und Status | Titel, Datum 11. Juli 2026, Engine 1.3.0, Dokumentstatus, kompakte Inhaltsübersicht | keine Tabelle/Grafik |
| 2 | Executive Summary | Produkt in drei Sätzen; Modellpunkt; fünf Kern-KPIs; Gesamturteil; drei größte Risiken | hervorgehobener Urteilskasten |
| 3 | Scope und Evidenz | Vier Ebenen Produktfakt/Annahme/Ergebnis/Interpretation; 93 geprüfte Claims; Einsatzgrenzen | kurzer Methodenkasten, keine Detailinventur |
| 4–5 | Produktmechanik | Indexed Growth, Protection/Caps, Income Rate, Fixed/Rising, Fees, Withdrawals/DVA/MVA, Spouse/Age Pension+ nur auf Kernebene | Tabelle 1; Payoff- und Income-Formeln |
| 6 | Engine und State Machine | Growth → Income → Out; materielles Event Ordering; monatliche Projektion; Q- und P-Auswertung | kompakte Prozessdarstellung im Text |
| 7 | Markt, Mortalität, Verhalten | BS-Basismodell; Heston/HW/COS nur als Varianten; synthetische Mortalität; heuristisches Verhalten; LSMC-Grenzen | Heston–HW-Risikokasten |
| 8 | Bewertungs- und Kennzahlenlogik | Q-PV, BEL/Gross VNB, Guarantee Value, Marktwertidentität, SCR/RM/PVFP; häufige Fehlinterpretationen direkt an den Formeln | zentrale Formeln, keine Tabelle |
| 9 | Modellpunkt und Annahmen | Vertrag, Markt, Verhalten/Kosten und blockweise Pfadzahlen in einer Tabelle | Tabelle 2 |
| 10–11 | Basisbewertung und Reconciliation | Executive KPIs; Wertüberleitung; Garantie- versus Gesamtproduktwert; MC-Präzision | Tabellen 3–4; Abbildung 1 |
| 12 | Kapital und Profit-Runoff | bindende Stressmodule; Research-Proxy; spätes Payback versus negativer PVFP | Tabelle 5; Abbildung 2 |
| 13 | Einfaktor-Sensitivitäten | nur ökonomisch materielle Szenarien; Kapital/RM in diesem Block aus; keine universellen Vorzeichenaussagen | Tabelle 6; Abbildung 3 |
| 14 | Kunden-Outcomes | Investment-Value-Erschöpfung und Garantie-Tail; In-force-Gewichte von Rohquantilen trennen | Abbildung 4; vier Kernzahlen im Text |
| 15 | Design und Income-Timing | Fixed/Rising, Spouse, Age Pension+ sowie früher/später Income Start; Kunden- und Versicherersicht trennen | Tabelle 7 |
| 16 | Modell-, Seed- und Versionsrisiko | 600-Pfad-Modellspanne, Seed-Studie, Versionswechsel und Carry-Attribution | Abbildung 5 |
| 17 | Validierung und Reproduzierbarkeit | 122 Tests; Originalrunner-Fehler; instrumentierter 9/9-Lauf; unvollständige Provenienz | Tabelle 8 |
| 18 | Gesamtinterpretation und Produktionsblocker | fünf robuste Mechanismen; sechs gebündelte Blocker; Governance; Schlussurteil | Schlusskasten |
| 19–20 | Literatur | ausschließlich die zitierte Kernauswahl | kompaktes Literaturverzeichnis |

Falls die Bibliografie weniger als zwei Seiten benötigt, soll der freie Raum
nicht mit Detailstoff gefüllt werden. Besser ist eine 18- bis 19-seitige,
lesbare Fassung als künstliches Strecken auf exakt 20 Seiten.

## 3. Zwingend zu übernehmende Aussagen

### 3.1 Gesamturteil und Scope

Die folgenden Aussagen müssen inhaltlich unverändert erhalten bleiben:

1. **Gesamturteil:** Die Engine ist ein *reviewed research prototype* und
   derzeit nicht freigabefähig für Pricing, Reservierung, APRA/LAGIC, Hedging
   oder Portfolioaussagen.
2. Die Juli-2026-Produktfakten und sämtliche im Paper berichteten
   1.2.0-/1.3.0-Ergebniszahlen wurden gegen Primärquellen beziehungsweise
   lokale CSV-/JSON-Artefakte geprüft; es wurde keine materiell falsche
   Basiszahl gefunden.
3. Produktfakt, Modellannahme, Rechenergebnis und Interpretation sind strikt zu
   trennen. Die Claim-to-Evidence-Matrix umfasst 93 materielle Claims: 31
   Produktfakten, 26 Modellannahmen, 30 Ergebnisse und 6 Interpretationen.
4. Der negative Basis-VNB beweist **nicht**, dass das reale Produkt oder
   Portfolio unprofitabel ist. Markt-, Mortalitäts-, Verhaltens-, Kosten-,
   Steuer-, Hedge- und Portfolioparameter sind illustrativ oder fehlen.
5. Der reine Monte-Carlo-Fehler misst weder Parameter-, Modell-, Vertrags-
   noch Implementierungsrisiko.

Empfohlene prägnante Schlussformulierung:

> Unter genau den dokumentierten illustrativen Annahmen ist der modellierte
> Einzelpolicenwert vor und nach Risk Margin negativ. Die Cashflow- und
> State-Machine-Architektur ist als Research-Grundlage substanziell, doch
> fehlende Produktionskalibrierung, Vertrags-/Admin-Reconciliation,
> In-force-Fähigkeit, APRA-Architektur und ein bestätigter End-to-End-Fehler
> verhindern jede Produktionsfreigabe.

### 3.2 Produktmechanik

Zwingend zu erhalten sind:

- AGILE ist **indexed, nicht unit-linked**. FIA/GLWB ist nur eine funktionale,
  US-geprägte Modellanalogie und weder rechtliche noch APRA-Klassifikation.
- Issuer ist Allianz Australia Life Insurance Limited. Der Investor ist
  specified beneficiary unter der Group-Policy-Struktur; die Investments
  liegen in Statutory Fund No. 2. Allianz SE garantiert die Leistungen nicht.
  Die ausführlichen Group-Policy-/Cessation-Details können entfallen, die
  Konzernabgrenzung nicht.
- Growth Phase und Lifetime Income Phase sind zu unterscheiden. Das Einkommen
  kann nach Erschöpfung des Investment Value lebenslang weiterlaufen; erst die
  nicht mehr durch IV finanzierte Zahlung erzeugt den Guarantee Claim.
- Juli-2026-Maximum-Returns für Commencement **oder Anniversary Dates**:
  Australian Equity 6,20 % Total / 13,00 % Partial; Global Equity 6,00 % Total
  / 12,80 % Partial.
- Guaranteed Minimums 0,25 % Total und 0,50 % Partial sind Untergrenzen des
  künftig festgesetzten **Maximum Return**, keine garantierten
  Mindestjahresrenditen.
- Das PDS erlaubt bei Total Protection alternativ einen garantierten
  einjährigen Fixed Return. Dieser Zweig und dessen pro-rata-DVA-Regel fehlen
  in der Engine.
- Fixed Income bleibt nominal konstant, vorbehaltlich reduzierender Excess
  Withdrawals. Rising Income startet niedriger und ratchetiert nur mit einem
  positiven Australian-Equity-Total-Protection-Credit; es ist keine
  CPI-Indexierung.
- Product Fee 0,30 % p. a. und LIP 1,15 % p. a.; die Engine hält beide Sätze
  konstant und approximiert tägliche Vertragsaccruals monatlich.
- DVA ist laut PDS ein Derivatewert mit pro-rata Mindestregeln, nicht bloß die
  realisierte Year-to-date-Indexrendite. Die Engine verwendet einen
  unbestätigten Hedgewertproxy ohne Protection Floor und Fixed-Return-Zweig.
  Die MVA ist ebenfalls ein unkalibrierter Zins-/Loading-Proxy, keine
  veröffentlichte Allianz-Produktionsformel.
- Spouse- und Age-Pension+-Mechanik dürfen nicht als frei austauschbare
  Modelllabels dargestellt werden. Election, Eligibility, Death/Lump-Sum-
  Rechte, CAS und Kapitalzugriff sind vertraglich bedingt. Für die Kurzfassung
  genügt ein Absatz; Detailgrenzen und Formeln können in die Langfassung
  verwiesen werden.
- Zwei Produktpunkte bleiben offen: Equal-age-Spouse-Tie-Regel beziehungsweise
  fractional-age-Interpolation sowie die konkrete APRA-Klassifikation von
  AGILE.

### 3.3 Modell und Numerik

Zwingend zu erhalten sind:

- Monatliche Zustandsprojektion `Growth → Income → Out`; `Out` ist
  absorbierend. Mortalität und Storno werden als Wahrscheinlichkeitsgewichte,
  nicht als binäre Life-by-Life-Ereignisse geführt.
- Materielles Event Ordering: Markt/DVA; Anniversary Credit/Rising Ratchet;
  Fees; Income Election; Tod; nachschüssiges Income; Withdrawals; Lapse.
- Q dient der marktkonsistenten Bewertung; P dient Profit-Signature und
  Kunden-Outcome-Verteilungen. P- und Q-Ergebnisse beantworten verschiedene
  Fragen.
- Basis ist Black–Scholes mit deterministischer Zinskurve. Heston,
  Hull–White und Heston–Hull–White sind Vergleichsmodelle, nicht kalibrierte
  Marktmodelle.
- Die Heston–Hull–White-COS-Komposition ist im Default **keine exakte positive
  unabhängige Gauß-Varianz**. Der Cross-Term ergibt
  `w = −2,326 × 10⁻⁴`; der Zweig ist als hybride, nicht gegen Joint Monte Carlo
  validierte Näherung zu kennzeichnen.
- Mortalität ist eine synthetische Gompertz–Makeham-Annäherung, keine
  offizielle australische oder Allianz-spezifische Pricing-/Reservebasis; kein
  stochastisches systematisches Langlebigkeitsmodell.
- Lapse, Take-up und Withdrawals sind heuristische, nicht für AGILE empirisch
  geschätzte Regeln. Off-anniversary Income Election verwendet bis zum
  nächsten Anniversary einen IV- statt Surrender-Value-Nenner.
- Das separate jährliche LSMC ist nicht in Standardpricing/Kapital/PVFP
  integriert. Sein berichteter MC-Schätzer ist wegen Sampling,
  Regression und samplebasiertem `max(optimal, static)` kein strikter
  numerischer Lower Bound. Tailhorizont und Joint-Life-Conditioning sind nicht
  like-for-like mit dem Monatsmotor.

### 3.4 Kennzahlen und Interpretation

Zwingend zu erhalten sind:

- `Guarantee Value = Claims − LIP`; er ist weder Gesamtproduktverlust noch
  Gesamtprodukt-Break-even.
- `Gross VNB = Fees + Margins − Claims − Expenses`; er liegt vor Risk Margin.
- `VNB nach RM = Gross VNB − RM` und verwendet hier nur einen
  Solvency-II-artigen Research-Proxy.
- `PVFP` ist der unter P-Annahmen diskontierte Distributable-Earnings-Runoff
  und nicht identisch mit dem risikoneutralen VNB.
- Die Identity Gap ist eine interne Cashflow-/Finanzierungsreconciliation.
  Sie beweist weder Vertragsrichtigkeit noch Kalibrierung oder Adminformeln.
- Der BSCR-Wert ist ausschließlich ein **Research-Proxy**. Er ist weder APRA
  Prescribed Capital Amount noch Fund-Kapitalquote, Hedge-Budget oder Reserve.
- Die Steuerlogik unterstellt sofort symmetrische 30-%-Steuerwirkung auch auf
  Verluste; Verlustvorträge, Deferred Tax und Recoverability fehlen.

## 4. Zwingend zu übernehmende Formeln

Die Kurzfassung sollte höchstens sieben kompakte Formelblöcke enthalten. Diese
sieben decken die notwendige Produkt- und Bewertungslogik ab.

### Formelblock 1 – Annual Return

\[
R=\frac{S_T}{S_0}-1,\qquad
c_{TP}(R)=\min\{\max(R,0),C\},
\]

\[
c_{PP10}(R)=
\begin{cases}
\min(R,C),&R\ge 0,\\
\min(0,R+0{,}10),&R<0.
\end{cases}
\]

Direkt darunter: nur marktgebundener Zweig; möglicher Fixed Return ist nicht
implementiert.

### Formelblock 2 – Statische Optionsreplikation

\[
V_{TP}=Call(1)-Call(1+C),\qquad
V_{PP10}=Call(1)-Call(1+C)-Put(0{,}90).
\]

Die wirtschaftliche Aussage genügt: Total Protection ist ein Bull Call
Spread; Partial Protection finanziert den höheren Cap teilweise durch den
verkauften Put.

### Formelblock 3 – Lifetime Income Rate

\[
I_0=IV_{\tau}^{post\ fee}\,g,\qquad
g=g_{base}(x_0,Gender,Optionen)+n_{Growth}\,e.
\]

Für den Basismodellpunkt zwingend ergänzen:

\[
g=7{,}05\%+5\times0{,}35\%=8{,}80\%.
\]

### Formelblock 4 – Q-Barwert und Q/P-Trennung

\[
PV_Q(CF)=\mathbb E^Q\!\left[\sum_t D_tCF_t\right],\qquad
D_t=\exp\!\left(-\int_0^t r_s\,ds\right).
\]

### Formelblock 5 – BEL, Gross VNB und Guarantee Value

\[
\begin{aligned}
BEL_{NU}={}&PV_Q(Claims)+PV_Q(Expenses)\\
&-PV_Q(Product\ Fees+LIP+Crediting\ Margin+MVA/AP+),\\
VNB_{gross}={}&-BEL_{NU},\\
GV={}&PV_Q(Guarantee\ Claims)-PV_Q(LIP).
\end{aligned}
\]

`AP+` ist nur eine platzsparende Kurznotation in dieser Formel und im Text als
Age Pension+ auszuschreiben.

### Formelblock 6 – Marktwertidentität

\[
\begin{aligned}
P_0={}&PV_Q(Income+Death+Surrender+Withdrawals)\\
&-PV_Q(Guarantee\ Claims)\\
&+PV_Q(Fees+Crediting\ Margin+MVA+Age\ Pension+).
\end{aligned}
\]

Unmittelbar danach muss die Einschränkung stehen: interne Reconciliation,
kein Produkt-/Kalibrierungsnachweis.

### Formelblock 7 – Kapital, Risk Margin und PVFP

\[
SCR_i=\max(0,NAV_{base}-NAV_i^{stress}),\qquad
SCR=\sqrt{\mathbf s^\top\mathbf C\mathbf s},
\]

\[
RM=0{,}06\sum_t SCR_{life}(t)P(0,t+1),\qquad
PVFP(h)=\sum_y\frac{DE_y}{(1+h)^y}.
\]

Die Heston–Hull–White-Fehlqualifikation sollte zusätzlich als einzelne
Risikogleichung, nicht als Methodenherleitung, erscheinen:

\[
w=Var\!\left(\int r\,dt\right)
+2Cov\!\left(\int r\,dt,\int\sqrt v\,dW^S\right)
=-2{,}326\times10^{-4}.
\]

Nicht übernehmen: vollständige Heston-/Hull–White-SDE-Herleitungen,
COS-Reihenformel, Mortalitätsintegrale, dynamische Lapse-/Withdrawal-Formeln,
MVA-Proxyformel, MWV-Formel und LSMC-Bellman-Rekursion. Ihre Aussagen werden
in Prosa zusammengefasst.

## 5. Zwingend zu übernehmende Zahlen

### 5.1 Basismodellpunkt

Die Basisannahmen sind in Tabelle 2 zusammenzufassen:

- Commencement Mitte 2026; Mann, Alter 65; Non-superannuation;
- AUD 100.000 Initial Investment;
- 100 % Australian Equity Total Protection;
- Maximum Return 6,20 %; Guaranteed Minimum des künftigen Maximum Return
  0,25 %;
- Fixed Income nach fünf Jahren, Alter 70; Rate 8,80 %;
- kein Spouse, kein Age Pension+, keine geplanten Withdrawals;
- Black–Scholes, deterministische Zinskurve, 4.000 Basispfade, Seed 2026;
- Zero Curve 1/2/5/10/20/30 Jahre:
  3,80/3,90/4,10/4,30/4,40/4,40 %;
- AUS-/Global-Volatilität 16/15 %, P-ERP 4,50 %, Return-Index-Carry 0 %;
- Product Fee/LIP 0,30/1,15 % p. a.; Acquisition Expense 2,00 %;
  Maintenance AUD 80 p. a. plus 5 bp IV; Expense Inflation 2,50 %;
- Income-Lapse 0,50 % p. a.; Hurdle 8 %; Tax 30 % sofort symmetrisch.

Pfadzahlen als Fußnote zur Tabelle, nicht als eigene Tabelle:
Basis 4.000; Sensitivitäten 1.200; Designs/Timing 1.500; Behaviour 600;
Outcomes 2.500; Modelle 600 je Modell; Seeds 800 je Seed bei fünf Seeds.

### 5.2 Executive KPIs

Tabelle 3 muss mindestens folgende Werte enthalten:

| Kennzahl | Darstellungswert | Technischer Prüfwert/Notiz |
|---|---:|---|
| Gross VNB | **−AUD 1.228** | −1.227,6468 |
| Gross NBM | −1,228 % | vor Risk Margin |
| pfadweiser SE / 95-%-Halbintervall | AUD 42 / ±AUD 83 | 42,2495 / 82,8090; nur Sampling |
| Non-unit BEL | +AUD 1.228 | +1.227,6468; Gegenzeichen zu Gross VNB |
| Guarantee Value | +AUD 10.080 | 10.079,7392 = Claims − LIP |
| Fair LIP / belastete LIP | 3,00 % / 1,15 % | exakt 3,0041561 %; Lücke 185 bp |
| BSCR-Proxy | AUD 17.205 | 17.205,2994; nicht APRA/LAGIC |
| Risk-Margin-Proxy | AUD 4.687 | 4.687,2625 |
| VNB nach RM | **−AUD 5.915** | −5.914,9093 |
| PVFP bei 8 % | **−AUD 12.899** | −12.898,9599 |
| IRR / Payback | 3,52 % / Jahr 23 | IRR 3,5191988 % |
| Q-Identity Gap | −0,169 % | −0,1689226 %; PASS |

Im Haupttext keine zusätzlichen Nachkommastellen verwenden.

### 5.3 Reconciliation

Tabelle 4 muss die sechs Wertkomponenten enthalten:

- Product Fees +AUD 2.269,84;
- Lifetime Income Premium +AUD 8.701,07;
- Crediting Margin +AUD 9.923,45;
- MVA Retained +AUD 217,37;
- Guarantee Claims −AUD 18.780,81;
- Expenses −AUD 3.558,57;
- Summe Gross VNB −AUD 1.227,65.

Im Text ergänzen:

- LIP deckt 46,3 % des Claimbarwerts;
- Customer Benefit PV = AUD 97.500,16
  (Income 69.417,96; Death 12.537,80; Surrender 15.544,39);
- finanziertes Q-PV = AUD 99.831,08; Residual −AUD 168,92;
- der Gap liegt sowohl unter 1,96×SE als auch unter der tatsächlich verwendeten
  weiteren PASS-Schwelle `max(0,25 %, 3SE)`.

### 5.4 Kapital und Runoff

Tabelle 5 beziehungsweise der Begleittext muss enthalten:

- Interest Down AUD 15.812,66, bindender und dominanter Standalone-Stress;
- Longevity AUD 3.489,70; Lapse Down AUD 818,45; Expenses AUD 313,88;
- Life SCR rund AUD 3.896; aggregierter BSCR AUD 17.205;
- Nullwerte bei Equity/Volatility/Mortality bedeuten wegen des Loss-Floors
  nicht, dass diese Risiken nicht existieren;
- Time-0-Strain −AUD 21.346;
- Maximum BEL inklusive RM rund AUD 47.669 in Jahr 17;
- Maximum Required Capital rund AUD 30.454 in Jahr 17;
- nominaler Payback Jahr 23 und terminal +AUD 27.526, zugleich PVFP bei 8 %
  −AUD 12.899.

### 5.5 Sensitivitäten

Tabelle 6 ist auf die folgenden sechs bis acht Zeilen zu begrenzen. Alle Werte
stammen aus dem 1.200-Pfad-Block **ohne Kapital und Risk Margin**:

| Szenario | Δ Gross VNB | Kernaussage |
|---|---:|---|
| Zinsen −100 bp | **−AUD 11.483** | größter negativer Einfaktorstress |
| Zinsen +100 bp | +AUD 9.773 | Nichtlinearität sichtbar |
| Income Start +2 Jahre | +AUD 3.261 | hilft Versicherer im Modell; keine Kundenempfehlung |
| Income Start −2 Jahre | −AUD 2.805 | längere Garantiedauer belastet |
| Maximum Returns −100 bp | +AUD 2.232 | weniger Kundenupside, höhere Finanzierungsmarge |
| Longevity, qₓ −10 % | −AUD 1.629 | längere Income Claims |
| Lapse −50 % | −AUD 818 | Vorzeichen ist modellpunktabhängig |
| Maintenance Expenses +10 % | −AUD 156 | nur Maintenance, nicht Acquisition/Commission |

Der Base-PVFP dieses Blocks (−AUD 66) darf nicht mit dem kapitalbelasteten
Basis-PVFP (−AUD 12.899) verglichen werden. Für Differenzen fehlen gepaarte
Standardfehler.

### 5.6 Kunden-Outcomes

Kein zusätzliches Outcome-Tabellenblatt. Abbildung 4 und folgende vier
Textpunkte genügen:

- Outcome-Pfade: 2.500 P-Pfade, effektiver Seed **2027**, obwohl das
  Settings-Objekt 2026 serialisiert;
- medianes Fixed Income ab Alter 70: AUD 9.812 nominal p. a.;
- IV-Erschöpfung: 47,56 % bei Alter 83, 85,36 % bei Alter 84 und 100 % bei
  Alter 86 auf dem ausgegebenen Jahresraster;
- die 50-%-Schwelle wird erstmals bei Alter 84 überschritten; Rohquantile sind
  keine Kundenprognose und getrennt vom In-force-Gewicht zu lesen.

### 5.7 Design und Income-Timing

Tabelle 7 sollte zwei kurze Panels enthalten.

Panel A – sechs bedingte Designs, mindestens Rate und Gross VNB:

- Single Fixed 8,80 %, Gross VNB −AUD 1.335;
- Single Rising 5,65 %, +AUD 6.445;
- Spouse Fixed 7,70 %, −AUD 5.149;
- Spouse Rising 4,55 %, +AUD 6.537;
- Age Pension+ Fixed 8,85 %, −AUD 2.252;
- Age Pension+ Rising 5,70 %, +AUD 7.207.

Die Spouse-Zeilen setzen zusätzlich eine Frau Alter 63 und
`continue_income`; Age Pension+ nutzt Single Male 65 und eine illustrative
CAS-Lebenserwartung von 20 Jahren. Designs sind bedingte Vertragsausprägungen,
kein gemeinsam bewertetes späteres Wahlrecht.

Panel B – drei Timing-Punkte, mindestens Gross VNB/Kundenleistungs-PV:

- Start nach 1 Jahr: −AUD 6.150 / AUD 102.337;
- Start nach 5 Jahren: −AUD 1.335 / AUD 97.548;
- Start nach 15 Jahren: +AUD 15.066 / AUD 80.996.

Interpretation: späterer Start erhöht in diesem Modell den Versichererwert,
senkt aber den Kundenleistungsbarwert; Utility, persönliche Steuer, Liquidität,
Überlebenspräferenzen und spätere Wahloptionalität fehlen.

### 5.8 Modell-, Seed- und Versionsrisiko

Zwingend in Seite 16:

- 600 Pfade je Modell: BS −AUD 1.275; Heston −AUD 3.788; BS–HW −AUD 1.943;
  Heston–HW −AUD 4.402;
- unbereinigte Gross-VNB-Spannweite AUD 3.127; Verhältnis zum Basis-
  95-%-Halbintervall rund 38, aber **kein reiner Model-Risk-Schätzer**, weil
  modellweise SEs fehlen;
- fünf Seeds mit je 800 BS-Pfaden: Mittel −AUD 1.209; Sample-SD AUD 96,64;
  mittlerer pfadweiser SE AUD 96,63; Range −AUD 1.292 bis −AUD 1.049;
- Versionswechsel 1.2.0 → 1.3.0: Gross VNB +AUD 1.743 → −AUD 1.228,
  Veränderung −AUD 2.970;
- kontrollierter Carry-Gegenlauf +AUD 1.879,32; isolierte Carry-Attribution
  −AUD 3.106,96, jedoch ohne separates publiziertes Manifest/CSV;
- der Versionsvergleich bündelt Code, Annahmen und Definitionen und ist daher
  Versionsattribution, nicht reines Implementation Risk.

### 5.9 Validierung und Reproduzierbarkeit

Tabelle 8 soll die folgenden Nachweise und Grenzen enthalten:

| Befund | Evidenz | Konsequenz |
|---|---|---|
| Testsuite | 122 Tests bestanden, Exit 0, 140,13 s | substanziell, aber nicht end-to-end |
| Originalrunner | Exit 1 nach 18,5 s in Block 1/9; `FrozenInstanceError` in `greeks()` | Standardlauf nicht lauffähig |
| Instrumentierter Lauf | `dataclasses.replace` nur prozesslokal; 9/9 Blöcke in 113,5 s | Zahlen reproduziert, kein Sourcefix |
| Outputvergleich | 14 CSVs zellgenau; Modellvergleich nur Laufzeiten abweichend; 10 PNGs byteidentisch | starke numerische Reproduktion |
| Manifest | Hash umfasst nur `agile_engine/*.py`; Runner, Patch, CLI, Inputs/Outputs fehlen | Provenienz unvollständig |
| Heston–HW | negatives `w`; kein Joint-MC-Benchmark | nur hybride Näherung |
| APRA | Fund/Assets/Hedges/Concentration/Operational/Combined Stress fehlen | BSCR ist nur Research-Proxy |

Die drei technischen Kernbotschaften müssen im Fließtext wiederholt werden:

1. Grüne Unit Tests ersetzen keinen öffentlichen API- und End-to-End-Test.
2. Der instrumentierte Lauf reproduziert die Ergebnisse, attestiert aber nicht
   den unveränderten Runner.
3. Ein Source Hash ohne Runner, Runtime-Patch, Inputs und Outputs ist keine
   vollständige Run-Provenienz.

## 6. Abbildungsauswahl – maximal fünf

Empfohlen werden genau diese fünf vorhandenen Abbildungen; sie decken die
zentralen Beziehungen ab und vermeiden die redundante Executive-Dashboard-
Grafik:

1. **Pricing- und Margin-Waterfall**  
   Quelle: `02_pricing_margin_waterfall.png`  
   Neuer Kurztitel: „Überleitung zum Gross VNB im 1.3.0-Basislauf“.
2. **Profit-, BEL- und Kapital-Runoff**  
   Quelle: `03_profit_capital_runoff.png`  
   Kurztitel: „Früher Strain, spätes Kapitalmaximum und Payback“.
3. **Sensitivitäts-Tornado**  
   Quelle: `04_sensitivity_tornado.png`  
   Caption muss „1.200 Pfade; ohne Kapital und Risk Margin“ enthalten.
4. **Customer Outcomes / Account Depletion**  
   Quelle: `05_customer_outcomes.png`  
   Caption muss „P-Maß, nominal, effektiver Seed 2027, keine
   Kundenprognose“ enthalten.
5. **Modellvergleich und Seed-Stabilität**  
   Quelle: `09_model_mc_stability.png`  
   Caption muss „600 Pfade je Modell; unbereinigte Spannweite; keine
   modellweisen SEs“ enthalten.

Alle fünf Quellen liegen unter:

`AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/`

Nicht übernehmen:

- `01_executive_dashboard.png`, weil Tabelle 3 dieselben KPIs lesbarer enthält;
- `06_product_design_tradeoffs.png`, weil Tabelle 7 die Modellpunkt-
  Qualifikationen klarer ausweisen kann;
- `07_income_start_tradeoff.png`, ebenfalls in Tabelle 7 verdichtet;
- `08_behaviour_liquidity_surfaces.png`, weil die Flächen ohne empirische
  AGILE-Kalibrierung in einer Kurzfassung übergewichtet würden;
- `10_market_risk_greeks.png`, weil die Greek API fehlerhaft ist und die
  Vor-Kosten-Einheiten nicht direkt mit VNB/Sensitivitäten vergleichbar sind.

Für die Kurzfassung sollten die Quell-PNGs möglichst nicht weiter verkleinert
werden; die Beschriftungen sind bereits relativ klein. Jede Abbildung
seitenbreit oder mindestens 85 % Textbreite setzen.

## 7. Tabellenplan – maximal acht

1. **Verifizierte Produktmechanik und Juli-2026-Raten**: vier Caps,
   Guaranteed Minimums, Fees, Basiseinkommensrate und je eine Zeile für
   Fixed-Return-/DVA-/MVA-Grenze.
2. **Basismodellpunkt und wesentliche Annahmen**: Vertrags-, Markt-, Mortalitäts-,
   Verhalten-, Kosten- und Pfadannahmen in einer 4-spaltigen Kompakttabelle.
3. **Executive KPIs**: Werte aus Abschnitt 5.2 dieser Vorlage.
4. **Gross-VNB-Reconciliation**: sechs Komponenten plus Summe; Customer Benefit
   PV als Fußnote, nicht als zweite Tabelle.
5. **Kapitalproxy**: vier positive Standalone-Stresses plus Life SCR/BSCR/RM;
   Nullmodule in einer Sammelzeile.
6. **Ausgewählte Einfaktor-Sensitivitäten**: höchstens acht Zeilen gemäß
   Abschnitt 5.5.
7. **Design und Timing**: zwei Panels in einer Tabelle gemäß Abschnitt 5.7.
8. **Validierung, Fehler und Konsequenz**: Tabelle gemäß Abschnitt 5.9.

Keine eigenständigen Tabellen für Quellenhierarchie, Engine-Module, Pfadzahlen,
Kundenleistungsbestandteile, vollständige Outcomes, Behavior Surface, Greeks,
Versionsvergleich, Notation, Artefaktinventar oder Kennzahlenmapping.

## 8. Konkrete Kürzungsvorschläge nach Originalkapitel

### Zusammenfassung und Kapitel 1–2

- Zusammenfassung von ca. 75 auf 35–45 Zeilen reduzieren.
- Forschungsfragen 1.2 vollständig streichen; Ziel und Scope in Seite 3
  integrieren.
- Quellenhierarchie-Tabelle streichen. In einem Absatz nennen: PDS/Rate Sheets,
  Primärliteratur/APRA, Code/Tests, Outputs.
- Hashes, Generierungszeit und Softwareversionen aus Kapitel 2 streichen;
  nur Engine 1.3.0, Basispfade/Seed und die Provenienzlücke in Kapitel 17
  erhalten.
- Die vier wissenschaftlichen Vorsichtsregeln auf zwei Sätze verdichten.

### Kapitel 3 Produktökonomik

- Rechtliche Struktur auf zwei Absätze kürzen; Investor/Life
  Insured/Beneficiary-Detailpfade nur soweit nötig für Spouse/Age Pension+.
- Terminologie-Tabelle GMWB/GLWB/GMLWB/FIA/VA streichen; eine einzige
  Abgrenzungsformulierung verwenden.
- Caps, Minimums, Fees und Basiseinkommensrate in Tabelle 1 zusammenführen.
- Payoff-Beispieltabelle streichen; nur das Beispiel `R = −18 % → TP 0 %,
  PP10 −8 %` im Text behalten, falls Platz vorhanden.
- DVA/MVA jeweils auf Definition, Engine-Proxy und fehlende Kalibrierung
  begrenzen; MVA-Formel streichen.
- Withdrawal-Limits (AUD 100, 95 %, AUD 2.000) und detaillierte Age-Pension+-CAS-
  Mathematik aus der Kurzfassung entfernen. Nur auf eingeschränkten
  Kapitalzugriff, Death Cap und bedingte Eligibility hinweisen.
- Automatischen spätesten Income Start und Default Fixed ohne Spouse in einer
  Fußnote oder einem Satz erhalten, weil dies eine korrigierte Produktregel
  ist; die Kontakt-/Bankdaten-Full-Withdrawal-Regel kann in die Langfassung
  verwiesen werden.

### Kapitel 4–6 Architektur, Markt, Mortalität und Verhalten

- Modultabelle vollständig streichen; Architektur in fünf Sätzen erklären.
- Zustandsvariablenliste auf IV, Locked Income, Phase/In-force, Cap/CAS und
  Marktstate reduzieren.
- Event Ordering vollständig, aber als eine nummerierte Einzeilerliste
  erhalten.
- Black–Scholes-, Heston- und Hull–White-SDEs streichen; nur Modellrolle,
  Defaultvolatilität und fehlende Kalibrierung beschreiben.
- COS-Methodenformel und 35-bp-Historie streichen; den negativen
  Heston–HW-Cross-Term und seine Konsequenz erhalten.
- Gompertz–Makeham- und Joint-Life-Formeln streichen; synthetische Basis,
  1,25-%-Improvement und fehlendes systematisches Langlebigkeitsrisiko in
  einem Absatz nennen.
- Dynamic-Lapse-/Withdrawal-Formeln streichen; heuristische Moneyness,
  Off-anniversary-Abweichung und nicht empirische Kalibrierung behalten.
- LSMC-Kapitel auf höchstens einen halben Textblock reduzieren: Zweck,
  jährliches Gitter, fehlende Integration, kein strikter numerischer Lower
  Bound, abweichender Tail/Joint-Life-Scope.

### Kapitel 7–9 Bewertung, Kapital und LSMC

- Cashflowliste direkt vor Formelblock 5 in einen Satz integrieren.
- `bel_total=P0+BEL_NU` streichen; nur warnen, dass die Enginegrößen keine
  APRA/AASB/IFRS Policy Liabilities sind.
- Fair-LIP-Nullstellenalgorithmus und Utility-Margin-Formel streichen.
- Crediting-Margin-Detaildiskussion auf „modelliertes Cap-Budget, kein
  beobachteter Hedgeprofit“ kürzen.
- APRA-Standardarchitektur auf einen Absatz reduzieren; LPS 110/114/115/117/118
  zitieren, keine Einzelstandard-Nacherzählung.
- LSMC nicht doppelt behandeln: vollständig in Seite 7 integrieren, Kapitel 9
  als eigenes Kapitel auflösen.

### Kapitel 10–11 Modellpunkt und Ergebnisse

- Vier Annahmentabellen zu Tabelle 2 fusionieren; Pfadzahlen in Fußnote.
- Executive Dashboard streichen; KPI-Tabelle behalten.
- Kundenleistungs-PV-Tabelle in einen Satz unter der Reconciliation überführen.
- Capital-Tabelle auf positive/bindende Module reduzieren; Nullmodule sammeln.
- Vollständige 16-zeilige Sensitivitätstabelle auf acht Zeilen kürzen.
- Outcome-Tabelle streichen; nur die Altersmarken 83/84/86 und das mediane
  Income nennen.
- Design- und Timing-Tabellen zu Tabelle 7 zusammenführen; Behavior-
  Surface-Tabelle/Grafik streichen.
- Greeks einschließlich Delta/Vega/Rho-Werten und Figure 10 vollständig
  streichen. Der API-Fehler gehört in die Validierungsseite, nicht in einen
  Ergebnisblock.
- Versionsvergleichstabelle streichen; nur Gross-VNB-Wechsel, Carry-
  Attribution und methodischen Risk-Margin-Hinweis im Text behalten.

### Kapitel 12–15 und Anhänge

- Testabdeckungsliste auf drei Beispiele reduzieren: Payoff, Identität,
  Timing/Spouse. Toleranzhinweis und fehlender End-to-End-Test bleiben.
- Auditkorrekturen nicht einzeln wiederholen; in vier Themen bündeln:
  Produktvintage, Event Ordering/Conditioning, Markt-/Carrylogik,
  Kapital/PVFP/Provenienz.
- Stacktrace und Python-Workaround-Code streichen; Fehlerursache,
  `dataclasses.replace` und Reproduktionsergebnis in Tabelle 8 reichen.
- Validitätsrisiken und zwölf Production-Blocker zu sechs Themen bündeln:
  (1) Vertrag/Admin/In-force, (2) Kalibrierung/Daten, (3) DVA/MVA/Hedges,
  (4) Verhalten/LSMC/Longevity, (5) APRA/Portfolio/Tax, (6) Code,
  Skalierung und Provenienz.
- Kapitel 13.1 mit den fünf robusten Mechanismen nahezu vollständig erhalten;
  Kapitel 13.2–13.5 auf ca. eine Seite verdichten.
- Lernpfad, Rechenübungen und Verständnisfragen vollständig streichen.
- Anhänge A–D vollständig streichen. Auf vollständiges Paper, Review Report
  und Claim-to-Evidence-Matrix verweisen.
- Literatur-Metadatenfehler (`deng2017`, A19, B3) nicht im Kurzpaper
  wiederholen; sie sind im Review Report dokumentiert und für die Kernbotschaft
  nicht erforderlich.

## 9. Empfohlene Kernliteratur

Das Kurzpaper sollte höchstens etwa 20 Quellen zitieren. Priorität:

1. offizielles AGILE PDS vom 19. Januar 2026;
2. Juli-2026 Lifetime Income Rates;
3. Juli-2026 Maximum Returns;
4. Guaranteed Minimums;
5. APRA LPS 110, 114, 115, 117 und 118;
6. Bauer et al. 2008 für den GMxB-Rahmen;
7. Black/Scholes 1973 und Heston 1993;
8. Hull/White 1990 und Fang/Oosterlee 2008;
9. Kling et al. 2014 für Verhalten;
10. Longstaff/Schwartz 2001 für LSMC;
11. lokale Engine-, Audit- und Ergebnispack-Quellen
    (`agileengine2026`, `agileaudit2026`, `agilerun2026`).

Nur Quellen behalten, die im Kurztext tatsächlich eine Aussage tragen. Keine
Literaturübersicht und keine fremden Fair-Fee-Zahlen aufnehmen.

## 10. Redaktionelle Abnahmekriterien

Vor der finalen DOCX-/PDF-Erzeugung prüfen:

- Umfang 18–22 Seiten; Ziel 20;
- höchstens fünf Abbildungen und acht Tabellen;
- alle Abbildungen mit Pfadzahl/Measure/Scope in der Caption;
- Basismodellpunkt vor der ersten Ergebniszahl vollständig definiert;
- `instrumentierter 1.3.0-Lauf` durchgehend, nie „unveränderter Standardlauf“;
- Outcome-Seed 2027, Basis-Seed 2026;
- `Maximum Return` nie mit Annual-Return-Floor verwechseln;
- Fair LIP nie als Gesamtprodukt-Break-even darstellen;
- Guarantee Value nie als Gross VNB darstellen;
- BSCR immer als Research-Proxy und nicht APRA/LAGIC kennzeichnen;
- Sensitivitäten ausdrücklich ohne Kapital/Risk Margin und mit 1.200 Pfaden;
- Modellvergleich ausdrücklich 600 Pfade je Modell und ohne modellweise SEs;
- Identity Gap nur als interne Reconciliation;
- keine Greek-Werte oder Figure 10;
- Literatur- und Querverweise nach Kürzung ohne verwaiste Referenzen;
- alle Originaldateien und die Engine unverändert lassen.

