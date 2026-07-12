---
title: "AGILE Modelling — Kurzfassung"
subtitle: "Produktmechanik, Bewertung, Ergebnisse und Model Risk — Reviewed Research Prototype 1.3.0"
author: "Interne Fach- und Lernunterlage"
date: "11. Juli 2026"
lang: de-DE
bibliography: AGILE_Modelling_references_reviewed.bib
link-citations: true
reference-section-title: Literaturverzeichnis
toc-title: Inhaltsverzeichnis
---

> **Dokumentstatus.** Diese Kurzfassung verdichtet die unabhängig geprüfte
> Langfassung auf die entscheidungsrelevanten Produktmechaniken,
> Modellannahmen, Ergebniszahlen und Validierungsbefunde. Sie ist weder
> Produktberatung noch eine Pricing-, Reserve-, Bilanz-, Kapital- oder
> Produktfreigabe und nicht für Hedging- oder Portfolioaussagen bestimmt. Alle
> Zahlen sind illustrative Resultate eines einzelnen
> New-Business-Modellpunkts der lokalen AGILE Modelling Research Engine 1.3.0.
> Produktfakt, Modellannahme, Ergebnis und Interpretation bleiben strikt
> getrennt.

# Executive Summary

Allianz Guaranteed Income for Life (AGILE) verbindet eine indexgebundene
Ansparphase mit jährlichem Schutz gegen negative Indexrenditen und einer
später aktivierbaren lebenslangen Einkommensgarantie. Funktional ähnelt die
Growth Phase einer Fixed Indexed Annuity und die Income Phase einem
Guaranteed Lifetime Withdrawal Benefit. Diese Begriffe sind jedoch nur
ökonomische Modellanalogien, keine rechtliche oder aufsichtsrechtliche
Klassifikation [@bauer2008; @holz2012]. AGILE wird von Allianz Australia Life Insurance Limited unter
einer Group Policy ausgegeben; die Investments werden Statutory Fund No. 2
zugeordnet [@allianz2026pds, S. 2 und 83--85].

Die Research Engine bildet Produktzustände monatlich ab, bewertet Cashflows
unter dem risikoneutralen Maß $Q$, erzeugt Real-World-Projektionen unter $P$
und ergänzt Mortalität, Verhalten, Kapitalproxy sowie ein separates
Least-Squares-Monte-Carlo-(LSMC-)Modul. Ihre Stärke liegt in der expliziten
Cashflow- und Zustandsarchitektur. Die Engine ist dennoch kein
Produktionsmodell: Adminformeln, Kalibrierung, In-force-Zustände,
Portfolioeffekte und APRA/LAGIC fehlen.

Die zugrunde liegende Review-Matrix trennt 93 materielle Aussagen in 31
Produktfakten, 26 Modellannahmen, 30 Ergebnisse und 6 Interpretationen. Die
Juli-2026-Produktfakten und die berichteten 1.2.0-/1.3.0-Zahlen wurden gegen
Primärquellen beziehungsweise lokale Ergebnisartefakte geprüft; keine
materiell falsche Basiszahl blieb in der reviewed Langfassung bestehen.

## Die sechs wichtigsten Aussagen

1. **Der illustrative Basisfall ist negativ.** Bei AUD 100.000 Prämie ergibt
   sich ein Gross VNB von rund **−AUD 1.228**; nach dem Risk-Margin-Proxy sind
   es **−AUD 5.915**. Der PVFP bei 8 % beträgt **−AUD 12.899**.
2. **Die lebenslange Garantie ist im Modell teuer.** Der modellierte faire
   Lifetime-Income-Premium-Satz beträgt 3,00 % p. a., gegenüber 1,15 % p. a.
   belasteter LIP. Der isolierte Guarantee Value beträgt +AUD 10.080.
3. **Zinsrisiko dominiert.** Ein paralleler Zinsrückgang um 100 bp
   verschlechtert den Gross VNB im Sensitivitätslauf um rund AUD 11.483. Der
   BSCR-Research-Proxy von AUD 17.205 wird vor allem durch Interest Down
   getrieben.
4. **Timing und Design sind materiell.** Späterer Income Start, Rising Income,
   Spouse-Schutz und Age Pension+ verändern Kundenleistungsbarwert und
   Versichererwert deutlich. Die Varianten sind bedingte Szenarien, kein
   gemeinsamer späterer Optionswert.
5. **Monte-Carlo-Fehler ist nicht das Hauptproblem.** Das 95-%-MC-Halbintervall
   des 4.000-Pfad-Basislaufs beträgt etwa ±AUD 83. Modellwahl und der
   Versionswechsel bewegen den Gross VNB dagegen um rund AUD 3.000; diese
   Vergleiche enthalten allerdings ebenfalls Sampling- und Parameteranteile.
6. **Testgrün ist keine Produktionsfreigabe.** 122 Tests bestehen, aber der
   unveränderte Standard-Runner bricht in `pricing.greeks()` mit einem
   `FrozenInstanceError` ab. Der Zahlenpack wurde nur mit einem transparenten,
   laufzeitlokalen Workaround vollständig reproduziert.

## Executive KPIs

| Kennzahl | Ergebnis | Richtige Einordnung |
|---|---:|---|
| Prämie | AUD 100.000 | einzelner illustrativer Modellpunkt |
| Gross VNB / Gross NBM | **−AUD 1.228 / −1,228 %** | vor Risk Margin |
| MC-Standardfehler / 95-%-Halbintervall | AUD 42 / ±AUD 83 | nur Sampling Error des Basispricing |
| Non-unit BEL | +AUD 1.228 | negatives Gegenstück zum Gross VNB |
| Guarantee Value | +AUD 10.080 | Claims minus LIP, nicht Gesamtproduktverlust |
| fairer / belasteter LIP | 3,00 % / 1,15 % | isolierter Rider-neutraler Satz vs. Modellinput |
| BSCR-/Risk-Margin-Proxy | AUD 17.205 / AUD 4.687 | kein APRA/LAGIC |
| VNB nach Risk Margin | **−AUD 5.915** | Research-Konvention |
| PVFP @ 8 % | **−AUD 12.899** | inklusive Reserve, Kapital und Tax-Annahme |
| IRR / Payback | 3,52 % / Jahr 23 | niedrigste Wurzel / undiskontiert |
| Q-Identity Gap | −0,169 % | interne Reconciliation, kein Kalibrierungsbeweis |

![Abbildung 1: Executive Dashboard des instrumentierten Black--Scholes-1.3.0-Basislaufs mit 4.000 Pfaden; AUD, Prozent und Jahre. Alle Werte sind illustrative Research-Resultate.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/01_executive_dashboard.png){width=92%}

# 1. Produktmechanik in Kürze

## 1.1 Rechtliche Rollen und zwei Produktphasen

Investor, Life Insured, beneficiary und Surviving Spouse sind nicht
gleichzusetzen. Die Group Policy wird an Allianz Australia Life Policy
Services Pty Limited ausgegeben; der Investor ist specified beneficiary und erhält die im
Investor Certificate dokumentierten Rechte. Bei Trustee-, Plattform- oder
Company-Strukturen kann die nominierte natürliche Person als Life Insured
grundsätzlich ohne eigenes Interesse unter der Group Policy bleiben
[@allianz2026pds, S. 2 und 83--84]. Garantien sind Verpflichtungen von Allianz
Australia Life aus den verfügbaren Assets des Statutory Fund, unter den im PDS
genannten Top-up- und begrenzten Cessation-Regeln; Allianz SE garantiert die
Leistungen nicht.

Ökonomisch besitzt AGILE zwei Phasen:

- **Growth Phase:** Das Investment Value erhält jährlich einen begrenzten,
  geschützten Credit auf Basis eines Return Index. Der Investor hält keine
  direkten Index- oder Fondsanteile; das Produkt ist *indexed*, nicht
  *unit-linked*.
- **Lifetime Income Phase:** Nach frühestens einem Jahr kann ein monatliches
  Einkommen irreversibel aktiviert werden. Nach Erschöpfung des Investment
  Value läuft das garantierte Einkommen weiter; erst diese Fortzahlung wird
  zum Versicherungsclaim.

Ein spätester automatischer Income Start erfolgt ohne Age Pension+ am nächsten
Anniversary nach Alter 100, mit Age Pension+ nach der bei Optionsbeginn
festgelegten Life Expectancy. Ohne rechtzeitige Instruktion ist Fixed Income
ohne Spouse der Default. Bei fehlenden Kontakt- oder Bankdaten behält sich
Allianz laut PDS stattdessen einen Full Withdrawal vor. Diese automatischen
Folgeereignisse sind in der Engine nicht vollständig als State-Machine-Regeln
implementiert [@allianz2026pds, S. 17 und 75].

## 1.2 Protected Investment Options und Annual Credit

Für Commencement- oder Anniversary Dates vom 1. bis 31. Juli 2026 gelten:

| Index | Total Protection | Partial Protection mit initial 10 % Buffer |
|---|---:|---:|
| Australian Equity | Cap 6,20 % | Cap 13,00 % |
| Global Equity | Cap 6,00 % | Cap 12,80 % |

Die Guaranteed Minimums von 0,25 % beziehungsweise 0,50 % sind Untergrenzen
des **künftig festgesetzten Maximum Return**, keine Mindestjahresrenditen
[@allianz2026maximums; @allianz2026minimums]. Die Caps werden jährlich neu
festgesetzt. Die Engine wiederholt mangels Cap-Schedule den Juli-Cap über die
gesamte Laufzeit; das ist eine Modellannahme. Aktuelle New-Business-Caps sind
nicht pauschal auf In-force-Policen oder andere Vintages übertragbar.

Mit jährlicher Indexrendite $R=S_T/S_0-1$ und Cap $C$ modelliert die Engine
den marktgebundenen Total-Protection-Zweig als

\[
c_{TP}(R)=\min\{\max(R,0),C\}.
\]

Partial Protection mit 10-%-Buffer lautet

\[
c_{PP10}(R)=
\begin{cases}
\min(R,C), & R\ge 0,\\
\min(0,R+0{,}10), & R<0.
\end{cases}
\]

Bei −18 % Indexrendite entstehen damit 0 % unter Total Protection und −8 %
unter Partial Protection. Das PDS erlaubt für Total Protection alternativ
einen garantierten einjährigen Fixed Return. Dieser Vertragszweig und sein
zeitanteiliger DVA-Floor fehlen in der Engine; die Payoffformeln sind deshalb
nicht universell [@allianz2026pds, S. 58, 60 und 62].

## 1.3 Lifetime Income, Gebühren und Liquidität

Beim Income Start ist das jährliche Anfangseinkommen

\[
I_0=IV_{\tau}^{post\ fee}\,g.
\]

Alter und `Gender` am **Product Commencement Date** bestimmen die Basisrate;
`Gender` bezeichnet dabei das bei Geburt registrierte Geschlecht gemäß PDS.
Vollständige Growth-Jahre liefern Escalators. Für den Basismodellpunkt gilt

\[
g=7{,}05\%+5\times0{,}35\%=8{,}80\%.
\]

Die 8,80 % werden auf das Investment Value bei Income Start angewandt; sie
sind weder Rendite auf die ursprüngliche Prämie noch Marktzinssatz
[@allianz2026rates]. Bei Spouse Income bestimmt das eindeutig jüngere Leben
die Rate. Die Regel bei gleich alten Personen unterschiedlichen Geschlechts
und die Interpolation nicht ganzzahliger Alter sind öffentlich nicht bestätigt
und bleiben offen.

Die Engine unterscheidet:

- **Fixed Income:** nominal konstant, sofern keine reduzierende Excess
  Withdrawal erfolgt;
- **Rising Income:** niedrigere Start-Rate, danach Erhöhung um positive Credits
  der Australian Equity Total Protection Option; keine CPI-Indexierung;
- **Spouse Income:** Fortsetzung für den Surviving Spouse unter den
  PDS-Bedingungen; der Modellinput fixiert die Death Election vorab;
- **Age Pension+:** CAS-basierte Begrenzung von Kapitalzugriff und Death
  Benefit, mit funding-spezifischer Election und Commencement.

Product Fee und Lifetime Income Premium betragen im geprüften PDS 0,30 % und
1,15 % p. a. und werden vertraglich täglich berechnet. Die Engine approximiert
monatlich und hält die Sätze konstant; das PDS enthält ein begrenztes
Änderungsrecht [@allianz2026pds, S. 41--42].

Ohne Age Pension+ können in der Growth Phase jährlich 5 % des anfänglichen
Investment Amount ohne Übertrag als Free Withdrawal genutzt werden. Excess-
und Full Withdrawals können in den ersten zehn Jahren einer MVA unterliegen;
es gelten unter anderem AUD 100 Mindestentnahme, 95-%-Einzel-/Jahresgrenzen
und mindestens AUD 2.000 verbleibender Investment Value.
Nach Age-Pension+-Beginn gilt eine eigene Lower-of-Logik aus Investment Value
abzüglich MVA und Maximum Withdrawal Value. DVA und MVA sind in der Engine nur
Proxies; die nicht veröffentlichte Adminformel und echte Transaktionsquotes
fehlen. Die DVA ist der Wert der relevanten Derivatekontrakte, nicht eine
realisierte Year-to-date-Rendite. Vertraglich gelten zeitanteilige Cap-,
Protection- und gegebenenfalls Fixed-Return-Mindestwerte, während der
Engine-Proxy Protection Floor und Fixed-Return-Zweig nicht vollständig
abbildet [@allianz2026pds, S. 31--35 und 62--70].

Der Death Benefit entspricht grundsätzlich dem positiven Investment Value
ohne MVA. Bei Spouse Income hängen Fortsetzung oder Lump Sum sowie der Default
vom Ownership- und Eligibility-Pfad ab; der Runner vereinfacht dies zum
Szenarioinput. Age Pension+ ist keine jederzeit frei aktivierbare Option:
Election und Commencement sind funding-, release- und altersspezifisch und
unwiderruflich. Non-superannuation-Trustee- und Company-Investors sind
grundsätzlich ausgeschlossen, außer Non-super-Platform-Trustees. Maximum
Withdrawal Value und Maximum Benefit on Death folgen der CAS; letzterer bleibt
bis zur halben Life Expectancy auf der Basis und springt danach auf den
MWV-Pfad. Ratecard- und CAS-Vintage müssen gemeinsam gespeichert werden
[@allianz2026pds, S. 15--17, 24--25, 38--40 und 65--70].

# 2. Modell- und Bewertungsansatz

## 2.1 Verarbeitungskette

| Baustein | Aufgabe | Zentrale Grenze |
|---|---|---|
| Produkt-State-Machine | Growth/Income, Credits, Fees, Death, Lapse, Withdrawals | automatische Events und In-force-State unvollständig |
| Zins- und Equity-Szenarien | Black--Scholes, Heston, Hull--White unter $Q$ und $P$ | illustrative statt kalibrierter Parameter |
| Crediting/DVA | Optionsreplikation und COS-Pricer | Fixed-Return- und Protection-Floors unvollständig |
| Mortalität/Verhalten | generational Mortality, Joint Life, Lapse, Take-up | keine Allianz-Experience-Kalibrierung |
| Pricing/Reconciliation | BEL, Guarantee Value, Fair LIP, Identity Gap | Einzelpolice, kein Portfolio |
| Kapital/Profit | Stressproxy, Risk Margin, PVFP und IRR | Solvency-II-artig, nicht APRA/LAGIC |
| LSMC | jährlicher Policyholder-Optionswert | separat, kein voller Monatsmotor |

Die Architektur-, Test- und Auditangaben beziehen sich auf die lokalen
internen Engine-, Methodology- und Audit-Artefakte und nicht auf unabhängige
Produktionsnachweise [@agileengine2026; @agilemethodology2026;
@agileaudit2026].

Die Ereignisreihenfolge im Monatsraster ist ökonomisch wesentlich: Marktpfad,
Crediting Anniversary/Rising Ratchet, Gebühren, Income Election, Tod,
nachschüssiges Income, Withdrawals und Lapse dürfen nicht beliebig vertauscht
werden. Mortalität und Storno werden als Wahrscheinlichkeitsgewichte statt als
binäre Life-by-Life-Ereignisse geführt. Die Audit-Historie zeigt,
dass Event Ordering und Conditioning größere Fehler erzeugen können als eine
einzelne Formel.

## 2.2 $Q$- und $P$-Maß

Unter $Q$ werden replizierbare Cashflows mit risikofreier Diskontierung und
risikoneutralen Drifts bewertet:

\[
PV_Q(CF)=\mathbb{E}^Q\!\left[\sum_tD_tCF_t\right],
\qquad D_t=\exp\!\left(-\int_0^t r_s\,ds\right).
\]

Unter $P$ werden Real-World-Profit-Signaturen und Kunden-Outcomes simuliert.
Die Trennung beantwortet zwei verschiedene Fragen:

- **$Q$:** Welchen heutigen Marktwert haben die finanzierbaren Cashflows?
- **$P$:** Wie verteilen sich Cashflows und Kapitalpfade unter einer
  angenommenen realen Renditeverteilung?

Die Engine verwendet Black--Scholes als Basismodell, Heston für stochastische
Volatilität und Hull--White für stochastische Zinsen [@blackscholes1973;
@heston1993; @hullwhite1990]. Der COS-Pricer ist für den Heston-DVA-Zweig
numerisch effizient [@fang2008]. In der Heston--Hull--White-Kopplung wird ein
Cross-Term als skalarer Gauß-Faktor behandelt. Bei den Defaultparametern ist
der betreffende Wert mit rund $-2{,}326\times10^{-4}$ jedoch leicht negativ.
Die Bezeichnung als exakte,
unabhängige Gaussian-variance composition ist daher falsch; der Zweig ist als
hybride, nicht gemeinsam gegen Monte Carlo validierte Näherung zu behandeln.

Die Mortalitätsbasis ist eine synthetische Gompertz--Makeham-Annäherung, keine
offizielle australische oder Allianz-spezifische Pricing-/Reservebasis.
Systematische Langlebigkeit wird nur gestresst, nicht stochastisch modelliert;
Lapse, Take-up und Withdrawals sind heuristische Verhaltensregeln.

## 2.3 Basisannahmen

| Bereich | Zentrale Basisannahme |
|---|---|
| Vertrag | Commencement Mitte 2026; Mann 65; AUD 100.000; Non-super; kein Spouse/Age Pension+ |
| Allocation | 100 % Australian Equity Total Protection; Cap 6,20 %; Guaranteed Minimum 0,25 % |
| Income | Fixed ab Alter 70, Rate 8,80 % |
| Weitere Vertragsinputs | keine geplanten Withdrawals; Adviser Fee 0; Bonus 0 |
| Kurve | 1/2/5/10/20/30Y: 3,80/3,90/4,10/4,30/4,40/4,40 % |
| Volatilität / ERP | AUS 16 %, Global 15 % / ERP unter $P$ 4,50 % |
| Fees | Product Fee 0,30 %, LIP 1,15 % p. a. |
| Kosten | 2 % Acquisition; AUD 80 p. a. + 5 bp IV Maintenance; 2,50 % Inflation |
| Verhalten | Income-Lapse 0,50 % p. a.; dynamischer Lapse-Proxy |
| Profit | 8 % Hurdle; 30 % sofort symmetrische Tax-Wirkung |
| Pfade | 4.000 Basis; 1.200 Sensitivitäten; je Block abweichend |

Return-Index-Carry ist null, weil die verwendeten Indizes Total-/Net-Return-
Indizes sind. Der mögliche Fixed-Return-Zweig ist ausgeschaltet,
MVA-Termination-Loadings sind null und der Juli-Cap wird wiederholt. Diese
Management- und Modellannahmen sind nicht als Produktfakten zu lesen.

Die Pfadzahlen unterscheiden sich: 4.000 für Basispricing/Kapital/Profit,
1.200 für Sensitivitäten, 1.500 für Design/Timing, 600 für Behaviour, 2.500
für Outcomes, 600 je Modell und fünf Seeds zu je 800 Pfaden. Base-Zeilen aus
verschiedenen Analyseblöcken sind deshalb nicht zellgleich zu erwarten.

## 2.4 Wertbegriffe und Kapital

Der Non-unit BEL wird intern als

\[
BEL_{NU}=PV_Q(Claims)+PV_Q(Expenses)-PV_Q(Fees+LIP+CM+MVA+APPlus)
\]

geschrieben. Der Gross VNB ist das negative Gegenstück. Der isolierte
Guarantee Value lautet $GV=PV_Q(Claims)-PV_Q(LIP)$ und misst nicht den Wert des
Gesamtprodukts. Der faire LIP ist der Rider-Satz, der allein LIP und Claims
ausgleicht; Product Fee, Crediting Margin, Expenses und Kapital fehlen in
diesem isolierten Break-even.

`bel_total=Premium+BEL_{NU}` ist nur eine interne Engine-Konvention und kein
regulatorischer Total BEL. Ebenso ist $p_z\le 1$ keine allgemeine Identität:
bei einem hypothetischen 50-%-Cap ergibt die unabhängige Gegenrechnung
$p_z=1{,}0449739$. Nichtnegative Crediting Margin gilt nur im finanzierbaren
Basis-Cap-Fall.

Die Identity Gap prüft, ob finanzierte Kunden- und Versicherercashflows die
Prämie innerhalb eines Monte-Carlo-Bands reconciliieren. Sie erkennt Cashflow
Leakage, nicht aber falsche Vertragsregeln oder unkalibrierte Parameter.

Der Kapitalproxy stresst Zins, Equity, Volatilität, Mortalität, Langlebigkeit,
Lapse, Kosten und Katastrophe und aggregiert über eine Korrelationsmatrix. Er
besitzt weder Statutory-Fund-Bilanz noch die vollständigen Insurance-, Asset-,
Concentration- und Operational-Risk-Komponenten nach LPS 110/114/115/117/118.
Er ist deshalb ausdrücklich **kein APRA Prescribed Capital Amount**
[@apra2023lps110; @apra2026lps114; @apra2023lps115; @apra2024lps117;
@apra2023lps118].

# 3. Basisfall und Ergebnisüberleitung

## 3.1 Versichererwert

Die Überleitung zum Gross VNB zeigt, wo der Wert entsteht:

| $Q$-Barwertkomponente | Beitrag zum Versichererwert |
|---|---:|
| Product Fees | +AUD 2.270 |
| Lifetime Income Premium | +AUD 8.701 |
| Crediting Margin | +AUD 9.923 |
| MVA Retained | +AUD 217 |
| Guarantee Claims | −AUD 18.781 |
| Expenses | −AUD 3.559 |
| **Gross VNB** | **−AUD 1.228** |

Die LIP deckt rund 46,3 % des Claimbarwerts. Product Fee, Crediting Margin und
MVA finanzieren einen großen Teil der verbleibenden Garantielücke, reichen
nach Expenses aber nicht für einen positiven Gross VNB. Die modellierten
Kundenleistungsbarwerte summieren sich auf AUD 97.500; die Q-Identity Gap von
−0,169 % liegt innerhalb der verwendeten Reconciliation-Toleranz
[@agilerun2026].

![Abbildung 2: Pricing- und Margin-Waterfall des 4.000-Pfad-$Q$-Basislaufs, AUD.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/02_pricing_margin_waterfall.png){width=92%}

## 3.2 Kapital, Profit und Timing

| Stressmodul | Standalone SCR |
|---|---:|
| Interest Down | **AUD 15.813** |
| Longevity | AUD 3.490 |
| Lapse Down | AUD 818 |
| Expenses | AUD 314 |
| Equity / Equity Volatility | jeweils AUD 0 im bindenden Proxy |
| **aggregierter BSCR-Proxy** | **AUD 17.205** |

Das Nullresultat für den Equity-Level-Schock ist nicht überraschend: AGILE
hält keinen direkten Equity-Fondsanteil. Equity wirkt primär über laufenden
Credit, DVA, Gebühren und künftige Garantien. Interest Down ist wesentlich,
weil Diskontierung, Accountpfad, Optionsbudget und langfristige Claims
gleichzeitig reagieren.

Der Time-0-Distributable-Strain beträgt rund −AUD 21.346. BEL inklusive Risk
Margin und Required-Capital-Proxy erreichen im Modell um Jahr 17 ihre Maxima.
Der kumulierte undiskontierte Payback wird erst in Jahr 23 positiv. Trotzdem
bleibt der PVFP bei 8 % negativ: frühe Strains und Kapitalbindung werden stark
gewichtet, späte Freisetzungen stark diskontiert. Die Tax-Logik unterstellt
sofortige 30-%-Entlastung auch auf Verluste; Verlustvorträge, Deferred Tax und
Realisierbarkeit fehlen.

## 3.3 Was das Ergebnis bedeutet — und was nicht

Der Basislauf erlaubt die Aussage:

> Unter genau den dokumentierten illustrativen Annahmen ist der modellierte
> Einzelpolicenwert vor und nach Risk Margin negativ.

Er beweist **nicht**, dass das reale AGILE-Portfolio unprofitabel ist. Es fehlen
tatsächliche Hedgekosten, reale Cap-Management-Regeln, Bestandsmortalität,
Kundenverhalten, Portfolioaggregation, Reinsurance, Steuer- und
Admininformationen. Umgekehrt wäre auch ein positiver Szenario-VNB keine
Produktionsfreigabe.

# 4. Sensitivitäten, Kunden-Outcomes und Produktdesign

## 4.1 Wichtigste Einfaktor-Sensitivitäten

Die Sensitivitäten verwenden 1.200 Pfade und schließen Kapital/Risk Margin aus.
Ihre Base-PVFP-Zahl ist daher nicht mit dem kapitalbelasteten Basis-PVFP
vergleichbar.

| Szenario | Gross VNB | Änderung |
|---|---:|---:|
| Base | −1.224 | 0 |
| Zinsen +100 bp | 8.549 | +9.773 |
| Zinsen −100 bp | −12.707 | **−11.483** |
| Maximum Returns −100 bp | 1.008 | +2.232 |
| Longevity: $q_x$ −10 % | −2.852 | −1.629 |
| Lapse +50 % | −498 | +725 |
| Income Start +2 Jahre | 2.037 | +3.261 |
| Income Start −2 Jahre | −4.029 | −2.805 |
| Excess 2 % p. a. + Free-Utilisation 100 % | 2.521 | +3.745 |
| Maintenance Expenses +10 % | −1.380 | −156 |

![Abbildung 3: Sensitivitäts-Tornado mit 1.200 Pfaden; AUD-Änderung des Gross VNB, ohne Kapital und Risk Margin.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/04_sensitivity_tornado.png){width=92%}

Die Interpretation ist mechanisch, nicht beratend: Niedrigere Zinsen und
höhere Langlebigkeit belasten; späterer Income Start verbessert im Modell den
Versichererwert, reduziert aber typischerweise den Kundenleistungsbarwert.
Niedrigere Caps verschieben Wert vom Kunden zum Versicherer. Withdrawals
reduzieren die Garantie und können deshalb den Versichererwert erhöhen; das
ist keine Wohlfahrtsaussage. Das Excess-2-%-Szenario setzt zugleich die
Free-Withdrawal-Utilisation auf 100 % und ist kein isolierter 2-%-Stress.
Gepaarte Standardfehler der Differenzen werden nicht ausgegeben.

## 4.2 Wann die Garantie sichtbar wird

Die Real-World-Outcome-Analyse verwendet 2.500 Pfade mit effektivem Seed 2027
aus `settings.seed+1`; im serialisierten Manifest steht nur der Ausgangsseed
2026. Werte sind nominal und vor persönlicher Steuer.

| Alter | IV Median | Fixed Income Median | Anteil IV erschöpft | In-force-Gewicht |
|---:|---:|---:|---:|---:|
| 70 | 110.078 | 9.812 | 0,00 % | 78,64 % |
| 82 | 10.174 | 9.812 | 10,48 % | 55,73 % |
| 83 | 526 | 9.812 | 47,56 % | 53,30 % |
| 84 | 0 | 9.812 | **85,36 %** | 50,80 % |
| 86 | 0 | 9.812 | 100,00 % | 45,58 % |

Ab Alter 83/84 wird im illustrativen Modell ein wachsender Anteil des
Einkommens direkt zum Guarantee Claim. Investment-Value-Quantile sind keine
Kundenprognose; Mortalität und Lapse stehen separat im In-force-Gewicht.

![Abbildung 4: Real-World-Verteilung von Investment Value, nominalem Income und Account Depletion mit 2.500 Pfaden und effektivem Seed 2027.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/05_customer_outcomes.png){width=92%}

## 4.3 Design- und Timing-Trade-offs

| Variante | Rate | Gross VNB | Guarantee Value | Kundenleistungs-PV |
|---|---:|---:|---:|---:|
| Single Fixed | 8,80 % | −1.335 | 10.183 | 97.548 |
| Single Rising | 5,65 % | 6.445 | 3.900 | 89.690 |
| Spouse Fixed | 7,70 % | **−5.149** | 14.908 | 100.957 |
| Spouse Rising | 4,55 % | 6.537 | 5.544 | 89.175 |
| Age Pension+ Fixed | 8,85 % | −2.252 | 12.483 | 98.394 |
| Age Pension+ Rising | 5,70 % | **7.207** | 7.198 | 88.838 |

Für Spouse wird eine 63-jährige Frau neben dem 65-jährigen Mann und die Death
Election `continue_income` modelliert. Age-Pension+-Varianten verwenden eine
illustrative CAS-Lebenserwartung von 20 Jahren. Rising-Varianten sind im Run
für den Versicherer günstiger, starten aber mit geringerem Einkommen. Spouse
Fixed besitzt den höchsten Kundenleistungsbarwert und ist zugleich am
teuersten. Persönliche Utility, Liquiditätspräferenz, Bequest Motive, Steuer
und Social Security sind nicht modelliert [@steinorth2015;
@actuariesinstitute2024].

Der Income-Start illustriert denselben Zielkonflikt: Bei Startalter 66 beträgt
der Gross VNB −AUD 6.150 und der Kundenleistungs-PV AUD 102.337; bei Startalter
80 sind es +AUD 15.066 beziehungsweise AUD 80.996. Der heutige Vergleich
ignoriert den zukünftigen Optionswert, adverse Selektion und neue
Informationen am tatsächlichen Wahlzeitpunkt.

![Abbildung 5: Income-Start-Trade-off mit 1.500 Pfaden; Rate, Gross VNB, Guarantee Value und Kundenleistungsbarwert nach Wartezeit.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/07_income_start_tradeoff.png){width=88%}

# 5. Validierung und Model Risk

## 5.1 Reproduzierbarkeit

Der unabhängige cachefreie Testlauf ergab **122 bestandene Tests in 140,13
Sekunden**. Die Suite prüft unter anderem Payoffbeispiele, DVA-Konvergenz,
Martingalbedingungen, Hull--White-Bondpreise, Buchungsidentitäten, Joint Life,
Rising Income, Withdrawals, Kapitalaggregation, Fair-Fee-Bracket und LSMC.
Einige Toleranzen sind jedoch breit; Testgrün beweist keine produktspezifische
Genauigkeit.

Der unveränderte Runner bricht in Block 1/9 nach 18,5 Sekunden ab:

```text
dataclasses.FrozenInstanceError: cannot assign to field 'index_levels'
```

`ScenarioSet` ist unveränderlich, während `pricing.greeks()` ein Feld direkt
überschreibt. Die Tests rufen diese öffentliche API nicht auf. Mit einem
prozesslokalen `dataclasses.replace`-Workaround, ohne Änderung einer
Engine-Datei, liefen 9/9 Blöcke in 113,5 Sekunden. Vierzehn CSV-Dateien waren
zellgenau, zehn PNGs bytegenau und das fachliche Manifest bis auf Zeitstempel
identisch zum publizierten instrumentierten Pack. Damit sind die Zahlen stark
reproduziert; der Standard-Runner ist dennoch nicht end-to-end lauffähig.

## 5.2 Wichtigste Modellrisiken

| Befund | Bedeutung |
|---|---|
| Runner/Greek-Immutability | Produktionsintegration bricht trotz grüner Unit Tests |
| unvollständige Provenienz | Manifest bindet Engine-Module, aber nicht gemeinsam Runner, Patch, CLI, Tests, externe Inputs, effektive Sub-Seeds und Output-Hashes |
| Heston--HW-COS-Cross-Term | hybride Näherung, nicht die behauptete exakte unabhängige Gauß-Komposition |
| DVA/MVA | Proxy ohne bestätigte Adminformel, Floors und echte Quotes |
| Off-anniversary Behaviour | Income-Lapse nutzt bis zum Anniversary IV statt Surrender Value |
| LSMC | jährliches separates Modul; Tail und Joint Life nicht like-for-like zum Monatsmotor |
| Tax und Expenses | sofort symmetrische Verlustentlastung; Expense-Stress nur Maintenance |
| statistische Präzision | viele Kennzahlen ohne outputseitigen Standardfehler |

Das LSMC liefert im Population-Sinn für eine fixe zulässige Policy einen Lower
Bound. Der berichtete MC-Schätzer ist aber wegen samplebasiertem
`max(optimal,static)` kein strikter numerischer Lower Bound. Der Default endet
bei Alter 105 beziehungsweise 40 Jahren, nutzt einen 30Y-Zero-Tail und
$\max(IV,I\times AF)$; die Static Policy ist nicht der vollständige
Monatsmotor [@longstaffschwartz2001; @huangkwok2016].

## 5.3 Versions- und Modellrisiko

| Kennzahl | v1.2.0 | v1.3.0 instrumentiert | Veränderung |
|---|---:|---:|---:|
| Gross VNB | +1.743 | −1.228 | **−2.970** |
| Fair LIP | 3,237 % | 3,004 % | −23,3 bp |
| Guarantee Value | 11.240 | 10.080 | −1.160 |
| Crediting Margin | 14.131 | 9.923 | −4.208 |
| BSCR | 16.839 | 17.205 | +366 |
| Risk Margin | 20.076 | 4.687 | **−15.389** |
| PVFP @ 8 % | −15.610 | −12.899 | +2.712 |

Der wichtigste Gross-VNB-Treiber war die Korrektur des Return-Index-Carry von
4 % auf null, um Dividendendoppelzählung bei Total-/Net-Return-Indizes zu
vermeiden. Der Gegenlauf wurde unabhängig mit +AUD 1.879,32 und einem
abgeleiteten Carry-Effekt von rund −AUD 3.106,96 bestätigt, ist aber nicht als
separates CSV-/Manifest-Artefakt archiviert. Der Gesamtvergleich bündelt Codefixes, Annahmen und
Definitionsänderungen und ist daher Versionsattribution, kein reiner
Implementation-Risk-Schätzer.

Der 600-Pfad-Modellvergleich liefert Gross VNB von −AUD 1.275 unter
Black--Scholes bis −AUD 4.402 unter Heston--Hull--White. Die Spannweite von AUD
3.127 ist groß gegenüber dem Basis-SE, aber mangels modellweiser
Standardfehler kein reines Model-Risk-Maß.

Über fünf Black--Scholes-Seeds beträgt der mittlere Gross VNB −AUD 1.209, die
Sample-SD AUD 96,64, der mittlere pfadweise Standardfehler AUD 96,63 und die
Spannweite −AUD 1.292 bis −AUD 1.049. Das ist ein internes
Plausibilitätssignal, keine umfassende Konvergenzstudie.

![Abbildung 6: Unbereinigter Modellvergleich mit 600 Pfaden je Modell und Black--Scholes-Seed-Stabilität mit fünf Seeds zu je 800 Pfaden; AUD und Prozent.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/09_model_mc_stability.png){width=90%}

Die Literatur-QA korrigierte außerdem drei Metadatenrisiken der Langfassung:
`deng2017` stammt von Geng Deng und Mike Yan; der Publisher-DOI-String ist
nicht registriert und wurde durch die stabile Risk.net-URL ersetzt. Im lokalen
Literaturindex war ein DOI bei Bégin/Sanders falsch, und eine vermeintliche
Drei-Autoren-Datei ist tatsächlich Yingfei Suns MSc-Thesis. Keine dieser
Fremdquellen wird zur ungeprüften Übertragung einer Fair Fee auf AGILE genutzt
[@deng2017].

# 6. Production Readiness und richtige Verwendung

## 6.1 Produktionsblocker

Vor produktiver Nutzung sind mindestens folgende Lücken zu schließen:

1. **Vertrag/Admin:** vollständige Reconciliation von DVA, MVA, Fixed Return,
   automatischen Events, Eligibility, Death Election und Reallokation.
2. **In-force-Fähigkeit:** Phase, Investment Value, Locked Income, laufendes
   Fixing, Certificate Cap, Issue Curve, CAS State und verbrauchte Allowance.
3. **Kalibrierung:** Markt-, Mortalitäts-, Lapse-, Take-up-, Withdrawal-,
   Kosten- und Tax-Parameter auf beobachtbare Daten; unabhängige Benchmarks.
4. **APRA/LAGIC und Portfolio:** Statutory-Fund-Bilanz, Hedges, Credit,
   Konzentration, Operational Risk, Management Actions und Aggregation.
5. **Vollständige Cashflows:** Adviser Fees, Tax/Withholding, Cooling-off,
   Reinsurance sowie belastbare Tax-Loss-/DTA-Logik.
6. **Engineering/Governance:** Greek-Fix, Standard-Runner-End-to-End-Test,
   Streaming/Chunking, Inputvalidierung und vollständige Run-Provenienz.

Zwei öffentliche Produktfragen bleiben ausdrücklich offen: die APRA-
Klassifikation als variable annuity business und die Rating-Regeln für gleich
alte Spouses beziehungsweise nicht ganzzahlige Commencement-Alter.

## 6.2 Was belastbar gelernt werden kann

- **Indexed statt unit-linked:** Ein Equity-Level-Schock wirkt nicht wie auf
  ein direktes Fondskonto; Zins- und Optionsbudgetrisiko können dominieren.
- **Garantie im Tail:** Sobald das Investment Value erschöpft ist, werden
  Income-Zahlungen zu Versicherungsclaims.
- **Timing ist eine Option:** Früher Start erhöht häufig den
  Kundenleistungsbarwert und belastet den Versicherer; späterer Start wirkt im
  Modell umgekehrt.
- **Behaviour ist nicht monoton:** Lapse und Withdrawals können je nach
  Moneyness und Timing Garantien freisetzen oder Gebühren vernichten.
- **Governance ist ökonomisch materiell:** Versions- und
  Implementierungsänderungen sind größer als der reine Basis-Sampling-Fehler.

## 6.3 Richtige Verwendung der Kennzahlen

| Kennzahl | Zulässige Aussage | Unzulässige Verkürzung |
|---|---|---|
| Guarantee Value | isolierte Claims-minus-LIP-Lücke | Gesamtproduktverlust |
| Gross VNB | $Q$-Versichererwert vor RM | realer Portfoliowert |
| VNB nach RM | Research-Wert nach Proxy-RM | regulatorischer VNB |
| PVFP | diskontierte Distributable Earnings unter $P$ | identisch mit $Q$-VNB |
| BSCR-Proxy | relative Risikotreiber im Modellpunkt | APRA PCA oder Fund-Kapital |
| Customer Benefit PV | Barwert modellierter Zahlungen | Utility oder Kundenprognose |
| Identity Gap | interne Finanzierungsreconciliation | Vertrags- oder Kalibrierungsnachweis |

# 7. Schlussfolgerung

AGILE ist kein Produkt, das sich mit einer einzelnen Income-Rate- oder
Optionsformel verstehen lässt. Der Wert entsteht aus dem Zusammenspiel von
jährlichem Crediting, DVA/MVA, Gebühren, Income Election, Mortalität,
Kundenverhalten, Kapitalbindung und Implementierungsqualität.

Der instrumentierte Basislauf zeigt einen negativen Versichererwert, eine
deutlich unter dem modellierten Fair-LIP liegende Rider Fee, dominantes
Interest-Down-Risk und den späten Übergang der Einkommensfinanzierung vom
Investment Value zur Garantie. Sensitivitäten und Designvarianten zeigen
große Trade-offs zwischen Startniveau, Langlebigkeitsschutz, Liquidität und
Versichererwert.

Wichtiger als die einzelne Basiszahl ist der Validierungsbefund: Der
Versionswechsel dreht das VNB-Vorzeichen, und eine öffentliche API bricht
trotz 122 bestandener Tests im End-to-End-Runner. Die sachgerechte Einstufung
lautet deshalb **reviewed research prototype**. Die Engine ist eine wertvolle
Lern-, Analyse- und Prototyping-Plattform, aber erst nach Vertrags- und
Admin-Reconciliation, Kalibrierung, In-force-Erweiterung, APRA/LAGIC,
Portfolioaggregation und vollständiger Model Governance produktionsfähig.

# Anhang: Kompakte Notation

| Symbol | Bedeutung |
|---|---|
| $R=S_T/S_0-1$ | jährliche Point-to-Point-Indexrendite |
| $C$ / $c(R)$ | Maximum Return / gutgeschriebener Annual Return |
| $IV_t$ / $I_t$ | Investment Value / jährliches Locked Income |
| $D_t$ / $P(s,t)$ | Diskontfaktor / Zero-Coupon-Bondpreis |
| $MWV_t$ | Age-Pension+-Maximum Withdrawal Value |
| $GV$ | Guarantee Value $=PV(Claims)-PV(LIP)$ |
| $BEL_{NU}$ | Non-unit Best Estimate Liability der Engine |
| $VNB_{gross}$ | risikoneutraler Versichererwert vor Risk Margin |
| $RM$ / $SCR$ | Risk-Margin- / Stresskapital-Research-Proxy |
| $PVFP$ | Present Value of Future Profits |
| $Q$ / $P$ | risikoneutrales / Real-World-Maß |
