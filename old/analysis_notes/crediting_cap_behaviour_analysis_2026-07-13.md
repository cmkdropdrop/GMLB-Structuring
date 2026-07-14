# Crediting-Cap: Hedge- und Behaviour-Analyse

Stand: 13. Juli 2026

## Ergebnis in Kürze

Die bisherige Randlösung von 0,25 % wird primär durch die im Produktdesign
definierte signierte Cap-Setting-/Crediting-Margin verursacht. Ohne diese
Margin springt der beste fixe Cap auf 20 %. In beiden Fällen schlägt die
validierte jährliche Fitted-Q-Regel den fairen fixen Vergleich nicht.

Das zuerst ergänzte Performance-Modell war ebenfalls zu schwach: Es
multiplizierte einen Basislapse von nur 0,5 % und blieb dadurch selbst bei
großen Performance-Lücken fast wirkungslos. Es wurde durch zwei konkurrierende
Exit-Ursachen ersetzt: gewöhnlicher Moneyness-Lapse und ein eigenständiger,
sättigender Performance-Excess-Hazard. Zusätzlich ist die Moneyness jetzt
signiert, eine Income Election kann nicht am selben Termin lapsen und eine
positive Income-Garantie kann bei Surrender Value null nicht ohne Gegenleistung
aufgegeben werden.

| Szenario | erster/bester Cap | direkter CSM-Proxy | MC-SE | adaptive Validierung vs. fix |
|---|---:|---:|---:|---:|
| Behaviour Base, mit Margin | 0,25 % | AUD 66.513 | AUD 2.242 | AUD -27.174 (SE 938) |
| Behaviour Base, ohne Margin | 20,00 % | AUD 4.789 | AUD 2.042 | AUD -15.132 (SE 1.019) |
| Behaviour High, mit Margin | 0,25 % | AUD 81.606 | AUD 1.927 | AUD -22.826 (SE 819) |

In allen drei Läufen wurde die adaptive Kandidatenregel verworfen. Der reine
Flexibilitätswert gegenüber dem jeweils besten zulässigen fixen Cap ist null.
Mit Margin liegt die deployte 0,25-%-Regel jedoch AUD 7.344 über dem besten vom
ursprünglichen Sanity Check verlangten fixen Cap aus 1–20 % (1 %). Dieser
Mehrwert stammt vollständig aus der zusätzlich zulässigen Minimumregel, nicht
aus jährlicher Zustandsabhängigkeit.

Die gemeinsame Ergebnisgrafik liegt unter
`AGILE_Modelling_Engine/portfolio_simulations/output/crediting_cap_behaviour/
competing_risk_behaviour_hedge_comparison.png`. Sie zeigt CSM-Cap-Kurven,
Behaviour-Base/High-Lapse-Kurven und den direkten Vergleich der deployten Regel
mit dem besten fixen 1–20-%-Benchmark.

## 1. Hedge-/Crediting-Margin

Der Schalter `--hedge-gain` steuert keine realisierte Rohbuchung
`max(Fundreturn - Cap, 0)`. Er steuert die im Produktdesign definierte
Cap-Setting-Margin des ZCB-/Call-Spread-Replikationspakets. Diese Margin kann
für teure hohe Caps negativ werden. Eine zusätzliche Rohbuchung der Performance
oberhalb des Caps würde die Ökonomie doppelt zählen.

Der Schalter verändert nur den Versicherer-Cashflow `crediting_margin`. DVA,
Kunden-Account-Value, Crediting, Lapse, In-force, Gebühren, Claims, Expenses und
Hedge-Execution-Kosten bleiben unverändert. Deshalb kann der Fixed-Cap-Effekt
auch direkt aus den Cashflow-Komponenten nachvollzogen werden:

- 0,25 %: CSM mit Margin AUD 66.513; ohne Margin AUD -47.072;
- 20 %: CSM mit Margin AUD -39.271; ohne Margin AUD 4.789.

Die zugehörige Crediting Margin beträgt beim 0,25-%-Cap rund AUD 113.585 und
beim 20-%-Cap rund AUD -44.060. Hohe Caps können in der Replikationslogik also
zu einem Netto-Crediting-Aufwand werden. Genau dieser Cashflow dreht das fixe
Optimum von 20 % ohne Margin auf 0,25 % mit Margin.

## 2. Audit des bisherigen Behaviour-Modells

Das bisherige Modell war ein Garantie-Antiselektionsmodell:

- wertvolle/ITM Income-Garantie reduziert den Lapse;
- OTM-Moneyness wurde durch `positive_part` auf null gesetzt und erhöhte den
  Lapse daher fälschlich nicht;
- Reference-Fund-Return, Credited Return und deren Differenz fehlten;
- Income-Basislapse war 0,5 % p. a., begrenzt durch einen Hazard-Multiplikator
  von 0,2 bis 3;
- Growth Full Surrender ist gemäß Produktdesign verboten und bleibt null;
- 38,63 % des gewichteten Continue-Income-Joint-Branches bleiben statisch,
  solange getrennte `p11/p10/p01`-Account-Value-/Fee-Kohorten fehlen;
- Income Take-up wird wegen der expliziten Modelpoint-Election deterministisch
  angewandt.

Der danach zunächst verwendete gemeinsame Faktor `exp(beta_gap * g)` löste die
Lücke nicht: Bei 0,5 % Basislapse und einem gemeinsamen Multiplikator-Cap blieb
auch die Performance-Reaktion an eine sehr kleine Basis gebunden. Die
Erwartung, dass Kunden bereits in Growth wegen schwacher Gutschrift kündigen,
widerspricht außerdem der derzeit verbindlichen Produktlogik; Full Surrender
ist dort vertraglich ausgeschlossen.

## 3. Neue Performance-sensitive Hazard-Funktion

Nach dem Annual Crediting wird für das gerade abgelaufene Jahr berechnet:

```text
g_raw,y = max(log(1 + R_reference,y) - log(1 + R_credited,y), 0)
g_y     = clip(max(g_raw,y - deadband, 0), 0, shortfall_max)
```

`R_reference` ist ausschließlich der vertragliche Kunden-Reference-Fund. Weder
Backing Assets noch Hedge-P&L oder künftige Marktperformance gehen ein.

Der gewöhnliche Hazard verwendet die signierte Garantie-Moneyness
`m = log(PV(Garantie) / Surrender Value)`:

```text
mu_ordinary = -log(1 - p_base)
              * exp(beta_m * m + beta_p * z + beta_mp * m * z)
```

Der Performance-Kanal ist davon als Cause-specific Hazard getrennt:

```text
r(m)           = max(retention_floor, exp(-retention_gamma * max(m, 0)))
mu_performance = r(m) * excess_hazard_cap
                 * (1 - exp(-g_y / excess_hazard_scale))
mu_total       = mu_ordinary + mu_performance
p(dt)          = 1 - exp(-mu_total * dt)
```

Die kombinierte Jahreswahrscheinlichkeit wird vor der monatskonsistenten
Umrechnung durch `annual_probability_cap` begrenzt. Für Diagnosen werden die
beiden Ursachen proportional zu ihren Hazards zerlegt; die Exit-Massen
addieren sich exakt zur gesamten Lapse-Masse.

Im Base-Fall gelten 2 % Deadband, 30 % Shortfall-Clip, 8 % asymptotischer
Performance-Hazard, 8 % Shortfall-Skala, 20 % Retention-Floor und 30 % Cap auf
die kombinierte Jahreswahrscheinlichkeit. Bei ATM-Garantie, 10 % roher
Performance-Lücke und 0,5 % Basislapse entstehen damit rund 5,4 % Jahreslapse
statt zuvor weniger als 1 %. Bei einer doppelt so hohen Garantie wie dem
Surrender Value fällt der Wert rational auf rund 2 %.

Der LSMC-Control-State enthält den trailing Performance-Shortfall explizit.
Damit kann die Folgeentscheidung die realisierte Kundenhistorie sehen, ohne
Look-ahead. Die heterogene Garantie-Moneyness der Modellpunkt-Kohorten wird im
kompakten Policy-State jedoch nur indirekt über die Crediting-Historie
repräsentiert. Die direkte Holdout-Validierung verhindert dadurch falsche
positive Deployments, kann aber einen tatsächlich brauchbaren adaptiven Wert
übersehen. Eine sofortige, separat kalibrierte Reaktion allein auf den zu
Jahresbeginn angekündigten neuen Cap wurde nicht erfunden.

## 4. Empirische und aktuarielle Grundlage

- Die [American Academy of Actuaries](https://www.actuary.org/wp-content/uploads/2025/05/life-paper-dynamic-lapses.pdf)
  nennt Credited Rate versus Alternativanlage, Garantie-Moneyness,
  Surrender-Charges, Duration und Produktart als getrennte Treiber. Für
  Variable Annuities beschreibt sie Base-Lapse mal Dynamic Adjustment Factor
  beziehungsweise logistische Modelle.
- Die [SOA/LIMRA Variable Annuity Behavior Study 2022-2024](https://www.soa.org/globalassets/assets/files/resources/research-report/2026/2022-24-variable-annuity-study-report.pdf)
  umfasst 11,5 Mio. Surrender-Exposures. Sie zeigt niedrige Surrenders bei
  aktivierten GLWB und systematischen Withdrawals sowie deutliche Abhängigkeit
  von Moneyness und Surrender-Charge-Horizont.
- Der [NAIC/Oliver-Wyman QIS-II-Bericht](https://content.naic.org/sites/default/files/committee_related_documents/cmte_e_va_issues_wg_related_qis_ii_public_report.pdf)
  berichtet nach der Surrender-Charge-Periode ungefähr 12 % Lapse für weit OTM
  liegende Garantien und rund 1-3 % für tief ITM liegende Segmente.
- [Knoller, Kraut und Schoenmaekers](https://onlinelibrary.wiley.com/doi/10.1111/jori.12076)
  finden in VA-Policendaten Garantie-/Options-Moneyness als stärksten
  Surrender-Erklärer.
- [Johansson, Aalto University](https://research.aalto.fi/en/publications/essays-on-retail-investors-mutual-fund-flows/)
  findet bei Investment-Type Unit-Linked Policies, dass positive
  Policenrenditen Terminations deutlich reduzieren und rollierende sowie
  Excess Returns zusätzliche Erklärungskraft besitzen. Das stützt die
  Richtung des Performance-Kanals, kalibriert aber nicht dessen Höhe für
  dieses australische Garantieprodukt.

## 5. Interpretation der neuen Ergebnisse

Im Behaviour-Base-Lauf fällt die kumulierte Full-Surrender-Wahrscheinlichkeit
von 10,08 % bei 0,25 % Cap auf 6,70 % bei 20 % Cap. Damit zeigt das
Gesamtportfolio nun klar die erwartete Richtung: Wer bei guter Fondsperformance
kaum Gutschrift erhält, kündigt häufiger. Dass die Kurve nicht noch steiler
ist, liegt vor allem an der Garantie-Retention, am statischen Joint-Life-Zweig
und daran, dass nach Surrender-Value-Erschöpfung kein ökonomisch unsinniger
Full Surrender mehr möglich ist.

Im High-Bündel liegt die kumulierte Surrender-Wahrscheinlichkeit bei 17,52 %
für 0,25 % und 10,25 % für 20 %. Der Behaviour-Kanal ist damit materiell. Die
Crediting Margin dominiert die CSM-Entscheidung trotzdem: CSM mit Margin fällt
im Base-Fall von AUD 66.513 bei 0,25 % auf AUD -39.271 bei 20 %, während er
ohne Margin in die Gegenrichtung bis AUD 4.789 steigt.

Das High-Ergebnis darf nicht als Kalibrierung interpretiert werden: Die
`high`-Basis wählt das gesamte High-Annahmenbündel, nicht nur einen einzelnen
Performance-Koeffizienten.

## 6. Verbleibende Modellgrenzen

Ein materieller, empirisch belastbarer Flexibilitätswert würde weitere
Produkt-/Experience-Information benötigen:

1. australische Experience-Daten für Lapse nach tatsächlich kommunizierter
   Reference- und Credited-Performance;
2. separate dynamische Joint-Life-`p11/p10/p01`-Kohorten;
3. einen kausal rollierbaren LSMC-Aggregatzustand für Garantie-Moneyness,
   Surrender Value, Income-Exposure und erschöpfte AV-Kohorten;
4. Klarstellung, ob Growth Surrender entgegen dem aktuellen Produktdesign
   zulässig sein soll;
5. gegebenenfalls ein empirischer Kanal für die sofortige Reaktion auf einen
   angekündigten Folgejahres-Cap;
6. Governance, Backtesting und Segmentierung nach Duration, Alter, Vertrieb,
   Surrender-Charge/MVA und Guarantee-Utilisation.

Ohne diese Erweiterungen wäre es methodisch falsch, den Behaviour-Parameter so
lange zu erhöhen, bis die flexible Strategie zwangsläufig besser aussieht.
