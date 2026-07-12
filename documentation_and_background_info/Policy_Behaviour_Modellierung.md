# Policy Behaviour im Repository

**Stand:** 12. Juli 2026  
**Status:** vereinfachtes dynamisches Behaviour-Modell mit festen, nicht
kalibrierten Proxy-Annahmen (`uncalibrated_proxy`)

Diese Dokumentation beschreibt den produktiv vorgesehenen Ist-Stand der
Policyholder-Behaviour-Modellierung. Entsprechend der Repository-Vorgabe wurde
der Stand statisch geprüft; es wurden keine Skripte oder Tests ausgeführt.

## 1. Kurzfassung

Der reguläre Projektionspfad verwendet für die nachfolgend modellierten
Verhaltensentscheidungen dynamische Funktionen, soweit Produkt-Gates und die
unten beschriebene Joint-Life-Zustandsgrenze nicht vorrangig sind:

| Verhalten | Modellform | Dynamische Eingaben | Auswertung |
| --- | --- | --- | --- |
| Full Surrender/Lapse in Growth | Cox-artiger proportionaler Hazard / Complementary-Log-Log | aktueller IV-/Surrender-Value-Zustand und eingezahlte Bruttoprämie | monatlich |
| Full Surrender/Lapse in Income | Cox-artiger proportionaler Hazard / Complementary-Log-Log | aktueller Garantie-PV relativ zum Surrender Value und Bruttoprämie | am Anniversary neu bestimmt, innerhalb des Policy Year gehalten |
| Income Take-up | Cox-artiger proportionaler Hazard / Complementary-Log-Log | aktueller PV des bei sofortigem Start erreichbaren Income relativ zum IV und Bruttoprämie | Entscheidung am jeweils aktuellen Anniversary |
| Free Withdrawal | Fractional Logit | aktueller Garantie-PV relativ zum IV, Bruttoprämie und MVA-Signal | am Anniversary beziehungsweise bei Income Election neu bestimmt, innerhalb des Policy Year gehalten |
| Excess Withdrawal | Fractional Logit | aktueller Garantie-PV relativ zum IV, Bruttoprämie und MVA-Signal | am Anniversary beziehungsweise bei Income Election neu bestimmt, innerhalb des Policy Year gehalten |

Für das inzwischen aktive generische Produkt gilt eine vorrangige
Vertragsgrenze: In Growth sind Full Surrender/Lapse sowie sämtliche Free-,
Partial- und Excess Withdrawals verboten. Die entsprechenden positiven
Legacy-Basiswerte werden aus Provenienzgründen weiterhin geladen, aber im
generischen Projektor strukturell auf null gesetzt. Aktiv bleiben im Kernmotor
Income Take-up sowie Lapse und Excess Withdrawal in der Income Phase; im
Portfolio-Runner wird Take-up durch den expliziten Modellpunkt-Termin ersetzt.

Der produktive Default wird nicht aus fest im Runner verdrahteten Behaviour-
Werten gebaut. Er wird mit `load_dynamic_behaviour_assumptions()` aus zwei CSVs
im Verzeichnis `input_dynamic_behaviour` geladen. Der Loader liefert ein
`DynamicBehaviourAssumptionSet`; dessen `behaviour` wird an Pricing,
Projektion, Profitability und Capital weitergereicht.

Der neue Portfolio-Runner besitzt eine ausdrücklich dokumentierte Ausnahme:
`income_start_year` ist in den gelieferten New-Business-Modellpunkten ein
vorgegebener Produkteingang und hat für diesen Lauf Vorrang vor dem dynamischen
Take-up-Hazard. Der Runner lädt und dokumentiert dennoch den vollständigen
Behaviour-Annahmensatz, verwendet daraus aber operativ die dynamischen
Income-Lapse- und Withdrawal-Komponenten für Single Life, den Single-Life-
Fallback und die Lump-Sum-Spouse-Ausprägung. Der bedingt gemeinsame
Continue-Income-Joint-Zweig verwendet die geladenen statischen CSV-Basisraten,
weil noch keine getrennten `p11/p10/p01`-Account-Value-Kohorten bestehen. Ein
anderer Runner kann weiterhin den nachfolgend beschriebenen dynamischen
Take-up-Zweig wählen, muss `spouse=True` derzeit aber deterministisch electen.
Ein direkter Continue-Income-Joint-Life-Kernaufruf muss außerdem statische,
state-unabhängige Lapse-/Withdrawal-Annahmen verwenden; der Portfolio-Wrapper
stellt diesen Joint-Zweig automatisch her und belässt den Single-Life-Fallback
dynamisch.

Die eingezahlte Prämie ist in allen Funktionen
`PolicySpec.initial_investment`. Sie ist die **bezahlte Bruttoprämie**, nicht
der nach Upfront Adviser Fee, Kosten oder Bonus verbleibende Investment Amount.

Der LSMC-Code bleibt aus Gründen der Nachvollziehbarkeit in
`AGILE_Modelling_Engine/agile_engine/lsmc.py` erhalten. Er ist aber archiviert:
Er gehört weder zur öffentlichen Paket-API noch zur CLI oder zum produktiven
Pricing-, Projection-, Capital- oder Profitability-Pfad. `optimal` ist kein
zulässiges `BehaviourModel`-Regime.

## 2. Scope und Begriffe

Gemäß Repository-Konvention bezeichnet **Policyholder** hier die versicherte
Person. Ein **Modelpoint** ist ein Beispiel für eine versicherte Person. Im
heutigen Vertragsmodell werden versicherte Person, Investor und wirtschaftlich
entscheidende Person noch nicht als getrennte Rollen geführt. Das ist eine
Modellgrenze für die weitere Generifizierung.

Zum grundsätzlich unterstützten Policy Behaviour zählen:

1. der Wechsel von Growth zu Lifetime Income,
2. Full Surrender/Lapse, soweit die jeweilige Produktphase dies zulässt,
3. Free und Excess Partial Withdrawals, soweit vertraglich zulässig,
4. die pfadweise Reaktion dieser Handlungen auf Markt-/Moneyness-Zustand und
   Prämienhöhe.

Mortalität ist ein konkurrierendes Decrement, aber kein Behaviour-Input.
Produktwahlen wie Fixed Income und Spouse sind weiterhin
Vertragseigenschaften beziehungsweise Szenarioinputs und keine vom
Behaviour-Modell optimierten Aktionen. Rising Income, Age Pension+ und eine
kundenseitige Investment Allocation gehören nicht zum generischen Produkt.

## 3. Architektur und Eingabequellen

| Datei | Aufgabe |
| --- | --- |
| `AGILE_Modelling_Engine/agile_engine/behavior.py` | validierte Hazard- und Fractional-Logit-Funktionen sowie typisierte Behaviour-Annahmen |
| `AGILE_Modelling_Engine/agile_engine/dynamic_behaviour_assumptions.py` | strikter CSV-Loader, Auswahl von Base/Low/High und Provenienz |
| `input_dynamic_behaviour/dynamic_behaviour_baselines.csv` | Basiswahrscheinlichkeiten und Basisutilisationen nach Phase und Policy Year |
| `input_dynamic_behaviour/dynamic_behaviour_coefficients.csv` | Regressionskoeffizienten, Referenzprämie, Signal-Clips, Floors und Caps |
| `AGILE_Modelling_Engine/agile_engine/projection.py` | Ermittlung der aktuellen Signale und Anwendung im Monatsmotor |
| `AGILE_Modelling_Engine/agile_engine/market_assumptions.py` | lädt australische Zinskurve und vorhandene ESG-Parameter aus `input_market_data`; Quelle der Marktpfade für die Signale |
| `AGILE_Modelling_Engine/agile_engine/product.py` | vertragliche Zulässigkeit, Withdrawal-Grenzen, MVA und Income Ratecard |
| `input_cost_assumptions/cost_assumptions.csv` | einzige Kostenquelle; Gebühren und MVA-Loadings verändern indirekt den Vertragszustand |
| `AGILE_Modelling_Engine/agile_engine/lsmc.py` | nur archivierter, nicht angebundener Forschungsstand |

Die Behaviour-CSV-Dateien liegen bewusst außerhalb von `input_market_data`.
Sie sind weder Marktdaten noch Kosten. Umgekehrt enthält die Kosten-CSV keine
Behaviour-Koeffizienten.

### 3.1 Loader und Provenienz

`load_dynamic_behaviour_assumptions()`:

- erwartet beide CSV-Dateien mit einem festen Schema,
- validiert vollständige und lückenlose Policy-Year-Bänder,
- verlangt für jede Zeile den Status `uncalibrated_proxy`,
- prüft Einheiten, Wertebereiche, strukturelle Nullen und den erzwungenen
  Income Start,
- verlangt für Income Lapse und Withdrawal-Komponenten genau ein offenes Band
  ab Policy Year 1, weil diese Felder im Kernmotor derzeit skalare Annahmen
  sind; weitere formal gültige Bänder werden nicht still ignoriert,
- wählt konsistent `value_basis="low"`, `"base"` oder `"high"`,
- liefert Quellpfade, SHA-256-Hashes, Effective Dates und die tatsächlich
  angewandten Werte für Run-Provenienz.

Low und High sind geordnete Sensitivitätsbänder, keine Konfidenzintervalle.
Bei negativen Koeffizienten ist `low` der numerisch kleinere und damit stärker
negative Wert.

### 3.2 Kostenquelle

Kosten werden ausschließlich aus folgender Datei geladen:

`C:\Users\user\Documents\GMLB Structuring\input_cost_assumptions\cost_assumptions.csv`

Insbesondere dürfen Gebühren, Maintenance Expenses, Hedge Execution Costs
oder MVA-Loadings nicht aus den Behaviour-CSV-Dateien oder zusätzlichen
Fallback-Dateien bezogen werden. Vertragswertwirksame Kundenentgelte und
MVA-Loadings beeinflussen Behaviour indirekt über IV, Surrender Value oder das
MVA-Signal; reine Versicherer-Expenses mindern den Kunden-IV nicht. Die
Prämienkovariate bleibt davon unberührt.

## 4. Gemeinsame dynamische Kovariaten

### 4.1 Bruttoprämie

Für jede Funktion gilt

\[
z=\operatorname{clip}\left(\log\frac{P}{100{.}000},-2,2\right),
\]

mit

- \(P=\texttt{PolicySpec.initial_investment}\),
- Referenzprämie \(P_{ref}=\text{AUD }100{.}000\).

Damit ist die Prämienhöhe nicht nur ein Selektionsmerkmal für eine
Modelpoint-Gruppe, sondern eine explizite Kovariate jeder dynamischen
Behaviour-Funktion. Der Clip verhindert extreme Extrapolation weit außerhalb
des Proxy-Bereichs.

### 4.2 Moneyness

Ein rohes Entscheidungssignal wird grundsätzlich als logarithmisches
Wertverhältnis formuliert und begrenzt:

\[
m_{raw}=\log(G/A),\qquad
m=\operatorname{clip}(m_{raw},-\log 2,\log 2).
\]

`G` und `A` hängen von der Entscheidung ab:

| Entscheidung | Rohes Signal | Transformation |
| --- | --- | --- |
| Growth Lapse | \(\log(IV/SV)\); erfasst den aktuellen Exit-/MVA-Nachteil | positiver Teil |
| Income Lapse | \(\log(PV(Income)/SV)\) | positiver Teil |
| Income Take-up | \(\log(PV(prospective\ Income)/IV)\) | vorzeichenbehaftet |
| Free/Excess Withdrawal | \(\log(PV(guaranteed\ Income)/IV)\) | positiver Teil; zusätzlich separates MVA-Signal |

In Growth wird der prospektive Garantie-PV aus aktuellem IV, der bei sofortigem
Income Start geltenden Ratecard und dem pfadweisen Annuitätenfaktor bestimmt.
In Income wird das bereits festgesetzte `income_annual` verwendet. Der
Annuitätenfaktor berücksichtigt aktuelles Alter, Mortalität, gegebenenfalls
Joint Life und einen pfadweisen Zehnjahres-Forward-Zero-Zins als transparenten
Diskontierungsproxy. Er bewertet monatlich nachschüssige Zahlungen auf derselben
jährlich reconciliierten Monatsmortalität wie der Cashflow-Projektor.

Der positive Teil bedeutet: Für Lapse und Withdrawals löst ein negatives
Garantie-Moneyness-Signal keine spiegelbildliche dynamische Reaktion aus.
Take-up verwendet dagegen das Vorzeichen, weil sowohl ein über als auch unter
dem IV liegender Garantie-PV für die Startentscheidung relevant sein soll.

## 5. Cox-/Proportional-Hazard-Modell

Lapse und Income Take-up verwenden dieselbe etablierte Hazard-Struktur. Aus
einer jährlichen bedingten Basiswahrscheinlichkeit \(p_0\) wird zunächst der
integrierte Basishazard

\[
\mu_0=-\log(1-p_0).
\]

Der lineare Prädiktor lautet

\[
\eta=\beta_m m+\beta_p z+\beta_{mp}mz+\beta_{MVA}MVA.
\]

Nach den vorgesehenen Hazard-Grenzen gilt

\[
h=\operatorname{clip}(\exp(\eta),h_{min},h_{max}),
\]

\[
p_a=1-\exp(-\mu_0 h).
\]

Das ist die diskrete Anwendung eines proportionalen Hazard-Modells; die
zugehörige Probability-Link-Darstellung ist Complementary Log-Log. Floors und
Caps begrenzen anschließend die jährliche Wahrscheinlichkeit. Eine
strukturelle Basiswahrscheinlichkeit von null bleibt exakt null, eine
erzwungene Wahrscheinlichkeit von eins bleibt eins.

### 5.1 Exakte Umrechnung auf den Monatsraster

Bei Lapse wird **zuerst** die jährliche Basisrate dynamisch skaliert. Erst
danach erfolgt die exakte Konversion:

\[
p_m=1-(1-p_a)^{1/12}.
\]

Damit wird nicht ein bereits monatlich konvertierter Wert linear
multipliziert. Growth Lapse wird mit dem aktuellen Exit-Zustand monatlich neu
bestimmt. Die Income-Lapse-Wahrscheinlichkeit wird am Anniversary sowie bei
Income Election aktualisiert und über das folgende Policy Year gehalten.

### 5.2 Income Take-up am aktuellen Anniversary

Dynamic Take-up ist eine bedingte jährliche Entscheidung auf dem jeweils
aktuellen Anniversary. Nach Crediting und Gebühren werden anhand des dann
vorliegenden Markt-, IV-, Zins- und Prämienzustands die prospektive Income Rate,
der Garantie-PV und die dynamische Take-up-Wahrscheinlichkeit ermittelt.

Der Projektor zieht dafür reproduzierbare jährliche Uniform-Variablen je
Marktpfad. Die Entscheidung wird nicht am Projektionsstart für alle späteren
Jahre vorweggenommen. Vertragliche Mindestwartezeiten und die automatische
Startregel nach Alter 100 bleiben vorrangige Grenzen. Im dynamischen Proxy ist
der Income Start ab Policy Year 15 erzwungen.

Diese Mechanik gilt für Läufe ohne vorrangigen expliziten
Modelpoint-Election-Termin. In der aktuellen Portfoliobewertung wird stattdessen
deterministisch am `income_start_year` electet, damit Spouse-Survival bis zu
einem eindeutigen Eligibility-Termin und der Single-Life-Fallback konsistent
gemischt werden können.

## 6. Fractional Logit für Withdrawals

Free- und Excess-Withdrawal-Nutzung sind erwartete Anteile im Intervall
`[0,1]`. Dafür wird die Basisutilisation \(u_0\) auf der Logit-Skala
verschoben:

\[
\operatorname{logit}(u)=\operatorname{logit}(u_0)
 +\beta_m m+\beta_p z+\beta_{mp}mz+\beta_{MVA}MVA.
\]

Die inverse Logit-Funktion liefert die dynamische Utilisation. Strukturelle
Nullen und Einsen bleiben erhalten. Das MVA-Signal ist der nichtnegative,
aktuell wirksame MVA-Anteil; ein negativer `beta_mva` dämpft die Nutzung bei
höherem MVA-Nachteil.

Die Werte werden zum Projektionsstart, am Anniversary und bei Income Election
neu bestimmt und innerhalb des Policy Year gehalten:

- Free Withdrawal: erwarteter Anteil der vertraglich verfügbaren Free
  Withdrawal Allowance,
- Excess Withdrawal: erwartete annualisierte Entnahme als Anteil des aktuellen
  IV.

Erst danach wendet `product.py` die Vertragsmechanik an, insbesondere Free
Allowance, Mindestentnahme, 95-%-Grenzen, Mindestrestwert, MVA und die
proportionale Reduktion des Lifetime Income. Das Behaviour-Modell darf diese
vertraglichen Grenzen nicht ersetzen.

Der Excess-Ansatz ist ein vereinfachtes Fractional-Response-Modell. Er trennt
nicht zwischen Entnahme-Inzidenz und -Höhe wie ein vollständiges
Hurdle-/Frequency-Severity-Modell.

## 7. Geladene Base-Annahmen

### 7.1 Basisraten und -utilisationen

| Komponente | Base |
| --- | --- |
| Growth Lapse Policy Year 1–11+ | 3,0 %, 3,5 %, 4,0 %, 4,0 %, 4,0 %, 3,5 %, 3,0 %, 3,0 %, 2,5 %, 2,0 %, 2,0 % p.a. |
| Income Lapse | 0,5 % p.a. |
| Income Take-up Policy Year 1–7 | 0 %, 10 %, 15 %, 20 %, 25 %, 30 %, 30 % p.a. |
| Income Take-up Policy Year 8–14 | 30 % p.a. |
| Income Take-up ab Policy Year 15 | 100 %; erzwungen |
| Free-Withdrawal-Utilisation | 25 % der verfügbaren Allowance p.a. |
| Excess-Withdrawal-Rate | 0,5 % des aktuellen IV p.a. |

### 7.2 Base-Koeffizienten

| Komponente | \(\beta_m\) | \(\beta_p\) | \(\beta_{mp}\) | \(\beta_{MVA}\) | wesentliche Grenze |
| --- | ---: | ---: | ---: | ---: | --- |
| Growth Lapse | -1,50 | -0,10 | -0,50 | 0 | Hazard-Multiplikator 0,2–3,0; jährlicher Cap 30 % |
| Income Lapse | -1,50 | -0,10 | -0,50 | 0 | Hazard-Multiplikator 0,2–3,0; jährlicher Cap 30 % |
| Income Take-up | 4,00 | 0,50 | 0,25 | 0 | Hazard-Multiplikator 0,05–25; jährlicher Cap 50 % vor Force-Regel |
| Free Withdrawal | 0,50 | -0,25 | -0,10 | -2,00 | Output 0–100 % |
| Excess Withdrawal | 0,50 | -0,25 | -0,10 | -2,00 | Output 0–100 % |

Diese Werte sind **keine** aus den unten genannten Quellen übernommene
Kalibrierung. Alle Basisraten, Koeffizienten, Clips, Floors und Caps sind als
`uncalibrated_proxy` gekennzeichnet. Sie sind weder eine australische
Experience Study noch eine vollständig kalibrierte Kundenprognose.

## 8. Einbindung in den Monatsmotor

Behaviour wird in eine erwartungswertgewichtete Zustandsprojektion eingebettet.
Tod und Lapse reduzieren das In-force-Gewicht; sie werden nicht als separate
binäre Kundenhistorie je Marktpfad simuliert. Income Take-up kann dynamisch
gezogen werden; der aktuelle Portfolio-Runner verwendet dagegen den expliziten
deterministischen Modelpoint-Termin.

Die behaviour-relevante Reihenfolge im Monat ist:

1. Markt-/Indexentwicklung,
2. am Anniversary vollständiger Fondscredit ohne Fixed-Income-Ratchet,
3. Fee-Accrual beziehungsweise Anniversary-Posting aus der zentralen Kostenbasis,
4. Expected-Death-Decrement des abgelaufenen Intervalls,
5. bei Survivors gegebenenfalls Income Election,
6. Lifetime-Income-Zahlung,
7. Free/Excess Partial Withdrawals,
8. Full Surrender/Lapse.

Dadurch sehen Take-up, zulässige Income-Withdrawals und Income-Lapse den zu
ihrem Entscheidungszeitpunkt aktuellen Vertragszustand. Growth-Lapse und
Growth-Withdrawals bleiben unabhängig von den CSV-Werten null. Income-Lapse
bleibt bei fortbestehender Garantie auch nach Aufzehrung des Account Value
möglich; ein Null-AV beendet nur einen Growth-Vertrag ohne Garantie. Ein Cap,
Floor oder Schutzmechanismus wird weiterhin
auf den gemäß Vertrag vollständig gebildeten Kundenfonds- beziehungsweise
Optionsreturn angewandt; Behaviour ändert diese Crediting-Reihenfolge nicht.

## 9. LSMC ist archiviert

Der frühere LSMC-Ansatz für wertmaximierendes Verhalten wird vorerst vollständig
aus dem verwendeten Modellpfad ausgeklammert:

- die fachliche Implementierung in `agile_engine/lsmc.py` bleibt als klar
  gekennzeichnetes Forschungs-/Historienartefakt erhalten,
- `value_optimal_behaviour` und `LSMCSettings` sind keine öffentliche
  Top-Level-API,
- die CLI bietet keinen `--lsmc`-Produktionslauf,
- `run_full_analysis.py` und `run_insurer_analysis.py` dispatchen nicht in den
  LSMC,
- `BehaviourModel(regime="optimal")` wird abgewiesen,
- Pricing, Projection, Capital, Sensitivities und Profitability verwenden nur
  die CSV-konfigurierte dynamische Behaviour-Basis.

Frühere Dokumentations- oder Changelog-Passagen zu LSMC-Ergebnissen beschreiben
nur die Entwicklungshistorie. Sie sind keine Aussage über den aktuellen
Produktionsdefault und dürfen nicht als Ergebnis des heutigen Basismodells
zitiert werden.

## 10. Verwendung unter Q und Real World

Dasselbe dokumentierte Behaviour-Assumption-Set wird unter beiden Maßen
angewandt; es gibt keine separate physische Behaviour-Kalibrierung. Die
effektiven Entscheidungen unterscheiden sich dennoch pfadweise, weil IV,
Surrender Value, MVA, Zins und Garantie-PV aus dem jeweiligen Marktpfad stammen.

Gemäß Repository-Konvention gilt:

- marktkonsistente Bewertung: standardmäßig Heston-Hull-White unter Q,
- vereinfachte Real-World-Projektion: Black-Scholes-Hull-White unter
  `Measure.REAL_WORLD`.

Die Real-World-Ergebnisse sind als vereinfachte Projektionen mit festen
Proxy-Annahmen zu kennzeichnen. Das Behaviour-Modell führt keine zusätzliche
Marktzeitreihe oder physische Verhaltenskalibrierung ein.

## 11. Modellgrenzen und Governance

1. **Keine Experience-Kalibrierung.** Die Parameter sind literatur- und
   praxisinformierte Startwerte, aber nicht auf Bestands- oder australischen
   Marktdaten geschätzt.
2. **Begrenzte Segmentierung.** Phase, Policy Duration, aktueller Markt-/
   Garantiezustand und Prämienhöhe wirken; weitere Merkmale wie Vertriebskanal,
   Steuerstatus, Liquiditätsbedarf, Gesundheit oder Adviser-Einfluss fehlen.
3. **Proxy für Garantie-PV.** Der Annuitätenfaktor nutzt einen
   Zehnjahres-Forward-Zero-Zins und ist kein vollständiger Cashflow-PV über die
   gesamte pfadweise Zinskurve.
4. **Einmalige Bruttoprämie.** Die Prämienkovariate ist der anfängliche bezahlte
   Betrag; spätere Beiträge oder Premium-Historien werden nicht modelliert.
5. **Gemischte Ereignisdarstellung.** Lapse und Tod sind gewichtete Decrements,
   Take-up wird diskret gezogen, Withdrawals sind erwartete Utilisationen.
6. **Withdrawal-Vereinfachung.** Es gibt kein kalibriertes
   Incidence-/Severity-Hurdle-Modell.
7. **LSMC ausgeschlossen.** Das Basismodell bildet kein optimal-rationales oder
   wertmaximierendes Verhalten ab.
8. **Kosten sind Proxy-Annahmen, sofern die Kosten-CSV sie so kennzeichnet.**
   Die zentrale Ablage macht sie nachvollziehbar, aber nicht automatisch
   beobachtet oder kalibriert.
9. **Produkt-Gates gehen vor.** Positive Legacy-Annahmen für Growth-Lapse oder
   Growth-Withdrawals werden im generischen Produkt geladen und dokumentiert,
   erzeugen aber keinen vertraglich unzulässigen Cashflow.
10. **Joint-Life-State-Grenze.** Der bedingt gemeinsame Continue-Income-Zweig
    verwendet state-unabhängige statische CSV-Basisraten. Der Single-Life-
    Fallback bleibt dynamisch. Vollständig dynamisches Joint-Life-Behaviour
    erfordert getrennte `p11`-, `p10`- und `p01`-AV-, Fee- und In-force-
    Kohorten und wird bis dahin nicht durch eine Nichtlinearität auf einem
    gemittelten Zustand approximiert.

Ergebnisse sind deshalb als **vereinfachte dynamische Policy-Behaviour-
Projektionen mit festen Proxy-Annahmen** zu bezeichnen.

## 12. Methodische Quellen

Die Quellen begründen die Wahl etablierter Modellklassen und relevanter
Kovariaten. Sie begründen **nicht** die konkreten CSV-Koeffizienten:

- Cox, *Regression Models and Life-Tables* (1972): Grundlage proportionaler
  Hazard-Modelle. [JSTOR](https://www.jstor.org/stable/2985181),
  [DOI](https://doi.org/10.1111/j.2517-6161.1972.tb00899.x)
- Society of Actuaries, *Predictive Analytics Call for Essays* (2016):
  versicherungsmathematische Anwendung von Lapse-Modellen mit Duration,
  Moneyness und weiteren erklärenden Variablen.
  [SOA-PDF](https://www.soa.org/4938ac/globalassets/assets/files/resources/essays-monographs/research-2016-predictive-analytics-call-essays.pdf)
- Society of Actuaries, *Policyholder Behavior in the Tail: Variable Annuity
  Guaranteed Benefits Survey* (2019/2020): Moneyness und Policy Size als in der
  Praxis verwendete Behaviour-Faktoren.
  [SOA-PDF](https://www.soa.org/4929f2/globalassets/assets/files/resources/research-report/2020/policy-behavior-tail-risk.pdf)
- Papke/Wooldridge, *Econometric Methods for Fractional Response Variables with
  an Application to 401(k) Plan Participation Rates*: methodischer Anker für
  Fractional-Logit-Antworten im Einheitsintervall.
  [NBER](https://www.nber.org/papers/t0147)
- Knoller/Kraut/Schoenmaekers, *On the Propensity to Surrender a Variable
  Annuity Contract*: empirische Einordnung der Bedeutung von Moneyness und
  Vertrags-/Prämienmerkmalen für dynamisches Verhalten.
  [Journal of Risk and Insurance](https://onlinelibrary.wiley.com/doi/10.1111/jori.12076)

## 13. Zentrale Fundstellen

- `input_dynamic_behaviour/README.md`
- `input_dynamic_behaviour/dynamic_behaviour_baselines.csv`
- `input_dynamic_behaviour/dynamic_behaviour_coefficients.csv`
- `AGILE_Modelling_Engine/agile_engine/dynamic_behaviour_assumptions.py`
- `AGILE_Modelling_Engine/agile_engine/behavior.py`
- `AGILE_Modelling_Engine/agile_engine/projection.py`
- `AGILE_Modelling_Engine/agile_engine/product.py`
- `AGILE_Modelling_Engine/agile_engine/cost_assumptions.py`
- `C:\Users\user\Documents\GMLB Structuring\input_cost_assumptions\cost_assumptions.csv`
- `AGILE_Modelling_Engine/agile_engine/lsmc.py` (archiviert, nicht angebunden)
- `Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md`
