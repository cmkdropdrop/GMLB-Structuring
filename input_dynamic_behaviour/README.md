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

Für jede versicherte Person werden drei erklärende Variablen gebildet:

```text
m = clip(log(G / A), -log(2), log(2))
z = clip(log(P / 100000), -2, 2)
g_raw = max(log(1 + R_reference) - log(1 + R_credited), 0)
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

`g_raw` ist die am Crediting-Anniversary bereits realisierte und für den Kunden
sichtbare Performance-Lücke des abgelaufenen Jahres. `R_reference` stammt
ausschließlich aus dem vertraglichen Kunden-Reference-Fund; Backing Assets,
Hedge-P&L oder künftige Marktperformance werden nicht verwendet.

Income Take-up und der gewöhnliche Lapse-Grund verwenden weiterhin einen
proportionalen Hazard-Ansatz mit **signierter** Garantie-Moneyness. Beim
Take-up wird der Predictor am aktuellen Anniversary zusätzlich um ausschließlich
zu diesem Zeitpunkt bekannte Zustände erweitert:

```text
mu_takeup = -log(1 - p_base) * exp(
    beta_m * m + beta_p * z + beta_mp * m * z
    + beta_av * log(AV / premium)
    + beta_income * prospective_annual_income / premium
    + beta_ref * previous_reference_return
    + beta_credit * previous_credited_return
    + beta_gap * visible_performance_gap
)
```

Beim Income-Lapse kommt ein eigenständiger konkurrierender Performance-Hazard
hinzu. Damit wird sichtbare Underperformance nicht mehr als Multiplikator der
kleinen gewöhnlichen Basislapse modelliert:

```text
g = clip(max(g_raw - deadband, 0), 0, shortfall_max)
r(m) = max(retention_floor, exp(-retention_gamma * max(m, 0)))
mu_performance = r(m) * excess_hazard_cap * (1 - exp(-g / excess_hazard_scale))
mu_total = mu_ordinary + mu_performance
p(dt) = 1 - exp(-mu_total * dt)
```

Die gemeinsame Jahreswahrscheinlichkeit wird durch `annual_probability_cap`
begrenzt und erst danach konsistent auf Monatswahrscheinlichkeiten umgerechnet.
Für Diagnosezwecke werden die beiden Exit-Ursachen proportional zu ihren
Cause-specific Hazards auf die Gesamtwahrscheinlichkeit verteilt; ihre Summe
entspricht daher exakt der gesamten Lapse-Masse. Der gewöhnliche relative
Hazard bleibt durch `multiplier_floor` und `multiplier_cap` begrenzt. Diese
Grenzen beschneiden den unabhängigen Performance-Hazard nicht. Strukturelle Nullen,
insbesondere Take-up im ersten Policy Year, bleiben exakt null. Die 100-%-Zeile
ab Policy Year 15 ist eine statistische Proxy-Annahme für Take-up, kein
vertraglicher Forced Start. Vertraglich erzwungen wird Income ausschließlich
am ersten Policy Anniversary nach Vollendung des 100. Lebensjahrs.

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

Der Portfolio-Hauptlauf verwendet den geladenen dynamischen Income-Take-up-
Hazard. `income_start_year` bleibt ausschließlich Eingabe für den expliziten
deterministischen Validierungsbenchmark. Dynamic Election wird nach Credit,
Fee-Posting und Mortalität auf jedem zulässigen Policy Anniversary neu aus den
dann sichtbaren Zuständen bestimmt. Für Joint Life werden Primary- und
Spouse-Lebensstatus getrennt behandelt; eine nichtlineare Funktion wird nicht
auf einen gemittelten `p11/p10/p01`-Zustand angewandt.
Die dynamischen Koeffizienten wirken für Single Life, den Single-Life-Fallback
und die Lump-Sum-Spouse-Ausprägung. Der bedingt gemeinsame Continue-Income-
Joint-Zweig verwendet dagegen die geladenen statischen Basisraten, solange
keine getrennten `p11/p10/p01`-AV-/Fee-Kohorten bestehen. Ein Full Surrender
gegen einen vollständig erschöpften Surrender Value wird nicht zugelassen:
Der Kunde würde sonst eine positive laufende Income-Garantie ohne Gegenleistung
aufgeben.
Sämtliche Behaviour-Parameter bleiben feste, nicht kalibrierte Proxy-Annahmen.
LSMC oder ein wertmaximierendes Optimal-Behaviour-Modell wird in diesem
statistischen Dynamic-Runner nicht verwendet; dafür besteht ein eigener
Training-/Evaluation-Runner mit eingefrorener Out-of-Sample-Policy.

Die Performance-Lapse-Parameter sind bewusst als konkurrierendes Risiko
parametrisiert. Im Base-Fall gelten 2 % Deadband, 8 % asymptotischer
Cause-specific Jahres-Hazard, 8 % Shortfall-Skala, 20 % Retention-Floor und
30 % Cap auf die kombinierte Jahreswahrscheinlichkeit. Bei 10 % roher
Performance-Lücke, ATM-Garantie und 0,5 % Basislapse ergibt das rund 5,4 %
Jahreslapse. Die Low-/High-Bänder verändern insbesondere Performance-Hazard,
Retention-Floor und Gesamt-Cap. Sämtliche Werte sind unkalibrierte Proxys und
keine australische Experience-Kalibrierung. Beim aktuellen Produkt bleibt
Growth Surrender vertraglich exakt null; wirksam ist der Performance-Kanal nur
in dynamisch modellierten Income-/Single-Life-Zweigen.

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

Der Performance-Gap-Kanal orientiert sich zusätzlich an Johansson, *The Impact
of Policy Returns on Surrender Behavior in Investment-Type Unit-Linked Life
Insurance* (Aalto University, 2026). Die SOA/LIMRA-Behaviour-Studien und die
NAIC-VA-Reform-Auswertung stützen daneben die getrennte Beibehaltung des
Garantie-Moneyness-Kanals und die niedrige Persistenzreaktion bei aktiven,
wertvollen Living-Benefit-Garantien.
