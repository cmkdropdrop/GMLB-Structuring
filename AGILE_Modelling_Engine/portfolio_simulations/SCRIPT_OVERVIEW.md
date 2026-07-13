# Skriptübersicht der Portfolio-Simulationen

Dieses Dokument beschreibt die Python-Dateien in `portfolio_simulations` und
grenzt ihre Aufgaben voneinander ab. Es beschreibt den aktuellen Codezustand,
nicht die Ergebnisse eines konkreten Laufs.

Die Bewertungsrunner in diesem Ordner arbeiten marktkonsistent unter dem
risikoneutralen Maß und standardmäßig mit Heston-Hull-White. Sie sind keine
Real-World-Projektionsrunner. Die laufend eingelesene Marktdatenquelle ist die
australische Zinskurve; die bereits vorhandenen Equity-, Heston-,
Hull-White- und Korrelationsparameter kommen aus `model_parameters.csv`.

Ausführlichere fachliche Dokumentation steht in:

- [`README.md`](README.md) für Bewertung, Aggregation, Behaviour-Benchmarks,
  Risikoanalyse und Outputs;
- [`CREDITING_CAP_STACKELBERG.md`](CREDITING_CAP_STACKELBERG.md) für Timing,
  Informationsmengen und Zielfunktionen der flexiblen Cap-Optimierung.

## Schnellwahl

| Fragestellung | Zu verwendende Datei |
|---|---|
| Normale Portfoliobewertung mit dynamischem Policyholder-Verhalten | `run_portfolio_valuation.py` |
| Portfoliobewertung mit optimaler Income-Election- und Full-Withdrawal-Policy | `run_portfolio_valuation_lsmc.py` |
| Vergleich mehrerer vorgegebener, konstanter Caps mit dynamischem Verhalten | `run_crediting_rate_scenarios.py` |
| Cap-×-Stress-Sensitivität mit je Zelle neu trainierter gemeinsamer LSMC-Policy | `run_lsmc_cap_behaviour_scenarios.py` |
| Integrierter Vergleich von Dynamic und LSMC über Caps und Risikostresse | `run_portfolio_risk_analysis.py` |
| Zustandsabhängige jährliche Cap-Optimierung als separate Stackelberg-Studie | `optimize_crediting_rate_lsmc.py` |
| Plot aus bereits fertigen Stackelberg-Ergebnissen | `plot_crediting_cap_behaviour_comparison.py` |

## Gemeinsame Eingabebasis

Die Hauptläufe verwenden standardmäßig folgende Repository-Quellen:

- `input_model_points_policyholders/model_points_policyholders_4_point_proxy.csv`;
- `input_cost_assumptions/cost_assumptions.csv`;
- `input_dynamic_behaviour/dynamic_behaviour_baselines.csv` und
  `dynamic_behaviour_coefficients.csv`;
- `AGILE_Modelling_Engine/input_market_data/australian_zero_curve.csv`;
- `AGILE_Modelling_Engine/input_market_data/model_parameters.csv`.

Die Eingabepfade und die jeweiligen Assumption-Set-IDs können bei den
Hauptläufen über Kommandozeilenparameter überschrieben werden. Die
Szenario-Orchestratoren reichen diese Einstellungen an ihre untergeordneten
Runner weiter. Es werden keine zusätzlichen Volatilitätsflächen,
Credit-Spread-Kurven oder separaten Kalibrierungsdateien verlangt.

Die Standardwerte für Monte-Carlo-Pfadanzahlen und Seeds der Portfolioanalyse
stehen zentral in
`../../input_MC_analysis/portfolio_analysis.csv`. Die Rollen `evaluation`,
`lsmc_training` und `lsmc_validation` trennen Evaluation, LSMC-Training und
Validierung. Die genaue Anzahl aktiver LSMC-Trainings-Seed-Sätze wird weiterhin
im jeweiligen Skript festgelegt; die CSV enthält nur die nummerierten
verfügbaren Seed-Sätze. Explizite CLI-Werte überschreiben den CSV-Standard.

## Bewertungsrunner

### `run_portfolio_valuation.py`

Dies ist der operative Basisrunner für die marktkonsistente
Portfoliobewertung mit statistischem beziehungsweise dynamischem Verhalten.

Der Runner:

1. lädt Markt-, Kosten-, Behaviour- und Modellpunktdaten;
2. baut einen gemeinsamen risikoneutralen Heston-Hull-White-Szenariosatz;
3. bewertet jeden Modellpunkt als eigenen repräsentativen Vertrag;
4. aggregiert die skalaren Ergebnisse genau einmal mit `contract_weight`;
5. prüft Portfolioaggregation, Hedgekosten und Backing-Income-Reconciliation;
6. schreibt Ergebnisse, Provenienz, Log und optional Grafiken.

Standardmäßig werden sowohl die Income Election als auch das Verhalten nach
Income Start dynamisch modelliert. Die wichtigsten Behaviour-Varianten sind:

- `--income-election-mode dynamic|deterministic`;
- `--post-income-behaviour dynamic|continue`.

`deterministic` und `continue` dienen insbesondere als Benchmarks für die
2×2-Zerlegung. Growth-Lapse und Growth-Withdrawals bleiben produktseitig
ausgeschlossen. Über `--stress-scenario` kann ein Einfaktorstress und über
`--crediting-cap-rate` ein nichtvertraglicher konstanter Cap vorgegeben
werden. `--hedge-cap-leg-mode sold|not_sold` steuert, ob die Cap-Call-Leg
verkauft wird oder der Above-Cap-Hedgegewinn beim Versicherer verbleibt.

Ohne fachlich vorgegebene Vertragsanzahl werden die Geldwerte als
normalisierter gewichteter Durchschnitt je repräsentativem Vertrag
ausgewiesen. Absolute Portfoliowerte entstehen entweder aus bestätigten
`exposure_count`-Werten der Eingabedatei oder aus
`--portfolio-contract-count`; bei gemeinsamer Angabe werden beide Quellen
gegeneinander validiert. Der Runner kann außerdem faire beziehungsweise
kommerzielle Break-even-Lifetime-Income-Premia je Modellpunkt oder für das
Gesamtportfolio lösen.

Wesentliche Outputs im gewählten Ausgabeverzeichnis sind:

- `portfolio_summary.csv`;
- `model_point_results.csv`;
- `portfolio_aggregation_reconciliation.csv`;
- optional `model_point_fair_fee_results.csv`;
- `run_manifest.json` und `portfolio_valuation.log`;
- standardmäßig vier Reporting-Grafiken unter `figures/` und bei
  Fair-Fee-Läufen optional eine fünfte Grafik.

Das Standardverzeichnis ist `output/portfolio_valuation`.

### `run_portfolio_valuation_lsmc.py`

Dieser Runner bewertet dasselbe Produkt und dieselbe Portfolioaggregation mit
optimalen Policyholder-Policys. Je eindeutiger `PolicySpec`-Signatur wird ein
eigener Fit trainiert; Modellpunkte mit identischer Signatur teilen diesen Fit.
Innerhalb jedes Fits werden Income Election und späterer Full Withdrawal
gemeinsam optimiert. Das jährliche Entscheidungsgitter enthält:

```text
Growth: WAIT | START_INCOME_NOW
Income: CONTINUE | FULL_WITHDRAWAL
```

Die LSMC-Policy maximiert den risikoneutralen Barwert der
Policyholder-Cashflows. Sie wird auf einem separaten Trainingssample gefittet
und anschließend unverändert auf unabhängigen Evaluationspfaden im monatlichen
Produktprojektor bewertet. Cross-Fitting, Ridge-Regularisierung,
Stabilitätsprüfungen und ein RMSE-basierter Exercise Buffer begrenzen
instabile Exercise-Signale. Ein instabiler Fit fällt konservativ auf WAIT
beziehungsweise CONTINUE zurück.

Der Runner berechnet vier Behaviour-Arme:

| ID | Income Election | Verhalten nach Election |
|---|---|---|
| V00 | deterministisch | Continue |
| V01 | deterministisch | gefittete Full-Withdrawal-Regel |
| V10 | gefittete Election | Continue |
| V11 | gefittete Election | gefittete Full-Withdrawal-Regel |

V01 und V10 sind Gegenfaktuale aus den je Policy-Signatur gemeinsam für V11
gefitteten Election-/Withdrawal-Regeln und keine separat optimierten Policys.
Standardmäßig wird zusätzlich der vollständige Dynamic-Behaviour-Runner auf
denselben Evaluationsszenarien ausgewertet; `--no-dynamic-benchmark` schaltet
nur diesen Zusatzvergleich ab.

Wichtige getrennte Einstellungen sind `--n-train`/`--train-seed` für das
Training und `--n-paths`/`--seed` für die Out-of-Sample-Bewertung. Auch die
Take-up- und Mortality-Seeds sind zwischen Training und Evaluation getrennt.
Der gewählte Stress wird auf beide Samples angewandt.

Neben den normalen Portfoliooutputs entstehen insbesondere:

- `income_election_distribution.csv`;
- `lsmc_behaviour_decomposition.csv`;
- `lsmc_vs_continue_summary.csv`;
- `lsmc_regression_diagnostics.csv`;
- `lsmc_action_summary.csv`;
- standardmäßig `comparison_summary.csv`, `model_point_comparison.csv` und
  `comparison_report.md` für den Dynamic-Vergleich;
- die Benchmark-Verzeichnisse `bench/v00`, `bench/v01` und `bench/v10` sowie
  optional `dynamic_benchmark`.

Das Standardverzeichnis ist `output/portfolio_valuation_lsmc`.

## Szenario- und Risiko-Orchestratoren

### `run_crediting_rate_scenarios.py`

Dieser schlanke Orchestrator vergleicht mehrere vorgegebene konstante
Maximum-Return-/Crediting-Cap-Raten. Für jeden Cap startet er
`run_portfolio_valuation.py` als eigenen Prozess. Standard sind 4 %, 6 %,
12 % und 20 %; die 6%-Baseline wird bei Bedarf automatisch ergänzt.

Alle Zellen verwenden dieselbe Pfadzahl, denselben Seed und dieselben
Heston-Substeps. Dadurch werden die Cap-Vergleiche mit Common Random Numbers
durchgeführt. Der Orchestrator validiert unter anderem Cap, Hedge-Modus,
Szenario-Fingerprint sowie die Reconciliation von Hedgekosten und Crediting
Margin. Abweichende Caps bleiben als nichtvertragliche Design-Sensitivitäten
gekennzeichnet.

Er schreibt unter `output/crediting_rate_scenarios`:

- vollständige Child-Ergebnisse unter `scenarios/crediting_rate_<rate>pct`;
- `crediting_rate_profitability_comparison.csv`;
- `crediting_rate_profitability_report.md`;
- `crediting_rate_profitability_comparison.png`, sofern Matplotlib verfügbar
  ist;
- `comparison_manifest.json`.

`--scenario-plots` behält zusätzlich die Standardgrafiken jedes Child-Laufs.

### `run_lsmc_cap_behaviour_scenarios.py`

Dieser Orchestrator untersucht, wie konstante Caps und Stresse die gemeinsame
optimale Income-Election-/Full-Withdrawal-Policy verändern. Jede
Cap-×-Stress-Zelle startet `run_portfolio_valuation_lsmc.py` und erhält einen
eigenen neuen Fit. Eine unter einem Cap trainierte Policy wird nicht auf einen
anderen Cap übertragen.

Standardmäßig werden die Caps 4 %, 6 %, 12 % und 20 % im Base-Szenario
gerechnet. Optional stehen unter anderem Zins-, Aktien-, Longevity-,
Mortality- und Expense-Stresse zur Verfügung. Innerhalb eines Stresses werden
gemeinsame Zufallszahlen verwendet; Training und Evaluation bleiben getrennt.

Der Orchestrator liest V00, V01, V10 und V11 ein, ergänzt optional den
Dynamic-Benchmark und berechnet die 2×2-Zerlegung in Election-Effekt,
Post-Election-Effekt und Interaktion. `--reuse-existing` verwendet Ergebnisse
nur nach Manifest-, Hash-, Parameter-, Fingerprint- und
Reconciliation-Prüfungen.

Die zusammenfassenden Outputs unter
`output/lsmc_cap_behaviour_scenarios` sind:

- `lsmc_cap_behaviour_comparison.csv`;
- `lsmc_cap_behaviour_report.md`;
- `lsmc_cap_behaviour_comparison.png`, sofern Matplotlib verfügbar ist;
- `comparison_manifest.json`;
- vollständige Zellergebnisse unter `scenarios/` beziehungsweise
  `stress_scenarios/<stress>/`.

### `run_portfolio_risk_analysis.py`

Dies ist der umfassendste Orchestrator. Für jede Cap-×-Stress-Zelle führt er
verpflichtend beide Hauptansätze aus:

- Dynamic Behaviour über `run_portfolio_valuation.py`;
- optimale Behaviour-Policy über `run_portfolio_valuation_lsmc.py`.

Zusätzlich werden die drei Dynamic-Benchmark-Arme für die 2×2-Zerlegung
gerechnet. Der im LSMC-Child eingebaute Dynamic-Benchmark wird dabei
deaktiviert, weil der Orchestrator den vollständigen Dynamic-Lauf bereits
separat erzeugt.

Der Default umfasst die Caps 4 %, 6 %, 12 % und 20 % sowie die zusätzlichen
Stresse `interest_up`, `interest_down` und `longevity`. Lapse-Risiko wird nicht
als separater statistischer Lapse-Schock modelliert, sondern über den
Dynamic-/LSMC-Vergleich und die Behaviour-Zerlegung analysiert. Weitere
Research-Stresse können explizit gewählt werden.

Unabhängige Zellen laufen in einer gemeinsamen Prozess-Queue. Standardmäßig
werden bis zu 16 Worker und ein BLAS/OpenMP-Thread je Child verwendet;
`--max-workers auto` begrenzt die Parallelität konservativ anhand von CPU und
geschätztem RAM. Dynamic und LSMC laufen innerhalb einer Zelle nacheinander.
Unter Windows prüft der Runner vorab die erwarteten Pfadlängen.

Die wichtigsten Analyseoutputs unter `output/portfolio_risk_analysis` sind:

- `portfolio_risk_by_crediting_cap.csv`;
- `crediting_cap_risk_sensitivities.csv`;
- `crediting_cap_effect_decomposition.csv`;
- `behaviour_effect_decomposition.csv`;
- `model_point_behaviour_model_gap.csv`;
- optional `portfolio_stress_losses_by_crediting_cap.csv`;
- `portfolio_risk_report.md`, `analysis_manifest.json` und Analysegrafiken;
- vollständige Child-Ergebnisse und je Child ein
  `orchestrator_console.log`.

Das Skript vergleicht Erwartungsbarwerte und Modellpunktkennzahlen. Es erzeugt
keine pfadweise Verlustverteilung und weist daher weder VaR/CTE noch Economic
Capital, Risk Margin oder eine regulatorische Stressaggregation aus.

## Separate Crediting-Cap-Management-Studie

### `optimize_crediting_rate_lsmc.py`

Dies ist der kanonische Runner für eine zustandsabhängige jährliche
Crediting-Cap-Policy. Er formuliert die Cap-Wahl als wiederholtes
Stackelberg-/Bilevel-Kontrollproblem mit zwei getrennten Zielfunktionen:

1. Der Versicherer kündigt einen Cap aus
   `{0,25 %, 1 %, 2 %, ..., 20 %}` an.
2. Der Policyholder beobachtet den Cap und wählt im Standardmodus per eigener
   LSMC-Wertfunktion zwischen CONTINUE und zulässigem FULL_WITHDRAWAL.
3. Erst nach dieser Best Response vergleicht der Versicherer seinen
   marktkonsistenten New-Business-CSM-Proxy und wählt den Cap.

Der Versicherer-Proxy berücksichtigt Product- und LIP-Fees, optionale
Crediting Margin, retained MVA/APS, Guarantee Claims, Expenses und Hedgekosten
mit ihren jeweiligen Vorzeichen. Er ist kein ausgewiesener IFRS-17-CSM und
enthält weder Risk Margin noch Kapital-, Steuer- oder Reinsurance-Effekte.

Der Runner trennt Control-Randomisation-/Cross-Fit-Training, Validation und
finale Evaluation. Für feste Cap-Benchmarks wird die Policyholder-LSMC je Cap
neu trainiert. Eine adaptive Policy wird nur deployt, wenn die numerischen,
Policyholder- und Validierungs-Gates bestanden sind; andernfalls wird der auf
dem Validation-Sample bestimmte beste feste Cap verwendet. Die finale
Bewertung erfolgt als unabhängiger Forward-Rollout im monatlichen
Produktprojektor.

Wichtige Abgrenzung: Diese Datei ist eine eigenständige Management-Action-
Studie. Die Income Election bleibt deterministisch gemäß Modellpunkt und
Automatic-Age-Backstop. Optimiert wird auf Policyholder-Seite nur Continue
gegen Full Withdrawal nach Income Start. Für eine gemeinsame Optimierung von
Income Election und Verhalten nach Election ist
`run_portfolio_valuation_lsmc.py` beziehungsweise für Cap-Sensitivitäten
`run_lsmc_cap_behaviour_scenarios.py` zu verwenden.

`--policyholder-behaviour` bietet die Modi `lsmc`, `dynamic` und `continue`.
Das Marktmodell ist fest Heston-Hull-White unter dem risikoneutralen Maß. Der
Defaultoutput ist `output/crediting_cap_lsmc` und enthält:

- `optimization_summary.json`, `lsmc_policy.json` und `run_manifest.json`;
- CSVs zu Erstjahreswerten, jährlicher Policy, Regressionen,
  Policyholder-Exercise, Fixed-Cap-Benchmarks und Modellpunktbehandlung;
- `run.log` mit DEBUG-Details;
- sieben Diagnosegrafiken unter `plots/`, wahlweise als PNG, SVG oder beides.

### `optimize_crediting_rate_dynamic_behaviour.py`

Dies ist der dedizierte Runner für dieselbe jährliche adaptive Cap-Studie
unter dem statistischen dynamischen Policyholder-Modell. Er fittet keine
Policyholder-LSMC und bietet deshalb keinen Behaviour-Modus-Schalter. Income
Election, Ordinary-/Performance-Lapse und Partial-/Excess-Withdrawals werden
direkt aus den versionierten Annahmen unter `input_dynamic_behaviour` im
monatlichen Projektor angewandt. Joint-Life-Modellpunkte verwenden dabei die
pfadweise Primary-/Spouse-Life-State-Behandlung.

Nur die Versicherer-Cap-Policy wird weiterhin durch cross-fitted
Control-Randomisation/Fitted-Q geschätzt. Die adaptive Policy wird auf einem
separaten Sample gegen das beste feste Cap validiert und danach auf einem
disjunkten finalen Sample direkt projiziert. Der Defaultoutput ist
`output/crediting_cap_dynamic_behaviour`; die Policy wird als
`dynamic_cap_policy.json` geschrieben. Die Behaviour-Annahmen bleiben
unkalibrierte Proxy-Annahmen.
Der Hedge-Standard ist ausdrücklich der vollständige Call Spread mit
verkaufter oberer Cap-Leg (`sold`); die Versicherung behält daher keine
Referenzfondsperformance oberhalb des Kundencaps. Money-Market-Backing-Income
bleibt davon unabhängig Bestandteil der CSM-Proxy.
Die Optimierungsgröße folgt explizit
`CSM = PV(Fee Income) + PV(Other Income) - PV(Claims) - PV(Costs)`.
Money-Market-Income und Hedge Gain werden dabei separat ausgewiesen; die
Kosten enthalten Akquisitions- und laufende Kosten sowie den vollständigen
fairen Optionsspread inklusive Markup, Management- und Ausführungskosten.

### `run_lsmc_crediting_cap.py`

Diese Datei ist ein veralteter Kompatibilitäts-Wrapper. Bei direkter
Ausführung gibt sie einen Hinweis aus und delegiert vollständig an
`optimize_crediting_rate_lsmc.py`. Es gelten daher dessen CLI und Outputs.

Der große historische Codeblock in der Datei enthält noch eine alte jährliche
Storage-Control-Näherung in `_legacy_main()`. Der normale Entry Point ruft
diese Funktion nicht auf. Sie bleibt nur für die Audit-Historie erhalten und
darf nicht für aktuelle Ergebnisse verwendet werden.

## Postprocessing und interne Hilfsmodule

### `plot_crediting_cap_behaviour_comparison.py`

Dieses Postprocessing-Skript führt keine Bewertung aus. Es liest drei bereits
abgeschlossene Ergebnisverzeichnisse von `optimize_crediting_rate_lsmc.py`:

- Base Behaviour mit Crediting Margin;
- Base Behaviour ohne Crediting Margin;
- High Behaviour mit Crediting Margin.

Aus `optimization_summary.json`, `fixed_cap_sanity_checks.csv` und
`model_point_projection_treatments.csv` erstellt es ein PNG mit:

- CSM-Proxy nach fixer Cap-Höhe mit und ohne Crediting Margin;
- kumulierter Full-Surrender-Wahrscheinlichkeit für Base und High Behaviour;
- Vergleich des besten festen Caps mit der flexiblen Regel.

Die drei Cap-Gitter müssen übereinstimmen und alle Summary-Dateien müssen den
Status `completed` haben. Die Defaultpfade zeigen auf speziell benannte
Research-Läufe unter `output/crediting_cap_behaviour` und nicht auf das
Defaultverzeichnis des Optimierungsrunners. Für andere Läufe sind daher
`--with-margin`, `--no-margin`, `--high-behaviour` und `--output` explizit zu
setzen. Titel und Fußnote enthalten fallbezogene Aussagen; der Plotter ist
nicht vollständig generisch.

### `_run_layout.py`

Internes Hilfsmodul ohne CLI. Es hält die stabilen logischen IDs der drei
Behaviour-Benchmarks und ordnet ihnen kompakte Verzeichnisse zu:

| Logische ID | Physisches Verzeichnis |
|---|---|
| `deterministic_election_continue` | `bench/v00` |
| `deterministic_election_post_behaviour` | `bench/v01` |
| `variable_election_continue` | `bench/v10` |

V11 liegt jeweils im Hauptverzeichnis des LSMC-Laufs; der Dynamic-Benchmark
liegt separat unter `dynamic_benchmark`.

### `_run_logging.py`

Internes Hilfsmodul ohne CLI. Es stellt das einheitliche lokale
Konsolenformat

```text
YYYY-MM-DD HH:MM:SS | LEVEL | Nachricht
```

bereit. `format_run_log_line()` erzeugt die formatierte Zeile;
`log_to_console()` schreibt sie sofort geflusht nach `stdout` oder in einen
übergebenen Stream. Das Modul formatiert das Level, filtert Meldungen aber
nicht selbst.

## Aufrufbeziehungen

- `run_crediting_rate_scenarios.py` ruft `run_portfolio_valuation.py` auf.
- `run_lsmc_cap_behaviour_scenarios.py` ruft
  `run_portfolio_valuation_lsmc.py` auf.
- `run_portfolio_risk_analysis.py` ruft beide Bewertungsrunner sowie die
  Dynamic-Benchmark-Arme auf.
- `run_lsmc_crediting_cap.py` delegiert an
  `optimize_crediting_rate_lsmc.py`.
- `plot_crediting_cap_behaviour_comparison.py` liest ausschließlich fertige
  Outputs von `optimize_crediting_rate_lsmc.py`.
- `_run_layout.py` und `_run_logging.py` werden von mehreren Runnern importiert
  und sind keine eigenständigen Simulationen.
