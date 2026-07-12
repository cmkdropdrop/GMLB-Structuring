# Portfoliobewertung

`run_portfolio_valuation.py` ist der operative Einstiegspunkt für die
marktkonsistente Bewertung der gewichteten New-Business-Modellpunkte des
generischen Index-Linked-Lifetime-Income-Fallprodukts. Jeder Modellpunkt wird
zuerst als eigener repräsentierter Vertrag bewertet. Erst danach werden seine
skalaren Ergebnisse mit dem Vertragsgewicht zum Portfolio aggregiert.

Der Defaultlauf verwendet Heston-Hull-White unter dem risikoneutralen Maß und
Plain Monte Carlo mit gemeinsamen Marktpfaden für alle Modellpunkte. COS und
LSMC werden nicht verwendet.

## Defaultlauf

Aus `AGILE_Modelling_Engine`:

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

Im Vergleichsoutput umfasst `pv_total_expenses_aud` sowohl die administrativen
Expenses als auch den Hedge-Execution-/Basis-Proxy. Die beiden Rohkomponenten
bleiben ausschließlich als Audit-Aufteilung in der CSV erhalten.

## Eingabedaten

Der Runner verwendet standardmäßig genau diese Repository-Quellen:

- `../../input_model_points_policyholders/model_points_policyholders.csv`;
- `../../input_cost_assumptions/cost_assumptions.csv`;
- `../../input_dynamic_behaviour/dynamic_behaviour_baselines.csv`;
- `../../input_dynamic_behaviour/dynamic_behaviour_coefficients.csv`;
- `../input_market_data/australian_zero_curve.csv`;
- `../input_market_data/model_parameters.csv`.

Die tatsächlichen Pfade, Annahmensatz-IDs und Source-Fingerprints werden im
Run-Manifest festgehalten. Die australische Zinskurve ist die laufend
eingelesene Marktdatenquelle. Die bereits vorhandenen Equity-, Heston-,
Hull-White- und Korrelationsparameter stammen aus `model_parameters.csv`.

Der Modellpunkt-Loader akzeptiert derzeit den gelieferten Duration-0-
New-Business-Zustand: Growth-Phase, Fixed Income, kein bereits initiiertes
Withdrawal und kein Locked Income. Premium, Initial Investment und Account
Value bei `t=0` müssen konsistent sein. Alte AGILE-Allokationsfelder sowie
Produkt-, PDS- und Cap-Metadaten werden nur auf Quellenintegrität geprüft; sie
steuern weder den generischen 50/50-Reference-Fund noch dessen festen 6%-Cap.

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
einzige vor der Projektion zusammengefasste Police. Insbesondere werden die 48
CSV-Zeilen nicht als 48 Policen interpretiert. Der Runner weist beim Start und
in den Outputs ausdrücklich auf diese Basis hin.

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
- Present Value of Guarantee Claims, Expenses und Hedge Costs;
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
| `--heston-substeps` | Heston-Substeps je Monat; Default 4 |
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

`income_start_year` ist im gelieferten Portfolio ein expliziter,
deterministischer Election-Termin und hat Vorrang vor dem dynamischen Take-up-
Hazard. Ein gegebenenfalls früherer automatischer Start nach Alter 100 wird
überall als effektiver Election-Termin verwendet. Die Behaviour-CSVs bleiben
Quelle für Income-Lapses und Withdrawals sowie für deren Provenienz.

Für Joint-Life-Modellpunkte wird die Spouse-Survival-Wahrscheinlichkeit bis zur
Election aus derselben Mortalitätsbasis fortgeschrieben. Der nicht mehr für
Spouse Income qualifizierte Anteil wird als Single-Life-Fallback bewertet. Nach
Election verwendet der bedingt gemeinsame Continue-Income-Zweig die
state-unabhängigen statischen CSV-Basisraten für Income-Lapse und Excess
Withdrawal; der Single-Life-Fallback bleibt dynamisch. Eine nichtlineare
Behaviour-Funktion wird nicht auf einen gemittelten `p11/p10/p01`-Zustand
angewandt. Getrennte Account-Value-/Fee-Kohorten, abhängige Leben sowie
Scheidungs-, Removal- und Common-Shock-Logik bleiben Modellgrenzen.

Income-Lapse bleibt bei fortbestehender Income-Garantie auch nach Aufzehrung
des Account Value aktiv. Der Surrender Benefit ist dann null; ein Lapse beendet
aber die Garantie sowie künftige Garantieclaims und laufende Expenses.

## Weitere Modellgrenzen

- Der Maximum Return ist als Produkteigenschaft fest auf 6 % gesetzt und kein
  aus einer Volatilitätsfläche kalibrierter Marktparameter.
- Der Reference Fund besteht aus 50 % Global Equity und 50 % nominalen
  australischen Staatsanleihen. Der Bond-Sleeve rolliert monatlich auf fünf
  Jahre konstante Restlaufzeit; monatlich wird auf 50/50 rebalanciert.
- Der unterjährige DVA ist ein moment-matched Black-Scholes-Proxy auf den
  vollständigen Reference Fund. Cap und Floor werden nicht getrennt auf Equity-
  und Bond-Sleeve angewandt.
- Bond Term Premium, Credit Spreads, Ausfälle, Ratingmigrationen,
  Inflation-Linked Bonds, eine separate FX-Schicht, Transaktionskosten und
  fondsinterne Gebühren fehlen.
- Die Dynamic-Behaviour-Annahmen sind unkalibrierte Proxys. Growth Withdrawals
  und Growth Surrender bleiben unabhängig davon produktseitig deaktiviert.
- Alle Werte sind gross of reinsurance. Kapital, Risk Margin und PVFP werden im
  schlanken Defaultlauf nicht berechnet. Insurer NPV und New Business Margin
  sind deshalb ausdrücklich before Risk Margin.
