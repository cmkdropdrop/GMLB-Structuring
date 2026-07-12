---
title: "AGILE Modelling"
subtitle: "Produktmechanik, marktkonsistente Bewertung, Risiko, Kapital und Profitabilität — eine wissenschaftliche Lernunterlage zur Research Engine 1.3.0"
author: "Interne Fach- und Lernunterlage"
date: "11. Juli 2026"
lang: de-DE
bibliography: AGILE_Modelling_references.bib
link-citations: true
reference-section-title: Literaturverzeichnis
toc-title: Inhaltsverzeichnis
---

> **Dokumentstatus.** Dieses Paper erklärt die technischen Grundlagen und die
> Ergebnisse der lokalen AGILE Modelling Engine. Es ist weder Produktberatung
> noch eine Preis-, Reserve-, Bilanz- oder Kapitalfreigabe. Sämtliche
> Ergebniszahlen sind illustrative Modellresultate für genau einen
> New-Business-Modellpunkt. Geldbeträge sind, soweit nicht anders angegeben,
> australische Dollar (AUD). Stichtag der Produkt- und Modellquellen ist der
> 11. Juli 2026.

# Zusammenfassung

Allianz Guaranteed Income for Life (AGILE) verbindet eine indexgebundene
Ansparmechanik mit jährlichem Schutz gegen negative Indexrenditen und einer
später aktivierbaren lebenslangen Einkommensgarantie. Ökonomisch liegt das
Produkt damit näher an einer **Fixed Indexed Annuity mit Guaranteed Lifetime
Withdrawal Benefit (GLWB)** als an einer klassischen fondsgebundenen Variable
Annuity, einer sofort beginnenden Leibrente oder einem reinen
Langlebigkeits-Pool. Rechtlich ist AGILE eine australische
Lebensversicherungsstruktur unter einer Group Policy; die garantierten
Leistungen sind Verpflichtungen von Allianz Australia Life aus Statutory Fund
No. 2 [vgl. @allianz2026pds, S. 2].

Dieses Paper rekonstruiert den Modellierungsweg von den vertraglichen
Cashflows über die stochastischen Markt- und Mortalitätsmodelle bis zu
Bewertung, Kapitalproxy, Profitabilität, Sensitivitäten und optimalem
Verhalten. Es trennt vier Ebenen, die in der Praxis leicht vermischt werden:

1. **Vertragstatsachen** aus Product Disclosure Statement (PDS), Juli-2026-
   Ratecard und Guaranteed Minimums;
2. **Modellannahmen** wie Zinskurve, Volatilität, Mortalität, Verhalten und
   Kosten;
3. **numerische Resultate** der Engine für einen konkret definierten
   Modellpunkt; und
4. **Interpretationen**, deren Gültigkeit von Kalibrierung, Datenqualität und
   Modellvollständigkeit abhängt.

Die Engine verwendet eine monatliche Zustandsprojektion, risikoneutrale
Monte-Carlo-Bewertung unter dem Maß (Q), Real-World-Projektionen unter (P),
eine statische Optionsreplikation der jährlichen Crediting Payoffs, einen
Heston-COS-Pricer für den Daily-Value-Adjustment-(DVA-)Hedgewert,
wahrscheinlichkeitsgewichtete Mortalitäts- und Stornodekremente sowie ein
separates jährliches Least-Squares-Monte-Carlo-(LSMC-)Modul für optimales
Verhalten. Die Buchungsidentität der Engine verbindet Prämie,
Versicherungsleistungen, Garantieclaims, Gebühren und Margen und fungiert als
wichtige Reconciliation. Sie belegt interne Rechenkonsistenz, nicht die
Richtigkeit der nicht veröffentlichten Allianz-Adminformeln.

Für den neu gerechneten, instrumentierten 1.3.0-Basislauf — Mann, Eintrittsalter
65, AUD 100.000, 100 % Australian Equity Total Protection, Fixed Income ab
Alter 70, Black--Scholes, 4.000 Pfade, Seed 2026 — ergibt sich ein Gross VNB
von **−AUD 1.228** beziehungsweise −1,23 % der Prämie. Nach dem
Solvency-II-artigen Risk-Margin-Proxy beträgt der modellierte VNB **−AUD
5.915**. Die belastete Lifetime Income Premium (LIP) von 1,15 % p. a. liegt
unter dem modellierten fairen Rider-Satz von 3,00 % p. a.; der isolierte
Guarantee Value beträgt deshalb +AUD 10.080 aus Sicht der Verpflichtung. Der
Kapitalproxy beträgt AUD 17.205 und wird vor allem vom Zinsschock nach unten
getrieben. Der PVFP bei 8 % Hurdle Rate ist mit −AUD 12.899 negativ.

Diese Zahlen sind **keine Aussage über das reale AGILE-Portfolio**. Sie beruhen
auf nicht kalibrierten Markt-, Mortalitäts-, Verhaltens- und Kostenannahmen,
enthalten kein APRA/LAGIC-Modul und können keine In-force-Policen abbilden. Der
Vergleich mit dem alten 1.2.0-Ergebnis zeigt zudem erhebliches
Implementation Risk: Der Gross VNB änderte sich durch Modellkorrekturen um
−AUD 2.970 und wechselte das Vorzeichen; diese Bewegung ist rund 70-mal so groß
wie der Monte-Carlo-Standardfehler des neuen Basislaufs.

Die aktuelle Qualitätsprüfung reproduzierte zwar **122 bestandene Tests**, fand
aber zugleich eine nicht getestete Integrationslücke: `pricing.greeks()`
versucht ein Feld eines unveränderlichen `ScenarioSet` zu überschreiben und
bricht mit `FrozenInstanceError` ab. Der neue Analyse-Pack wurde daher ohne
Quellcodeänderung mit einem transparent dokumentierten Laufzeit-Workaround
erzeugt. Gerade dieser Befund ist eine zentrale Lernbotschaft: Eine grüne
Unit-Test-Suite ersetzt weder End-to-End-Tests noch Modellgovernance,
Kalibrierung und unabhängige Ergebnisreconciliation.

**Schlüsselwörter:** AGILE; GLWB; Fixed Indexed Annuity; marktkonsistente
Bewertung; Monte Carlo; Heston; Hull--White; COS-Methode; Mortalität;
Policyholder Behaviour; LSMC; VNB; PVFP; Solvency II; APRA/LAGIC; Model Risk.

# 1. Zielsetzung und Forschungsfragen

## 1.1 Ziel des Dokuments

Das Ziel ist eine eigenständig nutzbare Lernunterlage, die nicht nur
Ergebnisse wiedergibt, sondern deren Entstehung erklärt. Nach der Lektüre
sollte nachvollziehbar sein,

- welche Produktrechte und Cashflows für die Bewertung relevant sind;
- wie Annual Return, Cap, Partial Protection, DVA, MVA und Lifetime Income
  mathematisch zusammenhängen;
- warum (Q)-Bewertung und (P)-Profitabilität unterschiedliche Fragen
  beantworten;
- wie Markt-, Mortalitäts- und Verhaltensrisiken in die Projektion eingehen;
- wie BEL, Guarantee Value, Gross VNB, VNB nach Risk Margin, PVFP und SCR-Proxy
  definiert sind;
- welche Ergebnisse der vorliegende Modellpunkt liefert und wie sie zu
  interpretieren sind; und
- an welchen Stellen die Engine wissenschaftlich plausibel, numerisch
  validiert, nur approximativ oder noch nicht produktionsfähig ist.

## 1.2 Forschungsfragen

Das Paper untersucht fünf Fragen:

1. Wie lässt sich die vertragliche AGILE-Mechanik in eine eindeutige Folge von
   Zuständen, Ereignissen und Cashflows übersetzen?
2. Welche stochastischen Modelle und numerischen Verfahren sind für die
   eingebetteten langfristigen Optionen geeignet?
3. Welche ökonomischen Risiko- und Werttreiber zeigt der illustrative
   Juli-2026-Modellpunkt?
4. Wie robust sind die Ergebnisse gegenüber Szenarien, Modellwahl,
   Zufallsseed und Implementierungsversion?
5. Welche zusätzlichen Daten, Modelle und Kontrollen wären für produktive
   Preis-, Reserve-, Hedge- oder Kapitalanwendungen erforderlich?

## 1.3 Abgrenzung

Nicht Gegenstand sind eine individuelle Geeignetheitsprüfung, Steuerberatung,
eine Prognose für einen konkreten Kunden, eine Bilanzierung nach AASB/IFRS 17
oder eine regulatorische Kapitalberechnung nach APRA/LAGIC. Ebenfalls nicht
bewertet wird das gesamte Allianz-Portfolio; die Engine startet jede Police am
Issue Date und kennt keinen In-force-Zustand.

# 2. Untersuchungsdesign und Evidenzhierarchie

## 2.1 Quellenklassen

Für wissenschaftlich belastbare Aussagen wird folgende Hierarchie verwendet:

| Rang | Quellenklasse | Zweck | Zentrale Einschränkung |
|---:|---|---|---|
| 1 | Offizielles PDS und offizielle Rate Sheets | Vertragsmechanik, Gebühren, Raten, Floors | Produktunterlagen können aktualisiert werden; Vintage ist zwingend |
| 2 | Primärliteratur und Prudential Standards | Bewertungsmethoden, stochastische Modelle, regulatorischer Rahmen | Allgemeine Methoden sind nicht automatisch produktspezifisch |
| 3 | Ausgeführter Quellcode 1.3.0 | Tatsächliche Rechenlogik | Implementierung kann von Dokumentation oder Vertrag abweichen |
| 4 | Tests, Methodology und Audit Report | Validierung, bekannte Fehler und Limitationen | Lokaler Audit ohne benannten externen Herausgeber ist kein formales Third-Party-Gutachten |
| 5 | Ergebnis-CSV, Manifest und Grafiken | Numerische Resultate | Nur für den dokumentierten Modellpunkt und Run gültig |
| 6 | Interne Synthesen (`AGILE.md`, Literaturindex) | Orientierung und Themenlandkarte | Sekundärquellen; Aussagen werden nicht ungeprüft als Produktfakt übernommen |

Die Produktmerkmale werden deshalb gegen PDS und Rate Sheets zitiert
[@allianz2026pds; @allianz2026rates; @allianz2026minimums]. Die mathematische
Einordnung stützt sich auf die GMxB-/GLWB-Literatur
[@bauer2008; @kling2014; @huangkwok2016; @shevchenkoluo2017]. Die tatsächliche
Modelllogik wird am aktuellen Code nachvollzogen [@agileengine2026], während
der Audit Report vor einer Fortschreibung älterer Ergebniszahlen warnt
[@agileaudit2026].

## 2.2 Reproduzierbarkeit des Zahlenlaufs

Der aktuelle Zahlenlauf liegt unter
`AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/`.
Seine wesentlichen Metadaten sind:

| Merkmal | Wert |
|---|---|
| Engine-Version | 1.3.0 |
| Modell | Black--Scholes, deterministische Zinskurve |
| Basis-Pfadzahl | 4.000 |
| Seed | 2026 |
| Python / NumPy / SciPy | 3.11.9 / 2.2.3 / 1.13.1 |
| Generierung | 11. Juli 2026, 05:16 UTC |
| Laufzeit | 83,6 Sekunden |
| Engine-Source-Hash | `503b509175810f3e7a9105c372d7ae6e6741d3cb4178461382305dcbaa360e46` |
| Scope | Illustrative New-Business Research; nicht APRA/LAGIC |

Der Quellcode-Hash erfasst **nicht** den nur im Python-Prozess vorgenommenen
Greek-Workaround. Daher wird der Lauf bewusst als *instrumentierte
Reproduktion* und nicht als unverändert reproduzierbarer Standardlauf
bezeichnet. Abschnitt 12.4 dokumentiert Ursache und Workaround.

## 2.3 Wissenschaftliche Vorsichtsregeln

Im gesamten Dokument gelten vier Konventionen:

1. Ein Resultat ohne Angabe von Modellpunkt und Annahmen ist unvollständig.
2. Ein Vorzeichen in einer Einfaktor-Sensitivität ist keine universelle
   ökonomische Gesetzmäßigkeit.
3. Eine interne Buchungsidentität ist kein Nachweis der Vertragsrichtigkeit.
4. Eine niedrige Monte-Carlo-Streuung deckt weder Parameter-, Modell- noch
   Implementierungsrisiko ab.

# 3. Produktökonomik und Vertragsmechanik

## 3.1 Rechtliche und ökonomische Einordnung

AGILE wird von Allianz Australia Life Insurance Limited ausgegeben. Die
Investments werden Statutory Fund No. 2 zugeordnet. Die Group Policy wird an
Allianz Australia Life Policy Services ausgegeben; der Investor erhält ein
wirtschaftliches Interesse und die im Investor Certificate dokumentierten
Leistungsrechte. Die Begriffe Investor, Life Insured und gegebenenfalls
Surviving Spouse sind deshalb auseinanderzuhalten [@allianz2026pds, S. 2].

Ökonomisch besteht das Produkt aus zwei Phasen:

1. **Growth Phase:** Das Investment Value erhält jährlich eine begrenzte,
   geschützte Indexgutschrift. Der Kunde trägt kein direktes Fondsanteilskonto;
   das Produkt ist *indexed*, nicht *unit-linked*.
2. **Lifetime Income Phase:** Nach frühestens einem Jahr kann ein lebenslanges
   monatliches Einkommen aktiviert werden. Das Einkommen kann nach
   Erschöpfung des Investment Value weiterlaufen; genau diese Fortzahlung
   erzeugt den Versicherungsclaim.

Die Klassifikation als FIA plus GLWB ist eine ökonomische Modellabstraktion,
nicht die rechtliche Produktbezeichnung. Die klassische GMxB-Literatur liefert
hierfür einen konsistenten Rahmen aus Account, Garantie, Tod, Rückkauf und
Entnahmeoptionen [@bauer2008].

## 3.2 Protected Investment Options

In der Growth Phase stehen vier Kombinationen zur Verfügung:

| Region / Index | Total Protection | Partial Protection: Initial 10 % |
|---|---:|---:|
| Australian Equity | Maximum Return 6,20 % | Maximum Return 13,00 % |
| Global Equity | Maximum Return 6,00 % | Maximum Return 12,80 % |

Die Werte gelten für Commencement Dates im Juli 2026 und werden an jedem
Anniversary Date neu festgesetzt. Sie sind vor Product Fee, Lifetime Income
Premium und Steuern angegeben [@allianz2026ratescentre]. Die im Investor
Certificate fixierten Guaranteed Minimums betragen 0,25 % für Total Protection
und 0,50 % für Partial Protection [@allianz2026minimums]. Für In-force-Policen
sind daher nie pauschal die aktuellen New-Business-Werte zu verwenden.

## 3.3 Annual-Return-Payoffs

Sei

\[
R=\frac{S_T}{S_0}-1
\]

die Point-to-Point-Rendite des maßgeblichen Return Index über ein
Crediting-Jahr und (C\ge 0) der Maximum Return. Dann modelliert die Engine
Total Protection als

\[
c_{\mathrm{TP}}(R)=\min\{\max(R,0),C\}.
\]

Die Kundenrendite liegt damit zwischen null und dem Cap. Partial Protection
mit 10-%-Buffer lautet

\[
c_{\mathrm{PP10}}(R)=
\begin{cases}
\min(R,C), & R\ge 0,\\
\min(0,R+0{,}10), & R<0.
\end{cases}
\]

Beispiele:

| Indexrendite | Total Protection bei 6,20 % Cap | Partial Protection bei 13,00 % Cap |
|---:|---:|---:|
| +15 % | +6,20 % | +13,00 % |
| +6 % | +6,00 % | +6,00 % |
| −5 % | 0,00 % | 0,00 % |
| −10 % | 0,00 % | 0,00 % |
| −18 % | 0,00 % | −8,00 % |

Total Protection ist wegen des stärkeren Floors typischerweise mit einem
niedrigeren Cap verbunden. Der Cap ist keine erwartete Rendite, sondern der
obere Rand eines nichtlinearen Payoffs.

## 3.4 Statische Optionsreplikation

Mit (X=S_T/S_0), normiertem Strike 1 und Call-/Put-Werten (Call(K)) und
(Put(K)) kann der Credit als Optionspaket repliziert werden:

\[
V_{\mathrm{TP}}=Call(1)-Call(1+C),
\]

\[
V_{\mathrm{PP10}}=Call(1)-Call(1+C)-Put(0{,}90).
\]

Total Protection ist ein Bull Call Spread. Bei Partial Protection finanziert
der Kunde den höheren positiven Cap teilweise durch den Verkauf eines
10-%-out-of-the-money Put. Diese Zerlegung verbindet die Vertragsformel mit
Hedgekosten, DVA und Crediting Margin. Die Bewertung folgt zunächst der
klassischen arbitragefreien Optionslogik [@blackscholes1973; @merton1973].

## 3.5 Lifetime Income Rate

Beim Start der Lifetime Income Phase wird das jährliche Anfangseinkommen als

\[
I_0=IV_{\tau}^{\text{post fee}}\cdot g
\]

bestimmt. Die Rate (g) ist

\[
g=g_{\mathrm{base}}(x_0,\text{Geschlecht},\text{Optionen})
+n_{\mathrm{Growth}}\,e(x_0,\text{Fixed/Rising}).
\]

Maßgeblich sind Alter und Geschlecht am **Product Commencement Date**, nicht
das Alter beim späteren Income Start. Bei Spouse Income bestimmt das jüngere
Leben einschließlich dessen Geschlecht die Rate. Nur vollständige Jahre in
der Growth Phase zählen als Escalator-Jahre [@allianz2026rates, S. 1--2].

Für den Basismodellpunkt — männlich, Alter 65, Single Fixed, fünf vollständige
Growth-Jahre — lautet die Juli-2026-Rechnung:

\[
g=7{,}05\%+5\times0{,}35\%=8{,}80\%.
\]

Die Rate von 8,80 % ist auf das Investment Value zum Income Start anzuwenden;
sie ist weder Renditegarantie auf die ursprüngliche Prämie noch ein
Marktzinssatz.

## 3.6 Fixed und Rising Income

Bei Fixed Income bleibt das jährliche nominale Einkommen konstant, solange
keine reduzierende Excess Withdrawal erfolgt. Bei Rising Income ist die
Start-Rate niedriger. Das Einkommen wird an einem Income Anniversary um den
positiven Credit der Australian Equity Total Protection Option erhöht:

\[
I_{a+1}=I_a\,[1+c_{\mathrm{AUS,TP},a}].
\]

Wegen Total Protection fällt der Ratchet nicht aufgrund negativer
Indexperformance. Rising Income ist dennoch **keine CPI-Indexierung**; die
Steigerung hängt von Indexperformance und Cap ab. Das PDS bestätigt, dass
erreichte Zahlungen nicht wegen negativer Marktbewegungen sinken
[@allianz2026pds, S. 21 und 73].

## 3.7 Gebühren

Die offiziellen laufenden Belastungen sind:

- Product Fee: 0,30 % p. a.;
- Lifetime Income Premium: 1,15 % p. a.

Beide werden vertraglich täglich auf das Investment Value ohne DVA Amount und
ohne bereits aufgelaufene Gebühren berechnet und zu bestimmten Events
abgezogen [@allianz2026pds, S. 41]. Die Engine approximiert dies monatlich:

\[
Fee_m\approx IV_{\mathrm{frame},m}\frac{f}{12}.
\]

Das ist für eine Research-Projektion praktikabel, aber kein Ersatz für eine
Admin-Reconciliation der täglichen Accrual- und Event-Deduction-Regeln. Bei
Age Pension+ entfällt die LIP erst ab dem späteren Zeitpunkt aus Income Start
und Pension Age beziehungsweise Relevant Condition of Release
[@allianz2026pds, S. 41].

## 3.8 Withdrawals, MVA und DVA

In der Growth Phase besteht grundsätzlich ein jährlicher Free Withdrawal
Amount von 5 % des anfänglichen Investment Amount, ohne Übertrag ungenutzter
Beträge. Excess Withdrawals und Full Withdrawals können in den ersten zehn
Jahren einer Market Value Adjustment (MVA) unterliegen. In der Income Phase
reduzieren Excess Withdrawals das künftige Einkommen proportional zum
Bruttoabzug einschließlich MVA [@allianz2026pds, S. 24 und 32--33].

Die Engine verwendet den unkalibrierten Zinsproxy

\[
f_{\mathrm{MVA}}(t)=
1-\left(\frac{1+z_{\mathrm{issue}}+s}{1+z_t+s}\right)^{\tau}
+\lambda_0+\lambda_1\tau,
\]

wobei (	au) die Restlaufzeit des Zehnjahresfensters ist. Bei der
Default-Einstellung kann die MVA den Auszahlungswert nur reduzieren.
Allianz veröffentlicht keine vollständige Produktionsformel; die Parameter
müssen daher an echte Transaktionsquotes kalibriert werden.

Die DVA bewertet unterjährige Transaktionen zwischen Anniversary Dates. Das
PDS beschreibt sie als unterjährige Berechnung des Returns, verweist aber auf
eine produktinterne Bewertungsmechanik [@allianz2026pds, S. 33]. Die Engine
setzt hierfür einen Hedgewertproxy ein:

\[
p_z(t)=P(t,T_{\mathrm{anniv}})+V_{\mathrm{package}}(t).
\]

Am Anniversary konvergiert der Faktor zu (1+c(R)). Der vertragliche
zeitanteilige Protection Floor und ein möglicher Fixed-Return-Zweig sind in
diesem Proxy noch nicht implementiert.

## 3.9 Tod, Spouse und Age Pension+

Der Death Benefit entspricht grundsätzlich dem positiven Investment Value zum
Zahlungszeitpunkt; auf Tod fällt keine MVA an [@allianz2026pds, S. 14 und 25].
Mit Spouse Insured kann das Einkommen nach dem Tod des primären Life Insured
für das überlebende Leben fortgesetzt werden oder — je nach modellierter
Election — eine Lump-Sum-Leistung entstehen.

Age Pension+ begrenzt Kapitalzugriff und Todesfallleistung über eine Capital
Access Schedule (CAS). Im Modell läuft der Maximum Withdrawal Value bei Basis
(B), verstrichener Zeit (e_t), Lebenserwartung (LE) und bereits erfolgten
Entnahmen (W_t) linear ab:

\[
MWV_t=\max\left\{B\left(1-\frac{e_t}{LE}\right)-W_t,0\right\}.
\]

Diese Mechanik kann Social-Security-Eigenschaften beeinflussen, ist aber kein
kostenloser Zusatzschutz: geringerer Kapitalzugriff und Death Cap verändern
Kunden- und Versicherercashflows. Für Production muss die vertragliche
CAS-Lebenserwartung im Model Point vorgegeben werden; die Ableitung aus der
illustrativen Best-Estimate-Mortalität ist nur ein Fallback.

# 4. Modellarchitektur und Zustandsmaschine

## 4.1 Modulare Verarbeitungskette

Die Engine trennt Produkt, Markt, Projektion und Auswertung:

| Modul | Fachliche Rolle |
|---|---|
| `product.py` | Produktparameter, Ratecard, Caps, Fees, Withdrawals, MVA, APS und Model Point |
| `curves.py` | Zero Curve, Diskontfaktoren und Forward Rates |
| `esg.py` | Black--Scholes, Heston, Hull--White und hybride Szenarien unter (Q) und (P) |
| `crediting.py` | Payoffs, Optionsreplikation, DVA, COS-Pricer und Fair-Cap-Hilfen |
| `mortality.py` | generational Mortalität, Joint Life, Lebenserwartung und Annuitätenfaktoren |
| `behavior.py` | statisches und dynamisches Storno, Take-up und Entnahmen |
| `projection.py` | monatliche Vertrags- und Cashflow-State-Machine |
| `pricing.py` | (Q)-Bewertung, BEL, Fair LIP und Greeks |
| `capital.py` | Solvency-II-artiger Stress- und Risk-Margin-Proxy |
| `profitability.py` | (P)-Cashflows, Reserve-/Kapital-Runoff, VNB und PVFP |
| `sensitivities.py` | standardisierte Einfaktoranalysen |
| `lsmc.py` | separates optimales Verhalten auf Jahresraster |

Diese Modularität verbessert Nachvollziehbarkeit und Testbarkeit. Sie erzeugt
aber auch Integrationsrisiken, wenn sich Schnittstellen — etwa die
Mutabilität von Szenarien — ändern.

## 4.2 Zustände

Die monatliche Projektion kennt drei Hauptzustände:

\[
\text{Growth}\longrightarrow\text{Income}\longrightarrow\text{Out}.
\]

`Out` ist absorbierend. Tod und Full Surrender führen aus Growth oder Income
in diesen Zustand. Anders als eine binäre Life-by-Life-Simulation führt die
Engine Mortalität und Storno als Wahrscheinlichkeitsgewichte. Dadurch werden
Cashflows mit In-force-Wahrscheinlichkeiten multipliziert und die
Monte-Carlo-Varianz sinkt.

## 4.3 Ereignisreihenfolge im Monatsraster

Die Reihenfolge ist ökonomisch materiell:

1. Marktbewegung und Aktualisierung des DVA-Wertes;
2. am Anniversary: Annual Credit und gegebenenfalls Rising Ratchet;
3. Gebührenabzug;
4. Income Election auf der Post-Fee-Basis und Neustart des Crediting-Zyklus;
5. Tod; Death Benefit basiert auf dem Wert vor der nachschüssigen Zahlung;
6. monatliche Income-Zahlung nur an bis zum Zahlungstermin Überlebende;
7. geplante Partial Withdrawals;
8. Lapse beziehungsweise Full Withdrawal.

Ein Wechsel der Reihenfolge kann Income Base, Death Benefit, Claims, Fees und
MVA verändern. Die auditierten Korrekturen der Engine betreffen genau solche
Timing-Fragen [@agileaudit2026].

## 4.4 Zustandsvariablen

Zu den zentralen Pfadzuständen gehören:

- Investment Value und DVA-Frame;
- jährliches Locked Income;
- Phase und In-force-Gewicht;
- Indexstände am Anfang des Crediting-Jahres;
- Cap-Vintage beziehungsweise Schedule;
- verbrauchter Free Withdrawal Amount;
- APS/CAS-Basis, Startzeit und verbleibender MWV;
- Survival-Zustände für Primary Life und Spouse; und
- Marktvariablen (S_t), gegebenenfalls (v_t) und (r_t).

Die Engine kann diese Zustände ab Issue aufbauen, aber nicht aus einem
beliebigen In-force-Snapshot initialisieren. Das ist ein zentraler
Production-Blocker.

# 5. Marktmodelle und numerische Optionsbewertung

## 5.1 (Q)-Maß und (P)-Maß

Unter dem risikoneutralen Maß (Q) werden replizierbare Cashflows ohne
Risikoprämie bewertet. Der modellierte Present Value eines Cashflows (CF_t)
ist

\[
PV_Q(CF)=\mathbb{E}^{Q}\!\left[D_tCF_t\right],\qquad
D_t=\exp\left(-\int_0^t r_s\,ds\right).
\]

Unter dem Real-World-Maß (P) wird der Equity Drift um eine angenommene
Risikoprämie erhöht. Dieses Maß dient der erwarteten Profit-Signature und den
Kunden-Outcome-Verteilungen, nicht der arbitragefreien Bewertung. Die
Trennung ist fundamental:

- (Q) beantwortet: *Welchen heutigen Marktwert haben die finanzierten
  Cashflows unter den Modellannahmen?*
- (P) beantwortet: *Wie könnten Cashflows und Kapitalpfade unter einer
  angenommenen realen Renditeverteilung verlaufen?*

Die Engine teilt derzeit Heston-Varianz- und Hull--White-Zinsparameter zwischen
(P) und (Q); nur der Equity Drift unterscheidet sich. Fehlende
Volatilitäts- und Zinsrisikoprämien begrenzen die Profitabilitätsaussage.

## 5.2 Zinskurve

Die kontinuierlich verzinste Zero Rate (z(t)) wird zwischen den gelieferten
Tenoren linear interpoliert und außerhalb flach extrapoliert. Es gilt

\[
P(0,t)=e^{-z(t)t}.
\]

Für den Basislauf werden die Punkte 1, 2, 5, 10, 20 und 30 Jahre mit 3,80 %,
3,90 %, 4,10 %, 4,30 %, 4,40 % und 4,40 % verwendet. Diese Kurve ist
illustrativ und nicht als datierte Markt-Kalibrierung dokumentiert.

## 5.3 Black--Scholes

Unter (Q) folgt jeder Return Index im Basismodell

\[
\frac{dS_{i,t}}{S_{i,t}}=(r_t-q_i)dt+\sigma_i\,dW_{i,t}^{Q}.
\]

Die Vertragsindizes sind Return-Indizes; der Default-Carry (q_i) ist daher
null. Eine frühere Engine-Version verwendete Dividend Yields und zählte die
Dividenden dadurch doppelt. Im Basislauf gelten (sigma_{AUS}=16\%),
(sigma_{Global}=15\%) und eine Equity-Korrelation von 0,75.

Black--Scholes ist transparent und effizient, bildet aber Smile, Skew und
stochastische Zinsen nicht ab. Für langfristige GLWB-Verpflichtungen kann diese
Vereinfachung materiell sein [@goudenege2016].

## 5.4 Heston

Das Heston-Modell ergänzt eine stochastische Varianz [@heston1993]:

\[
\frac{dS_t}{S_t}=(r_t-q)dt+\sqrt{v_t}\,dW_t^S,
\]

\[
dv_t=\kappa(\theta-v_t)dt+\xi\sqrt{v_t}\,dW_t^v,
\qquad d\langle W^S,W^v\rangle_t=\rho_{Sv}dt.
\]

Die Engine simuliert die Varianz per Full-Truncation Euler und den Index per
Log-Euler mit vier Substeps je Monat. Der negative Default
(ho_{Sv}=-0{,}60) beziehungsweise −0,65 erzeugt Equity Skew. Die Parameter
sind nicht an eine datierte Volatilitätsfläche kalibriert.

## 5.5 Hull--White

Für stochastische Zinsen verwendet die Engine ein Einfaktor-Hull--White-Modell
[@hullwhite1990], schematisch

\[
dx_t=-a x_tdt+\sigma_r dW_t^r,\qquad r_t=\phi(t)+x_t,
\]

wobei (phi(t)) die anfängliche Kurve fitten soll. Defaults sind
(a=0{,}03), (sigma_r=0{,}008) und eine Equity-Rate-Korrelation von −0,20.
Der BS--HW-Zweig simuliert Short Rate, integrierte Rate und Equity gemeinsam
gaußsch; der Heston--HW-Zweig ist ein hybrides Diskretisierungsschema.

## 5.6 COS-Methode unter Heston

Ein flacher Effective-Volatility-Ansatz kann den Heston-Skew nicht abbilden.
Die Engine bewertet deshalb die Crediting Packages bedingt auf (v_t) mit
der Fourier-Cosine-(COS-)Methode [@fang2008]. Für eine Dichte mit
charakteristischer Funktion (arphi(u)) und Intervall ([a,b]) wird der
Optionswert durch eine endliche Cosinusreihe approximiert:

\[
V\approx e^{-r\tau}\sum_{k=0}^{N-1}{}'
\operatorname{Re}\!\left[
\varphi\!\left(\frac{k\pi}{b-a}\right)
e^{-ik\pi a/(b-a)}
\right]U_k,
\]

wobei (U_k) die Payoff-Koeffizienten und der Strich das Halbgewicht des
ersten Terms bezeichnet. Default sind 128 Terme und ein breites
Truncation-Intervall. Alle Strikes eines Crediting Package teilen eine
Characteristic-Function-Auswertung. COS-Verfahren sind für GMxB-Bewertungen
auch in der Literatur etabliert [@alonsogarcia2018].

Der lokale Audit dokumentiert, dass die frühere Effective-Vol-Näherung das
Total-Protection-Package im illustrativen Heston-Fall um rund 35 bp p. a.
unterbewertete und dadurch VNB sowie Identity Gap verzerrte. Diese Zahl ist
ein enginespezifischer Testbefund, keine allgemeine Marktkonstante.

# 6. Mortalität, Verhalten und vertragliche Optionalität

## 6.1 Illustrative Mortalitätsbasis

Die Default-Mortalität ist eine synthetische Gompertz--Makeham-Tabelle. Für
Alter (x) wird die Force of Mortality als

\[
\mu(x)=A+Bc^x
\]

modelliert. Daraus folgt

\[
q_x=1-\exp\left(-\int_x^{x+1}\mu(u)\,du\right).
\]

Die Parameter sollen lediglich die Form einer australischen Lebenstafel
annähern. Sie sind weder eine offizielle ALT-2020--22-Tabelle noch eine
Allianz-spezifische Pricing- oder Reservierungsbasis. Im Run Manifest ist das
Basisjahr 2022, die jährliche Improvement Rate beträgt 1,25 %, mit Taper ab
Alter 90 und Ende bei 110.

Generational wird vereinfacht gerechnet:

\[
q(x,y)=q_x[1-i(x)]^{\max(y-y_0,0)}\,s,
\]

wobei (i(x)) die altersabhängige Verbesserung und (s) einen Stressfaktor
bezeichnet. Die monatliche Todeswahrscheinlichkeit unter konstanter Hazard im
Jahr lautet

\[
q_x^{(m)}=1-(1-q_x)^{1/12}.
\]

Diese deterministische generational Mortalität bildet idiosynkratische
Erwartungswerte ab, aber kein systematisches Langlebigkeitsrisiko. Gerade bei
lang laufenden GLWB-Cashflows können Mortalitätsmodell und Mortality Risk
Premium materiell sein [@piscopo2011; @fung2014; @cairns2006].

## 6.2 Joint Life

Unter angenommener Unabhängigkeit der beiden Leben ist die
Last-Survivor-Wahrscheinlichkeit

\[
{}_tp_{LS}={}_tp_1+{}_tp_2-{}_tp_1{}_tp_2.
\]

Im Monatsmotor wird die Joint-Life-Betrachtung ab der tatsächlichen Spouse-
Income-Election konditioniert. Der Projektionshorizont reicht standardmäßig
bis zum terminalen Alter 115 des länger laufenden gedeckten Lebens. Diese
Punkte sind wichtig, weil eine zu frühe oder unkonditionierte
Joint-Life-Mortalität den Tail der lebenslangen Zahlungen abschneidet.

## 6.3 Statisches und dynamisches Storno

Im Basisfall gelten illustrative jährliche Growth-Lapse-Raten von 3,0 % im
ersten Jahr, ansteigend bis 4,0 % und später fallend auf 2,0 %; in der Income
Phase beträgt die Rate 0,5 % p. a. Die Engine transformiert sie in monatliche
Wahrscheinlichkeiten.

Dynamisches Verhalten skaliert die Basisrate über Moneyness. In der Income
Phase ist

\[
M_t=\frac{PV_t(\text{garantiertes Einkommen})}{SV_t},
\]

und

\[
m_t=\operatorname{clip}
\{1-\beta(M_t-M_0),m_{\min},m_{\max}\}.
\]

Eine tief im Geld liegende Garantie führt damit zu weniger Storno. In der
Growth Phase wird analog der MVA-Abschlag berücksichtigt. Die Form ist von der
Behaviour-Literatur motiviert [@kling2014], ihre Parameter sind jedoch nicht
empirisch für AGILE geschätzt.

## 6.4 Income Take-up

Die Engine unterstützt deterministischen Start oder eine Hazard-Kurve. Im
Basislauf ist der Start deterministisch nach fünf Jahren; die im Objekt
gespeicherte Hazard-Kurve ist deshalb inaktiv. Sensitivitäten „Take-up ±2
Jahre“ verschieben faktisch diesen vertraglichen Start und sind keine
Schätzung einer echten Kundenwahrscheinlichkeit.

## 6.5 Partial Withdrawals

Eine dynamische Withdrawal Utilisation kann ebenfalls von Moneyness abhängen:

\[
u_t=\operatorname{clip}
\{1-\gamma(M_t-M_0),u_{\min},u_{\max}\}.
\]

Zusätzlich dämpft

\[
u_t^{MVA}=\operatorname{clip}(1-\gamma_{MVA}f_{MVA,t},0,1)
\]

Entnahmen, wenn die MVA hoch ist. Der Basislauf setzt geplante Free und Excess
Withdrawals auf null; die Verhaltensflächen variieren diese Annahmen.

## 6.6 Warum Verhalten ein eigenes Risiko ist

Verhalten ist weder rein versicherungstechnisch noch rein finanziell. Ein
Storno kann Gebühren und zukünftige Margen vernichten, zugleich aber eine im
Geld liegende Garantie beenden. Eine Entnahme zahlt Liquidität aus, reduziert
jedoch Investment Value und gegebenenfalls Locked Income. Das Vorzeichen hängt
deshalb von Phase, Moneyness, MVA, Gebühren und Garantie ab. Optimales
Verhalten im Bewertungsmodell bedeutet zudem nur Maximierung des modellierten
Vertragswerts, nicht psychologisch oder empirisch realistisches Handeln
[@kling2014].

# 7. Marktkonsistente Bewertung und Reconciliation

## 7.1 Cashflow-Komponenten

Die Projektion führt unter anderem folgende Barwertkomponenten:

- Kundenleistungen: Income, Death Benefit, Surrender Benefit und Partial
  Withdrawals;
- Versichererfinanzierung: Product Fees, LIP, Crediting Margin sowie
  einbehaltene MVA-/APS-Beträge;
- Versichereraufwand: Guarantee Claims und Expenses; und
- Premium als Time-0-Cashflow.

Ein Guarantee Claim entsteht, wenn eine fällige Income-Zahlung nicht mehr aus
dem Investment Value finanziert werden kann. Die Gesamtzahlung an den Kunden
ist damit nicht mit dem Claim gleichzusetzen.

## 7.2 BEL und Versichererwert

Der Non-unit BEL ist

\[
\begin{aligned}
BEL_{NU}={}&PV_Q(Claims)+PV_Q(Expenses)\\
&-PV_Q(Product\ Fees)-PV_Q(LIP)\\
&-PV_Q(Crediting\ Margin)-PV_Q(MVA/APS).
\end{aligned}
\]

Der Total BEL der Einzelpolice wird als

\[
BEL_{total}=P_0+BEL_{NU}
\]

ausgegeben. Der Gross VNB beziehungsweise `insurer_net_value` vor Risk Margin
ist das negative Gegenstück zum Non-unit BEL:

\[
VNB_{gross}=-BEL_{NU}.
\]

Diese Vorzeichenkonvention muss beim Lesen der Tabellen beachtet werden.

## 7.3 Guarantee Value und Fair LIP

Der isolierte Riderwert ist

\[
GV=PV_Q(Guarantee\ Claims)-PV_Q(LIP).
\]

(GV>0) bedeutet, dass die LIP den Claimbarwert im Modell nicht vollständig
deckt. Es bedeutet nicht automatisch, dass das Gesamtprodukt im gleichen
Umfang verlustreich ist, denn Product Fee, Crediting Margin und MVA können
gegenfinanzieren.

Der faire LIP-Satz (f^*_{LIP}) löst

\[
GV(f^*_{LIP})=0.
\]

Die Engine verwendet ein Brent-Nullstellenverfahren mit Common Random Numbers.
Der faire Rider-Satz ist kein Gesamtprodukt-Break-even und darf nicht ohne
Kalibrierung mit einer kommerziellen Preisentscheidung gleichgesetzt werden.

## 7.4 Crediting Margin

Zu Beginn eines Crediting-Jahres ist das Replikationsportfolio pro Einheit
Investment Value (p_z(s)\le 1). Die Engine bucht

\[
CM_s=IV_{frame,s}[1-p_z(s)]
\]

als Time-(s)-Marge. Der äquivalente Utility-Jahresendsatz lautet

\[
m=(1-V_{package})e^{r_{fwd}}-1.
\]

Diese Marge ist eine modellierte Cap-Budget-Differenz. Ohne echte Hedgepreise,
Transaktionskosten und Cap-Management-Regel ist sie keine beobachtete Marge
des Versicherers.

## 7.5 Marktwertidentität

Die zentrale Reconciliation ist

\[
\begin{aligned}
P_0={}&PV_Q(Income+Death+Surrender+Partial\ Withdrawals)\\
&-PV_Q(Guarantee\ Claims)\\
&+PV_Q(Fees+Crediting\ Margin+MVA+APS).
\end{aligned}
\]

Die relative Abweichung

\[
Gap=\frac{PV_Q(finanzierte\ Cashflows)-P_0}{P_0}
\]

sollte bis auf Monte-Carlo- und Diskretisierungsfehler nahe null sein. Ein
kleiner Gap zeigt, dass keine wesentliche Finanzierungsposition in der
Engine-Buchung verloren geht. Er sagt nicht, ob DVA, MVA, Mortalität oder
Gebühren den echten Vertrag korrekt abbilden.

# 8. Kapitalproxy und Profitabilität

## 8.1 Standalone-Stressverluste

Der Kapitalproxy berechnet für jeden Schock

\[
SCR_i=\max\{0,NAV_{base}-NAV_i^{stress}\}.
\]

Die Module umfassen Interest, Equity, Equity Volatility, Mortality,
Longevity, Lapse, Expenses und Catastrophe. Die Aggregation erfolgt über eine
Korrelationsmatrix:

\[
SCR=\sqrt{\mathbf{s}^{\top}\mathbf{C}\mathbf{s}}.
\]

Der Lapse SCR ist das Maximum aus Up, Down und Mass Lapse. Mass Lapse wird nur
als (40\%\times\max(NAV,0)) approximiert und nicht als vollständige
Surrender-State-Revaluation gerechnet.

## 8.2 Risk Margin

Der Research-Proxy verwendet 6 % Cost of Capital auf einen proportionalen
Runoff des Life SCR:

\[
RM=CoC\sum_t SCR_{life}(t)P(0,t+1).
\]

Marktrisiko wird dabei als hedgebar ausgeschlossen. Diese Konvention erklärt,
warum die Risk Margin nicht proportional zum gesamten BSCR sein muss.

## 8.3 Warum der Proxy nicht APRA/LAGIC ist

APRA LPS 110 verlangt Kapital auf Fund- und Entity-Ebene unter Einbezug von
Insurance, Asset, Asset Concentration und Operational Risk. Für
Variable-Annuity-Geschäft sieht der Standard eine genehmigte Methode vor
[@apra2023lps110]. LPS 114 behandelt Asset Risk aus On- und Off-Balance-Sheet-
Exposures und gilt in der aktuellen Fassung ab 1. Juli 2026
[@apra2026lps114].

Der Engine fehlen unter anderem:

- Statutory-Fund-Bilanz und Portfolioaggregation;
- Assets, Derivate, Hedgepositionen und Hedge Effectiveness;
- Credit, Default, FX, Inflation und Konzentrationen;
- Operational Risk und Combined Stress Scenario Adjustment; und
- APRA-spezifische Aggregation und Management Actions.

Ein Austausch einzelner Stressparameter kann diese Architektur nicht
ersetzen. Die Bezeichnung **BSCR-Research-Proxy** ist deshalb zwingend.

## 8.4 Real-World-Profit-Signature

Unter (P) wird pro Jahr die erwartete Versicherer-Cashflow-Signature
gebildet:

\[
Signature_y=Fees_y+CM_y+MVA_y+APS_y-Claims_y-Expenses_y.
\]

Die Reserveprojektion verwendet einen Certainty-Equivalent-Runoff der
risikoneutralen Cashflows, nicht Nested Stochastics. Für Jahr (y\ge 1) gilt
schematisch

\[
Profit_y=Signature_y+Interest(BEL_{y-1})-\Delta BEL_y.
\]

Distributable Earnings ergänzen Steuer, Kapitalertrag und Kapitalfreisetzung.
Bucket 0 enthält Time-0-Strain; Bucket (y\ge1) enthält Cashflows in
((y-1,y]).

## 8.5 Profitabilitätskennzahlen

Die wichtigsten Größen sind:

\[
VNB=VNB_{gross}-RM,
\]

\[
NBM=\frac{VNB}{P_0},
\]

\[
PVFP(h)=\sum_y\frac{DE_y}{(1+h)^y},
\]

sowie IRR und Payback Year der Distributable Earnings. Der Basislauf verwendet
8 % Hurdle Rate und 30 % Tax. Ein positiver nominaler kumulierter Runoff kann
bei hoher Hurdle Rate dennoch einen negativen PVFP erzeugen.

# 9. Optimales Verhalten mit Least-Squares Monte Carlo

## 9.1 Problem als stochastische Kontrolle

Vertragliche Wahlrechte machen den Wert pfad- und zustandsabhängig. Der
Policyholder vergleicht unmittelbare Ausübung mit dem bedingten Erwartungswert
des Fortsetzens. Formal erfüllt der Wert eine Bellman-Rekursion:

\[
V_n(X_n)=\max_{a\in\mathcal{A}(X_n)}
\left\{CF_n(X_n,a)+
\mathbb{E}^Q[D_{n,n+1}V_{n+1}(X_{n+1})\mid X_n,a]\right\}.
\]

Direkte Gitterverfahren werden bei mehreren Zustandsvariablen schnell teuer.
LSMC approximiert den Fortsetzungswert durch Regression
[@longstaffschwartz2001; @huangkwok2016].

## 9.2 Aktionsmengen

Das separate AGILE-LSMC verwendet jährlich:

- Growth: Continue, Start Income, Surrender, Free Withdrawal und Free plus
  Excess Withdrawal;
- Income: Continue, Surrender und Excess Withdrawal.

Damit geht die Aktionsmenge über eine reine Bang-Bang-Regel hinaus. Die
Withdrawal Fractions liegen auf einem diskreten Gitter, ähnlich den
Dynamic-Programming-Ansätzen der GMWB-Literatur [@shevchenkoluo2017].

## 9.3 Regressionsbasis und Adapted Policy

Die Features enthalten polynomiale Terme in normalisiertem Investment Value
und Income sowie gegebenenfalls Varianz- und Short-Rate-Zustände. Der Backward
Pass schätzt bedingte Fortsetzungswerte. Ein unabhängiger Forward Pass wählt
Aktionen ausschließlich auf Basis der Information zum Entscheidungszeitpunkt.
Realisierte Renditen des Folgejahres dürfen die Entscheidung nicht
vorwegnehmen.

Der out-of-sample-Wert dieser adapted Policy ist ein **Lower Bound** für den
wahren optimalen Policyholder Value. Er ist kein Liability Upper Bound. Fällt
die gelernte Policy unter den statischen Benchmark, greift die Implementierung
auf statisches Verhalten zurück. Daher ist die Prüfung „optimal ≥ static“
allein kein unabhängiger Qualitätsnachweis.

## 9.4 Grenzen des LSMC-Moduls

Das LSMC ist nicht in Standard-Pricing, Kapital oder Profitabilität integriert.
Es arbeitet jährlich, weist Age Pension+ und Off-anniversary Starts ab und
approximiert Gebühren, Income Timing und Tail Closeout. Die Aussage der
Methodology, Partial Withdrawals lieferten im Basisfall nur wenige Basispunkte
Zusatzoptionalität, ist eine illustrative Beobachtung; die Tests sichern nur
eine deutlich weitere Toleranz ab. Der sehr neue Deep-LSMC-Ansatz von
@langrene2026 ist ein methodischer Ausblick, aber noch kein unabhängiger
Produktionsbenchmark.

# 10. Fallstudie: Modellpunkt und Annahmen

## 10.1 Vertragsdaten

| Eingabe | Basisannahme |
|---|---:|
| Commencement | Mitte 2026 |
| Alter / Geschlecht | 65 / männlich |
| Funding Source | Non-superannuation |
| Initial Investment | AUD 100.000 |
| Growth Allocation | 100 % Australian Equity Total Protection |
| Maximum Return / Minimum | 6,20 % / 0,25 % |
| Income Start | nach 5 Jahren, Alter 70 |
| Income Type | Fixed |
| Rate | 7,05 % + 5 × 0,35 % = 8,80 % |
| Spouse / Age Pension+ | nein / nein |
| Adviser Fee / Bonus | 0 / 0 |
| geplante Withdrawals | keine |

Das zeitlich und kapazitätsmäßig begrenzte 2-%-Bonusangebot ist bewusst kein
Default. Seine Einbeziehung wäre ein anderes Szenario und würde sowohl
Investment Amount als auch Akquisitionskosten verändern.

## 10.2 Markt- und ESG-Annahmen

| Parameter | Wert |
|---|---:|
| Zero Curve 1/2/5/10/20/30 Jahre | 3,80/3,90/4,10/4,30/4,40/4,40 % |
| AUS / Global Volatilität | 16 / 15 % |
| Equity Risk Premium unter (P) | 4,50 % |
| Return-Index-Carry | 0 % |
| Equity-Korrelation | 0,75 |
| Heston (\rho_{Sv}), nur Modellvergleich | −0,60 / −0,65 |
| Hull--White (a,\sigma_r), nur Modellvergleich | 0,03 / 0,008 |

## 10.3 Verhalten, Kosten und Profitabilität

| Parameter | Wert |
|---|---:|
| Product Fee / LIP | 0,30 / 1,15 % p. a. |
| Acquisition Expense | 2,00 % der Prämie |
| Maintenance Expense | AUD 80 p. a. + 5 bp des IV |
| Expense Inflation | 2,50 % p. a. |
| Income-Phase Lapse | 0,50 % p. a. |
| Dynamic-Lapse Slope / Floor / Cap | 1,5 / 0,2 / 2,5 |
| Hurdle Rate / Tax | 8 / 30 % |

## 10.4 Pfadzahlen

Nicht alle Tabellen basieren auf derselben Pfadzahl:

| Analyseblock | Pfade |
|---|---:|
| Basispricing, Kapital, Profitabilität | 4.000 |
| Sensitivitäten | 1.200 |
| Product Design und Timing | 1.500 |
| Behaviour Surfaces | 600 |
| Kunden-Outcomes | 2.500 |
| Modellvergleich | 600 je Modell |
| Seed-Stabilität | 800 je Seed, fünf Seeds |

Kleine Abweichungen zwischen „Base“-Zeilen verschiedener Dateien sind daher
erwartetes Monte-Carlo-Rauschen und keine ökonomische Differenz.

# 11. Ergebnisse des instrumentierten 1.3.0-Laufs

## 11.1 Executive KPIs

| Kennzahl | Ergebnis | Einordnung |
|---|---:|---|
| Premium | AUD 100.000 | Modellprämie |
| Gross VNB | **−AUD 1.227,65** | vor Risk Margin |
| Gross NBM | −1,228 % | Gross VNB / Prämie |
| pfadweiser Standardfehler | AUD 42,25 | nur Monte-Carlo-Fehler |
| approximatives 95-%-MC-Halbintervall | ±AUD 82,81 | (1{,}96\times SE) |
| Non-unit BEL | +AUD 1.227,65 | negatives Vorzeichen zum Gross VNB |
| Guarantee Value | +AUD 10.079,74 | Claims minus LIP |
| fairer LIP / belasteter LIP | 3,0042 % / 1,1500 % | Rider-neutral vs. Produktannahme |
| Fair-LIP-Lücke | 185,42 bp | kein Gesamtprodukt-Break-even |
| BSCR-Proxy | AUD 17.205,30 | nicht APRA/LAGIC |
| Risk-Margin-Proxy | AUD 4.687,26 | 6-%-CoC auf Life-SCR-Runoff |
| VNB nach Risk Margin | **−AUD 5.914,91** | NBM −5,915 % |
| PVFP bei 8 % | **−AUD 12.898,96** | inkl. Reserve, Kapital und Tax |
| IRR | 3,519 % | niedrigste gefundene Wurzel |
| Payback | Jahr 23 | kumuliert, undiskontiert |
| Q-Identity Gap | −0,1689 % | innerhalb des laufbezogenen MC-Bands |

![Abbildung 1: Executive Dashboard des instrumentierten 1.3.0-Laufs. Alle Werte sind illustrative Research-Resultate.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/01_executive_dashboard.png){width=95%}

Der negative Gross VNB ist klein im Verhältnis zur Prämie, aber deutlich
größer als sein reiner Monte-Carlo-Fehler. Die Unsicherheit aus Parametern,
Modellwahl und Implementierung ist, wie die folgenden Abschnitte zeigen,
wesentlich größer als ±AUD 83.

## 11.2 Wert- und Margin-Reconciliation

Die Überleitung zum Gross VNB lautet:

| Q-Barwertkomponente | Beitrag zum Versichererwert |
|---|---:|
| Product Fees | +AUD 2.269,84 |
| Lifetime Income Premium | +AUD 8.701,07 |
| Crediting Margin | +AUD 9.923,45 |
| MVA Retained | +AUD 217,37 |
| Guarantee Claims | −AUD 18.780,81 |
| Expenses | −AUD 3.558,57 |
| **Gross VNB** | **−AUD 1.227,65** |

Die LIP deckt 46,3 % des Claimbarwerts. Die verbleibenden AUD 10.079,74 sind
der positive Guarantee Value. Product Fee, Crediting Margin und MVA
finanzieren einen großen Teil dieser Lücke, reichen nach modellierten Expenses
jedoch nicht für einen positiven Gross VNB.

![Abbildung 2: Pricing- und Margin-Waterfall.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/02_pricing_margin_waterfall.png){width=95%}

Die Q-Barwerte der Kundenleistungen betragen:

| Kundenleistung | Q-Barwert |
|---|---:|
| Income paid | AUD 69.417,96 |
| Death Benefits | AUD 12.537,80 |
| Surrender Benefits | AUD 15.544,39 |
| Partial Withdrawals | AUD 0,00 |
| **Summe** | **AUD 97.500,16** |

Nach Abzug der vom Versicherer finanzierten Claims und Hinzurechnung der
Finanzierungspositionen entstehen AUD 99.831,08. Gegenüber der Prämie bleibt
ein Residual von −AUD 168,92 beziehungsweise −0,1689 %. Der Reconciliation-
Status ist „PASS“, weil die Abweichung innerhalb der laufbezogenen Schwelle
liegt. Das ist eine numerische Diagnose, keine ökonomische Erfolgskennzahl.

## 11.3 Kapitalproxy

| Stressmodul | Standalone SCR |
|---|---:|
| Interest Down, bindend | AUD 15.812,66 |
| Longevity | AUD 3.489,70 |
| Lapse Down, bindend | AUD 818,45 |
| Expenses | AUD 313,88 |
| Equity | AUD 0,00 |
| Equity Volatility | AUD 0,00 |
| Mortality | AUD 0,00 |
| Catastrophe | AUD 0,00 |

Nach Korrelation beträgt der Market SCR AUD 15.812,66, der Life SCR rund AUD
3.896 und der aggregierte BSCR AUD 17.205,30. Zinsen dominieren, weil fallende
Zinsen den Barwert langfristiger Garantieclaims erhöhen und zugleich
Finanzierungs- und Cap-Kanäle verändern.

Ein Nullwert bedeutet nur, dass der gewählte Stress nach dem Floor
(\max(0,Loss)) keinen Kapitalverlust erzeugt. Er bedeutet nicht, dass kein
Equity-, Volatilitäts- oder Mortality Risk existiert. Mass Lapse ist im
Basisfall null, weil der grobe Proxy (40\%\times\max(NAV,0)) bei negativem
Basis-NAV null wird.

## 11.4 Profit-, Reserve- und Kapital-Runoff

![Abbildung 3: Profit-, BEL- und Kapital-Runoff.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/03_profit_capital_runoff.png){width=95%}

Die wesentlichen Runoff-Beobachtungen sind:

- Time-0-Profit-Signature: −AUD 1.179;
- Time-0-Distributable Strain: −AUD 21.346;
- Maximum des BEL inklusive Risk Margin: rund AUD 47.669 in Jahr 17;
- Maximum des Required-Capital-Proxy: rund AUD 30.454 in Jahr 17;
- Profit-Signature ab Jahr 17 negativ, Minimum rund −AUD 4.651 in Jahr 21;
- kumulierte undiskontierte Distributable Earnings ab Jahr 23 positiv; und
- terminal nominal rund +AUD 27.526, trotz PVFP von −AUD 12.899 bei 8 %.

Die scheinbare Kombination aus spätem nominalem Payback und negativem PVFP ist
ökonomisch konsistent: frühes Kapital und frühe Strains werden hoch gewichtet,
späte Freisetzungen stark diskontiert.

## 11.5 Einfaktor-Sensitivitäten

Die Sensitivitätsrechnung verwendet 1.200 Pfade und schaltet Kapital sowie Risk
Margin aus. Die Base-PVFP-Zahl von −AUD 66 ist daher nicht mit dem
kapitalbelasteten Basis-PVFP von −AUD 12.899 zu verwechseln.

| Szenario | Gross VNB | Δ Gross VNB | Guarantee Value | PVFP @ 8 % | Δ PVFP |
|---|---:|---:|---:|---:|---:|
| Base | −1.224 | 0 | 10.092 | −66 | 0 |
| Zinsen +100 bp | 8.549 | +9.773 | 6.499 | 6.933 | +6.999 |
| Zinsen −100 bp | −12.707 | **−11.483** | 14.764 | −8.263 | **−8.196** |
| Equity Vol +25 % relativ | −787 | +436 | 10.269 | 75 | +141 |
| Maximum Returns −100 bp | 1.008 | +2.232 | 10.851 | 1.380 | +1.446 |
| Longevity: (q_x\) −10 % | −2.852 | −1.629 | 11.780 | −1.183 | −1.117 |
| Mortality: (q_x\) +10 % | 207 | +1.431 | 8.600 | 913 | +979 |
| Lapse +50 % | −498 | +725 | 8.788 | 370 | +436 |
| Lapse −50 % | −2.042 | −818 | 11.526 | −561 | −495 |
| Dynamic Lapse aus | −527 | +696 | 9.336 | 403 | +469 |
| Income Start +2 Jahre | 2.037 | +3.261 | 7.905 | 2.084 | +2.151 |
| Income Start −2 Jahre | −4.029 | −2.805 | 11.824 | −1.878 | −1.811 |
| Free Withdrawals 100 % | −362 | +862 | 7.635 | 393 | +460 |
| Excess Withdrawals 2 % p. a. | 2.521 | +3.745 | 4.027 | 2.307 | +2.373 |
| Expenses +10 % | −1.380 | −156 | 10.092 | −175 | −108 |
| ERP −100 bp, nur (P) | −1.224 | 0 | 10.092 | −253 | −187 |

![Abbildung 4: Sensitivitäts-Tornado; ohne Kapital und Risk Margin.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/04_sensitivity_tornado.png){width=95%}

### Interpretation

1. **Zinsrisiko dominiert.** −100 bp verschlechtern den Gross VNB um AUD
   11.483; +100 bp verbessern ihn um AUD 9.773. Die Beziehung ist nicht
   linear und wirkt über Discounting, Account, Cap-Budget, Gebühren und MVA.
2. **Späterer Income Start hilft dem Versicherer im Modell.** Zwei Jahre
   später verbessern den Gross VNB um AUD 3.261; früherer Start belastet.
   Daraus folgt keine Kundenempfehlung.
3. **Niedrigere Caps erhöhen den Versichererwert.** Der Kunde erhält weniger
   Upside, das Optionspaket wird günstiger beziehungsweise die Crediting
   Margin größer. Gleichzeitig steigt hier der Guarantee Value, weil auch
   Account- und Fee-Pfade reagieren.
4. **Langlebigkeit belastet.** Niedrigere (q_x) verlängern Income Claims.
5. **ERP wirkt nur unter (P).** Der risikoneutrale Gross VNB bleibt gleich,
   der Real-World-PVFP fällt.
6. **Withdrawal-Szenarien sind nicht wertneutral.** Entnahmen reduzieren die
   Garantie. Das Szenario „Excess 2 %“ setzt im Skript zugleich die Free
   Withdrawal Utilisation auf 100 % und ist kein isolierter 2-%-Stress.

Common Random Numbers reduzieren das Differenzrauschen. Gepaarte
Standardfehler der Sensitivitäten werden aber nicht ausgegeben; kleine
Differenzen sind daher vorsichtig zu lesen.

## 11.6 Kunden-Outcomes

Die Outcome-Analyse simuliert 2.500 Real-World-Black--Scholes-Pfade mit Seed
2027. Werte sind nominal und vor persönlicher Steuer oder Withholding.

| Alter | IV P5 | IV P50 | IV P95 | IV-Mittel | Fixed Income P50 | IV erschöpft | In-force-Gewicht |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 70 | 97.561 | 110.078 | 123.927 | 110.446 | 9.812 | 0,00 % | 78,64 % |
| 80 | 16.231 | 28.829 | 42.492 | 28.995 | 9.812 | 0,00 % | 60,33 % |
| 81 | 6.919 | 19.628 | 33.626 | 19.797 | 9.812 | 0,04 % | 58,08 % |
| 82 | 0 | 10.174 | 24.273 | 10.720 | 9.812 | 10,48 % | 55,73 % |
| 83 | 0 | 526 | 14.769 | 3.686 | 9.812 | 47,56 % | 53,30 % |
| 84 | 0 | 0 | 5.232 | 635 | 9.812 | **85,36 %** | 50,80 % |
| 85 | 0 | 0 | 0 | 33 | 9.812 | 98,92 % | 48,23 % |
| 86 | 0 | 0 | 0 | 0 | 9.812 | 100,00 % | 45,58 % |

![Abbildung 5: Verteilung von Investment Value, Income und Account Depletion.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/05_customer_outcomes.png){width=95%}

Auf dem Jahresraster überschreitet die Erschöpfungsquote erstmals bei Alter 84
die 50-%-Schwelle. Ab diesem Bereich wird ein wachsender Anteil der
Income-Zahlungen direkt zu Guarantee Claims. Das ist kein erwarteter
„Kontostand eines Kunden“: IV- und Income-Quantile sind rohe Marktzustände vor
stochastischen Decrementen. Das separate In-force-Gewicht enthält Mortalität
und Lapse.

Die jährlichen erwarteten Claims beginnen um Alter 81/82 sichtbar zu werden
und erreichen in der ausgegebenen Bucket-Struktur rund AUD 4.591 in Jahr 21.
Weil Zahlungen nachschüssig sind, enthält der Bucket Jahr 6 die Zahlungen im
Intervall ((5,6]), obwohl Income am Ende von Jahr 5 aktiviert wird.

## 11.7 Produktdesignvarianten

Jede Variante ist eine bedingte Vertragsausprägung, nicht der Wert eines
gemeinsamen späteren Wahlrechts.

| Variante | Rate | Q-Start-Income | Gross VNB | Guarantee Value | LIP / Claims | Kundenleistungs-PV |
|---|---:|---:|---:|---:|---:|---:|
| Single Fixed | 8,80 % | 9.517 | −1.335 | 10.183 | 46,1 % | 97.548 |
| Single Rising | 5,65 % | 6.110 | 6.445 | 3.900 | 71,3 % | 89.690 |
| Spouse Fixed | 7,70 % | 8.327 | **−5.149** | 14.908 | 39,0 % | 100.957 |
| Spouse Rising | 4,55 % | 4.921 | 6.537 | 5.544 | 66,7 % | 89.175 |
| APS Fixed | 8,85 % | 9.571 | −2.252 | 12.483 | 27,8 % | 98.394 |
| APS Rising | 5,70 % | 6.164 | **7.207** | 7.198 | 40,1 % | 88.838 |

![Abbildung 6: Bedingte Produktdesign-Trade-offs.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/06_product_design_tradeoffs.png){width=95%}

Rising-Varianten haben niedrigere Start-Raten und sind im illustrativen Modell
für den Versicherer deutlich wertvoller. Spouse Fixed ist wegen niedrigerer
Sterblichkeitsdekremente und hohem garantierten Income am teuersten. APS Rising
hat den höchsten Gross VNB, nutzt aber eine illustrative CAS-Lebenserwartung
von 20 Jahren. Kundennutzen, Liquiditätspräferenz, Steuer und Social-Security-
Effekte sind in dieser Rangfolge nicht enthalten [vgl. @steinorth2015].

## 11.8 Timing des Income Starts

| Wartezeit | Startalter | Rate | Q-Start-Income | Gross VNB | Guarantee Value | Kundenleistungs-PV |
|---:|---:|---:|---:|---:|---:|---:|
| 1 Jahr | 66 | 7,40 % | 7.509 | −6.150 | 12.859 | 102.337 |
| 3 Jahre | 68 | 8,10 % | 8.482 | −4.171 | 11.947 | 100.378 |
| 5 Jahre | 70 | 8,80 % | 9.517 | −1.335 | 10.183 | 97.548 |
| 10 Jahre | 75 | 10,55 % | 12.365 | 6.852 | 4.504 | 89.287 |
| 15 Jahre | 80 | 12,30 % | 15.569 | 15.066 | −1.791 | 80.996 |

![Abbildung 7: Trade-off des Income-Start-Zeitpunkts.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/07_income_start_tradeoff.png){width=95%}

Längeres Warten erhöht im Modell Rate, Start-Income und Versichererwert,
reduziert aber den Barwert der Kundenleistungen. Bei 15 Jahren übersteigt der
LIP-Barwert die modellierten Claims. Diese Tabelle ignoriert Kundenutility,
Überlebenspräferenzen, adverse Selektion und den Optionswert, den Startzeitpunkt
später auf Basis neuer Informationen zu wählen.

## 11.9 Verhalten und Liquidität

Die kombinierte Fläche zeigt, dass das Vorzeichen des Lapse-Effekts mit dem
Income-Start wechselt. Bei Start nach fünf Jahren verbessert ein höherer
Lapse-Multiplikator den Gross NBM; bei sehr spätem Start kann das Gegenteil
gelten, weil lange Fee- und Margin-Pfade verloren gehen.

| Lapse-Multiplikator | Start 1 | Start 3 | Start 5 | Start 8 | Start 12 | Start 15 |
|---:|---:|---:|---:|---:|---:|---:|
| 0,5 | −6,60 % | −4,71 % | −2,10 % | 2,96 % | 10,20 % | 15,80 % |
| 1,0 | −6,24 % | −4,11 % | −1,28 % | 3,72 % | 10,28 % | 15,10 % |
| 1,5 | −5,90 % | −3,55 % | −0,55 % | 4,33 % | 10,23 % | 14,36 % |

Withdrawal Utilisation reduziert in den Szenarien den Guarantee Value und
erhöht deshalb den Versichererwert. Bei 0 % Excess steigt der Gross NBM von
−1,28 % bei keiner Free-Utilisation auf −0,40 % bei vollständiger Nutzung.
Bei 2 % Excess p. a. liegen die Werte bei 2,26 % beziehungsweise 2,48 %.

![Abbildung 8: Behaviour- und Withdrawal-Surfaces.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/08_behaviour_liquidity_surfaces.png){width=95%}

Die Flächen sind Modellmechanik, keine empirischen Best Estimates. Eine
Verbesserung des Versichererwerts durch Kundenentnahmen ist insbesondere keine
Wohlfahrtsaussage.

## 11.10 Modell- und Seed-Risiko

Der Modellvergleich verwendet je Modell nur 600 Pfade:

| Modell | Gross VNB | Gross NBM | Guarantee Value | Identity Gap |
|---|---:|---:|---:|---:|
| Black--Scholes | −1.275 | −1,28 % | 10.112 | −0,270 % |
| Heston | −3.788 | −3,79 % | 9.022 | −0,082 % |
| Hull--White + BS | −1.943 | −1,94 % | 10.718 | −0,019 % |
| Heston + Hull--White | −4.402 | −4,40 % | 9.742 | −0,118 % |

Die Spannweite des Gross VNB beträgt AUD 3.127. Sie ist rund 37-mal so groß
wie der 95-%-MC-Halbintervall des 4.000-Pfad-Basislaufs. Sie enthält sowohl
echten Modellunterschied als auch Monte-Carlo-Rauschen und ist wegen fehlender
Kalibrierung keine Konfidenzgrenze.

Über fünf Seeds mit je 800 Black--Scholes-Pfaden ergeben sich:

- Mittelwert Gross VNB: −AUD 1.209;
- Sample Standard Deviation der fünf Schätzer: AUD 96,64;
- mittlerer pfadweiser Standardfehler: AUD 96,63; und
- Spannweite: −AUD 1.292 bis −AUD 1.049.

Die Übereinstimmung von Seed-Streuung und ausgewiesenem Standardfehler ist ein
gutes internes Plausibilitätssignal, ersetzt aber keine umfassende
Konvergenzstudie.

![Abbildung 9: Stochastisches Modellrisiko und Seed-Stabilität.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/09_model_mc_stability.png){width=95%}

## 11.11 Greeks: nur instrumentierte Vor-Kosten-Sicht

Der Laufzeit-Workaround erzeugte folgende Finite-Difference-Diagnostik:

| Größe | Ergebnis |
|---|---:|
| Greek NAV vor Expenses | AUD 2.330,92 |
| Equity Delta, normalisierte Engine-Ausgabe | 0,000504 |
| Vega je +1 Volatilitätspunkt | 0,001159 der Prämie, rund +AUD 116 |
| Rho je +100 bp | 0,103904 der Prämie, rund +AUD 10.390 |

Der Greek NAV liegt genau um den Expense-Barwert von AUD 3.558,57 über dem
Gross VNB, weil die API keine Expense Assumptions entgegennimmt. Die Greeks
sind deshalb nicht direkt mit VNB, Sensitivitäten oder Kapitalstress
vergleichbar. Aufgrund des bestätigten Integrationsfehlers werden sie nur als
technische Diagnose, nicht als freigegebene Risikokennzahlen verwendet.

![Abbildung 10: Instrumentierte Greek-Ausgabe und Marktstress-Proxy.](AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/10_market_risk_greeks.png){width=95%}

## 11.12 Versionsvergleich 1.2.0 zu 1.3.0

| Kennzahl | v1.2.0 | v1.3.0 instrumentiert | Veränderung |
|---|---:|---:|---:|
| Gross VNB | +1.743 | −1.228 | **−2.970** |
| Fair LIP | 3,237 % | 3,004 % | −23,3 bp |
| Guarantee Value | 11.240 | 10.080 | −1.160 |
| Crediting Margin | 14.131 | 9.923 | −4.208 |
| BSCR | 16.839 | 17.205 | +366 |
| Risk Margin | 20.076 | 4.687 | **−15.389** |
| VNB nach RM | −18.334 | −5.915 | +12.419 |
| PVFP @ 8 % | −15.610 | −12.899 | +2.712 |
| IRR | 4,17 % | 3,52 % | −0,65 Prozentpunkte |
| Payback | Jahr 22 | Jahr 23 | +1 Jahr |
| 50-%-IV-Erschöpfung | Alter 83 | Alter 84 | +1 Jahr |

Die wichtigste Änderung ist der Return-Index-Carry: 1.2.0 verwendete 4 % für
den australischen und 2 % für den globalen Index. Da es sich um Total-/Net-
Return-Indizes handelt, wertete der Audit dies als Dividendendoppelzählung und
setzte den Carry auf null. Ein kontrollierter Gegenlauf mit 1.3.0-Code, aber
alten Carries ergab einen Gross VNB von rund +AUD 1.879; der isolierte
Carry-Effekt erklärt damit etwa −AUD 3.107 und den Großteil des
Vorzeichenwechsels.

Der Risk-Margin-Rückgang ist dagegen überwiegend methodisch: 1.3.0 verwendet
nur den Life SCR und schließt Market Risk als hedgebar aus. Beide Vergleiche
zeigen, warum Ergebnisse stets mit Source Version, Assumptions Fingerprint und
Definition berichtet werden müssen. Die v1.2.0-Zahlen sind historischer
Vergleich, keine alternative aktuelle Schätzung.

# 12. Validierung, Audit und Model Risk

## 12.1 Reproduzierter Teststand

Ein aktueller Lauf von `python -m pytest -q` ergab **122 bestandene Tests in
108,24 Sekunden**. Die Suite deckt unter anderem ab:

- PDS-Payoffbeispiele einschließlich −18 % Indexrendite → −8 % unter Partial
  Protection;
- Black--Scholes-Closed-Form gegen eine große unabhängige Monte-Carlo-
  Stichprobe;
- DVA-Konvergenz zum Anniversary Payoff;
- risikoneutrale Equity-Martingale und Hull--White-Zero-Bond-Reproduktion;
- Buchungsidentitäten für Basismodell, Hull--White, Withdrawals, Spouse und
  Off-anniversary Income Start;
- Rising-Income-Monotonie und Income-Fortzahlung nach IV-Erschöpfung;
- Ratecard, jüngeren Spouse, APS-Withdrawal- und Death-Cap-Beispiele;
- nachschüssiges Income-/Death-Timing;
- 95-%-Withdrawal-Limits und Free Allowance;
- Kapital-Nichtnegativität und Diversifikation;
- Fair-Fee-Bracket und Reproduzierbarkeit; sowie
- LSMC-Monotonie und statischen Benchmark.

Das ist für einen Research-Prototyp substanziell. Die Toleranzen sind jedoch
teilweise breit: Die monatliche Buchungsidentität darf je nach Test 60--80 bp
abweichen; das jährliche LSMC darf bis 5 % vom Monatsmotor abweichen. Testgrün
ist daher kein Beweis hoher produktspezifischer Genauigkeit.

## 12.2 Wichtige Auditkorrekturen

Die lokale Audit-Historie korrigierte unter anderem:

- die vollständige Juli-2026-Ratecard und Guaranteed Minimums;
- Rating nach Alter und Geschlecht am Commencement Date;
- Joint-Life-Projektionshorizont und Spouse Conditioning;
- Reihenfolge von Annual Credit, Fees und Income Election;
- Mortalitätsbasisjahr und First-Year Catastrophe Shock;
- doppelt gezählten LSMC-Terminalwert und Look-ahead Bias;
- Return-Index-Carry und Dividendendoppelzählung;
- APS Commencement, MWV, MVA- und Death-Cap-Mechanik;
- Survivor-only Payments in arrears;
- Capital-/Risk-Margin-Runoff, PVFP und Vega-Normalisierung; und
- Szenario-Provenienz, Immutability und Eingabevalidierung.

Die Liste zeigt, dass fachliche Modellvalidierung nicht nur Formeln prüft,
sondern vor allem Event Ordering, State Conditioning, Einheiten, Vintage und
Schnittstellen.

## 12.3 Was die Identity Gap kann — und was nicht

Die Identity Gap ist eine starke interne Kontrolle gegen Cashflow Leakage.
Sie kann Fehler wie vergessene Fees, doppelte Claims oder inkonsistente
DVA-Abwicklung sichtbar machen. Sie kann aber nicht erkennen, ob

- der DVA-Proxy die echte Allianz-Formel trifft;
- die MVA-Parameter richtig kalibriert sind;
- Mortalität oder Verhalten realistisch sind;
- die Zins- oder Volatilitätsmodelle Marktdaten treffen; oder
- rechtliche Optionen vollständig modelliert wurden.

Eine korrekte Buchung eines falschen Vertrags kann eine perfekte Identity Gap
haben.

## 12.4 Aktueller End-to-End-Fehler in `greeks()`

`ScenarioSet` ist in Version 1.3.0 als unveränderliche Dataclass definiert.
Die publizierte Funktion `pricing.greeks()` erzeugt jedoch eine flache Kopie
und weist anschließend dem Feld `index_levels` einen neuen Wert zu. Der
unveränderte Runner bricht reproduzierbar ab:

```text
dataclasses.FrozenInstanceError: cannot assign to field 'index_levels'
```

Die Testsuite ruft `greeks()` nicht auf. Das Kapitalmodul löst einen
vergleichbaren Equity Shock korrekt mit `dataclasses.replace`.

Für dieses Paper wurde **keine Quelldatei geändert**. Nur in der laufenden
Python-Session wurde die im Reportmodul gebundene Greek-Funktion durch eine
semantisch gleiche Variante mit folgender Kernlogik ersetzt:

```python
levels = {ix: lv.copy() for ix, lv in base_scen.index_levels.items()}
for ix in levels:
    levels[ix][:, 1:] *= scale
shocked = dataclasses.replace(base_scen, index_levels=levels)
```

Danach lief der vollständige Pack in ein separates Verzeichnis. Der Workaround
ist reversibel und transparent, wird aber vom Engine-Source-Hash des Manifests
nicht erfasst. Für echte Reproduzierbarkeit wären erforderlich:

1. ein geprüfter Source Fix;
2. ein Regressionstest für die öffentliche Greek API;
3. ein End-to-End-Test des Standard-Runners; und
4. eine Provenienz, die Runner und Laufzeitinstrumentierung hasht.

## 12.5 Validitätsrisiken

### Interne Validität

- Diskretisierung auf Monatsraster; Fees nur monatlich approximiert.
- Heston/Hull--White-Schemata haben verbleibenden Diskretisierungsfehler.
- Greeks und einige Sensitivitäten nutzen unterschiedliche Expense-/Capital-
  Scopes.
- LSMC ist nicht mit der Monatsbewertung integriert.

### Externe Validität

- Nur ein New-Business-Modellpunkt.
- Keine Allianz-Bestands-, Admin-, Hedge- oder Experience-Daten.
- Illustrative statt markt- beziehungsweise bestandskalibrierter Parameter.
- Keine Portfolioaggregation oder Selection Effects.

### Konstruktvalidität

- Der Solvency-II-artige Proxy ist kein APRA/LAGIC-Kapital.
- Der DVA-/MVA-Hedgewert ist nicht die bestätigte Adminformel.
- Gross VNB, VNB nach RM und PVFP beantworten unterschiedliche Fragen.
- „Customer Outcome“ ist keine persönliche Prognose oder Utility-Messung.

### Statistische Validität

- Pfadzahlen unterscheiden sich nach Analyseblock.
- Sensitivitäten berichten keine gepaarten Standardfehler.
- Der Modellvergleich mit 600 Pfaden vermischt Modell- und Sampling-Effekt.
- Fünf Seeds genügen für eine Plausibilisierung, nicht für eine umfassende
  Konvergenzanalyse.

## 12.6 Production-Blocker

Die wichtigsten offenen Punkte sind:

1. **Kein In-force Model Point.** Es fehlen aktuelle Phase, IV, Locked Income,
   laufendes Fixing, Certificate Cap, Issue Curve, CAS State und verbrauchte
   Allowance.
2. **Unvollständige Optionalität.** Fixed/Rising, Spouse, APS, Death Election
   und Reallokation sind Szenarioinputs; der gemeinsame spätere Optionswert
   fehlt.
3. **Unkalibrierter DVA/MVA.** Protection Floor, Fixed-Return-Zweig und echte
   Quotes fehlen.
4. **Kein APRA/LAGIC.** Fund-Level-Assets, Hedges, Credit, Konzentration,
   Operational Risk und Combined Stress fehlen.
5. **Keine Produktionskalibrierung.** Mortalität, Lapse, Take-up, Withdrawals,
   Expenses, (P)- und (Q)-Marktparameter sind illustrativ.
6. **Fehlende Cashflows.** Ongoing Adviser Fees, Tax/Withholding, Cooling-off,
   Reinsurance und Teile der Investor-Eligibility fehlen.
7. **Kein systematisches Langlebigkeitsmodell.** Longevity wird nur gestresst,
   nicht stochastisch bewertet oder gehedgt.
8. **Skalierung.** Lange Projektionen werden nicht gestreamt oder gechunked
   und können im Capital Revaluation Loop mehrere GB benötigen.

# 13. Fachliche Interpretation

## 13.1 Belastbare strukturelle Aussagen

Trotz aller Einschränkungen lassen sich fünf robuste Mechanismen lernen:

1. **AGILE ist indexed, nicht unit-linked.** Ein Equity-Level-Schock wirkt
   primär auf den laufenden Credit-/DVA-Zyklus; das Konto hält nicht direkt
   den Index. Daher kann Interest Risk strukturell größer als Equity-Level-
   Risk sein.
2. **Die lebenslange Garantie wird im Tail sichtbar.** Im Basisfall fällt das
   Investment Value um Alter 83/84 auf vielen Marktpfaden auf null, während
   Fixed Income weiterläuft.
3. **Lifetime Income Timing ist eine große Option.** Früher Start erhöht
   Kundenleistungs-PV und Liability, später Start erhöht im illustrativen
   Modell Versichererwert.
4. **Behaviour wirkt nicht monoton.** Storno und Entnahmen können je nach
   Moneyness und Timing Gebühren vernichten oder Garantien freisetzen.
5. **Modell- und Implementation Risk dominieren Sampling Risk.** Modellwahl
   bewegt den Gross VNB um über AUD 3.000; der Versionswechsel ebenfalls um
   fast AUD 3.000; der 4.000-Pfad-MC-Halbintervall beträgt nur rund AUD 83.

## 13.2 Was aus dem negativen Basis-VNB nicht folgt

Der Basislauf beweist nicht, dass AGILE real unprofitabel ist. Nicht modelliert
oder unkalibriert sind unter anderem reale Cap-Management-Regeln, tatsächliche
Hedgekosten, Bestandsmortalität, Kundenverhalten, Kosten, Tax, Reinsurance,
Portfolioeffekte und Management Actions. Umgekehrt beweist ein positives
Szenario-VNB keine Profitabilität. Die sachgerechte Aussage lautet:

> Unter genau den dokumentierten illustrativen Annahmen ist der modellierte
> Einzelpolicenwert vor und nach Risk Margin negativ; die Aussage ist für das
> reale Portfolio nicht freigabefähig.

## 13.3 Kunden- versus Versicherersicht

Die Rankings der Designvarianten illustrieren einen grundlegenden Trade-off:
Höhere garantierte Startzahlungen, Joint Life und früher Income Start erhöhen
oft den Kundenleistungsbarwert und belasten den Versichererwert. Rising Income
verschiebt Leistung vom sicheren Startniveau in bedingte spätere Steigerungen.
Age Pension+ tauscht Kapitalzugriff gegen andere Produkt- und
Social-Security-Eigenschaften. Ein rein risikoneutraler Barwert misst dabei
weder Utility noch Liquiditätsbedarf, Bequest Motive oder persönliche Steuer
[@steinorth2015; @actuariesinstitute2024].

## 13.4 Richtige Verwendung des Kapitalergebnisses

Der BSCR-Proxy ist nützlich, um im Research-Modell Risikotreiber und
Korrelationseffekte zu vergleichen. Er darf verwendet werden für Aussagen wie
„Interest Down dominiert in diesem Modellpunkt“. Er darf nicht verwendet
werden als:

- APRA Prescribed Capital Amount;
- Kapitalquote des Statutory Fund;
- Hedgebudget;
- Reservierungsanforderung; oder
- Portfolio-Kapital ohne Aggregation.

## 13.5 Modellgovernance als Teil der Ökonomik

Der Versionsvergleich ist nicht nur Softwarethema. Eine falsche
Dividend-Yield-Basis veränderte Crediting Margin und Gross VNB materiell; eine
andere Risk-Margin-Definition veränderte VNB nach RM um über AUD 12.000.
Definition, Datenvintage, Codeversion und Kontrolle sind daher Bestandteil der
ökonomischen Kennzahl. Gute Modellgovernance umfasst mindestens:

- Product Sign-off gegen PDS und Investor Certificate;
- Market Data Sign-off mit Stichtag und Instrumentuniversum;
- Assumption Committee für Mortality, Behaviour und Expenses;
- unabhängige Code- und Method Validation;
- Benchmarking gegen analytische Sonderfälle und zweite Implementierung;
- Convergence-, Seed- und Discretisation-Studien;
- Change Control mit Ergebnisattribution; und
- klare Use Limitations im Reporting.

# 14. Lernpfad und Kontrollfragen

## 14.1 Empfohlene Lernreihenfolge

1. **Produkt zuerst:** Abschnitte 3.2--3.9 lesen und jeden Cashflow einer
   Vertragsregel zuordnen.
2. **State Machine:** Abschnitt 4 und besonders das Event Ordering verstehen.
3. **Finanzmathematik:** Payoff, Optionsreplikation, (Q/P), DVA und
   Marktwertidentität durcharbeiten.
4. **Biometrie und Verhalten:** unterscheiden, welche Risiken durch
   Erwartungswerte, Stress oder Option modelliert werden.
5. **Kennzahlen:** Guarantee Value, Gross VNB, VNB nach RM und PVFP anhand der
   Reconciliation selbst nachrechnen.
6. **Ergebnisse:** erst danach Sensitivitäten, Designs und Modellvergleich
   interpretieren.
7. **Kritik:** zuletzt Audit, Tests, Integrationsfehler und Production-Blocker
   prüfen.

## 14.2 Rechenübungen

1. Berechne den Annual Credit für (R=-18\%, -5\%, +8\%, +15\%) unter
   beiden Protection Types und den Juli-2026-Caps.
2. Zeige algebraisch, dass der Total-Protection-Payoff einem Call Spread
   entspricht.
3. Berechne die Fixed Rate eines 65-jährigen Mannes nach 1, 5, 10 und 15
   Growth-Jahren aus der Juli-2026-Ratecard.
4. Rekonstruiere den Gross VNB aus den sechs Barwertkomponenten in Abschnitt
   11.2.
5. Erkläre, weshalb (GV=10.080) nicht gleich (VNB=-1.228) ist.
6. Berechne den ungefähren 95-%-MC-Halbintervall aus (SE=42{,}25).
7. Vergleiche den Modellspread von AUD 3.127 mit Sampling- und
   Versionsrisiko.
8. Erkläre, warum ein Zero Equity SCR nicht „kein Equity Risk“ bedeutet.
9. Zeichne die Cashflow-Reihenfolge für einen Tod im ersten Monat nach Income
   Election.
10. Formuliere einen Test, der den aktuellen `greeks()`-Fehler künftig
    verhindert.

## 14.3 Verständnisfragen

- Warum ist ein Return-Index-Carry von null plausibler als der Dividend Yield
  der Indexbestandteile?
- Warum ist der Cap zugleich Kundenleistungsgrenze und Pricing Lever?
- Welche Informationen fehlen, um eine bestehende Police zu bewerten?
- Warum braucht die Bewertung ein (Q)-Maß und die Profitabilität zusätzlich
  ein (P)-Maß?
- Welcher Unterschied besteht zwischen Claim, Income Payment und Death
  Benefit?
- Wann ist Joint-Life Conditioning relevant?
- Warum ist eine LSMC-Policy out-of-sample nur ein Lower Bound?
- Welche APRA-Komponenten kann der aktuelle Kapitalproxy nicht abbilden?
- Warum kann ein positiver nominaler Runoff einen negativen PVFP haben?
- Welche Aussage erlaubt die Identity Gap, und welche ausdrücklich nicht?

# 15. Schlussfolgerung

Die AGILE Modelling Engine bildet eine anspruchsvolle Verbindung aus
indexierter Accumulation, Derivatebudget, lebenslanger Garantie, Mortalität,
Verhalten und Kapitalbindung ab. Ihre stärkste Eigenschaft ist die explizite
Cashflow- und State-Machine-Architektur mit einer marktwertkonsistenten
Reconciliation. Das macht Wechselwirkungen sichtbar, die in einer einfachen
„Income Rate × Account“-Betrachtung verloren gehen.

Der instrumentierte 1.3.0-Lauf zeigt für den illustrativen 65-jährigen
New-Business-Modellpunkt einen negativen Gross VNB, eine deutlich unter dem
modellierten Fair-LIP liegende belastete Rider Fee, dominantes Interest-Down-
Risk und einen späten Übergang der Income-Finanzierung vom Investment Value
zur Garantie. Timing, Design und Verhalten verändern den Wert wesentlich.

Wichtiger als die einzelne Basiszahl ist jedoch das Validierungsergebnis: Der
Versionswechsel dreht das VNB-Vorzeichen, und eine öffentliche API bricht trotz
122 bestandener Tests im End-to-End-Runner. Wissenschaftlich korrekt ist die
Engine daher als **reviewed research prototype** einzustufen. Für produktive
Nutzung müssen Vertrags- und Admin-Reconciliation, Markt- und
Bestandskalibrierung, In-force-Fähigkeit, APRA/LAGIC, Portfolioaggregation,
unabhängige Benchmarks und Model Governance ergänzt werden.

Die zentrale Lernbotschaft lautet: Ein langfristiges Retirement-Income-
Produkt wird nicht durch eine einzelne Rendite- oder Rentenformel verstanden.
Sein Wert entsteht aus dem Zusammenspiel von Vertragsereignissen,
Finanzmarktmodell, Mortalität, Verhalten, Kosten, Kapital und
Implementierungsqualität.

# Anhang A: Notation

| Symbol | Bedeutung |
|---|---|
| (S_t) | Stand des Referenzindex |
| (R=S_T/S_0-1) | jährliche Point-to-Point-Indexrendite |
| (C) | Maximum Return / Cap |
| (c(R)) | vertraglich gutgeschriebener Annual Return |
| (IV_t) | Investment Value |
| (I_t) | jährliches Locked Lifetime Income |
| (P(s,t)) | Zero-Coupon-Bondpreis |
| (D_t) | Money-Market-Diskontfaktor |
| (v_t) | Heston-Varianz |
| (r_t) | Short Rate |
| (q_x) | jährliche Todeswahrscheinlichkeit im Alter (x) |
| (MWV_t) | Age-Pension+-Maximum Withdrawal Value |
| (GV) | Guarantee Value (=PV(Claims)-PV(LIP)) |
| (BEL_{NU}) | Non-unit Best Estimate Liability |
| (VNB_{gross}) | risikoneutraler Versichererwert vor Risk Margin |
| (RM) | Risk-Margin-Proxy |
| (PVFP) | Present Value of Future Profits |
| (SCR) / BSCR | Stresskapital / aggregierter Research-Proxy |
| (Q) / (P) | risikoneutrales / Real-World-Wahrscheinlichkeitsmaß |

# Anhang B: Kennzahlen-Mapping

| Reportbegriff | Formel | Häufige Fehlinterpretation |
|---|---|---|
| Guarantee Value | Claims − LIP | nicht Gesamtproduktverlust |
| Gross VNB | Fees + Margins − Claims − Expenses | nicht nach Kapital/RM |
| VNB nach RM | Gross VNB − RM | RM ist hier Research-Proxy |
| NBM | VNB / Premium | in `executive_kpis.csv` nach RM |
| Gross NBM | Gross VNB / Premium | in Sensitivitätsdatei vor RM |
| PVFP | diskontierte Distributable Earnings | nicht identisch mit (Q)-VNB |
| Customer Benefit PV | PV von Income, Death, Surrender, Withdrawals | keine Utility oder Prognose |
| Identity Gap | relative Finanzierungsdifferenz | kein Vertrags- oder Kalibrierungsnachweis |

# Anhang C: Reproduktionsartefakte

Die wichtigsten lokalen Quellen und Ergebnisse sind:

- `AGILE.md` — interne Produktsynthese; nur Orientierung;
- `AGILE_Modelling_Engine/README.md` — Architektur und Use Limitations;
- `AGILE_Modelling_Engine/METHODOLOGY.md` — Modellmethodik und Fix-Historie;
- `AGILE_Modelling_Engine/AUDIT_REPORT.md` — Auditbefunde und Blocker;
- `AGILE_Modelling_Engine/agile_engine/` — ausführbarer Quellcode;
- `AGILE_Modelling_Engine/tests/` — 122 Tests;
- `AGILE_Modelling_Engine/examples/output/insurer_analysis/` — historischer
  1.2.0-Pack, nicht fortzuschreiben;
- `AGILE_Modelling_Engine/examples/output/insurer_analysis_v1_3_runtime_workaround/`
  — maßgeblicher instrumentierter 1.3.0-Pack; und
- `Papers on Pricing/` — lokale akademische Literatur.

Für eine formale Reproduktion sind mindestens Python 3.10+, NumPy, SciPy,
Pandas und Matplotlib erforderlich. Der Standard-Runner ist erst nach einem
geprüften Fix der Greek-Immutability wieder unverändert end-to-end lauffähig.

# Anhang D: Literatur- und Quellenkritik

Kein einzelnes Paper modelliert exakt AGILEs Kombination aus jährlichem
Point-to-Point-Crediting, DVA, MVA und lebenslangem Income. Der Ansatz ist eine
Synthese aus Equity-Indexed-Annuity-Numerik [@deng2017], GMxB-Rahmen
[@bauer2008; @milevskysalisbury2006], lebenslanger GLWB-Literatur
[@holz2012; @piscopo2011], stochastischen Marktmodellen
[@goudenege2016; @gudkov2019], Behaviour [@kling2014] und numerischer Kontrolle
[@huangkwok2016; @alonsogarcia2018].

Der lokale kuratierte Literaturindex endet nach Abschnitt C mit einem
Platzhalter und ist nicht vollständig. Einzelne Metadaten darin sind
fehlerhaft; insbesondere sollte eine dort abgelegte 2025-Datei nicht ohne
Prüfung als Bégin/Sanders/Sun-Journalpaper zitiert werden. Dieses Paper nutzt
daher eine kleinere, überprüfte Kernauswahl. Faire Gebühren aus fremden
Studien werden bewusst nicht auf AGILE übertragen, weil Vertrag, Markt,
Mortalität und Verhalten abweichen.

