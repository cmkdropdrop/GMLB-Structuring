# Dynamische Behaviour-Annahmen

Die verständliche fachliche Erklärung mit schematischen Grafiken steht in
[`Policy_Behaviour_Modellierung.md`](../documentation_and_background_info/Policy_Behaviour_Modellierung.md).
Dieses Verzeichnis bleibt die exakte technische Quelle für die geladenen
Parameter und ihre Governance-Metadaten.

Die beiden CSV-Dateien in diesem Verzeichnis sind die Eingabequelle für das
vereinfachte dynamische Policyholder-Behaviour-Modell:

- `dynamic_behaviour_baselines.csv` enthält die Basisraten beziehungsweise
  Basis-Utilisationen nach Phase und Policy Year.
- `dynamic_behaviour_coefficients.csv` enthält die Reaktionskoeffizienten und
  gemeinsamen Kovariatengrenzen.

Der Loader ist
`AGILE_Modelling_Engine/agile_engine/dynamic_behaviour_assumptions.py`.

## Modellform

Die technische Modellform kann mehrere Zustandsgrößen aufnehmen. In der
versionierten Basis `dynamic_proxy_2026-07-13_v2` werden bewusst nur die ohne
Experience-Daten hinreichend begründbaren Treiber aktiviert:

```text
m_raw = log(G / A)
m = clip(m_raw, -log(2), log(2))
z = clip(log(P / 100000), -2, 2)
g_raw = max(log(1 + R_reference) - log(1 + R_credited), 0)
g_takeup = clip(g_raw, 0, 1)
```

Die Standard-Hazard- und Fractional-Logit-Funktionen verwenden das geclippte
`m`. Nur das Retention-Gate des konkurrierenden Performance-Lapse verwendet
den positiven Teil von `m_raw` mit seiner eigenen Obergrenze `log(4)`.

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
sichtbare Lücke zwischen vollständigem Reference-Fund-Faktor und Crediting-
Faktor des abgelaufenen Jahres. Beim Total-Protection-Design bildet sie damit
vor allem einen Cap-Gap ab, nicht allgemein schlechte Marktperformance.
`R_reference` stammt ausschließlich aus dem vertraglichen Kunden-Reference-
Fund; Backing Assets, Hedge-P&L oder künftige Marktperformance werden nicht
verwendet.

Income Take-up und gewöhnlicher Income-Lapse verwenden einen proportionalen
Hazard-Ansatz mit **signierter** Garantie-Moneyness. In der kontrollierten
Basis sind Premium-, Account-Value-, einzelne Return- und Interaktionseffekte
null. Der sichtbare Performance-Gap ist neben der Garantie-Moneyness als
zweiter Take-up-Treiber aktiviert:

```text
mu_takeup = -log(1 - p_base) * exp(
    beta_m * m + beta_p * z + beta_mp * m * z
    + beta_av * log(AV / premium)
    + beta_income * prospective_annual_income / premium
    + beta_ref * previous_reference_return
    + beta_credit * previous_credited_return
    + beta_gap * g_takeup
)
```

Die Baseline `p_base` ist nach Policy Year gestaffelt und bildet damit die
Vertragsdauer ab. Aktiv sind `beta_m = 4` und der unkalibrierte
Performance-Gap-Proxy `beta_gap = 4`; die übrigen zusätzlichen Koeffizienten
der dargestellten Erweiterung sind in v2 null. Der gesamte Log-Hazard-Predictor
wird gemeinsam einmalig durch `multiplier_floor` und `multiplier_cap` begrenzt.
Es wird keine zusätzliche Zukunftsinformation oder physische Kalibrierung
eingeführt.

Beim Income-Lapse kommt ein eigenständiger konkurrierender Performance-Hazard
hinzu. Damit wird sichtbare Underperformance nicht mehr als Multiplikator der
kleinen gewöhnlichen Basislapse modelliert:

```text
g = clip(max(g_raw - deadband, 0), 0, shortfall_max)
m_ret = clip(max(m_raw, 0), 0, log_moneyness_max)
r(m) = max(retention_floor, exp(-retention_gamma * m_ret))
mu_performance = r(m) * excess_hazard_cap * (1 - exp(-g / excess_hazard_scale))
mu_total = mu_ordinary + mu_performance
p_raw_annual = 1 - exp(-mu_total)
p_combined_annual = max(
    p_ordinary_annual,
    min(p_raw_annual, annual_probability_cap)
)
p(dt) = 1 - (1 - p_combined_annual)^dt
```

Die gemeinsame Jahreswahrscheinlichkeit wird durch `annual_probability_cap`
begrenzt und erst danach konsistent auf Monatswahrscheinlichkeiten umgerechnet.
Der Cap begrenzt nur das inkrementelle kombinierte Risiko; er reduziert niemals
eine bereits höhere gewöhnliche Lapse-Wahrscheinlichkeit.

Für Diagnosezwecke werden die beiden Exit-Ursachen proportional zu ihren
Cause-specific Hazards auf die Gesamtwahrscheinlichkeit verteilt; ihre Summe
entspricht daher exakt der gesamten Lapse-Masse. Der gewöhnliche relative
Hazard bleibt durch `multiplier_floor` und `multiplier_cap` begrenzt. Diese
Grenzen beschneiden den unabhängigen Performance-Hazard nicht. Der Performance-
Hazard ist in Low null und in Base sowie High als unkalibrierter 8-%-Proxy aktiv.
Income-Lapse wird an jedem monatlichen Full-Withdrawal-Zeitpunkt aus dem
aktuellen Zustand neu bestimmt. Das freiwillige Take-up-Band bleibt ab Policy
Year 8 offen bei 30 % in Base; es gibt keinen Behaviour-bedingten 100-%-Start.
Vertragliche automatische Starts werden ausschließlich durch die Produktlogik
des Projektors erzwungen.

Free- und Excess-Withdrawal verwenden technisch eine Fractional-Logit-Funktion:

```text
logit(u) = logit(u_base)
           + beta_m * m
           + beta_p * z
           + beta_mp * m * z
           + beta_mva * mva_fraction
```

Growth-Free-Withdrawals sind vertraglich strukturell null. Für Income-Excess-
Withdrawals ist eine kleine signierte Moneyness-Reaktion mit
`beta_m = -0,5` aktiv: Eine relativ weniger wertvolle Garantie erhöht, eine
relativ wertvollere Garantie senkt die erwartete Mehrentnahme. Diese Richtung
entspricht der NAIC-QIS-II-Beobachtung höherer Excess-Withdrawal-Raten bei weit
aus dem Geld liegenden Garantien; die konkrete Koeffizientenhöhe ist dennoch
ein unkalibrierter Repository-Proxy. Premium und Interaktion bleiben mangels
Experience null. Der bestehende MVA-Covariate mit `beta_mva = -2` reduziert die
erwartete Mehrentnahme bei aktueller MVA-Belastung. Das MVA-Signal wird nicht
auf den MVA-freien Free-Withdrawal-Anteil angewandt. Bei monatlicher Frequenz
werden die Zustandsraten monatlich und bei jährlicher Frequenz am tatsächlichen
Entnahmezeitpunkt nach der regulären Income-Zahlung aktualisiert. Der Excess-
Ansatz ist eine erwartete annualisierte Rate als Anteil des Investment Value
und kein vollständiges empirisches Incidence-/Severity-Hurdle-Modell.
Im optionalen Monatsmodus wird die Rate als `r/12` auf das jeweils aktuelle,
im Jahresverlauf sinkende Investment Value angewandt; sie rekonstruiert daher
nicht exakt eine einmalige Entnahme von `r` auf dem Jahresanfangswert. Der
geladene v2-Basissatz verwendet die jährliche Frequenz.

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
Direkte Aufrufe der generischen Low-Level-Funktion
`DynamicLapseParams.growth_probability()` enthalten dieses Produkt-Gate nicht
und dürfen deshalb nicht als Produktprojektion verwendet werden.

Der Portfolio-Hauptlauf verwendet den geladenen dynamischen Income-Take-up-
Hazard. `income_start_year` bleibt ausschließlich Eingabe für den expliziten
deterministischen Validierungsbenchmark. Dynamic Election wird nach Credit,
Fee-Posting und Mortalität auf jedem zulässigen Policy Anniversary neu aus den
dann sichtbaren Zuständen bestimmt. Für Joint Life werden Primary- und
Spouse-Lebensstatus getrennt behandelt; eine nichtlineare Funktion wird nicht
auf einen gemittelten `p11/p10/p01`-Zustand angewandt.
Die dynamischen Koeffizienten wirken für Single Life und Joint Life. Bei
zustandsabhängiger Election werden Primary- und Spouse-Lebensstatus mit einem
separaten, reproduzierbaren Mortalitäts-Seed pfadweise fortgeschrieben. Nach
Election werden Continue-Income-Entscheidungen damit auf dem tatsächlichen
Status beider Leben und nicht auf einem gemittelten `p11/p10/p01`-Zustand
ausgewertet. Der explizite deterministische Benchmark behält aus
Rückwärtskompatibilität die Modellpunkt-Election-Regel. In den Portfolio-
V00/V01/V10/V11-Vergleichen verwendet er jedoch dieselben pfadweisen
Primary-/Spouse-Mortalitätsziehungen wie die übrigen Arme, damit die
Behaviour-Zerlegung keinen Wechsel der Mortalitätsmethodik mitmisst. Nur der
Standalone-Low-Level-Projektor behält standardmäßig den historischen Expected-
Decrement-Fallback. Ein Full Surrender gegen einen vollständig
erschöpften Surrender Value wird nicht zugelassen:
Der Kunde würde sonst eine positive laufende Income-Garantie ohne Gegenleistung
aufgeben.
Sämtliche Behaviour-Parameter bleiben feste, nicht kalibrierte Proxy-Annahmen.
LSMC oder ein wertmaximierendes Optimal-Behaviour-Modell wird in diesem
statistischen Dynamic-Runner nicht verwendet; dafür besteht ein eigener
Training-/Evaluation-Runner mit eingefrorener Out-of-Sample-Policy.

Die Performance-Lapse-Parameter sind als konkurrierendes Modellrisiko
parametrisiert. Low deaktiviert den zusätzlichen Hazard. Base und High
aktivieren den bisherigen asymptotischen 8-%-Hazard als unkalibrierten Proxy.
Formparameter wie 2 % Deadband, 8 % Skala und 20 % Retention-Floor bleiben
erhalten. Bei 0,5 % gewöhnlicher Basislapse und ATM-Garantie steigt die
modellierte Jahreslapse dadurch von 0,5 % ohne Gap auf rund 5,41 % bei einem
Gap von 10 %. Diese Materialität ist ein explizites, nicht kalibriertes
Modellrisiko und muss über Low/Base/High sowie Experience-Backtesting
kontrolliert werden. Beim aktuellen Produkt bleibt Growth Surrender
vertraglich exakt null; in dieser Phase wirkt der Performance-Gap stattdessen
über eine frühere freiwillige Income Election.

## Mortalitätsabgrenzung

Single-Life-Läufe verwenden Expected Decrements. Portfolio-Joint-Life-Läufe
einschließlich der deterministischen Faktorbenchmarks verwenden getrennte
pfadweise Primary-/Spouse-Lebensstatus und einen gemeinsamen Mortalitäts-Seed;
die Resultate bleiben Monte-Carlo-Erwartungswerte. Mangels einer
bereitgestellten, fachlich
freigegebenen Mortalitätstafel bleibt die verwendete Gompertz-Makeham-Basis
illustrativ.
Ergebnisse sind deshalb als vereinfachte Projektionen auf illustrativer Proxy-
Mortalitätsbasis zu kennzeichnen und nicht als vollständig kalibrierte Best-
Estimate-Mortalitätsprognose.

## Einordnung und Governance

Die CSVs unterscheiden `contractual_constraint` für vertraglich erzwungene
Nullen von `uncalibrated_proxy` für Behaviour-Annahmen. Das Metadatenmanifest
weist den Satz deshalb als `mixed` aus und listet beide Statuswerte. Die Proxy-
Zeilen sind literatur- und praxisinformierte Startwerte, aber weder eine
australische Experience Study noch eine vollständig kalibrierte Prognose. Vor
einer Produktionsverwendung sind interne Bestandsdaten, Segmentierung,
Credibility, Backtesting und Governance-Freigabe erforderlich.

Dies gilt ausdrücklich auch für sämtliche Regressionskoeffizienten sowie die
Hazard-Multiplikator-Floors und -Caps; diese Grenzen sind ebenfalls
`UNCALIBRATED_PROXY` und keine beobachteten Verhaltensschranken.

Die `low_value`- und `high_value`-Spalten sind gerichtete Behaviour-Level. Der
Loader verlangt `low_value <= base_value <= high_value` und lässt zwischen den
Bändern nur Baselines sowie dafür freigegebene Output-/Hazard-Caps variieren.
Vorzeichenbehaftete Slopes und sonstige Shape-Parameter müssen identisch
bleiben; ihre Unsicherheit ist separat zu stressen. Das gewählte Level wird
über `value_basis="low"`, `"base"` oder `"high"` selektiert.

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

Direkte Praxisquellen:

- [NAIC, Variable Annuity Statutory Reserve and Capital Reform – QIS II
  Public Report (2018), insbesondere Abschnitt 7](https://content.naic.org/sites/default/files/committee_related_documents/cmte_e_va_issues_wg_related_qis_ii_public_report.pdf)
- [SOA/LIMRA, Variable Annuity Guaranteed Living Benefits Utilization – 2015
  Experience](https://www.soa.org/globalassets/assets/files/resources/research-report/2018/variable-annuity-guaranteed-utilization.pdf)
- [SOA, 2018 Variable Annuity Guaranteed Benefits
  Survey](https://www.soa.org/globalassets/assets/Files/resources/research-report/2018/2018-variable-annuity-report.pdf)
