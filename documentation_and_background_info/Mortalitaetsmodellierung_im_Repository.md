# Mortalitätsmodellierung im Repository

Stand der Analyse: 12. Juli 2026  
Analysierter Kern: `AGILE_Modelling_Engine` Version 2.0.0 sowie die zugehörigen Eingabe- und Hintergrunddateien

> **Methodischer Hinweis:** Diese Dokumentation beruht ausschließlich auf statischer Code- und Dateilektüre. Entsprechend den Repository-Anweisungen wurden keine Skripte und keine Tests ausgeführt. Aussagen über Testabdeckung beschreiben daher den vorhandenen Testcode, nicht das Ergebnis eines aktuellen Testlaufs.

> **Behaviour-Abgrenzung:** LSMC ist inzwischen nur noch archivierter
> Quellcode und kein verwendeter Bewertungs- oder Projektionspfad. Für die
> aktuelle dynamische, markt- und bruttoprämienabhängige Modellierung von
> Lapse, Income Take-up und Withdrawals ist
> [Policy_Behaviour_Modellierung.md](Policy_Behaviour_Modellierung.md)
> maßgeblich. Spätere LSMC-Verweise in diesem Dokument sind historischer oder
> methodischer Kontext für Mortalität, keine Beschreibung des aktiven Modells.

## Kurzfazit

Die aktive Engine modelliert Mortalität als **deterministische, generational verbesserte Sterblichkeitstafel**. Todesfälle werden in der normalen Projektion nicht für einzelne versicherte Personen simuliert. Stattdessen werden Todesfallleistungen, Rentenzahlungen und der verbleibende Bestand mit bedingten Sterbe- und Überlebenswahrscheinlichkeiten gewichtet.

Die derzeit von den Beispielen verwendete Basistafel ist keine eingelesene australische Sterbetafel, sondern eine im Code erzeugte, illustrative Gompertz-Makeham-Kurve. Sie soll laut Code lediglich die Form der Australian Life Tables 2020–22 approximieren. Für eine produktive Bewertung ist sie ausdrücklich durch eine freigegebene Pricing- beziehungsweise Best-Estimate-Basis zu ersetzen.

Die wichtigsten Merkmale sind:

- getrennte jährliche $q_x$ für Männer und Frauen;
- Basisjahr 2022 und eine feste generational angewandte Mortalitätsverbesserung;
- monatliche Cashflow-Projektion mit deterministischen Wahrscheinlichkeitsgewichten;
- Primary-Life- und, nach Wahl der Spouse-Income-Fortsetzung, Last-Survivor-Mortalität;
- identische Mortalitätsbasis in risikoneutraler Bewertung und Real-World-Projektion;
- Mortalitäts-, Langlebigkeits- und Katastrophenstresse für Sensitivitäten und einen Solvency-II-artigen Kapitalproxy;
- keine aktive stochastische oder systematische Langlebigkeitsmodellierung.

## 1. Relevante Bestandteile des Repositories

| Datei | Rolle im Mortalitätsmodell |
| --- | --- |
| [`agile_engine/mortality.py`](../AGILE_Modelling_Engine/agile_engine/mortality.py) | Basistafel, Improvements, Monats-$q$, Survival, Joint Life, Lebenserwartung, Annuitätenfaktor und Stresse |
| [`agile_engine/product.py`](../AGILE_Modelling_Engine/agile_engine/product.py) | Demografische Policy-Felder, Spouse-Death-Election und vertragliche Fixed-Income-Rate |
| [`agile_engine/projection.py`](../AGILE_Modelling_Engine/agile_engine/projection.py) | Monatliche Anwendung der Mortalität auf In-force-Gewichte und Cashflows |
| [`agile_engine/pricing.py`](../AGILE_Modelling_Engine/agile_engine/pricing.py) | Risikoneutrale Bewertung und Auflösung des Projektionshorizonts |
| [`agile_engine/model_points.py`](../AGILE_Modelling_Engine/agile_engine/model_points.py) | Validierte Zuordnung der Policyholder-Modellpunktdatei auf `PolicySpec` |
| [`agile_engine/portfolio.py`](../AGILE_Modelling_Engine/agile_engine/portfolio.py) | Expected-Decrement-Bewertung je Modellpunkt, Joint-/Single-Life-Election-Mischung und Portfolioaggregation |
| [`agile_engine/profitability.py`](../AGILE_Modelling_Engine/agile_engine/profitability.py) | Real-World-Projektion mit derselben Mortalitätsbasis |
| [`agile_engine/capital.py`](../AGILE_Modelling_Engine/agile_engine/capital.py) | Mortalitäts-, Langlebigkeits- und Katastrophenstress im Kapitalproxy |
| [`agile_engine/sensitivities.py`](../AGILE_Modelling_Engine/agile_engine/sensitivities.py) | Standard-Sensitivitäten auf $q_x$ |
| [`agile_engine/lsmc.py`](../AGILE_Modelling_Engine/agile_engine/lsmc.py) | Legacy-Research-Code; nicht im Portfolio-Bewertungspfad verwendet |
| [`input_model_points_policyholders/model_points_policyholders.csv`](../input_model_points_policyholders/model_points_policyholders.csv) | Operative Quelle der demografischen New-Business-Modellpunktfelder |
| [`Code based on Papers/`](../Code%20based%20on%20Papers) | Methodenreferenzen mit weiteren Mortalitätsansätzen; nicht Teil der aktiven Engine |

## 2. Eingaben und Konstruktion der Mortalitätsbasis

### 2.1 `MortalityTable`

Die zentrale Klasse ist die unveränderliche Dataclass `MortalityTable` in `mortality.py` (Zeilen 33–89).

| Feld | Default | Bedeutung |
| --- | ---: | --- |
| `qx_male` | kein allgemeiner Constructor-Default | jährliche Männer-$q_x$, Indizes 0 bis 115 |
| `qx_female` | kein allgemeiner Constructor-Default | jährliche Frauen-$q_x$, Indizes 0 bis 115 |
| `base_year` | 2022 | Kalenderjahr der Basistafel |
| `improvement_rate` | 0,0125 | jährliche Verbesserung bis zum Taper-Alter |
| `improvement_taper_age` | 90 | Beginn des linearen Tapers |
| `improvement_end_age` | 110 | Ende der Verbesserung |
| `stress_multiplier` | 1,0 | multiplikativer Stress auf alle $q_x$ |
| `q_add_first_year` | 0,0 | additives Jahres-$q$ im ersten Projektionsjahr |

Beide $q_x$-Arrays müssen 116 endliche Werte enthalten, vollständig in $[0,1]$ liegen und bei Alter 115 mit $q_{115}=1$ enden. Der Constructor kopiert die Arrays defensiv und setzt sie auf read-only. Auch Improvements und Stressparameter werden validiert.

### 2.2 Illustrative Gompertz-Makeham-Basis

Die aktiven Beispielprogramme erzeugen die Mortalität mit `MortalityTable.gompertz_makeham()`; es wird keine Sterbetafeldatei gelesen. Die Defaults in `mortality.py` (Zeilen 95–115) sind:

| Geschlecht | (A) | (B) | (c) |
| --- | ---: | ---: | ---: |
| männlich | 0,000300 | 0,000017 | 1,103 |
| weiblich | 0,000200 | 0,000009 | 1,106 |

Aus der Makeham-Gompertz-Intensität

\[
\mu_s(x)=A_s+B_s c_s^x
\]

wird durch Integration über ein Lebensjahr die jährliche Sterbewahrscheinlichkeit erzeugt:

\[
q^{\text{base}}_{x,s}
=1-\exp\left(
-A_s-B_s c_s^x\frac{c_s-1}{\ln(c_s)}
\right).
\]

Die Werte werden auf $[10^{-6},1]$ begrenzt; $q_{115}$ wird anschließend zwingend auf 1 gesetzt.

Der Code bezeichnet diese Kurve ausdrücklich als **illustrativ** und nur als Approximation der Form von ALT 2020–22. Sie ist daher weder eine offizielle ALT-Tabelle noch eine nachgewiesene Pricing-, Reservierungs- oder Experience-Basis.

### 2.3 Externe $q_x$-Tabellen

`MortalityTable.from_qx()` in `mortality.py` (Zeilen 117–148) kann vom Aufrufer gelieferte Alters-, Männer-$q_x$- und Frauen-$q_x$-Vektoren verarbeiten. Die Funktion:

- liest selbst keine Datei;
- verlangt im Produktionsmodus eine Abdeckung der Alter 0 bis 114;
- interpoliert fehlende Alterswerte linear in den $q_x$;
- setzt $q_{115}=1$;
- begrenzt externe $q_x$ auf $[10^{-6},1]$;
- erlaubt konstante Endpunktextrapolation nur nach explizitem `allow_constant_extrapolation=True`, das im Code als Research Override bezeichnet wird.

Die Validierung begrenzt weder die maximale Lücke zwischen zwei gelieferten Altern noch verlangt sie einen altersmonotonen Verlauf. Beispielsweise würde eine formal vollständige Spannweite nur mit den Stützstellen 0 und 114 akzeptiert und über den gesamten Bereich linear interpoliert. Ob eine solche Eingabe fachlich zulässig ist, muss daher außerhalb dieser Factory sichergestellt werden.

Im Repository gibt es derzeit weder eine operative Mortalitätsdatei noch einen Loader, der eine solche Datei an `from_qx()` übergibt. `input_market_data/model_parameters.csv` enthält ausschließlich Marktmodellparameter und keine Mortalitätsannahmen.

### 2.4 Demografische Modelpoint-Felder

Die Engine erwartet in `PolicySpec` insbesondere:

- `age` und `sex` der primären versicherten Person;
- `commencement_year` zur Verankerung der Improvements;
- `spouse`, `spouse_age` und `spouse_sex`;
- `spouse_death_election` mit `continue_income` oder `lump_sum`;
- `income_start_year` für den expliziten Election Anniversary.

`Sex` unterstützt technisch nur `M` und `F`. Bei `spouse=True` müssen Alter und
Geschlecht der zweiten versicherten Person gesetzt sein.
`PolicySpec.validate_against()` prüft die demografischen und vertraglichen
Grenzen des generischen Produkts. Nicht mehr zum Produkt gehörende
Age-Pension+-Felder bleiben lediglich aus Legacy-Kompatibilitätsgründen in der
Dataclass vorhanden und müssen im generischen Portfolio deaktiviert sein.

`load_policyholder_model_points()` liest und validiert insbesondere
`primary_age`, `primary_sex`, `spouse`, `secondary_age`, `secondary_sex`,
`commencement_year`, `spouse_death_election`, `life_basis` und
`income_start_year`. `life_basis` wird gegen die Spouse-Felder reconciliert;
Single versus Joint wird im `PolicySpec` technisch aus `spouse` abgeleitet.

Damit ist die derzeitige Verdrahtung:

```text
Policyholder-Modellpunkt-CSV
    └── load_policyholder_model_points()
            └── validierter PolicySpec je Modellpunkt

Portfolio-Runner
    ├── gemeinsame Marktpfade und Expected-Decrement-Projektion
    └── MortalityTable.gompertz_makeham() als ausdrücklich illustrativer Proxy

Produktive Mortalitätstafel
    └── weiterhin kein Repository-Input und kein governter Dateiloader
```

## 3. Jährliche Mortalität und Improvements

### 3.1 Altersinterpolation

Für ein gebrochenes Alter $x=n+f$ interpoliert `MortalityTable.q()` linear zwischen den jährlichen Tabellenwerten:

\[
q^{\text{base}}(x)
=(1-f)q^{\text{base}}_n+f q^{\text{base}}_{n+1}.
\]

Das ist eine lineare Interpolation von Wahrscheinlichkeiten, nicht von Hazard Rates oder Log-Survival-Werten.
Eine bewusste Ausnahme gilt am Tabellenende: $q_{115}=1$ ist ein technischer
Terminal-Sentinel und wird für $114\le x<115$ nicht in $q_{114}$
hineininterpoliert.

### 3.2 Altersabhängige Improvement Rate

Die Improvement Rate ist für Männer und Frauen identisch und lautet:

\[
i(x)=0{,}0125\cdot
\operatorname{clip}\left(\frac{110-x}{110-90},0,1\right).
\]

Damit gilt:

- bis einschließlich Alter 90: 1,25 % pro Jahr;
- zwischen 90 und 110: linear fallende Verbesserung;
- ab Alter 110: keine weitere Verbesserung.

### 3.3 Generational angewandtes $q$

Sei

\[
y=\texttt{commencement\_year}-\texttt{base\_year}+t
\]

der Abstand zum Basisjahr am Projektionszeitpunkt $t$, und sei $\tau=t$ die Policendauer. Dann verwendet die Engine im Wesentlichen:

\[
q(x,s,y,\tau)=
\operatorname{clip}\left[
q^{\text{base}}_s(x)\,(1-i(x))^{\max(y,0)}\,m
+a\,\mathbf 1_{\{\tau<1\}},
0,1
\right],
\]

mit Stressmultiplikator $m$ und First-Year-Add-on $a$.

Die Projektion erhöht Alter und Kalenderzeit gemeinsam. Für den Default-Modelpoint mit `commencement_year=2026.5` und `base_year=2022` werden daher bereits bei Vertragsbeginn 4,5 Jahre Improvement angewandt. Negative Abstände zum Basisjahr werden auf null gesetzt; die Engine verschlechtert die Tafel für Zeitpunkte vor dem Basisjahr nicht rückwärts.

### 3.4 Umrechnung auf Monate

Die monatliche bedingte Sterbewahrscheinlichkeit ist:

\[
q_m=1-(1-q_a)^{1/12}.
\]

Das entspricht einer Constant-Force- beziehungsweise Constant-Hazard-
Umrechnung des am Policy Anniversary ermittelten Jahres-$q$.

Die aktive Engine ermittelt das generational verbesserte Jahres-$q$ nun einmal
am jeweiligen Policy Anniversary und hält den daraus konvertierten Monatshazard
für die folgenden zwölf Monate konstant. Außerhalb des terminalen Jahres gilt
daher exakt:

\[
\prod_{m=1}^{12}(1-q_m)=1-q_a.
\]

`MortalityTable.monthly_q_curve()` ist die gemeinsame Quelle für den
Cashflow-Projektor, die Spouse-Survival-Gewichtung und die
versicherungsmathematischen Hilfsgrößen. `q_monthly()` bleibt als lokaler
Einzelwert-Konverter verfügbar, wird im produktiven Lifetime-Pfad aber nicht
monatlich mit neuem gebrochenem Alter aufgerufen.

### 3.5 Terminales Alter

Das terminale Alter ist als Modulkonstante `MAX_AGE = 115` codiert. Die
zentrale Monatskurve setzt das Todesdekrement im Intervall, dessen Ende Alter
115 erstmals erreicht, auf eins. Damit endet der volle Lifetime-Horizont über
den normalen Death-Eventflow: Fee Settlement, post-fee Death Benefit und kein
anschließendes nachschüssiges Income. Diese harte Terminalkonvention ist von
der eigentlichen Gompertz-Makeham-Kurve beziehungsweise einer externen Tafel
zu unterscheiden. Der Sentinel $q_{115}=1$ wird nicht in gebrochene Alter unter
115 zurückinterpoliert; bis zur terminalen Monatsgrenze wird höchstens
$q_{114}$ als Tabellenendrate verwendet.

## 4. Survival, Joint Life und versicherungsmathematische Hilfsgrößen

### 4.1 Jährliche Survival-Kurve

`survival_curve()` sampelt die gemeinsame monatliche Survival-Kurve an den
Policy Anniversaries:

\[
S_0=1,
\qquad
S_{k+1}=S_k\left(1-q(x+k,s,y+k)\right).
\]

Damit stimmen jährliche Survival-Punkte und die monatlich aufgebaute
Primary-Survival-Kurve an den gemeinsamen Rasterpunkten überein.

### 4.2 Last-Survivor-Survival

Für zwei versicherte Personen nimmt `joint_last_survivor_curve()` unabhängige Lebensdauern an:

\[
S^{LS}_k
=P(\text{mindestens eine Person lebt})
=S^{(1)}_k+S^{(2)}_k-S^{(1)}_k S^{(2)}_k.
\]

Es gibt keine Couple-Mortality, gemeinsame Todesursache, Bereavement-Komponente oder sonstige Abhängigkeit zwischen den beiden Lebensdauern.

### 4.3 Lebenserwartung

`life_expectancy()` summiert die monatliche Survival-Kurve trapezoidal:

\[
e_x\approx\frac1{12}\sum_m\frac{S_m+S_{m+1}}{2}.
\]

Das ist eine Approximation der **vollständigen** Lebenserwartung. Der Modulheader von `mortality.py` nennt dagegen eine „curtate life expectancy“. Methodendocstring und Implementierung sind eindeutig trapezoidal-komplett; die Bezeichnung im Modulheader ist daher eine interne Dokumentationsinkonsistenz.

### 4.4 Annuitätenfaktor

`annuity_factor()` bewertet eine Zahlung von 1 pro Jahr als zwölf monatlich
nachschüssige Teilzahlungen auf derselben Mortalitätskurve wie der
Cashflow-Projektor. Bei flacher stetiger Rate $r$ gilt:

\[
a_x=\frac1{12}\sum_{m=1}^{M}S_m e^{-rm/12}.
\]

Für Joint Life wird der Horizont bis zur längeren Restlaufzeit der beiden Leben
ausgedehnt und die unabhängige Last-Survivor-Survival monatlich verwendet. Die
blockweise geometrische Auswertung ändert nur die Rechenform, nicht die
monatliche Zahlungsdefinition.

Dieser Annuitätenfaktor setzt **nicht** die vertragliche Lifetime Income Rate. Die garantierte Rate kommt aus der separat codierten `IncomeRateTable` in `product.py`. Alter, Geschlecht, Fixed/Rising, Single/Spouse und gegebenenfalls die jüngere Person steuern dort eine Produkt-Ratecard. Die Mortalitätstafel beeinflusst die Bewertung dieser Rate, nicht ihre vertragliche Höhe.

## 5. Anwendung in der monatlichen Projektion

### 5.1 Deterministische Decrements statt simulierter Todeszeitpunkte

Die Hauptprojektion arbeitet auf einem Monatsraster. Für jeden Marktpfad wird ein In-force-Gewicht (w) geführt, das bei 1 startet. Es gibt keinen Bernoulli-Zug, keinen zufälligen Todesmonat und keinen Mortalitäts-Seed.

Am Monatsende wird der erwartete Todesfallcashflow gebucht:

\[
CF^{death}_k=w_{k-1}\,q_{m,k}\,DB_k.
\]

Danach wird das Gewicht des überlebenden Bestands aktualisiert:

\[
w^{\text{after death}}_k
=w_{k-1}(1-q_{m,k}).
\]

Alle späteren Cashflows desselben Monats, insbesondere die nachschüssige Rentenzahlung, werden mit diesem bereits reduzierten Gewicht gebucht. Lapse wird anschließend separat angewandt:

\[
w_k=w^{\text{after death}}_k(1-l_k).
\]

Der Vertragszustand wird somit als Zustand des bedingt fortbestehenden Teilbestands weitergeführt. Ein konkreter Marktpfad wird nicht durch einen individuellen Tod beendet.

### 5.2 Mortalitätsrelevante Ereignisreihenfolge

Die aktive Expected-Decrement-Reihenfolge ist, soweit für Mortalität relevant:

1. Markt- und Indexentwicklung;
2. gegebenenfalls Anniversary-Crediting und reguläres Fee-Posting;
3. Todesdekrement und Death Benefit für das gerade abgelaufene Intervall unter
   dem am Intervallbeginn geltenden Coverage-State;
4. gegebenenfalls Income Election ausschließlich für den überlebenden Bestand;
5. nachschüssige Lifetime-Income-Zahlung nur an Überlebende;
6. Partial Withdrawals;
7. Lapse beziehungsweise Full Withdrawal.

Dies ist eine Rasterkonvention für erwartete Monatsdekremente. Sie ist von der
vertraglichen Same-Day-Reihenfolge zu unterscheiden: Ein Tod nach wirksamer
Election gehört im Monatsraster bereits zum folgenden Intervall.

Damit ist die normale Todesfallleistung das aktuelle Account Value nach dem
modellierten Gebührenabzug, aber vor der nachschüssigen Monatszahlung. Auf Tod
wird keine MVA abgezogen. Ein über das Account Value hinausgehender separater
Todesfallschutz wird nicht modelliert. Age Pension+ und ein CAS Death Cap
gehören nicht zum generischen Produkt; entsprechende Felder im Kern sind nur
Legacy-Kompatibilität.

### 5.3 Bedeutung der Ergebnisfelder

Die Interpretation der Projektionsausgaben ist wichtig:

- `cashflows` sind bereits mit Mortality- und In-force-Wahrscheinlichkeiten gewichtete Erwartungswertcashflows;
- `inforce` enthält sowohl Mortalität als auch Lapse und kann wegen dynamischem Verhalten marktpfadabhängig sein;
- `survival_primary` enthält nur die deterministische Mortalität der primären versicherten Person;
- `iv_paths`, `income_paths` und `phase_paths` beschreiben den Zustand des bedingt fortbestehenden Vertrags und keine Population mit realisierten Todesfällen.

Folglich sind Quantile von Account Value oder Income über Marktpfade **keine vollständigen individuellen Kunden-Outcome-Verteilungen inklusive zufälligem Todesalter**. Dafür wäre eine separate Life-by-Life-Simulation oder eine explizite Mischung nach Todeszeitpunkten erforderlich.

### 5.4 Single Life und Spouse-Option

| Vertragszustand | Maßgebendes Todesdekrement |
| --- | --- |
| Single Life, Growth oder Income | Primary-Life-$q_m$ |
| Spouse vorgesehen, noch in Growth | Primary-Life-$q_m$ |
| Spouse + `continue_income`, nach Income Election | bedingtes Last-Survivor-$q_m$ |
| Spouse + `lump_sum`, auch nach Income Election | Primary-Life-$q_m$ |

Der monatliche Kernprojektor bewertet einen `continue_income`-Pfad bedingt
darauf, dass beide Personen am tatsächlichen Income-Election-Termin leben. Er
setzt dazu die Survival-Zustände bei `elect_income()` auf 1. Danach berechnet
die Engine:

\[
q^{LS}_{m,k}
=1-\frac{S^{LS}_{k+1}}{S^{LS}_k}.
\]

Damit wird auf beide Personen als am Income-Election-Termin lebend
konditioniert. Der Death Benefit wird in der Income Phase erst bei Extinktion
des Last-Survivor-Status fällig. Beim `lump_sum`-Pfad löst dagegen der Tod der
primären versicherten Person die Leistung aus; die zweite Person verändert das
Mortalitätsdekrement nicht.

Der Portfolio-Wrapper ergänzt für New-Business-Modellpunkte den im Kernprojektor
nicht geführten Spouse-Status vor Election. Beim expliziten, deterministischen
`income_start_year` berechnet er die Spouse-Survival-Wahrscheinlichkeit bis zum
Election Anniversary. Er mischt den bedingt gemeinsamen Joint-Life-Wert mit
einem Single-Life-Fallback für den Anteil, bei dem der Spouse vor Election
verstorben ist. Weil beide Teilprojektionen bis zum gemeinsamen Election-Termin
identisch sind, werden die Vor-Election-Cashflows dabei nicht doppelt gezählt.
Scheidung, Entfernung der zweiten Person, Common Shock und sonstige rechtliche
Eligibility-Änderungen bleiben außerhalb des Modells.

Der Kernprojektor weist `spouse=True` mit dynamischem oder Hazard-basiertem
Income Take-up ausdrücklich ab. Ohne vor Election fortgeschriebenen
Couple-/Eligibility-State könnte ein vor dem pfadabhängigen Election-Termin
verstorbener Spouse sonst faktisch wieder als lebend konditioniert werden. Der
Portfolio-Runner verwendet deshalb den effektiven deterministischen
Election-Termin einschließlich des Age-100-Backstops. Ein direkter
Continue-Income-Joint-Life-Aufruf mit dynamischen Lapse-/Withdrawal-Reaktionen
wird ebenfalls abgewiesen; der Portfolio-Wrapper verwendet für den bedingt
gemeinsamen Zweig die state-unabhängigen statischen CSV-Basisraten.

### 5.5 Prüfpunkt am Election-Zeitschritt

Die aktive Projektion merkt sich den Phasenstatus am Beginn des gerade endenden
Monats. Am Anniversary werden zunächst Credit und das reguläre Fee-Posting
bestimmt. Anschließend wird das Expected-Death-Decrement des abgelaufenen
Intervalls noch unter dem Pre-Election-Coverage-State angewandt. Nur die
überlebenden Verträge führen danach `elect_income()` aus und starten die neue
DVA-/Crediting-Periode. Für das Intervall bis zum Election-Termin gilt deshalb
Primary-Life-Mortalität; Last-Survivor-Mortalität beginnt mit dem folgenden
Monatsintervall.

Diese Rasterkonvention ordnet einen Tod im abgelaufenen Monat unmittelbar vor
der Election ein. Ein Tod nach Election gehört zum Folgeintervall. Dadurch
werden Pre-Election-Mortalität und Post-Election-DVA nicht mehr hybrid
kombiniert.

Diese Boundary-Regel ist im Kernprojektor von der Portfolio-Mischung zu
unterscheiden. Der Kern führt vor Election weiterhin kein vollständiges
Vier-Zustände-Modell; der Portfolio-Pfad bildet für den bekannten Election-Termin
jedoch die entscheidende Eligibility-Aufteilung „Spouse lebt“ versus
„Single-Life-Fallback“ explizit ab.

### 5.6 Projektionshorizont und Closeout

`ProjectionConfig.max_age` ist standardmäßig 115. Ohne expliziten kürzeren Horizont reicht die Bewertung:

- bei Single Life beziehungsweise `lump_sum` bis Alter 115 der primären Person;
- bei `continue_income` bis Alter 115 desjenigen Lebens mit der längeren Restlaufzeit.

Beim normalen, bis zum terminalen Alter laufenden Horizont schließt das harte
Todesdekrement den Bestand über den regulären Death-Eventflow; der technische
Residualbetrag ist null. Bei einem explizit kurzen Horizont werden zunächst
offene Gebühren abgerechnet und das verbleibende post-fee Account Value separat
in `terminal_closeout` gebucht. `death_benefits` enthält damit ausschließlich
modellierte Todesfallleistungen.

## 6. Wirkung in Pricing, Verhalten und Profitabilität

### 6.1 Risikoneutrale Bewertung

`value_contract()` erzeugt risikoneutrale Marktszenarien und reicht die `MortalityTable` unverändert in die Projektion. Marktpfadweise Account Values und Cashflowhöhen werden mit den deterministischen Mortalitätsgewichten kombiniert und anschließend mit den pfadweisen Geldmarktkonten diskontiert.

Der normale Death Benefit entspricht dem Account Value und ist damit grundsätzlich aus dem Kundenkonto finanziert. Mortalität beeinflusst den Versichererwert vor allem über die Dauer von:

- Lifetime-Income-Premium und anderen Gebühren;
- Garantieclaims nach Erschöpfung des Account Value;
- laufenden Expenses;
- Crediting-, MVA- und APS-Retained-Cashflows;
- dynamischem Verhalten.

### 6.2 Indirekter Einfluss auf Verhalten

Der Mortalitäts-Annuitätenfaktor fließt in die Moneyness-Signale für:

- dynamische Withdrawal Utilisation;
- dynamische Income-Phase-Lapses.

Für Single Life, den Single-Life-Fallback und die Lump-Sum-Spouse-Ausprägung
wirkt der monatliche Mortalitäts-Annuitätenfaktor weiterhin in den dynamischen
Signalen. Im bedingt gemeinsamen `continue_income`-Zweig werden dagegen die aus
den CSVs geladenen statischen Basisraten für Income-Lapse und Excess Withdrawal
verwendet. Solange keine getrennten `p11`-, `p10`- und `p01`-AV-/Fee-Kohorten
geführt werden, wird damit bewusst keine nichtlineare Behaviour-Funktion auf
einen erwarteten Survivor-State angewandt. Der Single-Life-Fallback bleibt
dynamisch.

### 6.3 Real-World-Projektion

`analyse_profitability()` verwendet für die Real-World-Marktszenarien exakt dieselbe `MortalityTable` wie die risikoneutrale Bewertung. Es gibt:

- kein separates Mortalitätsmaß;
- keinen Marktpreis des Langlebigkeitsrisikos;
- keine unterschiedliche P- und Q-Mortalität;
- keine Abhängigkeit zwischen Mortalität und Marktmodellschocks.

Die Real-World-Abweichung liegt damit im Marktmodell, nicht in der Mortalitätsdynamik.

## 7. Separate Mortalitätslogik im LSMC-Modul

Die optionale Optimal-Behaviour-Bewertung in `lsmc.py` ist nicht einfach ein anderer Aufrufer des monatlichen Mortalitätsmotors. Sie enthält eine eigene annualisierte Approximation:

- jährliche Primary-$q$ statt monatlicher Decrements;
- jährliche, nachschüssige Income-Zahlung;
- bei `continue_income` eine unbedingte Last-Survivor-Kurve ab Issue;
- keine Konditionierung der Joint-Life-Kurve am pfadindividuellen Income-Election-Termin;
- Default-Horizont höchstens bis Alter 105 beziehungsweise 40 Jahre;
- approximativer Account-aware Tail Value am Horizont;
- kein Age Pension+ und keine Off-Anniversary-Starts.

Auch das LSMC führt Survival als Erwartungswertgewicht und simuliert keine individuellen Todeszeitpunkte. Todesfälle erhalten das Investment Value vor der Jahreszahlung; nur Überlebende erhalten Income und Continuation Value.

Die Joint-Life-Konditionierung und der Horizont sind damit bewusst nicht vollständig konsistent mit dem monatlichen Kernmotor. Das Modul ist außerdem nicht automatisch in Pricing, Kapital oder Profitabilität integriert.

## 8. Referenzcode außerhalb der aktiven Engine

Im Ordner `Code based on Papers` existieren weitere Mortalitätsansätze:

- `more_code.py` enthält ein einfaches jährliches Demo-Gompertz-$q$, extern übergebbare $q$-Vektoren und erwartungswertgewichtete Death Benefits;
- `gmwb_models.py` enthält ein Dahl-Møller-/Gompertz-Modul für stochastische Mortalität;
- `Shevchenko_lou2016.py` ist ausdrücklich ohne Mortalität und Death Benefit implementiert.

Keines dieser Module wird von `agile_engine` importiert. Insbesondere ist das vorhandene Dahl-Møller-Modell **kein Bestandteil der laufenden Bewertung**. Die Dateien dienen laut `METHODOLOGY.md` als Methoden- und Implementierungsreferenzen.

## 9. Vorhandene Validierung

Der vorhandene Testcode deckt unter anderem folgende Mortalitätsaspekte ab:

| Testdatei | Gedeckter Aspekt |
| --- | --- |
| [`test_projection_pricing.py`](../AGILE_Modelling_Engine/tests/test_projection_pricing.py) | fallende Survival-Kurve, plausible grobe Lebenserwartung, höhere LE unter Longevity-Stress |
| [`test_spouse_conditioning.py`](../AGILE_Modelling_Engine/tests/test_spouse_conditioning.py) | Joint-Life-Reset am Income-Election-Step und Primary-Decrement beim Lump-Sum-Pfad |
| [`test_review_fixes.py`](../AGILE_Modelling_Engine/tests/test_review_fixes.py) | First-Year-Cat-Stress und begrenzter Survival-Effekt |
| [`test_independent_audit_fixes.py`](../AGILE_Modelling_Engine/tests/test_independent_audit_fixes.py) | Cat-Stress nach Policendauer, Income nur für Monatsend-Survivors, Pflichtabdeckung externer Tafeln |
| [`test_audit_fixes.py`](../AGILE_Modelling_Engine/tests/test_audit_fixes.py) | Joint-Life-Horizont, Annuitätenfaktor und defensive Unveränderlichkeit der $q_x$-Arrays |
| [`test_capital_profit_lsmc.py`](../AGILE_Modelling_Engine/tests/test_capital_profit_lsmc.py) | Stressvorzeichen und Dominanz der Longevity-Exposure im Beispielbestand |

Nicht erkennbar sind dagegen:

- eine Golden-Source-Reconciliation gegen eine offizielle ALT- oder unternehmenseigene Tafel;
- ein Test eines produktiven Mortalitätsloaders;
- eine systematische Reconciliation der monatlichen und jährlichen Survival-Diskretisierung;
- eine Life-by-Life-Outcome-Validierung;
- ein Test, der die fachliche Boundary zwischen Primary- und Joint-Decrement rund um den Election-Zeitpunkt alternativ zur aktuellen Konvention prüft;
- Boundary-Tests für Improvement-Taper und terminale Alter 90, 110, 114.x und 115;
- Positivtests für externe Tafeln, große Alterslücken und die Research-Extrapolation;
- eine Prüfung des Joint-Life-Verhaltenssignals nach dem ersten Todesfall.

## 10. Wesentliche Modellgrenzen und Risiken

### Hohe Priorität für produktive Nutzung

1. **Keine freigegebene Mortalitätsbasis:** Der aktive Default ist synthetisch und illustrativ. Es fehlt eine versionierte, fachlich freigegebene australische Pricing-/Best-Estimate-Tafel.
2. **Kein Datenloader:** `from_qx()` ist nur eine Array-Factory. Quelle, Basis-ID, Effective Date, Units, Freigabestatus und Dateihash einer produktiven Mortalitätstafel werden nicht über einen eigenen Loader verwaltet.
3. **Begrenzter Modelpoint-Loader:** Die vorhandenen demografischen
   Portfoliofelder und ein optionaler `exposure_count` werden validiert auf den
   Bewertungszustand abgebildet. Unterstützt ist derzeit jedoch nur der
   gelieferte Duration-0-New-Business-Zustand. Fehlt `exposure_count`, sind nur
   normalisierte Werte beziehungsweise eine explizite Gesamtvertragszahl
   verfügbar.
4. **Nur New-Business-State:** Die Engine startet Modelpoints bei Issue. Policendauer, aktueller Survival-/Spouse-Status und andere In-force-Zustände sind nicht als operative Bewertungszustände implementiert.
5. **Keine stochastische/systematische Langlebigkeit:** Trend-, Level- und Prozessunsicherheit werden nicht als Zufallsfaktoren simuliert; Kapitalstresse ersetzen kein kalibriertes systematisches Longevity-Modell.

### Fachliche Vereinfachungen

6. **Begrenzte Risikoklassifikation:** Mortalität hängt nur von Alter, binärem Geschlecht, Kalenderzeit und globalen Stressparametern ab. Raucherstatus, Gesundheit, Underwriting/Selection, sozioökonomische Merkmale, Geburtsjahrkohortenparameter und Cause of Death fehlen.
7. **Einheitliches Improvement-Modell:** Männer und Frauen verwenden dieselbe Improvement Rate und denselben Taper; es gibt keine kalenderjahr- oder kohortenspezifische Improvement-Matrix.
8. **Unabhängige Joint Lives:** Couple- und Common-Shock-Effekte werden ausgeschlossen.
9. **Joint-Life-Proxy vor Election:** Der Portfolio-Pfad gewichtet
   Spouse-Survival bis zum deterministischen Election Anniversary und einen
   Single-Life-Fallback. Ein allgemeines zeitabhängiges Vier-Zustände-Modell für
   dynamische Election, Scheidung, Removal oder rechtliche Eligibility besteht
   weiterhin nicht.
10. **Identische P-/Q-Basis:** Pricing und Real-World-Projektion unterscheiden die Mortalität nicht und enthalten keinen Longevity Risk Premium.
11. **Stressinteraktionen:** Bei dynamischem Verhalten oder fehlender APS-Life-Expectancy verändern Mortalitätsstresse zusätzlich Verhalten beziehungsweise Vertragsparameter-Fallbacks.

### Numerische und Reporting-Grenzen

12. **LSMC-Zeitdiskretisierung:** Der aktive Monatsmotor, Lebenserwartung und
    Behaviour-Annuitätenfaktor verwenden dieselbe Monatsmortalität; das
    archivierte jährliche LSMC bleibt davon abweichend.
13. **Policy-Year-Constant-Force:** Das jährlich definierte $q_x$ wird je Policy
    Year konstant auf Monate umgerechnet. Innerhalb des Jahres werden Alter
    und Improvement daher nicht kontinuierlich neu interpoliert.
14. **Election-Boundary:** Das Intervall bis zur Election verwendet
    Primary-Life-Mortalität und erst das Folgeintervall Joint Mortality. Im
    Portfolio wird die Spouse-Eligibility am expliziten Election-Termin durch
    die Joint-/Single-Life-Mischung ergänzt; andere Same-Day- oder
    Eligibility-Konventionen sind nicht abgebildet.
15. **Separater Residual-Closeout:** Bei kurzen Horizonten enthält
    `terminal_closeout` einen technischen post-fee Closeout für Überlebende;
    dieser ist kein tatsächlicher Tod.
16. **Keine realisierten Death Outcomes:** Marktpfadquantile der Zustände sind keine individuellen Policyholder-Verteilungen inklusive Todesalter.
17. **Terminologie Lebenserwartung:** Implementiert und im Modulheader nun
    konsistent benannt ist eine trapezoidale Approximation der vollständigen
    Lebenserwartung.
18. **LSMC-Abweichungen:** Joint-Life-Konditionierung, Raster und Default-Horizont weichen vom monatlichen Kernmotor ab.
19. **Hartes Terminalalter:** Das Intervall, dessen Ende Alter 115 erstmals
    erreicht, erhält unabhängig vom Tabellen-$q$ ein Todesdekrement von eins.
20. **Externe Tabellen nur formal geprüft:** Sehr große Alterslücken können linear überbrückt werden; Source- und Plausibilitätsprüfungen fehlen.
21. **Keine dynamischen Joint-Life-Zustandskohorten:** Im bedingt gemeinsamen
    Continue-Income-Zweig werden deshalb state-unabhängige statische
    Behaviour-Basisraten verwendet. Individuelle First-Death-Outcomes und
    abhängige Couple-Mortalität werden nicht simuliert.

## 11. Empfohlener Einsatz der Mortalität in der Portfolio-Bepreisung

### 11.1 Grundprinzip

Mortalität sollte nicht als ein einziger pauschaler Faktor auf den bereits aggregierten Portfoliowert angewandt werden. Der sachgerechte Ablauf ist:

1. für jeden Modelpoint eine passende Best-Estimate-Mortalität bestimmen;
2. alle lebens-, first-death- und last-death-abhängigen Cashflows dieses Modelpoints damit projizieren;
3. den vollständigen Vertrag je Modelpoint bewerten;
4. erst danach die Modelpoint-Werte mit den zugehörigen Vertrags- beziehungsweise Exposure-Gewichten aggregieren.

In kompakter Form:

\[
PV_{\text{Portfolio}}
=\sum_i N_i\,PV_i,
\]

wobei $PV_i$ der Wert eines durch Modelpoint $i$ repräsentierten Vertrags und $N_i$ dessen Vertragsanzahl beziehungsweise Exposure ist.

Für erwartete Barwerte und Fair-Fee-Berechnungen ist die bereits in der Engine angelegte Wahrscheinlichkeitsgewichtung grundsätzlich geeigneter als zufällig gezogene individuelle Todeszeitpunkte. Sie vermeidet zusätzliche Monte-Carlo-Varianz und liefert bei linear aggregierbaren Cashflows unmittelbar den Erwartungswert.

### 11.2 Best-Estimate-Mortalitätsbasis

Für jeden Modelpoint und Projektionszeitpunkt sollte eine aktuelle bedingte Sterbewahrscheinlichkeit der Form

\[
q^{BE}_{i,t}
=q^{\text{Basis}}_{x,s}
\times I_{x,t}
\times F^{\text{Portfolio}}_i
\times F^{\text{Selection}}_{i,t}
\]

verwendet werden. Dabei bezeichnen:

- $q^{\text{Basis}}_{x,s}$ die Basistafel nach erreichtem Alter und Geschlecht beziehungsweise Rating-Klasse;
- $I_{x,t}$ die kohorten- und kalenderzeitbezogene Mortalitätsverbesserung;
- $F^{\text{Portfolio}}_i$ eine durch eigene Erfahrung gestützte Portfolioanpassung;
- $F^{\text{Selection}}_{i,t}$ gegebenenfalls Underwriting-, Selection- oder Bestandsdauereffekte.

Die offiziellen Australian Life Tables können als Ausgangspunkt oder Credibility-Anker dienen, sind aber Bevölkerungstafeln und nicht automatisch eine passende Versicherten- oder Produkttafel. AASB 17 verlangt, nationale und interne Mortalitätsinformationen nach ihrer Aussagekraft zu gewichten und nicht ausschließlich nationale Statistiken zu verwenden. Relevante fachliche Referenzen sind [AASB 17, insbesondere Abschnitte 33 und B49–B58](https://standards.aasb.gov.au/aasb-17-dec-2022), die [Australian Life Tables 2020–22](https://aga.gov.au/node/271) und [APRA LPS 340](https://www.apra.gov.au/standards/lps-340).

Eine produktive Basis sollte mindestens folgende Metadaten tragen:

- `mortality_basis_id` und Version;
- Quelle und Effective Date;
- Basis-$q_x$ oder Basisintensitäten;
- Improvement-Ansatz;
- abgedeckte Rating-Klassen;
- Experience- und Credibility-Anpassungen;
- Freigabestatus und verantwortliche aktuarielle Funktion;
- Dateihash beziehungsweise reproduzierbare Provenienz.

Best Estimate, Experience, Stress und gegebenenfalls eine kommerzielle Pricing-Basis sollten als getrennte, benannte Layer geführt werden. Vorsicht, Gewinnmarge und Kapitalbedarf sollten nicht unkenntlich in die Best-Estimate-$q_x$ eingerechnet und später ein zweites Mal belastet werden.

### 11.3 Modelpoint-Segmentierung

Ein Modelpoint darf nur Verträge zusammenfassen, deren Mortalität und Leistungsmechanik hinreichend homogen sind. Materielle Segmentierungsmerkmale sind insbesondere:

- erreichtes Alter beziehungsweise Geburtsjahr;
- Geschlecht oder andere zulässige Rating-Klasse;
- Primary-/Spouse-Alter und aktueller Life Status;
- New Business versus In-force;
- Policendauer und gegebenenfalls Selection-Dauer;
- aktueller Vertragszustand, etwa Growth oder Income;
- Income- und Death-Benefit-Ausprägung;
- Underwriting-, Vertriebs- oder Produktkohorte;
- relevante Vertrags- und Ratecard-Vintage.

Zu grobe Modelpoints können trotz korrekter Durchschnittsmortalität zu falschen Werten führen, weil Garantien, Gebühren und Death Benefits nichtlinear von Alter, Vertragszustand und Account Value abhängen.

### 11.4 Bedingter Start am Bewertungsstichtag

Für einen bestehenden In-force-Vertrag ist bereits beobachtet, dass die versicherte Person am Bewertungsstichtag lebt. Deshalb beginnt jeder In-force-Modelpoint am Stichtag bedingt lebend:

\[
S_{i,0}=1
\]

beziehungsweise mit $N_i$ lebenden Verträgen. Die historische Survival-Wahrscheinlichkeit seit Issue darf nicht nochmals auf den aktuell beobachteten Bestand angewandt werden.

Ab dem Stichtag sind das heutige erreichte Alter, die heutige Policendauer und der heutige Vertrags- und Couple-Status zu verwenden. `commencement_year` bleibt für Kohorte, Improvements und vertragliche Vintage relevant, ist aber kein Grund, den bereits beobachteten Bestand erneut um frühere Todesfälle zu reduzieren.

Für echte New-Business-Modelpoints am Issue Date startet die Projektion dagegen regulär mit dem gesamten Neugeschäftsexposure. Die derzeit vorhandenen 48 Modelpoints sind laut Begleitdokumentation New-Business-Modelpoints; eine spätere Erweiterung um In-force-Bestände benötigt zusätzliche aktuelle Zustandsfelder.

### 11.5 Expected-Decrement-Projektion für Single Life

Sei $I_{i,t-1}$ das In-force-Gewicht vor dem Todesdekrement und $q_{i,t}$ die bedingte Monatssterblichkeit. Dann gilt:

\[
Deaths_{i,t}=I_{i,t-1}q_{i,t},
\]

\[
Survivors_{i,t}=I_{i,t-1}(1-q_{i,t}).
\]

Die Cashflows werden am vertraglich richtigen Ereigniszeitpunkt gewichtet, zum Beispiel:

\[
CF^{Death}_{i,t}=Deaths_{i,t}\,DB_{i,t},
\]

\[
CF^{Income}_{i,t}=Survivors_{i,t}\,Income_{i,t}.
\]

Lapse und andere Decrements werden anschließend entsprechend der dokumentierten Ereignisreihenfolge angewandt. Bei der gegenwärtigen Konvention wäre beispielsweise:

\[
I_{i,t}=Survivors_{i,t}(1-l_{i,t}).
\]

Für eine produktive Umsetzung sollte die Monatsmortalität aus einer konsistenten Hazard- oder Survival-Interpolation abgeleitet werden. Das Produkt von zwölf Monats-Survival-Faktoren sollte mit der zugrunde liegenden Jahrestafel und dem verwendeten Improvement-Verlauf reconciliert werden.

### 11.6 Joint-Life-State-Modell

Für Joint-Life-Verträge ist eine reine Last-Survivor-Kurve nur dann ausreichend, wenn alle künftigen Cashflows ausschließlich davon abhängen, ob mindestens eine Person lebt. Sobald Benefit, Wahlrecht, Verhalten oder Eigentümerschaft davon abhängen, welche Person verstorben ist, sollte ein Vier-Zustände-Modell verwendet werden:

| Zustand | Bedeutung |
| --- | --- |
| $p_{11}$ | beide Personen leben |
| $p_{10}$ | nur die primäre Person lebt |
| $p_{01}$ | nur die zweite Person lebt |
| $p_{00}$ | beide Personen sind verstorben |

Unter unabhängigen Lebensdauern ergeben sich beispielsweise:

\[
p'_{11}=p_{11}(1-q_1)(1-q_2),
\]

\[
p'_{10}=p_{10}(1-q_1)+p_{11}(1-q_1)q_2,
\]

\[
p'_{01}=p_{01}(1-q_2)+p_{11}q_1(1-q_2).
\]

Das Produktmodell legt anschließend zustandsabhängig fest:

- ob Income weiterläuft;
- ob Primary Death, First Death oder Last Death eine Leistung auslöst;
- welche Person ein verbleibendes Wahlrecht ausüben kann;
- welcher Annuitätenfaktor für dynamisches Verhalten maßgebend ist;
- wann der Vertrag beendet wird.

Der aktuelle Portfolio-Pfad implementiert für die gelieferten
New-Business-Modellpunkte eine reduzierte Form dieses Prinzips: Bis zum
expliziten Election Anniversary wird Spouse-Survival separat bestimmt;
anschließend werden der bedingt gemeinsame Joint-Life-Pfad und der
Single-Life-Fallback gewichtet. Diese Mischung bildet die Eligibility am festen
Election-Termin sowie lineare Expected-Death-Cashflows konsistent ab.

Nach Election werden weiterhin keine getrennten AV-, Fee-, Lapse- und
Withdrawal-Zustände für $p_{11}$, $p_{10}$ und $p_{01}$ geführt. Der aktive
Portfolio-Default wendet deshalb auf den bedingt gemeinsamen Joint-Life-Zweig
nur die state-unabhängigen statischen CSV-Basisraten an; der Single-Life-
Fallback bleibt dynamisch. Dadurch wird die frühere Jensen-/Selektions-
Inkonsistenz vermieden, ohne ein nicht vorhandenes vollständiges
Vier-Zustände-Modell zu behaupten. Ein künftiger vollständiger Ausbau muss die
Zustandskohorten einschließlich Account Value und Fee-Subledger separat
fortschreiben.

Damit muss der Spouse im Portfolio nicht künstlich wieder als lebend angenommen
werden. Für einen künftigen In-force-Modelpoint ist stattdessen der am Stichtag
bekannte Couple-Status zu laden. Abhängigkeit zwischen den Lebensdauern kann
später durch gemeinsame Mortalitätsfaktoren oder eine geeignete
Couple-Mortality-Annahme ergänzt werden.

### 11.7 Zusammenspiel von Marktmaß und Mortalität

Für die vereinfachte marktkonsistente Bewertung ist folgende Trennung sachgerecht:

\[
V_i
=E^{Q,\text{Markt}}\left[
\sum_t D_t\,
E^{BE,\text{Mort}}\left(CF_{i,t}\mid\text{Marktpfad}\right)
\right].
\]

Damit gilt:

- Zins- und Aktienrisiken werden unter dem risikoneutralen Maß bewertet;
- Mortalität wird als aktuelle Best-Estimate-Nichtmarktannahme in die Cashflows eingebaut;
- Mortalität wird nicht allein deshalb risikoneutralisiert, weil das Marktmodell unter $Q$ läuft;
- ein Marktpreis des Langlebigkeitsrisikos wird nur angesetzt, wenn dafür eine explizite, begründete Basis existiert;
- Risiko-, Kapital- und Gewinnmargen werden separat ausgewiesen.

Für Real-World-Profitabilitätsprojektionen kann dieselbe Best-Estimate-Mortalität verwendet werden, während nur das Marktmodell unter dem Real-World-Maß läuft. Eine davon abweichende Experience-Basis ist möglich, sollte aber bewusst benannt, kalibriert und in der Ergebnisüberleitung erklärt werden.

### 11.8 Portfolioaggregation und vorhandene Gewichte

Der Wert eines Modelpoints ist zuerst pro repräsentiertem Vertrag zu bestimmen. Anschließend erfolgt die Aggregation mit der tatsächlichen Vertragszahl:

\[
PV_{\text{Portfolio}}=\sum_i N_iPV_i.
\]

Für die vorhandene Modelpoint-Datei ist die dokumentierte Semantik zu beachten:

- `contract_weight` ist das Aggregationsgewicht für Vertragsbarwerte;
- `premium_volume_weight` ist eine Exposure- und Kontrollgröße und darf nicht zusätzlich auf denselben Barwert angewandt werden;
- summieren sich die `contract_weight` auf 1, entsteht zunächst ein durchschnittlicher Vertragswert;
- für einen absoluten Portfoliowert ist dieser Durchschnitt mit der gesamten Vertragsanzahl zu skalieren;
- alternativ sollte künftig direkt ein Feld wie `exposure_count` oder `number_of_contracts` je Modelpoint geliefert werden.

Bei normierten Gewichten gilt:

\[
\overline{PV}=\sum_i w_i^{contract}PV_i,
\qquad
PV_{\text{Portfolio}}=N_{\text{total}}\overline{PV}.
\]

Alle Modelpoints sollten dieselben Marktpfade verwenden. Das erhält gemeinsame Marktbewegungen, reduziert Rauschen bei Modelpoint-Vergleichen und macht Fair-Fee- beziehungsweise Sensitivitätsrechnungen stabiler. Für nichtlineare Portfolio-Risikomaße sind zunächst die pfadweisen Modelpoint-Cashflows zu Portfoliopfaden zu summieren und erst danach das Risikomaß zu berechnen.

### 11.9 Fair Fee oder Portfolio-Preis

Bei einer einheitlichen Produktgebühr $f$ sollte nicht für jeden Modelpoint eine separate Fair Fee gelöst und anschließend gemittelt werden. Stattdessen wird $f$ direkt so bestimmt, dass das aggregierte Portfolioziel erfüllt ist:

\[
0=\sum_i N_i\left[
PV_Q(Fees_i(f))
-PV_Q(GuaranteeClaims_i(f))
-PV_Q(Expenses_i)
-PV_Q(HedgeCosts_i)
\right]
-TargetLoad.
\]

`TargetLoad` kann je nach Pricing-Ziel explizit Reinsurance, Risk Adjustment, Cost of Capital, Acquisition Strain oder eine Zielrendite enthalten. Welche Komponenten einbezogen werden, muss vor der Fair-Fee-Suche definiert werden. Mortality, Lapse und Gebühren wirken teilweise gegenseitig aufeinander; deshalb ist stets der vollständige Vertrag unter der jeweiligen Gebühr neu zu projizieren.

Bei einer alter-, geschlechts- oder optionsabhängigen Ratecard ist entsprechend ein gemeinsames Portfolioziel unter den vorgegebenen Ratecard-Restriktionen zu lösen, statt unabhängige Modelpoint-Raten ohne Portfoliokonsistenz zu setzen.

### 11.10 Wann individuelle Todeszeitpunkte simuliert werden sollten

Expected Decrements reichen normalerweise für:

- erwartete Vertrags- und Portfoliobarwerte;
- Fair-Fee- und Pricing-Suchen;
- erwartete Profit Signatures;
- lineare BEL- und Cashflow-Aggregation.

Eine Life-Event-Simulation oder stochastische Mortalitätsszenarien werden dagegen benötigt für:

- individuelle Kundenoutcome- und Todesalterverteilungen;
- Reinsurance mit Retention, Limits oder Aggregatdeckungen;
- Random Mortality Risk kleiner oder konzentrierter Portfolios;
- systematisches Longevity Risk;
- nichtlineare Portfolio- und Kapitalmetriken;
- komplexe Leistungen oder Verhaltensregeln nach dem ersten Todesfall.

Systematische Mortalitätsszenarien müssen als gemeinsamer Faktor auf alle betroffenen Modelpoints wirken. Unabhängige Death Draws je Modelpoint würden systematisches Risiko fälschlich wegdiversifizieren.

### 11.11 Empfohlene Zielarchitektur und Umsetzung im Repository

Für die schrittweise Generifizierung sollte die Mortalität in folgende Komponenten zerlegt werden:

1. **Demografischer Modelpoint**
   
   Eine generische Struktur für eine oder mehrere versicherte Personen mit Alter beziehungsweise Geburtsdatum, Rating-Klasse, Policendauer, Coverage-Rolle, aktuellem Life Status und Exposure Count.

2. **Versionierte Mortalitätsbasis**
   
   Ein eigener Loader außerhalb von `input_market_data`, weil Mortalität eine Versicherungs- und keine Marktdatenannahme ist. Er liefert Basis, Improvements, Metadaten und Provenienz.

3. **Life-State-Engine**
   
   Eine produktunabhängige Komponente berechnet Single- und Joint-Life-State-Übergänge. Sie kennt noch keine produktspezifischen Benefit-Beträge.

4. **Produktabhängige Benefit-Regeln**
   
   Das Produktmodell ordnet den Life States Death Benefit, Income Continuation, Wahlrechte und Vertragsbeendigung zu.

5. **Portfolio-Loader und Aggregator**
   
   Ein Loader überführt die vorhandene Modelpoint-Datei validiert in Engine-Objekte. Ein Portfolio-Projektor verwendet gemeinsame Marktpfade, projiziert die Modelpoints in Batches und aggregiert mit Vertragsanzahlen beziehungsweise `contract_weight`.

6. **Explizite Bewertungsbasis**
   
   Jeder Lauf benennt Best-Estimate-, Experience- und gegebenenfalls weitere Risikobasen sowie den Pricing-Zweck. Ergebnisse und Manifeste enthalten die Basis-IDs und Hashes.

7. **Zwei Projektionsmodi**
   
   `expected_decrement` dient stabilen Pricing-, Reservierungs- und Portfolio-Barwerten; `life_event_simulation` dient individuellen Outcomes und nichtlinearen Risikofragen.

Für den weiteren Ausbau ist folgende Reihenfolge sinnvoll; Modelpoint-Loader und
Portfolioaggregation sind für den derzeitigen New-Business-Bestand bereits
umgesetzt:

1. produktiven Mortalitätsloader und Basis-Metadaten einführen;
2. den optionalen Exposure Count produktiv befüllen und den Modelpoint-Loader
   um vollständige In-force-Felder ergänzen;
3. vorhandene Portfolioaggregation um Batching und Konvergenzdiagnostik erweitern;
4. In-force-Startzustände unterstützen;
5. Joint-Life-State-Modell einführen;
6. Expected-Decrement- und Life-Event-Modus trennen;
7. A/E-Monitoring, Reconciliation- und Portfolio-Konvergenztests ergänzen.

Die zentrale Zielregel lautet:

> Mortalität je Modelpoint bestimmen, sämtliche zustandsabhängigen Cashflows damit gewichten, den vollständigen Vertrag je Modelpoint bewerten und erst anschließend mit dem tatsächlichen Vertragsbestand aggregieren.

## 12. Gesamtbeurteilung

Die Mortalitätslogik der aktiven Engine ist für einen Research-Prototypen nachvollziehbar strukturiert: Die Formeln sind zentralisiert, Inputs werden defensiv behandelt, Improvements sind kalenderzeitlich korrekt am Commencement Year verankert, Death-/Income-Timing ist explizit und wesentliche Stresspfade sind vorhanden.

Die größte Einschränkung liegt nicht in der algebraischen Umsetzung, sondern in der **Basis und Interpretation**: Aktuell wird eine illustrative synthetische Kurve ohne operativen Datenloader verwendet; Mortalität bleibt deterministisch und für P und Q identisch; Joint-Life- und Outcome-Logik enthalten bewusst vereinfachte Zustände. Ergebnisse sind deshalb als Research-Projektionen auf Proxy-Mortalitätsbasis zu kennzeichnen und nicht als vollständig kalibrierte aktuarielle Prognose.
