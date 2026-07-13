# Portfoliobewertung

`run_portfolio_valuation.py` ist der operative Einstiegspunkt für die
marktkonsistente Bewertung der gewichteten New-Business-Modellpunkte des
generischen Index-Linked-Lifetime-Income-Fallprodukts. Jeder Modellpunkt wird
zuerst als eigener repräsentierter Vertrag bewertet. Erst danach werden seine
skalaren Ergebnisse mit dem Vertragsgewicht zum Portfolio aggregiert.

Der Defaultlauf verwendet Heston-Hull-White unter dem risikoneutralen Maß und
Plain Monte Carlo mit gemeinsamen Marktpfaden für alle Modellpunkte. COS und
LSMC werden nicht verwendet.

Auf Versichererseite ist das administrative Guthaben nicht im Reference Fund
investiert. Es verdient ausschließlich den pfadweisen AUD-Overnight-Return aus
der Hull-White-Zinssimulation. Die annualisierte Optionsreplikation wird davon
getrennt als Hedge gebucht; Kunden-AV, Crediting und Claims bleiben unverändert.

## Defaultlauf

Aus `AGILE_Modelling_Engine`:

Der Befehl setzt für den Default `mc_conditional` einen zuvor exakt passend
erzeugten Hedgepreis-Cache voraus; der Precompute-Ablauf steht im folgenden
Abschnitt.

```powershell
python portfolio_simulations/run_portfolio_valuation.py
```

Die Grafiken werden standardmäßig headless mit Matplotlib erzeugt. Matplotlib
ist eine reguläre Projektabhängigkeit und wird bei der normalen Installation
des Modelling Engine mit installiert:

```powershell
pip install -e .
```

Falls ausschließlich die CSV-/JSON-Ergebnisse benötigt werden, kann die
Grafikerstellung ausdrücklich abgeschaltet werden:

```powershell
python portfolio_simulations/run_portfolio_valuation.py --no-plots
```

Pfadanzahlen und Seeds werden standardmäßig aus
`../../input_MC_analysis/portfolio_analysis.csv` gelesen. Die Datei enthält
getrennte Rollen für Evaluation, LSMC-Training und LSMC-Validierung. Wie viele
der nummerierten LSMC-Trainings-Seed-Sätze tatsächlich aktiv sind, bestimmt das
aufrufende Skript und nicht die CSV. Explizite Kommandozeilenwerte für
Pfadanzahlen oder Seeds bleiben als Overrides verfügbar.

Die Aktienquote des Reference Fund wird aus
`../../input_equity_allocation/equity_allocation.csv` gelesen. Der Bondanteil
wird immer als `1 - equity_weight` abgeleitet. Der mitgelieferte Basiswert ist
30 % Aktien / 70 % Bonds; die Allokation ist eine Produkteingabe und kein
kalibrierter Marktparameter.

## Wiederverwendbare Q-Markt- und Hedge-Caches

Der Standard `mc_conditional` bewertet die jährlich neu gekaufte einjährige
Call-Spread-Hedgeposition aus einem vorab berechneten Cache. Nur
`precompute_q_market_and_hedge_cache.py` schreibt Cache-Einträge; alle
Bewertungs-, Behaviour- und Optimierungsrunner sind reine Leser. Ein Beispiel
für den gelieferten 4-Point-Default mit 6 % Cap ist:

```powershell
python portfolio_simulations/precompute_q_market_and_hedge_cache.py `
  --horizon-years 53 --n-paths 2000 --seed 2026 --cap-grid 0.06
python portfolio_simulations/run_portfolio_valuation.py `
  --require-market-cache --require-hedge-cache
```

Horizont, Pfadzahl, Seed und Cap-Grid müssen zum jeweiligen Consumer exakt
passen. Training, Validierung und Evaluation benötigen wegen ihrer
unterschiedlichen Seeds und Pfadzahlen eigene Einträge. Dasselbe gilt für jede
Marktstress-Variante. Der Key bindet außerdem Kurven- und Parameter-Hashes,
ESG-Konfiguration, Heston-Substeps, Aktienallokation samt Datei-Hash sowie die
Cross-Fit-Einstellungen. Es gibt keine unscharfe Cache-Suche und ein
existierender inkonsistenter Eintrag wird nie überschrieben.

Ohne `--cap-grid` verwendet der Precompute-Runner das vollständige
Optimierungsgrid 0,25 %, 1 %, 2 %, ..., 20 %. Der schnelle LSMC-Grid und
Fixed-Cap-Läufe müssen ihr jeweils exaktes Grid ausdrücklich angeben.

Die großen Markt- und Preisarrays liegen getrennt als read-only memory-mapped
`.npy`-Dateien unter `portfolio_simulations/cache/q_market_paths` und
`portfolio_simulations/cache/q_hedge_prices`; Manifeste und Content-
Fingerprints werden beim Laden erneut geprüft. Diese Verzeichnisse sind nicht
für Git bestimmt.

Für jedes Anniversary und jeden Cap-Punkt schätzt ein fold-excluding
Ridge-Modell den bedingten Barwert des im Folgejahr realisierten vollständigen
Reference-Fund-Call-Spreads. Features sind ausschließlich der zum Anniversary
bekannte Zustand: Heston-Varianz, Short Rate, ein- und fünfjähriger Zero Rate
und Vertragsjahr. Nach der Schätzung werden Nichtnegativität, Cap-Monotonie,
der Nullwert bei Cap null und eine diskontierte Payoff-Obergrenze erzwungen.
Es gibt weder Look-ahead über den Folgejahres-Payoff des eigenen Pfads noch
nested Monte Carlo.

Die Hedgekosten werden damit jährlich am jeweiligen Anniversary neu bewertet;
es wird kein kompletter Forward-Start-Strip bei Vertragsbeginn gekauft. Der
unterjährige DVA bleibt davon getrennt ein moment-matched Black-Scholes-Proxy.
Der entsprechende BS-Hedgewert wird bei `mc_conditional` nur als diagnostischer
Proxy ausgegeben und nicht zusätzlich als Kosten gebucht. Als ausdrücklich
gewählter Fallback steht
`--hedge-pricing-method moment_matched_bs` zur Verfügung; dafür ist kein
Hedgepreis-Cache erforderlich.

## Crediting-Rate-Szenarien

`run_crediting_rate_scenarios.py` ruft den Portfolio-Runner für mehrere
konstante Maximum-Return-/Crediting-Rate-Szenarien auf und vergleicht die
marktkonsistente Profitabilität vor Risk Margin. Der vertragliche Maximum
Return des Fallprodukts bleibt 6 %. Abweichende Raten sind ausdrücklich als
nichtvertragliche Design- und Sensitivitätsszenarien gekennzeichnet.

Die Standardszenarien sind 4 %, 6 %, 12 % und 20 %. Sie können ohne weitere
Ratenangabe gerechnet werden:

```powershell
python portfolio_simulations/run_crediting_rate_scenarios.py
```

Alternativ können Dezimalwerte oder Werte mit Prozentzeichen angegeben werden,
zum Beispiel `0.04 0.06 0.08` oder `4% 6% 8%`. Alle Läufe verwenden dieselbe
Pfadanzahl, denselben Seed und dieselben Heston-Substeps. Der Runner prüft
zusätzlich, dass die Marktszenario-Fingerprints über alle Raten identisch sind.

Die Ergebnisse liegen standardmäßig unter
`portfolio_simulations/output/crediting_rate_scenarios`:

- `crediting_rate_profitability_comparison.csv` enthält die vergleichbaren
  Portfolio-Kennzahlen und Deltas gegen den 6%-Basisfall;
- `crediting_rate_profitability_report.md` enthält eine kompakte Ergebnistabelle;
- `crediting_rate_profitability_comparison.png` vergleicht Insurer NPV und New
  Business Margin jeweils vor Risk Margin;
- `scenarios/crediting_rate_*` enthält die vollständigen Ergebnisse jedes
  einzelnen Aufrufs von `run_portfolio_valuation.py`.

Der Vergleichsoutput trennt administrative Expenses, gesamten Hedge Cost,
fairen Optionspaketwert, 0,50%-Kaufmarge, 0,30%-Management-Fee-Drag,
gegebenenfalls den Legacy-Execution-Proxy, Money-Market-Ertrag und optionalen
Above-Cap-Hedge-Gewinn. Dadurch werden Kosten und Erträge nicht über ein
irreführendes Total-Expense-Feld vermischt.

## Eingabedaten

Der Runner verwendet standardmäßig genau diese Repository-Quellen:

- `../../input_model_points_policyholders/model_points_policyholders_4_point_proxy.csv`;
- `../../input_cost_assumptions/cost_assumptions.csv`;
- `../../input_dynamic_behaviour/dynamic_behaviour_baselines.csv`;
- `../../input_dynamic_behaviour/dynamic_behaviour_coefficients.csv`;
- `../input_market_data/australian_zero_curve.csv`;
- `../input_market_data/model_parameters.csv`.

Die 4-Point-Datei ist der schnelle operative Default. Die ausführliche
48-Point-Variante bleibt über
`--model-points ../../input_model_points_policyholders/model_points_policyholders.csv`
explizit verfügbar. Die tatsächlichen Pfade, Annahmensatz-IDs und
Source-Fingerprints werden im
Run-Manifest festgehalten. Die australische Zinskurve ist die laufend
eingelesene Marktdatenquelle. Die bereits vorhandenen Equity-, Heston-,
Hull-White- und Korrelationsparameter stammen aus `model_parameters.csv`.

Der Modellpunkt-Loader akzeptiert derzeit den gelieferten Duration-0-
New-Business-Zustand: Growth-Phase, Fixed Income, kein bereits initiiertes
Withdrawal und kein Locked Income. Premium, Initial Investment und Account
Value bei `t=0` müssen konsistent sein. Alte AGILE-Allokationsfelder sowie
Produkt-, PDS- und Cap-Metadaten werden nur auf Quellenintegrität geprüft; sie
steuern weder die zentrale Reference-Fund-Allokation noch dessen festen 6%-Cap.

## Einzelbewertung und Portfolioaggregation

Die Verarbeitung erfolgt in dieser Reihenfolge:

1. Ein gemeinsamer Satz risikoneutraler Marktszenarien wird aufgebaut.
2. Jeder Modellpunkt wird mit seiner eigenen Demografie, Prämie,
   Single-/Joint-Life-Ausprägung und Income-Election einzeln projiziert.
3. Je Modellpunkt werden unskalierte Per-Contract-Werte gespeichert.
4. Die Per-Contract-Werte werden mit `contract_weight` zu einem normierten
   Durchschnittsvertrag aggregiert.
5. Nur wenn `exposure_count` je Modellpunkt oder eine gesamte Vertragsanzahl
   `N_total` vorhanden ist, werden zusätzlich absolute Modellpunkt-Exposures
   und Portfoliowerte berechnet.

`premium_volume_weight` ist ausschließlich eine Exposure- und Kontrollgröße.
Es darf nicht als zweites Gewicht auf denselben Barwert angewandt werden.

### Normalisierte Basis ohne Vertragsanzahl

Die gelieferten `contract_weight` summieren sich auf eins. Ohne weitere
Bestandsangabe gilt daher:

```text
normalised_average_PV = sum_i(contract_weight_i * per_contract_PV_i)
```

Das ist ein gewichteter Durchschnittsvertrag, kein absoluter Bestand und keine
einzige vor der Projektion zusammengefasste Police. Insbesondere werden die
Modellpunktzeilen — im Default vier Proxy-Zeilen — nicht als einzelne Policen
interpretiert. Der Runner weist beim Start und in den Outputs ausdrücklich auf
diese Basis hin.

### Absolute Portfoliobasis

Für einen Bestand mit beispielsweise 100.000 Verträgen:

```powershell
python portfolio_simulations/run_portfolio_valuation.py `
  --portfolio-contract-count 100000
```

Dann gilt je Modellpunkt und für das Gesamtportfolio:

```text
represented_contract_count_i = N_total * contract_weight_i
portfolio_contribution_PV_i   = represented_contract_count_i * per_contract_PV_i
portfolio_total_PV            = sum_i(portfolio_contribution_PV_i)
```

Alternativ kann die Inputdatei ein fachlich bestätigtes `exposure_count` je
Modellpunkt liefern. Dann verwendet der Core diese Bestandszahlen direkt und
prüft ihre Summe. Ein zusätzlich angegebenes `--portfolio-contract-count` muss
mit der Source-Summe übereinstimmen.

Die Vertragsanzahl muss fachlich vorgegeben werden. Der Runner erfindet weder
eine Bestandsgröße noch unterstellt er einen Vertrag je Modellpunktzeile.

## Ausgaben

Der Default-Ausgabeordner ist
`portfolio_simulations/output/portfolio_valuation/`.

### Tabellarische Ergebnisse

- `portfolio_summary.csv` enthält Portfolio-Kennzahlen und Kontrollfelder.
  Additive Geldbeträge werden immer als `normalised_average_<metric>`
  ausgewiesen. Bei vorhandenen Source-Exposures oder explizitem `N_total` kommen
  `portfolio_total_<metric>`-Felder hinzu.
- `model_point_results.csv` enthält genau eine Zeile je geladenem Modellpunkt:
  `per_contract_<metric>`, `normalised_contribution_<metric>` sowie bei
  absoluter Portfoliobasis `represented_contract_count` und
  `portfolio_contribution_<metric>`.
- `portfolio_aggregation_reconciliation.csv` gleicht für jede additive
  Kennzahl die Summe der Modellpunktbeiträge mit dem ausgewiesenen
  Portfolioergebnis ab.
- `model_point_fair_fee_results.csv` wird erzeugt, wenn individuelle Fair-Fee-
  Berechnungen angefordert wurden. Es enthält die Fee-Solver-Status, Raten,
  Spreads und Profitabilitätswerte in einer kompakten Datei.

### Run-Protokoll und Manifest

- `portfolio_valuation.log` enthält Zeitstempel, Eingabe- und Basisangaben,
  Fortschrittsmeldungen je Modellpunkt, Solver-Status und abschließende KPIs.
- Eigene Konsolenmeldungen der Portfolio-, Szenario-, LSMC- und Risiko-Runner
  beginnen einheitlich mit lokaler Zeit im Format
  `YYYY-MM-DD HH:MM:SS | LEVEL | Meldung`.
- `run_manifest.json` dokumentiert Engine-Version, Laufzeit, Methoden,
  Annahmensätze, Datenquellen, Szenario-Fingerprint, Gewichtungsregeln,
  Fair-Fee-Einstellungen, Outputs und Modellgrenzen.

Mit `--log-level DEBUG|INFO|WARNING|ERROR` wird die Detailtiefe gesteuert.
`--log-file` kann einen abweichenden Pfad vorgeben.

### Grafiken

Standardmäßig entstehen im Unterordner `figures/`:

1. `01_portfolio_nonunit_bel_components.png`: Komponenten des Non-Unit BEL;
2. `02_model_point_npv_contributions.png`: Wertbeitrag jedes Modellpunkts zum
   normalisierten beziehungsweise absoluten Insurer NPV;
3. `03_model_point_profitability_heatmaps.png`: New Business Margin nach Alter,
   Prämie, Geschlecht und Single-/Joint-Life;
4. `04_portfolio_exposure_mix.png`: Contract-Weight- und separate
   Premium-Volume-Weight-Sicht;
5. `05_model_point_fair_fee_gaps.png`: optionale Fair-Fee-Spreads bei
   angeforderten individuellen Fee-Solves.

Alle Geldachsen und Fußzeilen kennzeichnen, ob normalisierte Durchschnittswerte
oder absolute Portfoliowerte gezeigt werden. Die Grafiken sind Reporting-Sichten
auf bereits berechnete Skalare und lösen keine zusätzlichen Projektionen aus.

## Kennzahlen

Der Lauf berichtet insbesondere:

- Gross Present Value of Policyholder Benefits;
- Present Value of Future Charges, getrennt nach Product Fee und Lifetime
  Income Premium;
- Present Value of Guarantee Claims, Expenses und Hedge Costs, einschließlich
  fairem Optionspaket, Kaufmarge und Hedge-Management-Fee;
- Present Value of stochastic Money-Market Income und des optionalen retained
  Excess Hedge Gain;
- Non-Unit Best Estimate Liability und Total Best Estimate Liability;
- Market-Consistent Insurer Net Present Value before Risk Margin;
- New Business Margin before Risk Margin;
- Guarantee Value sowie Market-Consistency- und Aggregationsabgleiche.

`market_consistent_bel_total_aud` ist der heutige marktkonsistente Wert der
gesamten zukünftigen Liabilities einschließlich Account-Value-Komponente.
`pv_future_fees_aud` ist der Present Value of Future Charges aus tatsächlich
vereinnahmbaren Product Fees und Lifetime Income Premiums.

Guarantee Claims sind bereits der aus dem Account Value nicht finanzierte Teil
des Income-Cashflows. Sie dürfen deshalb nicht zusätzlich zum Gross PV der
Policyholder Benefits addiert werden.

Das Money-Market Income wird auf dem administrativen Crediting-Frame am Beginn
jedes Monatsintervalls gebildet. Der unterjährige DVA-Optionswert bleibt eine
Liability-Größe und wird nicht als Backing-Asset behandelt; als Return dient
ausschließlich die pfadweise AUD-Overnight-Akkumulation.

Die Profitabilitätsklassifikation eines Modellpunkts verwendet standardmäßig
eine Materialität von einem Basispunkt seiner Prämie. Der Grenzwert kann über
`--profitability-materiality-bp` geändert werden. NPV und NBM bleiben zusätzlich
als kontinuierliche Kennzahlen erhalten.

## Individuelle und portfolioeinheitliche Fair Fees

Die beiden Fragestellungen werden getrennt ausgewiesen.

### Modellpunktbezogene Diagnostik

```powershell
python portfolio_simulations/run_portfolio_valuation.py `
  --fair-lip `
  --commercial-break-even-lip
```

- `--fair-lip` löst je Modellpunkt
  `PV(Guarantee Claims) - PV(LIP) = 0`.
- `--commercial-break-even-lip` löst je Modellpunkt den vollständigen
  Market-Consistent Insurer NPV before Risk Margin auf null.

Die Differenz zwischen belasteter und modellimplizierter Rate sowie der NPV-
Beitrag zeigen, an welchen Modellpunkten unter den gegebenen Annahmen mehr oder
weniger verdient wird. Die Ergebnisse sind Diagnostiken und keine empfohlenen
kundenspezifischen Gebühren.

### Einheitliche Portfolio-Fee

```powershell
python portfolio_simulations/run_portfolio_valuation.py `
  --portfolio-fair-lip `
  --portfolio-commercial-break-even-lip
```

- `--portfolio-fair-lip` löst eine einzige LIP gegen den aggregierten
  Guarantee Value des Portfolios.
- `--portfolio-commercial-break-even-lip` löst eine einzige LIP gegen den
  aggregierten Insurer NPV before Risk Margin.

Eine einheitliche Portfolio-Fee wird direkt gegen das aggregierte Ziel gelöst.
Sie ist ausdrücklich kein Durchschnitt der individuellen Fair Fees. Alle Solver
verwenden dieselben Marktszenarien wie die Basisbewertung. Wenn innerhalb der
zulässigen Grenzen kein Vorzeichenwechsel besteht, wird ein `no_bracket_*`-
Status statt eines extrapolierten Ergebnisses ausgegeben.

Die ausgewiesenen Objective-Werte der Portfolio-Solver verwenden die
normalisierte Durchschnittsvertragsbasis. Eine Multiplikation mit `N_total`
ändert bei vorhandenem Bestand nur die AUD-Skalierung, nicht die gefundene Fee.

## Wichtige Schalter

| Schalter | Bedeutung |
|---|---|
| `--n-paths` | Anzahl gemeinsamer Q-Pfade; Default 2.000 |
| `--seed` | Market-Scenario-Seed; Default 2026 |
| `--take-up-seed` | separater Seed der pfadweisen Income-Election |
| `--mortality-seed` | separater Seed für pfadweise Lebenszustände |
| `--income-election-mode dynamic\|deterministic` | Dynamic-Hauptlauf oder expliziter Modellpunkt-Benchmark |
| `--post-income-behaviour dynamic\|continue` | Post-Election-Behaviour oder No-Exit-Benchmark |
| `--heston-substeps` | Heston-Substeps je Monat; Default 4 |
| `--hedge-cap-leg-mode sold\|not_sold` | `sold` ist der Standard ohne Above-Cap-Gewinn; `not_sold` behält die Cap-Call-Leg |
| `--portfolio-contract-count` | gesamte Anzahl repräsentierter Verträge |
| `--fair-lip` | aktuariell faire LIP je Modellpunkt |
| `--commercial-break-even-lip` | kommerzielle Break-even-LIP je Modellpunkt |
| `--portfolio-fair-lip` | einheitliche aktuariell faire Portfolio-LIP |
| `--portfolio-commercial-break-even-lip` | einheitliche kommerzielle Portfolio-Break-even-LIP |
| `--fair-fee-lower`, `--fair-fee-upper` | anfängliche Fee-Klammer |
| `--fair-fee-maximum-upper` | maximale Erweiterung der Klammer |
| `--fair-fee-tolerance` | numerische Toleranz des Fee-Solvers |
| `--profitability-materiality-bp` | Materialität der Profitabilitätsklassifikation |
| `--no-plots` | Grafikerstellung ausdrücklich deaktivieren |
| `--log-level` | Detailtiefe von Konsole und Logfile |
| `--log-file` | optionaler abweichender Logfile-Pfad |
| `--output` | Ausgabeverzeichnis |

Inputpfade und Annahmensatz-IDs können über `--model-points`,
`--cost-assumptions`, `--cost-assumption-set`, `--dynamic-behaviour`,
`--behaviour-assumption-set`, `--zero-curve` und `--model-parameters`
explizit gesetzt werden.

## Mortalität, Verhalten und Joint Life

Der schlanke Research-Runner verwendet den ausdrücklich illustrativen
Gompertz-Makeham-Proxy. Er approximiert lediglich die Form von ALT 2020-22 und
ist keine kalibrierte oder freigegebene australische Insured-Lives-Basis.

Im Dynamic-Hauptlauf ist die Income Election ab Vertragsbeginn eine
zustandsabhängige pfadweise Take-up-Entscheidung. Auf jedem vertraglich
zulässigen Policy Anniversary verwendet sie nur den dann bekannten Zustand,
unter anderem Account Value, sofort erreichbares Lifetime Income,
Garantie-Moneyness, bisherige Reference-/Credited Returns, sichtbaren
Performance Gap, Alter und Vertragsdauer. Mindestwartezeit und Rate Card gelten
am tatsächlichen Start. Ein noch lebender, nicht electeder Vertrag startet
spätestens am ersten zulässigen Anniversary nach Erreichen des Alters 100.

`income_start_year` des Modellpunkts ist deshalb im Dynamic-Hauptlauf kein
realisierter Starttermin mehr. Es bleibt als rückwärtskompatibler Produktinput
für `--income-election-mode deterministic` und für die expliziten
2×2-Validierungsbenchmarks sowie als vorab deklarierter Kandidat der
LSMC-Trainings-Untergrenze erhalten. Die Behaviour-CSVs sind die Parameterquelle
für Dynamic Take-up sowie Ordinary-/Performance-Lapse und Withdrawals; es wird
keine zusätzliche physische Kalibrierung eingeführt.

Single-Life-Verträge verwenden erwartete Dekremente. Joint-Life-Verträge
werden in den Portfolio-Hauptläufen und in allen V00/V01/V10/V11-Armen mit
pfadweise getrennten Primary-/Spouse-Lebenszuständen fortgeschrieben. Die
nichtlineare Take-up- oder Lapse-Funktion wird nicht auf einen gemittelten
`p11/p10/p01`-Zustand angewandt; alle Faktor-Arme verwenden dieselben
Mortalitätsziehungen. Der Standalone-Low-Level-Projektor behält für rein
deterministische Joint-Life-Läufe standardmäßig den historischen Expected-
Decrement-Fallback. Abhängige Leben, Scheidung, Removal und Common-Shock-
Mortalität bleiben Modellgrenzen.

Income-Lapse bleibt bei fortbestehender Income-Garantie auch nach Aufzehrung
des Account Value aktiv. Der Surrender Benefit ist dann null; ein Lapse beendet
aber die Garantie sowie künftige Garantieclaims und laufende Expenses.
Ordinary Hazard, Performance Hazard und Gesamtwahrscheinlichkeit werden
getrennt ausgewiesen. Income Election und Full Withdrawal am selben
Entscheidungszeitpunkt sind nicht zulässig; die erste Income-Zahlung folgt der
vertraglichen monatlichen Event-Reihenfolge nach der Election.

## Optimal-Behaviour-Portfoliobewertung mit LSMC

`run_portfolio_valuation_lsmc.py` bewertet dasselbe generische Portfolio mit
demselben Heston-Hull-White-Modell unter Q, denselben Markt-, Kosten-,
Mortalitäts- und Produktannahmen sowie derselben Portfolioaggregation wie
`run_portfolio_valuation.py`. Die eingefrorene LSMC-Policy projiziert den
Vertrag ab t=0 und optimiert Income Election und die monatlichen freiwilligen
Income-Aktionen in einer gemeinsamen phasenabhängigen Bellman-Rekursion:

```text
Growth: WAIT | START_INCOME_NOW
Income: CONTINUE | PARTIAL_WITHDRAWAL | FULL_WITHDRAWAL
```

`START_INCOME_NOW` ist ein Zustandsübergang, keine sofortige Auszahlung. Das
Lifetime Income wird mit der Rate Card und dem am Election-Zeitpunkt bekannten
Zustand fixiert; danach greift dieselbe optimierte Income-Phase-Policy. Income
kann nur auf zulässigen Anniversaries und nicht vor der Mindestwartezeit
beginnen. Das reguläre Fixed Income bleibt danach eine verpflichtende
monatliche Zahlung. PARTIAL ist nach der regulären Event-Reihenfolge bereits
im Election-Monat zulässig, FULL dagegen erst ab dem Folgemonat. Materiell
fehlende oder instabile Regressionen machen den Fit ungültig und brechen den
Runner nach Ausgabe der Diagnostik ab; sie werden nicht still als WAIT oder
CONTINUE interpretiert.

Growth-Surrender und Growth-Withdrawals bleiben vertraglich verboten. Für
PARTIAL werden AUD 100 sowie 25%, 50%, 75% und 100% des maximal zulässigen
Grossbetrags `max(AV - 2.000, 0)` geprüft; ungültige und doppelte Beträge
entfallen. Eine lokale Runde prüft anschließend die benachbarten Mittelpunkte.
Account Value und Locked Income werden mit den bestehenden Produktformeln
proportional reduziert; die MVA wirkt auf den ausgezahlten Cashflow.

Der Defaultlauf verwendet für jeden von drei vorab festgelegten Trainings-
Seed-Tripeln 4.000 Trainingspfade, dazu 2.000 gemeinsame unabhängige
Validierungspfade und 2.000 davon ebenfalls getrennte finale Evaluationspfade:

```powershell
python portfolio_simulations/run_portfolio_valuation_lsmc.py
```

Die Backward-Induction verwendet pfadgruppierte fünfteilige Cross-Fits und
regressiert direkte Action Advantages. Standardisierung erfolgt nur im
jeweiligen Trainingsfold; ein augmentierter truncated-SVD/Ridge-Solve ersetzt
Normalgleichungen. Ridge wird aus einem festen Raster per OOF-Decision-Loss
gewählt, und der konservative Puffer basiert auf der Advantage-RMSE. Die
Zustände enthalten nur am
Entscheidungszeitpunkt bekannte Größen; zukünftige Returns, Caps,
Diskontfaktoren oder Hedge-Ergebnisse sind ausgeschlossen. Nur die auf dem
Trainingssample eingefrorene gemeinsame Policy wird im monatlichen Projektor
zuerst validiert und danach final bewertet. Election-only, Income-action-only
und Combined müssen jeweils eine gepaarte 95%-Nichtunterlegenheitsgrenze von
minus einem Basispunkt der Prämie gegen die vorab festgelegte Benchmarkbibliothek
einhalten. Die Validation verändert die Policy nicht; das finale Sample wird
niemals zur Policy-Auswahl verwendet.

Election wird auf vertraglichen Policy Anniversaries entschieden; die drei
Income-Aktionen werden monatlich entschieden. Separate Training-, Validation-
und Evaluation-Seeds für Marktpfade, Take-up und Mortalität werden im Manifest
und durch unterschiedliche Szenario-Fingerprints ausgewiesen. Jeder der drei
Fits muss die Election-, Income- und Combined-Gates einzeln bestehen und wird
auf denselben finalen Pfaden berichtet. Seed 1 ist vorab als Primary Policy
festgelegt; die Evaluation wird nicht zur Auswahl zwischen Seeds verwendet.

Der Runner rechnet standardmäßig zusätzlich:

- den unveränderten Dynamic-Behaviour-Benchmark auf exakt demselben
  Evaluationsszenariosatz;
- `deterministic_election_continue` (V00);
- `deterministic_election_post_behaviour` (V01);
- `variable_election_continue` (V10);
- den LSMC-Out-of-sample-Rollout.

Die drei fachlichen Benchmark-IDs werden physisch kompakt unter
`bench/v00`, `bench/v01` und `bench/v10` abgelegt.

V01 verwendet die monatliche Income-Aktionsregel aus dem gemeinsamen Fit, ohne sie
unter deterministischer Election separat neu zu fitten. V10 verwendet
umgekehrt die Election-Regel aus dem gemeinsamen Fit und unterdrückt alle
freiwilligen Income-Aktionen in der Evaluation, ohne eine Continue-only-
Election-Policy neu zu optimieren.
Beide Einschränkungen werden im Manifest ausgewiesen; die vier Werte bleiben
eine transparente Faktorzerlegung der eingefrorenen gemeinsamen Policy und
keine Sammlung vier unabhängig optimierter Verträge.

Neben den vollständigen Portfolio- und Modellpunktergebnissen entstehen
`comparison_summary.csv`, `model_point_comparison.csv`,
`lsmc_vs_continue_summary.csv`, `lsmc_regression_diagnostics.csv`,
`lsmc_action_summary.csv`, `lsmc_validation_summary.csv` und
`lsmc_validation_manifest.json` sowie
`lsmc_multi_seed_validation_evaluation.csv`. Regressionen, Fallbacks und Action-Anteile
werden für `income_election`, `continue`, `partial_withdrawal` und
`full_withdrawal` getrennt ausgewiesen. Das Manifest dokumentiert Training,
Validation und Evaluation einschließlich separater Seeds,
Szenario- und Fit-Basis-Fingerprints, Action Sets, Forced-Election-Regel,
Joint-Life-Behandlung und Benchmark-Semantik. Mit
`--no-dynamic-benchmark` kann nur der zusätzliche Originalvergleich
abgeschaltet werden; der Variable-Election/Continue-Benchmark bleibt als
LSMC-Validierung aktiv.

Fair-Fee-Solves sind in diesem Runner bewusst nicht freigeschaltet. Eine
Gebührenänderung verändert die optimale Policy und würde deshalb bei jedem
Root-Finder-Schritt ein neues LSMC-Training erfordern.

### Sensitivität gegenüber dem Crediting Cap

Der separate Szenario-Runner trainiert die gemeinsame Election-/Post-Election-
Policy für jede Cap×Stress-Zelle neu und bewertet Varianten innerhalb eines
Stresses mit Common Random Numbers auf einem vom Training getrennten Pfadsatz:

```powershell
python portfolio_simulations/run_lsmc_cap_behaviour_scenarios.py `
  --cap-rates 4% 6% 12% 20% `
  --stress-scenarios base interest_up equity_level_down `
  --no-dynamic-benchmark
```

Er erzeugt `lsmc_cap_behaviour_comparison.csv`, einen kompakten Markdown-Bericht,
eine Grafik, ein Manifest sowie die vollständigen Einzelergebnisse je Zelle.
Wiederverwendung wird erst nach Prüfung von Cap, Stress, Seeds, Action Sets,
Benchmark-Semantik, Reconciliations und runner-erzeugtem Fit-Basis-Fingerprint
zugelassen. Das Vergleichsmanifest belegt einen eindeutigen Joint-Policy-Fit je
Cap×Stress-Zelle.

Report und CSV zeigen Startjahr-Momente, Election-/Forced-Anteile,
Growth-Dauer/-Exposure, Income-Lapse, separate ungewichtete Election- und
Full-Withdrawal-Aktionsraten sowie Phasen-PVs. Die vier Benchmarks zerlegen den
Behaviour-Effekt in Income-Election-Timing, Verhalten nach Election und deren
Interaktion. Portfolio-Kennzahlen sind vertrags-, Q-pfad- und
In-force-/Survival-gewichtet; Action-Raten bleiben ungewichtete
Modellpunkt-/Pfad-/Entscheidungsdiagnostik. Da die Portfolioausgabe kein
pfadweises gepaartes Konfidenzintervall enthält, sollten Aussagen zur Stabilität
der Verhaltensoptionalität zusätzlich mit unabhängigen Trainings- und
Evaluations-Seeds repliziert werden.

### Portfolio-Risikoanalyse über Caps und Behaviour-Ansätze

`run_portfolio_risk_analysis.py` orchestriert für jedes Cap sowohl
`run_portfolio_valuation.py` als auch `run_portfolio_valuation_lsmc.py` und
untersucht standardmäßig nur Lapse-, Zins- und Longevity-Risiko. Das Lapse-
Risiko wird über den Dynamic-/LSMC-Vergleich und die 2×2-Zerlegung von
Election und Post-Election Behaviour gemessen; es wird nicht als zusätzlicher
statistischer Lapse-Rate-Schock auf die LSMC-Policy angewandt. Die zusätzlichen
Default-Einfaktorstresse sind deshalb `interest_up`, `interest_down` und
`longevity`.

Damit werden standardmäßig in jeder Cap×Stress-Zelle zwingend beide
Hauptansätze gerechnet und verglichen: Dynamic Behaviour mit dynamischer Income
Election und dynamischem Post-Election-Verhalten sowie die neu trainierte
LSMC-Policy. Das intern an den LSMC-Child übergebene
`--no-dynamic-benchmark` verhindert ausschließlich eine zweite, redundante
Dynamic-Rechnung innerhalb dieses Childs; der separate Dynamic-Hauptlauf des
Risiko-Runners bleibt immer aktiv.

Equity-Level-, Equity-Volatility-, Mortality- und Expense-Stresse bleiben als
explizite Forschungsoptionen über `--stress-scenarios` verfügbar, gehören aber
nicht mehr zum Standardlauf. Die Ergebnisse werden als CSVs, Grafiken,
Markdown-Bericht und auditiertes Manifest ausgegeben:

```powershell
python portfolio_simulations/run_portfolio_risk_analysis.py
```

Die aggregierten Risiko-, Behaviour-, LSMC-Diagnostik- und CSM-/Werttreiber-
Grafiken werden standardmäßig unter `figures/` erzeugt. `--no-plots`
deaktiviert diese Analyseplots ausdrücklich. Mit `--scenario-plots` können
zusätzlich die Standardgrafiken jedes einzelnen Dynamic-/LSMC-Child-Laufs
angefordert werden; sie bleiben wegen der großen Dateimenge standardmäßig
deaktiviert.

Je Cap und Ansatz werden unter anderem mean/median/p10/p90 des Income-
Startjahrs, Election-Anteile je Policy Year, verbleibende Growth-Exposures,
Forced-Election-Anteil, mittlere Growth-Dauer, Ordinary-/Performance-/Total-
Income-Lapse, Benefits vor/nach Election, Growth-Fees, Growth-Crediting-Margin,
Post-Election-Guarantee-Claims, Money-Market-Ertrag, Hedgekosten-Komponenten,
optionalem Hedge-Gewinn, BEL und Versicherer-NPV ausgewiesen. Dynamic
und LSMC verwenden dieselben Evaluation-Szenarien; LSMC-Training bleibt davon
getrennt. Das zusätzliche `behaviour_effect_decomposition.csv` enthält die
2×2-Zerlegung in Election-, Post-Election- und Interaktionseffekt. Alte
Fixed-Election-/Surrender-only-Ausgaben und Ausgaben mit abweichendem
`hedge_cap_leg_mode` werden bei `--reuse-existing` abgelehnt.

Unabhängige Kombinationen aus Cap und Stress werden in einer gemeinsamen Queue
standardmäßig mit bis zu 16 Workern parallel gerechnet. Dadurch bleiben die
Worker nach den vier Basisfällen nicht ungenutzt, während auf das Stressgitter
gewartet wird. BLAS/OpenMP ist je Child standardmäßig auf einen Thread begrenzt,
damit die äußere Parallelisierung nicht durch verschachtelte Thread-Pools
ausgebremst wird. Der optionale Sicherheitsmodus `--max-workers auto` leitet
eine konservative Workerzahl aus den für den Prozess verfügbaren logischen CPUs,
dem aktuell verfügbaren physischen RAM, Trainings-/Evaluationspfaden und dem aus
den Modellpunktaltern geschätzten Projektionshorizont ab. Dabei bleiben mindestens
35 % des verfügbaren RAM und mindestens 2 GiB als Reserve unberührt; ohne
zuverlässige RAM-Erkennung wird nur ein Worker verwendet, und die Automatik
startet höchstens 16 Worker. Dynamic und LSMC laufen innerhalb eines Workers
nacheinander, weil LSMC den höheren Speicher-Peak hat. Passt nach der
konservativen Schätzung nicht einmal ein Worker in das RAM-Budget, bleibt die
bisherige serielle Ausführung als deutlich gewarnter Fallback erhalten.

Eine konfigurierte Zahl überschreibt die konservative Automatik und wird im
Manifest als mögliche RAM-Überschreitung gekennzeichnet. Für die RAM-begrenzte
Automatik gilt beispielsweise:

```powershell
python portfolio_simulations/run_portfolio_risk_analysis.py `
  --max-workers auto --blas-threads 1 --reuse-existing
```

Jeder Child-Prozess schreibt seine Konsole isoliert nach
`orchestrator_console.log` im jeweiligen Szenarioverzeichnis. Command-Header,
Thread-Angabe und Child-Logging tragen dabei ebenfalls lokale Zeitstempel. Die
feste Jobreihenfolge, Seeds und Common-Random-Number-Logik bleiben unabhängig
von der Completion-Reihenfolge erhalten. Eine GPU wird nicht automatisch
verwendet; der numerische Stack besitzt derzeit kein kompatibles GPU-Backend.

Die physischen Verzeichnisse der drei Behaviour-Benchmarks heißen kompakt
`bench/v00`, `bench/v01` und `bench/v10`. Ihre fachlichen Langnamen bleiben in
Manifesten, Reports und Kennzahlen unverändert. Vor dem Start von Child-Runs
prüft der Risiko-Runner unter Windows die längsten erwarteten CSV- und
Grafikpfade gegen die 260-Zeichen-Grenze und verlangt bei Bedarf einen kürzeren
`--output`-Pfad.

## Research-Runner fuer flexible Crediting-Caps

Die kanonische Cap-Optimierung wird aus `AGILE_Modelling_Engine` gestartet:

```powershell
python portfolio_simulations/optimize_crediting_rate_lsmc.py
```

Sie ist kein American-Option-Stopping-Modell, sondern eine
Stackelberg-/Bilevel-Cap-Studie mit zwei getrennten Zielfunktionen. Der
Versicherer vergleicht Caps aus `{0.25%, 1%, 2%, ..., 20%}` anhand seines
New-Business-CSM-Proxys; der Policyholder maximiert davon getrennt seinen
risikoneutralen Leistungsbarwert. Der Default ist
`--policyholder-behaviour lsmc`; `dynamic` und `continue` bleiben als
reproduzierbare Vergleichsmodi verfügbar.

Fixed-Cap-Fits und die cap-randomisierte gekoppelte Response-Surface verwenden
dieselbe Follower-Schicht:
`combined_optimal_behaviour_lsmc_v2` über beide Projector-Hooks
`income_election_policy` und `income_action_policy`:

```text
Growth: WAIT | START_INCOME_NOW
Income monatlich: CONTINUE | PARTIAL_WITHDRAWAL | FULL_WITHDRAWAL
```

Für die gekoppelte Policy wird die kombinierte v2-Reaktionsfunktion auf den
vollständigen randomisierten Cap-Pfaden trainiert. Ihre complete-path
Out-of-Fold-Policy erzeugt die Versicherer-Fitted-Q-Targets; dieselbe danach
eingefrorene Policy wird ohne Refit im adaptiven Validation-Kandidaten über
beide Projector-Hooks verwendet. Damit liefern Fixed-Cap- und gekoppelte Fits bei
identischem Cap, State und Action Set ihre Aktion aus derselben Code- und
Regressionsschicht. Die historische jährliche `CONTINUE/FULL_WITHDRAWAL`-
Zweiwertrekursion und ihre `surrender_policy` bleiben als explizite Diagnostik
erhalten, sind aber nicht Bestandteil des produktiven LSMC-Pfads und können
nicht deployt werden.

Die gemeinsamen Core-Cashflows `crediting_margin` und `hedge_costs` bleiben die
Eingangsgrößen des CSM-Proxys; damit wirken zentral gebuchte Hedgekosten mit
ihrem Versichererzeichen in beiden Follower-Schichten.

Der gekoppelte v2-Fit gruppiert alle Replikate eines vollständigen
Markt-/Kontrollpfads im selben Fold und erzeugt own-path-Out-of-Fold-Targets.
Er ist jedoch noch nicht verschachtelt Leader-fold-exklusiv; genau deshalb
bleibt die adaptive Response-Surface fail-closed. Der Policyholder-State enthält unter
anderem Account und Surrender Value, Locked Income, Garantie-PV/-Moneyness,
Zinsen, Heston-Varianz, Duration, den angekündigten Cap und vergangene
Reference-/Credited Returns. Der Leader-State ergänzt exakte pre-action
Portfolioexposures. Joint-Life- und Single-Life-Fallback-Signatures werden vor
der gewichteten Portfolioaggregation separat optimiert. `contract_weight`
wird genau einmal verwendet; `premium_volume_weight` ist kein
Bewertungsgewicht.

Die Ereignisgrenze bleibt die des Monatsprojektors: zuerst Annual Credit unter
dem alten Cap, Fee Posting, Mortality und Income Election; danach wird der neue
Cap angekündigt und der DVA-/Hedge-Zeitraum neu gestartet; anschließend folgen
Income, Partial Withdrawal und Full Withdrawal. Der Policyholder sieht daher
den neuen Cap bei einer zulässigen Income-Aktion am selben
Anniversary. Die normative Timing-Tabelle und die Gleichgewichtsdefinition
stehen in `CREDITING_CAP_STACKELBERG.md`.

Der bestehende Schalter `--no-hedge-gain` steuert weiterhin nur, ob das
gemeinsame Core-Aggregat `crediting_margin` in den CSM-Proxy einfließt. Dieses
Aggregat besteht nun aus Money-Market-Ertrag und einem nur bei nicht
verkaufter Cap-Call-Leg zulässigen Above-Cap-Gewinn; die Hedgekosten bleiben
davon getrennte Outflows. Der Optimierungs-Runner erhält in diesem Schritt
keinen eigenen Schalter zur Wahl der Cap-Leg-Strategie.

Training/Cross-Fitting, Validation und finale Evaluation sind drei disjunkte
Samples mit berichteten Fingerprints. Für Null-Crediting, 0.25%, jeden fixen
Cap von 1% bis 20% und uncapped Crediting wird das Policyholder-LSMC jeweils
frisch und cap-konsistent trainiert. Der beste fixe Cap wird nur auf dem
Validation-Sample gewählt. Die cap-randomisierte v2-Reaktionsfläche wird auf
dem Validation-Sample als adaptiver Kandidat ausgewertet, bleibt aber
fail-closed: Für einen produktiven adaptiven Rollout fehlen in diesem Runner
noch verschachtelte Leader-/Follower-Folds, eine gemeinsame On-Policy-Iteration
und die drei Trainings-Seeds mit getrennten Election-, Income- und Combined-
Gates. Deshalb wird weiterhin der vorab gewählte fixe Cap mit seinem eigenen
v2-Follower verwendet. Evaluationsergebnisse dürfen Policy, Cap-Auswahl oder
Fallback nicht verändern.

Jeder Fixed-Cap-Fit wird unmittelbar auf `fit_version`, `valid`,
`start_income_mask`, `choose_income_action`, die verpflichtende monatliche
Action-Surface und eine leere Legacy-Surrender-Schicht geprüft. Ein materiell
ungültiger Fit oder eine negative unabhängige Policyholder-Validation bricht
den Lauf hart ab; er wird nicht still als `WAIT` oder `CONTINUE` ausgeliefert.
Numerisch ausgelassene immaterielle Zustände bleiben die einzige interne
No-Action-Konvention und werden in den Diagnosen ausgewiesen.
Vor dem Einfrieren wird eine statistisch nicht robuste dynamische Policy jedoch
explizit auf den besten vorab deklarierten festen Trainingsanker zurückgesetzt;
gewählter Starttermin und Income-Modus werden in CSV und Manifest protokolliert.

Im LSMC-Modus ersetzt die kombinierte v2-Policy die statistischen
Ordinary-/Performance-Lapses und planmäßigen freiwilligen Withdrawals; sie
werden nicht parallel angewandt. Growth Surrender und Growth Withdrawals sowie
die Aufgabe einer positiven Income-Garantie gegen Surrender Value null bleiben
strukturell ausgeschlossen. Das bestehende dynamische
Lapse-/Performance-Gap-Modell wird weiterhin als separater Benchmark
ausgewiesen.

Die eigentliche Ergebnisbewertung ist immer ein unabhängiger Forward-Rollout
durch den monatlichen Produktprojektor; Bellman- oder Regressionswerte werden
nur als Diagnostik gespeichert. Die Hauptgrafik
`plots/00_flexibility_value.png` zeigt den direkt projizierten CSM des besten
fixen Caps und der tatsächlich deployten Policy, das gepaarte Delta samt
95%-Intervall, die Policyholder-Exercise-Rate sowie Rand-Cap-/Fallback-Hinweise.
CSV/JSON-Ausgaben enthalten zusätzlich Policyholder-PV, Cap-Verteilungen,
Cashflowzerlegung, getrennte Regressiondiagnostik, Sample-Fingerprints und die
vollständige eingefrorene Policy-/Input-Provenienz. Das Manifest-Schema
`crediting-cap-lsmc-2.2` weist Fixed-Cap- und Coupled-Follower-Version,
Deployment-Eignung, Blockgrund, Projector-Hooks und Action-Set explizit aus.

`run_lsmc_crediting_cap.py` ist nur noch ein veralteter Kompatibilitaets-
Einstieg und delegiert bei direkter Ausfuehrung an diesen kanonischen Runner.

## Weitere Modellgrenzen

- Der Maximum Return ist als Produkteigenschaft fest auf 6 % gesetzt und kein
  aus einer Volatilitätsfläche kalibrierter Marktparameter.
- Die Global-Equity-Quote des Reference Fund kommt aus
  `../../input_equity_allocation/equity_allocation.csv`; der Bondanteil ist ihr
  Komplement. Der Bond-Sleeve rolliert monatlich auf fünf Jahre konstante
  Restlaufzeit; monatlich wird auf die konfigurierte Zielallokation
  rebalanciert.
- Der unterjährige DVA ist ein moment-matched Black-Scholes-Proxy auf den
  vollständigen Reference Fund. Cap und Floor werden nicht getrennt auf Equity-
  und Bond-Sleeve angewandt.
- Die jährlichen Conditional-MC-Hedgewerte sind cross-fitted
  Regressionsschätzungen aus simulierten Einjahres-Payoffs und keine
  ausführbaren Marktquotes. Unterschiedliche Seeds, Stressvarianten,
  Allokationen oder Cap-Grids sind getrennte Cache-Einträge.
- Bond Term Premium, Credit Spreads, Ausfälle, Ratingmigrationen,
  Inflation-Linked Bonds, eine separate FX-Schicht, Transaktionskosten und
  kundenbezogene fondsinterne Gebühren fehlen. Die separate fixe 0,30%-Fee auf
  das Hedge-Notional ist dagegen als Versichererkosten enthalten.
- Die 0,30%-Hedge-Management-Fee ist ein fixer jährlicher Notional-Kostenproxy
  und kein Abzug vom Kunden-Reference-Fund. Nach einem unterjährigen Tod, Lapse
  oder Withdrawal wird kein Options-Unwind beziehungsweise Recovery modelliert;
  die jährlichen Anschaffungskosten gelten als versunkene Kosten und ein
  `not_sold`-Gewinn nur für das am Settlement aktive Restnotional.
- Die Dynamic-Behaviour-Annahmen sind unkalibrierte Proxys. Growth Withdrawals
  und Growth Surrender bleiben unabhängig davon produktseitig deaktiviert.
- Alle Werte sind gross of reinsurance. Kapital, Risk Margin und PVFP werden im
  schlanken Defaultlauf nicht berechnet. Insurer NPV und New Business Margin
  sind deshalb ausdrücklich before Risk Margin.
