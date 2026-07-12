# Unabhängige Code-, Formel-, Reproduzierbarkeits- und Zahlenprüfung

Prüfstand: 11. Juli 2026  
Geprüfter Engine-Bestand: `AGILE_Modelling_Engine`, Version 1.3.0  
Aktueller, unabhängig nachgerechneter Engine-Source-Hash:  
`503b509175810f3e7a9105c372d7ae6e6741d3cb4178461382305dcbaa360e46`

## 1. Kurzurteil

Die im Fachpaper aus dem instrumentierten 1.3.0-Lauf berichteten Basis-,
Sensitivitäts-, Kunden-, Produktdesign-, Timing-, Modell-, Seed- und
Versionszahlen stimmen mit den vorhandenen CSV-/JSON-Artefakten bis auf die
angegebene Rundung überein. Die zentralen Reconciliations (Gross VNB,
Non-unit BEL, Guarantee Value, Fair-LIP-Lücke, BSCR, Risk Margin, VNB nach
Risk Margin, PVFP, IRR und Marktwertidentität) lassen sich algebraisch aus den
Artefakten rekonstruieren. Es wurde keine falsche materielle Basiszahl im
Paper gefunden.

Die Standardausführung ist dagegen **nicht reproduzierbar**: Der unveränderte
Runner bricht mit `FrozenInstanceError` in `pricing.greeks()` ab. Der im Paper
beschriebene prozesslokale `dataclasses.replace`-Workaround ist semantisch
nachvollziehbar und reproduziert die publizierten Greeks sowie den gesamten
Analyse-Pack exakt. Seine Provenienz ist aber nicht im Manifest gebunden.
Zusätzlich bestehen methodische bzw. dokumentarische Punkte bei der
Heston--Hull--White-COS-Kopplung, dem LSMC-„Lower Bound“, dynamischem Verhalten,
der Expense-Sensitivität, Steuerannahmen und der ausgewiesenen numerischen
Präzision.

Der Engine-Quellcode und beide bestehenden Ergebnisverzeichnisse wurden nicht
verändert. Reproduktionsartefakte liegen ausschließlich unter
`_review_work/runner_unmodified_1_3/` und
`_review_work/runner_workaround_reproduction/`.

## 2. Befunde nach Schweregrad

### C-01 — HOCH: Öffentliche Greek-API und Standard-Runner brechen ab

**Fundstellen:** Fachpaper Z. 78--85 und 1451--1483;
`agile_engine/esg.py:185-186, 288-305`;
`agile_engine/pricing.py:251-265`;
`examples/run_insurer_analysis.py:1179-1187`.

`ScenarioSet` ist eine `frozen=True`-Dataclass; außerdem werden die enthaltenen
Arrays schreibgeschützt. `greeks()` erzeugt mit `copy.copy` nur eine flache
Kopie und versucht danach:

```python
scen.index_levels = {...}
```

Das scheitert bereits an der Dataclass-Zuweisung, bevor ein Equity-Greek
berechnet wird. Der unveränderte Standard-Runner mit den Originalpfadzahlen
brach unabhängig nach 18,5 Sekunden in Block 1/9 exakt so ab:

```text
dataclasses.FrozenInstanceError: cannot assign to field 'index_levels'
```

Die Tests enthalten weder einen Aufruf von `greeks()` noch einen
End-to-End-Aufruf von `run_insurer_analysis.py` (`rg` über `tests/`: kein
Treffer). Das Paper beschreibt Fehler und Ursache korrekt.

**Empfehlung:** In einer zukünftigen Engine-Version `levels` separat kopieren,
schocken und `dataclasses.replace(base_scen, index_levels=levels)` verwenden;
Regressionstest für die öffentliche API und einen Fast-End-to-End-Test des
Runners ergänzen. Für Version 1.3.0 ist der Pack ausdrücklich nur als
instrumentierter Lauf zu bezeichnen.

### C-02 — HOCH: Manifest/Source-Hash attestiert den tatsächlich ausgeführten Lauf nicht vollständig

**Fundstellen:** Fachpaper Z. 158--179 und 1465--1483;
`examples/run_insurer_analysis.py:241-246, 1361-1399`.

Der Manifest-Hash wird ausschließlich aus Dateiname und Bytes der Dateien
`agile_engine/*.py` gebildet. Nicht erfasst werden insbesondere:

- `examples/run_insurer_analysis.py`;
- der prozesslokale Greek-Patch;
- Kommandozeile bzw. Patch-ID;
- Tests, Paket-/Lock-Dateien und externe Eingabedateien;
- Hashes der erzeugten CSV-, JSON-, Markdown- und PNG-Artefakte.

Der aktuelle Source-Hash stimmt zwar bytegenau mit dem 1.3.0-Manifest überein,
aber gerade deshalb kann der Hash nicht unterscheiden, ob der abstürzende
Original-Runner oder der erfolgreiche Runtime-Patch verwendet wurde. Der
Paper-Hinweis in Z. 176--179 ist richtig, behebt die Attestierungslücke jedoch
nicht. `provenance.valuation` und `provenance.capital` binden Modellannahmen und
Szenarioinhalt, nicht aber Greek-Patch, Runner oder alle Analyseblöcke.

**Empfehlung:** Run-Bundle-Manifest mit Hash von Engine, Runner, Patch/Wrapper,
Kommandozeile, Umgebung, allen Inputartefakten und allen Outputs; Patch als
versioniertes Artefakt statt nur prozesslokal; getrennte Provenienz-IDs für
Pricing, Fair Fee, Greeks, Capital, P-Projektion, Sensitivitäten, Designs,
Outcomes, Modellvergleich und Seed-Studie.

### C-03 — HOCH: „Exakter“ Gaussian Add-on unter Heston--Hull--White ist im Basisfall keine positive Varianz

**Fundstellen:** `METHODOLOGY.md:63-74`;
`agile_engine/esg.py:373-403`;
`agile_engine/projection.py:896-911`;
`agile_engine/crediting.py:197-235`;
`tests/test_heston_cos.py:103-130`; Fachpaper Z. 583 und 1489--1491.

Die Methodology bezeichnet den Hull--White-Beitrag im Heston-COS-Pricer als
„independent Gaussian variance add-on (exact composition,
martingale-preserving)“. Tatsächlich liefert `rate_gauss_var()`

\[
w=\operatorname{Var}(\textstyle\int r\,dt)
  +2\operatorname{Cov}(\textstyle\int r\,dt,\int\sqrt v\,dW^S).
\]

Wegen der negativen Equity-Rate-Korrelation ist dieser Wert bereits mit den
Defaultparametern für AUS und ein Jahr negativ:

\[
\operatorname{Var}_r=2{,}0860\cdot10^{-5},\quad
2\operatorname{Cov}=-2{,}5346\cdot10^{-4},\quad
w=-2{,}3260\cdot10^{-4}.
\]

Eine negative Größe ist keine Varianz eines unabhängigen Gauß-Faktors. Der
COS-Code verwendet für die Wahl des Truncation-Intervalls zwar
`maximum(w, 0)`, setzt im Characteristic-Function-Faktor aber das rohe negative
`w` ein. Das entspricht einer inversen Gauß-Dämpfung, nicht der behaupteten
unabhängigen Faltung. Zudem ersetzt der Cross-Term die stochastische
`sqrt(v)`-Abhängigkeit durch eine Effective-Vol-Größe. Der Test
`test_gaussian_add_on_is_exact_in_the_bs_limit` validiert nur den Sonderfall
`xi -> 0`, `rho_sv = 0` und **positives** `w=0,01`; er beweist nicht die
Heston--Hull--White-Kopplung im Defaultfall. Der breite Identity-Gap-Test ist
eine Buchungskontrolle, kein unabhängiger Optionspreisbenchmark.

Der numerische Effekt auf das einjährige AUS-TP-Package ist im Default klein
(COS-Package 0,0336323 bei `w=0` versus 0,0337297 beim negativen Add-on), doch
die mathematische Behauptung „exakt“ ist nicht haltbar. Die
Heston--Hull--White-Zeile des Modellvergleichs ist deshalb als hybride
Näherung zu behandeln.

**Empfehlung:** „exact composition“ streichen; positive reine Ratevarianz und
Equity-Rate-Cross-Effekt nicht als dasselbe unabhängige `w` ausgeben; entweder
eine gültige gemeinsame Transform/CF-Kopplung oder einen gegen Joint-MC
validierten Näherungspricer implementieren. Bis dahin Ergebnis ausdrücklich
als Modellproxy kennzeichnen.

### C-04 — MITTEL: Effektiver Outcome-Seed widerspricht dem Manifestfeld

**Fundstellen:** Fachpaper Z. 1215--1218;
`examples/run_insurer_analysis.py:529-535, 1298-1307`;
Manifest JSON-Pfad `run_settings.outcome.seed`.

Das Manifest nennt für den Outcome-Block Seed 2026. Die tatsächlich ausgeführte
Funktion simuliert mit `settings.seed + 1`, also 2027. Das Paper nennt korrekt
2027, das Manifest allein ist jedoch irreführend und nicht hinreichend für eine
generische Reproduktion.

**Empfehlung:** `effective_simulation_seed: 2027` im Manifest speichern oder
dem Outcome-Settings-Objekt unmittelbar Seed 2027 übergeben.

### C-05 — MITTEL: Off-anniversary Income-Lapse verwendet IV statt Surrender Value

**Fundstellen:** Fachpaper Z. 676--693;
`agile_engine/behavior.py:54-62`;
`agile_engine/projection.py:538-559, 600-604, 839-859`.

Dokumentiert ist

\[
M_t=PV(\text{garantiertes Einkommen})/SV_t.
\]

`income_lapse_multiplier_at()` dividiert jedoch durch `iv`, nicht durch den
MVA-/APS-bereinigten Surrender Value. Bei einem Anniversary wird dies später
im gleichen Schritt durch die korrekte `pv_guar/sv`-Berechnung überschrieben;
bei einem off-anniversary Income Start bleibt der IV-basierte Multiplikator bis
zum nächsten verschobenen Anniversary aktiv. Mit Defaultkurve bei `t=1,5`
beträgt der MVA-Faktor rund 1,178 %, sodass bereits dort IV und SV abweichen.

**Empfehlung:** In der Helper-Funktion denselben Surrender-Value- und APS-
Lower-of-Pfad wie im Anniversary-Lapse-Block verwenden oder die Formel im
Paper auf den tatsächlich verwendeten IV-Proxy einschränken; Regressionstest
für fractional income start + MVA + dynamic lapse ergänzen.

### C-06 — MITTEL: Die Ungleichung `p_z(s) <= 1` ist keine allgemeine Identität

**Fundstellen:** `METHODOLOGY.md:53-61`; Fachpaper Z. 799--816;
`agile_engine/projection.py:525-536`.

Die Buchung

\[
CM_s=IV_s[1-p_z(s)]
\]

ist korrekt und lässt auch eine negative Cap-Marge zu. `p_z(s) <= 1` folgt
aber nicht allgemein aus Arbitragefreiheit; es gilt nur, wenn der festgesetzte
Cap/Payoff aus dem verfügbaren Budget finanzierbar ist. Gegenbeispiel aus dem
ausgeführten BS-Pricer (`r=3,8%`, `sigma=16%`, Total Protection):

- Cap 6,20 %: `p_z=0,9917909` (Basisfall, positive Marge);
- Cap 50 %: `p_z=1,0449739` (negative Marge).

**Empfehlung:** Ungleichung durch „im vorliegenden Cap-Basisfall“ ersetzen und
explizit zulassen, dass `CM_s < 0` bei einem über Budget liegenden Cap eine
Subvention/Verlustmarge darstellt.

### C-07 — MITTEL: Der gemeldete LSMC-Wert ist kein strikter numerischer Lower Bound

**Fundstellen:** Fachpaper Z. 966--989;
`agile_engine/lsmc.py:20-32, 430-441, 591-598`.

Die gelernte adapted Policy ist zulässig; ihr **wahrer Erwartungswert** liegt
damit unter oder auf dem wahren Optimum. Der ausgegebene Wert ist aber ein
Monte-Carlo-Schätzer. Zusätzlich wählt der Code nach Sichtung derselben
Evaluationsstichprobe `max(value_opt, value_static)` und übernimmt bei Bedarf
den Static-Fallback. Der Maximalwert zweier verrauschter Schätzer hat
Selektionsbias und kann numerisch oberhalb des wahren Optimums liegen. „Valid
lower bound“ ist daher ohne Fehlerband/asymptotische Qualifikation zu stark.

**Empfehlung:** Formulieren als „out-of-sample estimate of an admissible-policy
value; population value is a lower bound“. Policy-Auswahl auf Validation-Set,
abschließende Bewertung auf unabhängigem Test-Set; Standardfehler/Konfidenzband
ausgeben.

### C-08 — MITTEL: Wichtige LSMC-Grenzen fehlen in der Paper-Zusammenfassung

**Fundstellen:** `agile_engine/lsmc.py:34-41, 67-74, 234-270`;
Fachpaper Z. 981--989.

Zusätzlich zu den im Paper genannten Grenzen gilt:

- Default-Horizont endet bei Alter 105 (höchstens 40 Jahre), nicht beim
  Monatsmotor-Default 115;
- Joint-Life-Mortalität wird im LSMC laut Modul selbst unkonditioniert ab Issue
  gebildet, während der Monatsmotor ab tatsächlicher Election konditioniert;
- der Tail nutzt einen pauschalen 30-jährigen Zero Rate und den
  `max(account, income * annuity_factor)`-Closeout;
- das Static-Benchmark-Verhalten ist der im LSMC implementierte feste
  Startpfad, nicht der vollständige dynamische Monatsmotor.

Diese Punkte sind für Spouse- und Tail-Optionalität materiell und sollten in
Abschnitt 9.4 explizit stehen.

### C-09 — MITTEL: „Expenses +10 %“ stresst nur Maintenance Expenses

**Fundstellen:** Fachpaper Z. 1187;
`agile_engine/sensitivities.py:13-15, 96-104`.

Die Sensitivität multipliziert nur `maintenance_per_policy` und
`maintenance_pct_of_iv` mit 1,1. Acquisition Expense (2 % = AUD 2.000) und
Commission bleiben unverändert. Das erklärt den Gross-VNB-Effekt von nur
−AUD 155,90: Er ist 10 % des modellierten Maintenance-PV von rund AUD 1.559,
nicht 10 % des gesamten Expense-PV von AUD 3.558,57.

**Empfehlung:** Tabellenzeile in „Maintenance Expenses +10 %; Acquisition
unverändert“ umbenennen.

### C-10 — MITTEL: Spouse-Designresultate enthalten im Paper nicht genannte Modellpunkte

**Fundstellen:** Fachpaper Z. 1245--1266;
`examples/run_insurer_analysis.py:327-351`.

Die Spouse-Varianten verwenden eine 63-jährige Frau neben dem 65-jährigen Mann
und die Default-Election `continue_income`. Diese Annahmen stehen weder in der
Ergebnistabelle noch im Basisannahmenblock; das Manifest enthält nur den
Single-Life-Basismodellpunkt. Die Spouse-Werte sind ohne Lesen des Runners
nicht vollständig rekonstruierbar.

**Empfehlung:** Tabellenfußnote „Spouse: Frau, 63, Continue Income“ ergänzen.
Für APS ist die im Text genannte CAS-LE von 20 Jahren bereits korrekt.

### C-11 — MITTEL: Ausgewiesene Nachkommastellen übersteigen die belegte MC-Präzision

**Fundstellen:** Fachpaper Z. 1058--1077, 1123--1170 und 1509--1515;
`executive_kpis.csv`, `capital_proxy.csv`, `profit_runoff.csv`.

Nur Gross VNB, Guarantee Value und Identity Gap erhalten im Runner pfadweise
Standardfehler. Für Fair LIP, BSCR, Risk Margin, PVFP, IRR, Designs, Timing und
Sensitivitätsdifferenzen fehlen passende Fehlermaße. Die Cent-/Vierdezimal-
Darstellung ist daher rechnerisch reproduzierbar, nicht statistisch belastbar.

Eine ergänzende, ausdrücklich kleine Fünf-Seed-Studie mit je 800 Pfaden ergab:

| Größe | Mittel der fünf Schätzer | Sample-SD bei 800 | grob auf 4.000 skaliert |
|---|---:|---:|---:|
| Fair LIP | 3,00318 % | 1,524 bp | 0,682 bp |
| BSCR | AUD 17.233 | AUD 34,08 | AUD 15,24 |
| Risk Margin | AUD 4.697 | AUD 19,37 | AUD 8,66 |
| PVFP | −AUD 12.967 | AUD 87,82 | AUD 39,28 |
| IRR | 3,4977 % | 1,606 bp | 0,718 bp |

Die Skalierung mit `1/sqrt(5)` ist nur eine grobe MC-Indikation; fünf Seeds
sind kein belastbares Konfidenzverfahren. Sie zeigt aber, dass z. B. Fair LIP
`3,0042 %` nicht auf 0,01 bp und PVFP nicht auf Cent ökonomisch präzise sind.

**Empfehlung:** Managementtabellen angemessen runden; gepaarte SEs für
Stressdifferenzen, Seed-/Batch-SE für Capital/PVFP/Fair Fee und
Konfidenzintervalle ausgeben.

### C-12 — MITTEL: PVFP enthält eine symmetrische sofortige Steuerentlastung auf Verluste

**Fundstellen:** Fachpaper Z. 1027--1037 und 916--934;
`agile_engine/profitability.py:238-255`.

`(1-tax) * profit` wird auch auf negative Gewinne angewendet. Damit werden
Verluste sofort mit 30 % steuerlich entlastet. Es gibt weder Tax-Loss-Carry-
Forward noch Deferred-Tax-/Recoverability-Logik. Das ist eine zulässige
illustrative Annahme, aber die Formulierung „inkl. Tax“ ist ohne diese
Einschränkung unvollständig.

**Empfehlung:** Als „symmetrische sofortige 30-%-Steuerannahme“ deklarieren;
für Production Verlustvorträge, DTA-Realisierbarkeit und steuerliche Basis
modellieren.

### C-13 — NIEDRIG: Modellspannweite ist rund 38-, nicht rund 37-mal das 95-%-Halbintervall

**Fundstelle:** Fachpaper Z. 1321--1324.

Exakt: `3126,9807 / 82,8090 = 37,7614`. Normales Runden ergibt 38. „Mehr als
37-mal“ wäre ebenfalls korrekt.

### C-14 — NIEDRIG: Reconciliation-CSV zeigt nicht die tatsächlich verwendete PASS-Schwelle

**Fundstellen:** `examples/run_insurer_analysis.py:306-318`;
`reconciliations.csv`.

Die CSV-Spalte zeigt für die Identity `1,96 * SE = 0,0019457`; der PASS-Status
wird jedoch gegen `max(0,0025, 3*SE) = 0,0029782` getestet. Im vorliegenden
Lauf liegt der Gap von −0,0016892 unter beiden Grenzen, der Status ist also
unverändert richtig. Für Governance sollte die tatsächlich verwendete
Schwelle dennoch separat gespeichert und benannt werden.

## 3. Formel- und Implementierungsabgleich

| Thema | Paperformel / Aussage | Ausgeführter Code | Urteil |
|---|---|---|---|
| Total Protection | `min(max(R,0),C)` | `crediting.py:74-85` | korrekt |
| Partial Protection 10 | `min(R,C)` für `R>=0`, sonst `min(0,R+0,10)` | `crediting.py:74-85` | korrekt; Beispiele +15/+6/−5/−10/−18 reproduziert |
| Statische Replikation | `Call(1)-Call(1+C)` bzw. minus `Put(0,90)` | `crediting.py:119-132` | algebraisch korrekt |
| DVA-Hedgewert | `P(t,T)+V_package(t)` | `crediting.py:139-157`, `projection.py:429-476` | korrekt als **Modellproxy**, nicht bestätigte Adminformel; `p_z<=1` nur bedingt |
| Crediting Margin | `IV_frame*(1-p_z)` am Periodenstart | `projection.py:525-536, 610-613` | korrekt gebucht; kann negativ sein |
| Lifetime Income Rate | Commencement-age/sex + volle Growth-Jahre × Escalator | `product.py:349-409`, `projection.py:561-576` | Basis 7,05 %+5×0,35 %=8,80 % korrekt |
| Rising Income | Ratchet um positiven AUS-TP-Credit | `projection.py:625-668` | korrekt; Anniversary-Zahlung nutzt noch altes Income, danach Ratchet |
| Gebühren | monatlich `IV_frame*f/12` | `projection.py:686-712` | Paper nennt Approximation korrekt; tatsächliche Daily/Event-Mechanik fehlt |
| MVA | `1-[(1+z_issue+s)/(1+z_now+s)]^tau + loadings` | `product.py:438-501` | Vorzeichen/Einheiten konsistent; unkalibrierter Proxy |
| APS MWV | `max(B*(1-e/LE)-W,0)` | `product.py:532-552`, `projection.py:974-1012` | korrekt; Half-LE-Death-Cap-Sprung separat implementiert |
| Mortality | GM-Basis, generational improvement, Monats-q | `mortality.py:96-115, 174-203` | korrekt zur dokumentierten Näherung; Clip/Cat-Add-on ergänzen den Kurzterm |
| Joint Life | `p1+p2-p1*p2` bei Unabhängigkeit | `mortality.py:220-228`; Monatsmotor `projection.py:749-767` | Monatsmotor ab Election korrekt konditioniert; LSMC nicht |
| Dynamic Lapse | `PV guarantee / surrender value` | `behavior.py:50-93`, `projection.py:538-559, 831-860` | Anniversary korrekt; off-anniversary IV/SV-Inkonsistenz, siehe C-05 |
| BEL | Claims + Expenses − Product Fee − LIP − CM − MVA/APS | `pricing.py:170-185` | exakt |
| Gross VNB | `-BEL_nonunit` | `ProjectionResult.pv_insurer_net`, `pricing.py:179-183` | exakt bis Floating-Point (`9,1e-13` Gap) |
| Guarantee Value | Claims − LIP | `pricing.py:174` | exakt |
| Fair LIP | Nullstelle des Guarantee Value mit CRN | `pricing.py:192-224` | korrekt; Root-Residual im Lauf ca. −AUD 0,054, MC-Fehler nicht berichtet |
| SCR-Standalone | `max(0,NAV_base-NAV_stress)` | `capital.py:204-269` | korrekt zum Research-Proxy |
| Aggregation | `sqrt(s'Cs)` | `capital.py:160-168, 230-274` | exakt reproduziert |
| Risk Margin | 6 % CoC auf Life-SCR-Pattern, Diskont `t+1` | `capital.py:276-310` | Paperformel und Code stimmen |
| Profit Signature | Fees+CM+MVA+APS−Claims−Expenses | `profitability.py:89-96` | exakt |
| Reserve/Profit | CE-BEL, Reservezins, Delta BEL | `profitability.py:99-113, 238-255` | Paper korrekt als Schema; Steuerannahme siehe C-12 |
| PVFP/IRR/Payback | DE bei Hurdle; niedrigste IRR-Wurzel | `profitability.py:116-154, 257-279` | exakt reproduziert |
| Q/P | Q für Wert/BEL, P mit ERP für Outcomes/Profit | `pricing.py:125-167`, `profitability.py:192-200` | korrekt getrennt; P und Q teilen Heston-/HW-Dynamik wie im Paper offengelegt |
| LSMC | annual adapted policy, diskrete Aktionen | `lsmc.py` | Mechanik nachvollziehbar; methodische Einschränkungen C-07/C-08 |

Zusätzliche Verhaltenspräzisierung: Der im Paper als `PV_t` bezeichnete
Income-Moneyness-Wert ist kein vollständiger marktkonsistenter Tail-PV. Der
Code verwendet einen Mid-year-Annuitätenfaktor mit einem flachen, pathweisen
10-Jahres-Zero-Rate-Proxy (`projection.py:542-559`). Das ist für eine
heuristische Behaviour-Regel vertretbar, sollte aber als Proxy benannt werden.

## 4. Direkte Zahlenreconciliation des 1.3.0-Laufs

### 4.1 Executive KPIs und Wertzerlegung

Quelle: `executive_kpis.csv`, `pv_components.csv`, `reconciliations.csv`.

\[
\begin{aligned}
VNB_{gross}={}&2.269{,}8434+8.701{,}0665+9.923{,}4505+217{,}3672\\
&-18.780{,}8056-3.558{,}5689\\
={}&-1.227{,}6468.
\end{aligned}
\]

Damit:

- Non-unit BEL = `+1.227,6468`;
- `BEL_nonunit + insurer_net_value = 9,09e-13`;
- Gross NBM = `−1.227,6468 / 100.000 = −1,2276468 %`;
- Guarantee Value = `18.780,8056 − 8.701,0665 = 10.079,7392`;
- LIP-Funding-Ratio = `8.701,0665 / 18.780,8056 = 46,3296 %`;
- Fair-LIP-Lücke = `(3,0041561 % − 1,15 %)*10.000 = 185,4156 bp`;
- VNB nach RM = `−1.227,6468 − 4.687,2625 = −5.914,9093`;
- NBM nach RM = `−5,9149093 %`.

Alle im Paper Z. 1062--1077 und 1090--1103 gezeigten Werte sind damit korrekt
gerundet.

### 4.2 Marktwertidentität und Kundencashflows

\[
PV(\text{Kundenleistungen})=
69.417{,}9605+12.537{,}7998+15.544{,}3950+0
=97.500{,}1553.
\]

\[
\begin{aligned}
PV(\text{finanziert})={}&97.500{,}1553-18.780{,}8056\\
&+2.269{,}8434+8.701{,}0665+9.923{,}4505+217{,}3672\\
={}&99.831{,}0774.
\end{aligned}
\]

Residual `= −168,9226`, relative Identity Gap
`= −168,9226 / 100.000 = −0,1689226 %`. Paper Z. 1107--1121 ist korrekt.

Pfadweiser Identity-SE ist `0,0992717 %`; das ausgewiesene
`1,96*SE = 0,1945726 %`. Der beobachtete Gap liegt betragsmäßig innerhalb
dieses Bands.

### 4.3 Kapitalproxy und Risk Margin

Aus `capital_proxy.csv`:

- Market SCR = Interest Down = `15.812,6571`;
- Life-Vektor in Matrixreihenfolge =
  `(Mortality 0; Longevity 3.489,6950; Lapse 818,4516;
  Expense 313,8751; Cat 0)`;
- mit der Manifest-Korrelationsmatrix:
  `sqrt(s' C_life s) = 3.896,0212`;
- Top-Level mit Korrelation 0,25:
  `sqrt(15.812,6571² + 3.896,0212² + 2*0,25*15.812,6571*3.896,0212)
  = 17.205,2994`.

Das in `profit_runoff.csv` gespeicherte Required-Capital-Pattern geteilt durch
BSCR rekonstruiert das Pattern. Mit der Manifestkurve folgt exakt:

\[
0{,}06\sum_t 3.896{,}0212\,pattern_t\,P(0,t+1)
=4.687{,}2625.
\]

Paper Z. 1125--1145 ist korrekt. Nullwerte für Equity/Vol/Mortality/Cat sind
gefloor­te Stressverluste und kein Risikofreiheitsnachweis, wie das Paper
richtig erklärt.

### 4.4 Profit-, Reserve- und Kapital-Runoff

Direkt aus `profit_runoff.csv`:

| Paper-Aussage | CSV-Rekonstruktion | Status |
|---|---:|---|
| Time-0 Profit Signature | −1.179,0891 | korrekt gerundet |
| Time-0 Distributable Strain | −21.345,7359 | korrekt gerundet |
| BEL inkl. RM Maximum | 47.668,8123 in Jahr 17 | korrekt |
| Required Capital Maximum | 30.453,5183 in Jahr 17 | korrekt |
| erste negative Signature ab | Jahr 17 | korrekt |
| Minimum Signature | −4.650,5839 in Jahr 21 | korrekt |
| erster positiver kumulierter DE-Stand | Jahr 23 | korrekt |
| terminal kumuliert nominal | +27.525,6418 | korrekt |

Direkte Metrikprüfung:

- `sum(DE_y/(1,08)^y) = −12.898,9599`;
- bei `IRR=3,5191988 %` ist der NPV `1,26e-7` AUD, numerisch null;
- es gibt im abgesuchten Engine-Bereich für den Basis-Run nur einen
  Vorzeichenwechsel der IRR-Funktion.

### 4.5 Sensitivitäten

Quelle: `sensitivities.csv`, 1.200 Pfade, `capital_included=False` in jeder
Zeile. Jede Paper-Zeile Z. 1171--1188 stimmt mit Rundung überein:

| Szenario | Gross VNB | Delta VNB | GV | PVFP | Delta PVFP |
|---|---:|---:|---:|---:|---:|
| Base | −1.223,60 | 0 | 10.092,16 | −66,11 | 0 |
| Rates +100 bp | 8.549,14 | 9.772,74 | 6.498,88 | 6.932,72 | 6.998,82 |
| Rates −100 bp | −12.706,78 | −11.483,18 | 14.763,59 | −8.262,56 | −8.196,46 |
| Equity vol +25 % | −787,32 | 436,28 | 10.269,05 | 74,92 | 141,02 |
| Caps −100 bp | 1.008,40 | 2.232,01 | 10.851,25 | 1.379,99 | 1.446,10 |
| Longevity −10 % qx | −2.852,23 | −1.628,63 | 11.779,79 | −1.183,48 | −1.117,38 |
| Mortality +10 % qx | 207,33 | 1.430,93 | 8.600,02 | 913,26 | 979,37 |
| Lapse +50 % | −498,16 | 725,44 | 8.787,51 | 369,51 | 435,61 |
| Lapse −50 % | −2.041,95 | −818,35 | 11.525,99 | −561,13 | −495,02 |
| Dynamic lapse off | −527,25 | 696,35 | 9.336,34 | 402,60 | 468,71 |
| Income start +2y | 2.037,40 | 3.261,00 | 7.904,87 | 2.084,50 | 2.150,60 |
| Income start −2y | −4.028,53 | −2.804,92 | 11.824,05 | −1.877,54 | −1.811,44 |
| Free withdrawals 100 % | −362,04 | 861,56 | 7.635,30 | 393,41 | 459,51 |
| Excess withdrawals 2 % | 2.521,02 | 3.744,62 | 4.027,46 | 2.306,61 | 2.372,71 |
| Maintenance expenses +10 % | −1.379,51 | −155,90 | 10.092,16 | −174,50 | −108,39 |
| ERP −100 bp | −1.223,60 | 0 | 10.092,16 | −253,26 | −187,15 |

Die Paper-Hinweise zu verschiedenen Scopes, CRN, fehlenden gepaarten SEs und
dem kombinierten Free+Excess-Szenario sind korrekt. Nur die Expense-Bezeichnung
ist gemäß C-09 zu präzisieren.

### 4.6 Kunden-Outcomes

Quelle: `customer_outcome_quantiles.csv` und
`customer_annual_cashflows.csv`; tatsächlicher Seed 2027, 2.500 P-Pfade.

Alle in Z. 1222--1229 gezeigten Alterspunkte stimmen. Insbesondere:

- Alter 70: IV-P5/P50/P95 = `97.560,62 / 110.077,95 / 123.927,38`,
  Income-P50 `9.811,68`, In-force `78,6426 %`;
- Alter 83: IV-P50 `525,91`, Exhaustion `47,56 %`;
- Alter 84: IV-P50 `0`, Exhaustion `85,36 %` — erster Jahrespunkt über 50 %;
- Alter 86: Exhaustion `100 %`;
- Guarantee Claims beginnen in Jahr 16/Alter 81 mit `0,7213`, werden in
  Alter 82 mit `196,2742` sichtbar und erreichen ihr Maximum
  `4.591,4679` in Jahr 21/Alter 86.

Die Paper-Einschränkung, dass IV-/Income-Quantile rohe bedingte Marktstates und
nicht decrementgewichtete individuelle Kontostände sind, entspricht dem
Runner (`np.quantile(result.iv_paths, ...)`, In-force separat).

### 4.7 Produktdesigns und Income-Start-Timing

Quelle: `product_designs.csv`, `income_start_timing.csv`, je 1.500 Q-Pfade.

Alle sechs Designzeilen und alle fünf Timingzeilen stimmen mit dem Paper:

| Design | Rate | Q-Start-Income | Gross VNB | GV | LIP/Claims | Customer PV |
|---|---:|---:|---:|---:|---:|---:|
| Single Fixed | 8,80 % | 9.516,99 | −1.335,37 | 10.183,01 | 46,068 % | 97.548,20 |
| Single Rising | 5,65 % | 6.110,34 | 6.444,98 | 3.900,44 | 71,320 % | 89.690,17 |
| Spouse Fixed | 7,70 % | 8.327,37 | −5.148,74 | 14.908,08 | 39,036 % | 100.956,54 |
| Spouse Rising | 4,55 % | 4.920,72 | 6.536,91 | 5.544,07 | 66,694 % | 89.174,68 |
| APS Fixed | 8,85 % | 9.571,07 | −2.251,60 | 12.482,84 | 27,831 % | 98.393,52 |
| APS Rising | 5,70 % | 6.164,42 | 7.207,39 | 7.197,72 | 40,076 % | 88.838,26 |

| Warten | Rate | Q-Start-Income | Gross VNB | GV | Customer PV |
|---:|---:|---:|---:|---:|---:|
| 1 | 7,40 % | 7.508,71 | −6.150,19 | 12.858,83 | 102.336,52 |
| 3 | 8,10 % | 8.481,92 | −4.171,36 | 11.947,16 | 100.377,87 |
| 5 | 8,80 % | 9.516,99 | −1.335,37 | 10.183,01 | 97.548,20 |
| 10 | 10,55 % | 12.364,80 | 6.851,88 | 4.504,13 | 89.287,01 |
| 15 | 12,30 % | 15.569,06 | 15.065,91 | −1.790,62 | 80.995,65 |

Interpretationen sind als bedingte Szenarien, nicht als gemeinsame spätere
Wahloption, korrekt eingeschränkt. Verdeckte Spouse-Annahme siehe C-10.

### 4.8 Behaviour-/Liquiditätsflächen

Quelle: `behaviour_takeup_lapse.csv`, `behaviour_withdrawals.csv`, je
600 Q-Pfade.

Die 18 im Paper gezeigten NBM-Zellen für Lapse-Multiplikatoren 0,5/1,0/1,5
und Startjahre 1/3/5/8/12/15 stimmen auf 0,01 Prozentpunkte. Auch die genannten
Withdrawal-Endpunkte stimmen:

- Excess 0 %, Free 0 %: `−1,27514 %`; Free 100 %: `−0,40141 %`;
- Excess 2 %, Free 0 %: `2,25854 %`; Free 100 %: `2,48444 %`.

### 4.9 Modellvergleich und Seed-Stabilität

Quelle: `model_comparison.csv`, `mc_seed_stability.csv`.

Modellwerte (je 600 Pfade) stimmen vollständig. Spannweite:

\[
-1.275{,}1382-(-4.402{,}1189)=3.126{,}9807.
\]

Seedwerte (je 800 Pfade) ergeben exakt:

- Mittel Gross VNB `−1.209,3281`;
- Sample-SD `96,6363`;
- mittlerer pfadweiser SE `96,6274`;
- Range `−1.291,7770` bis `−1.048,5100`.

Die Nähe von Seed-SD und mittlerem SE ist ein positives internes Signal. Vier
Modelle mit 600 Pfaden haben jedoch keine ausgegebenen modellweisen SEs; die
Spannweite bleibt eine Mischung aus Modell- und Sampling-Effekt, wie das Paper
richtig sagt.

### 4.10 Greeks

Der dokumentierte Runtime-Fix wurde unabhängig mit 4.000 Pfaden ausgeführt und
reproduziert `market_greeks.csv` bitgenau:

- NAV vor Expenses `2.330,9220089`;
- Equity Delta normalized `0,0005040199003`;
- Vega je +1 Vol-Punkt `0,0011589665405` der Prämie = AUD 115,90;
- Rho je +100 bp `0,1039039335197` der Prämie = AUD 10.390,39.

`2.330,9220 - (−1.227,6468) = 3.558,5689`, exakt der Expense-PV. Die
Scope-Erklärung des Papers ist richtig. Die Equity-Delta-Einheit sollte
zusätzlich erläutert werden: Der Output ist
`dNAV/d(index scale)/premium`; eine +1-%-Skalenbewegung wird noch mit 0,01
multipliziert.

### 4.11 Versionsvergleich 1.2.0 / 1.3.0

Direkte Differenzen der beiden `executive_kpis.csv` bzw.
`pv_components.csv`:

| Kennzahl | v1.2.0 exakt | v1.3.0 exakt | Delta exakt | Paper gerundet |
|---|---:|---:|---:|---:|
| Gross VNB | 1.742,5596 | −1.227,6468 | −2.970,2065 | −2.970 |
| Fair LIP | 3,2366718 % | 3,0041561 % | −23,2516 bp | −23,3 bp |
| Guarantee Value | 11.240,1445 | 10.079,7392 | −1.160,4054 | −1.160 |
| Crediting Margin | 14.131,0792 | 9.923,4505 | −4.207,6287 | −4.208 |
| BSCR | 16.839,4522 | 17.205,2994 | 365,8472 | +366 |
| Risk Margin | 20.076,0624 | 4.687,2625 | −15.388,8000 | −15.389 |
| VNB nach RM | −18.333,5028 | −5.914,9093 | 12.418,5935 | +12.419 |
| PVFP | −15.610,4687 | −12.898,9599 | 2.711,5088 | +2.712 |
| IRR | 4,1726138 % | 3,5191988 % | −0,6534 %-Pkt. | −0,65 |
| Payback | 22 | 23 | +1 | +1 |

Der nicht archivierte Carry-Gegenlauf wurde unabhängig rekonstruiert, indem im
aktuellen 1.3.0-Code sowohl Product- als auch ESG-Carry konsistent auf AUS 4 %
und Global 2 % gesetzt wurden. Ergebnis: Gross VNB `+1.879,3178`; isoliertes
Delta zum 1.3.0-Basislauf `−3.106,9647`. Damit sind die Paperangaben „rund
+1.879“ und „etwa −3.107“ korrekt. Für Auditierbarkeit sollte dieser
Gegenlauf künftig ein eigenes Manifest/CSV erhalten.

Der RM-Methodeneffekt ist auch größenordnungsmäßig nachweisbar: Würde man beim
aktuellen Pattern statt Life SCR den gesamten BSCR als CoC-Basis verwenden,
ergäben sich rund AUD 20.700 statt AUD 4.687, nahe dem historischen 1.2-Wert
von AUD 20.076.

## 5. Pfadzahlen, MC-Fehler und Risikoklassen

Die Paper-Pfadzahlen stimmen mit `run_manifest.json` und Runner überein:

| Block | Pfade | Maß/Seed |
|---|---:|---|
| Basispricing, Capital, Profitability | 4.000 | Q Seed 2026; P effektiv 2027 |
| Sensitivitäten | 1.200 | Q Seed 2026; P effektiv 2027 je Szenario |
| Design/Timing | 1.500 | Q Seed 2026 |
| Behaviour | 600 | Q Seed 2026 |
| Outcomes | 2.500 | P effektiv Seed 2027 |
| Modellvergleich | 600 je Modell | Q Seed 2026 |
| Seed-Stabilität | 800 je Seed | fünf ausgewiesene Seeds |

Für den Basis-Gross-VNB wurde der pfadweise Fehler unabhängig aus den
Cashflowmatrizen neu berechnet:

- SE `42,24949` AUD;
- 95-%-Halbintervall `1,96*SE = 82,80899` AUD;
- Versionsbewegung `2.970,2065 / 42,24949 = 70,30` SE.

Das Paper trennt MC-Fehler grundsätzlich richtig von Parameter-, Modell- und
Implementierungsrisiko. Ergänzend gilt:

- der SE integriert Mortalität/Lapse als deterministische Gewichte und misst
  primär Marktszenario-Sampling, nicht Experience Risk;
- CRN senken Differenzvarianz, ersetzen aber keinen gepaarten SE;
- Fair-Fee-Root-Toleranz ist kein MC-Konfidenzintervall;
- Capital/RM/PVFP sind nichtlineare Outputs und benötigen eigene Fehlermaße;
- 600-Pfad-Modellwerte dürfen nicht mit dem 4.000-Pfad-Basis-SE normiert werden,
  ohne deren eigenen Samplingfehler einzubeziehen;
- Parameter-, Kalibrierungs-, Vertrags-, Admin-, Modell- und Code-Risiko
  werden von keinem der MC-Bänder erfasst.

## 6. Reproduzierbarkeitsprotokoll

### 6.1 Umgebung

```text
Python 3.11.9
NumPy 2.2.3
SciPy 1.13.1
pandas 2.2.3
Matplotlib 3.9.4
Windows-10-10.0.26200-SP0
agile_engine 1.3.0
```

Diese Werte stimmen mit dem 1.3.0-Manifest.

### 6.2 Testsuite

Ausgeführt ohne pytest-Cache-Schreibzugriff:

```powershell
python -m pytest -p no:cacheprovider -q
```

Ergebnis: Exit Code 0; Wandzeit 140,13 Sekunden. Separate Collection:
`122 tests collected in 1,20s`. Damit sind 122 bestandene Tests belegt. Die im
Paper genannte Laufzeit 108,24 Sekunden ließ sich auf derselben Softwareumgebung
nicht reproduzieren; Laufzeit ist umgebungs-/lastabhängig und kein fachlicher
Fehler. Ein erster auf 120 Sekunden begrenzter Versuch lief folgerichtig ins
Timeout.

### 6.3 Unveränderter Standard-Runner

```powershell
python examples/run_insurer_analysis.py `
  --output ..\_review_work\runner_unmodified_1_3
```

Ergebnis: Exit Code 1 nach 18,5 Sekunden, `FrozenInstanceError` in
`pricing.py:260`; keine vollständigen Outputs.

### 6.4 Instrumentierter Runner

Nur im Python-Prozess wurde die in `main()` gebundene Greek-Funktion durch die
im Paper skizzierte `dataclasses.replace`-Variante ersetzt. Alle übrigen
Runnerfunktionen, Inputs und Pfadzahlen blieben unverändert. Output:
`_review_work/runner_workaround_reproduction/`.

Ergebnis: vollständige 9/9 Blöcke, Exit Code 0, Runner-Laufzeit 113,5 Sekunden.

Vergleich gegen
`examples/output/insurer_analysis_v1_3_runtime_workaround/`:

- 14 CSV-Dateien in jeder Zelle exakt identisch;
- `model_comparison.csv` in allen fachlichen Zellen exakt identisch, nur
  `runtime_seconds` erwartungsgemäß verschieden (max. Differenz 0,437 s);
- alle zehn PNGs SHA-256-/byteidentisch;
- `run_manifest.json` nach Entfernung von `generated_utc` strukturell und
  wertmäßig identisch;
- Managementbericht nur bei Erstellzeit und Gesamtlaufzeit verschieden;
- Engine-Hash vor und nach den Läufen unverändert.

Damit ist der **instrumentierte** Zahlenlauf stark reproduziert, der
**unveränderte Standardlauf** dagegen nachweislich nicht lauffähig.

## 7. Priorisierte Korrekturen für Paper/Review-Fassung

1. Greek-Fehler und unvollständige Provenienz unverändert prominent belassen;
   Outcome-Seed-Divergenz ergänzen.
2. Heston--Hull--White Gaussian Add-on nicht als exakt bezeichnen und die
   negative Defaultgröße erklären; Heston-HW-Ergebnis als Näherung markieren.
3. LSMC-„Lower Bound“ statistisch präzisieren; Alter-105-Horizont und
   unkonditioniertes Joint Life ausdrücklich ergänzen.
4. `p_z<=1` auf den finanzierbaren/betrachteten Cap-Fall einschränken.
5. Sensitivität in „Maintenance Expenses +10 %“ umbenennen; symmetrische
   Steuerentlastung auf Verluste offenlegen.
6. Spouse-Modellpunkt (Frau 63, Continue Income) in Tabelle/Fußnote nennen.
7. Ergebnisse stärker runden und für Fair LIP, Capital, RM, PVFP, Designs und
   Stressdifferenzen MC-Fehler bzw. fehlende Fehlermaße kenntlich machen.
8. Carry-Gegenlauf als eigenes versioniertes CSV-/Manifest-Artefakt ablegen.
