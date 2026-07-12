# Dynamische Behaviour-Annahmen

Die beiden CSV-Dateien in diesem Verzeichnis sind die Eingabequelle für das
vereinfachte dynamische Policyholder-Behaviour-Modell:

- `dynamic_behaviour_baselines.csv` enthält die Basisraten beziehungsweise
  Basis-Utilisationen nach Phase und Policy Year.
- `dynamic_behaviour_coefficients.csv` enthält die Reaktionskoeffizienten und
  gemeinsamen Kovariatengrenzen.

Der Loader ist
`AGILE_Modelling_Engine/agile_engine/dynamic_behaviour_assumptions.py`.

## Modellform

Für jede versicherte Person werden zwei erklärende Variablen gebildet:

```text
m = clip(log(G / A), -log(2), log(2))
z = clip(log(P / 100000), -2, 2)
```

`G` ist der Barwert der laufenden beziehungsweise bei sofortigem Income Start
prospektiven Garantie. `A` ist der für die jeweilige Entscheidung relevante
Account-/Surrender-Value. `P` ist die eingezahlte Brutto-Prämie
`PolicySpec.initial_investment`; sie wird nicht um Upfront Adviser Fee,
Versichererkosten oder Bonus Interest bereinigt. Gebühren und MVA-Loadings
stammen weiterhin ausschließlich aus
`input_cost_assumptions/cost_assumptions.csv`. Soweit sie vertraglich den
Kundenwert betreffen, verändern sie Account-/Surrender-Value oder MVA-Signal;
reine Versicherer-Expenses mindern den Kunden-IV nicht.

Lapse und Income Take-up verwenden einen proportionalen Hazard-Ansatz:

```text
lambda = -log(1 - p_base) * exp(beta_m * m + beta_p * z + beta_mp * m * z)
p(dt)  = 1 - exp(-lambda * dt)
```

Die jährliche dynamische Lapse-Wahrscheinlichkeit wird erst nach Anwendung der
Kovariaten auf Monatswahrscheinlichkeiten umgerechnet. Der relative
Hazard-Multiplikator wird zusätzlich durch `multiplier_floor` und
`multiplier_cap` begrenzt. Strukturelle Nullen,
insbesondere Take-up im ersten Policy Year, bleiben exakt null. Im Policy Year
15 wird Income unabhängig von den Kovariaten erzwungen.

Free- und Excess-Withdrawal verwenden eine Fractional-Logit-Funktion:

```text
logit(u) = logit(u_base)
           + beta_m * m
           + beta_p * z
           + beta_mp * m * z
           + beta_mva * mva_fraction
```

Der aktuelle Excess-Ansatz ist eine erwartete annualisierte Rate als Anteil
des Investment Value. Er ist kein vollständiges empirisches
Incidence-/Severity-Hurdle-Modell.

## Verwendung im generischen Portfolio-Runner

Der generische Portfolio-Runner lädt und validiert weiterhin beide CSV-Dateien
mit `load_dynamic_behaviour_assumptions()`. Annahmenset, angewandte Werte,
Effective Dates und Dateihashes bleiben dadurch in der Run-Provenienz
nachvollziehbar.

Die generische Vertragslogik hat Vorrang vor den geladenen Behaviour-Raten. In
der Growth-Phase sind Full Surrender/Lapse, Free Withdrawals und Excess
Withdrawals vertraglich nicht zulässig und werden daher strukturell auf null
gesetzt. Die betreffenden CSV-Werte werden nicht als tatsächlich wirksame
Growth-Phase-Wahrscheinlichkeiten ausgegeben.

Die explizite Spalte `income_start_year` des Modellpunkts hat im aktuellen
Portfolio-Runner Vorrang vor dem geladenen Income-Take-up-Hazard. Take-up wird
dort am betreffenden Policy Anniversary deterministisch ausgelöst. Das ist
zugleich die Voraussetzung dafür, die Spouse-Survival-Wahrscheinlichkeit bis
zu diesem Termin und den Single-Life-Fallback konsistent zu mischen. Die
geladenen Income-Lapse- und Withdrawal-Raten bleiben in der Income-Phase aktiv.
Die dynamischen Koeffizienten wirken für Single Life, den Single-Life-Fallback
und die Lump-Sum-Spouse-Ausprägung. Der bedingt gemeinsame Continue-Income-
Joint-Zweig verwendet dagegen die geladenen statischen Basisraten, solange
keine getrennten `p11/p10/p01`-AV-/Fee-Kohorten bestehen. Income-Lapse bleibt
bei fortbestehender Garantie auch nach Account-Value-Erschöpfung aktiv.
Sämtliche Behaviour-Parameter bleiben feste, nicht kalibrierte Proxy-Annahmen.
LSMC oder ein wertmaximierendes Optimal-Behaviour-Modell wird im
Portfolio-Runner nicht verwendet. Außerhalb des Portfolio-Runners unterstützt
der Kernmotor den vereinfachten dynamischen Take-up-Modus nur für Single Life;
Spouse Income erfordert bis zur Modellierung der Pre-Election-Eligibility einen
deterministischen Election-Termin.

## Mortalitätsabgrenzung

Die Portfolio-Barwerte verwenden deterministische Expected Decrements je
Modellpunkt. Mangels einer bereitgestellten, fachlich freigegebenen
Mortalitätstafel bleibt die verwendete Gompertz-Makeham-Basis illustrativ.
Ergebnisse sind deshalb als vereinfachte Expected-Decrement-Projektionen auf
illustrativer Proxy-Mortalitätsbasis zu kennzeichnen und nicht als vollständig
kalibrierte Best-Estimate-Mortalitätsprognose.

## Einordnung und Governance

Alle Zeilen sind als `uncalibrated_proxy` gekennzeichnet. Sie sind
literatur- und praxisinformierte Startwerte, aber weder eine australische
Experience Study noch eine vollständig kalibrierte Prognose. Vor einer
Produktionsverwendung sind interne Bestandsdaten, Segmentierung, Credibility,
Backtesting und Governance-Freigabe erforderlich.

Dies gilt ausdrücklich auch für sämtliche Regressionskoeffizienten sowie die
Hazard-Multiplikator-Floors und -Caps; diese Grenzen sind ebenfalls
`UNCALIBRATED_PROXY` und keine beobachteten Verhaltensschranken.

Die `low_value`- und `high_value`-Spalten sind geordnete Sensitivitätsbänder;
der Loader verlangt `low_value <= base_value <= high_value`. Bei negativen
Koeffizienten bedeutet `low` daher den numerisch kleineren, stärker negativen
Wert. Das gewählte Band wird über `value_basis="low"`, `"base"` oder `"high"`
selektiert.

Zentrale Literatur-/Praxisanker der Proxy-Struktur sind Cox-artige
Proportional-Hazard-Modelle, dynamische Variable-Annuity-Behaviour-Modelle nach
Bauer/Kling/Russ beziehungsweise Kling/Ruez/Russ und SOA-/LIMRA-Studien zu
GLWB-Entnahme- und Income-Election-Verhalten. Die konkreten Koeffizienten sind
keine aus diesen Quellen übernommene Kalibrierung.
