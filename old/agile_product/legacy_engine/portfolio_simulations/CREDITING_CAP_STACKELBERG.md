# Crediting-Cap-Optimierung als Stackelberg-Kontrollproblem

## Zweck und Geltungsbereich

Dieses Dokument definiert das fachliche Timing und das Gleichgewicht für die
jährliche Crediting-Cap-Optimierung mit endogen optimalem
Policyholder-Verhalten. Es ist die normative Grundlage für Implementierung,
Tests und Ergebnisinterpretation.

Die Optimierung ist **kein** Standard-LSMC einer amerikanischen Option. Sie ist
ein wiederholtes stochastisches Stackelberg-/Bilevel-Kontrollproblem:

1. Die Versicherung wählt als Leader den Cap für das beginnende Crediting-Jahr.
2. Der Policyholder beobachtet die zu diesem Zeitpunkt vertraglich bekannten
   Informationen und wählt mit seiner eigenen Zielfunktion zwischen
   `CONTINUE` und `FULL_WITHDRAWAL`.
3. Die Versicherung antizipiert diese Best Response.
4. In späteren Jahren wird dieselbe rekursive Regel erneut angewandt.

Die bestehende monatliche Ereignisreihenfolge in
`agile_engine/projection.py` bleibt unverändert. Erforderliche Hooks und
State-Snapshots dürfen den Ablauf instrumentieren, aber kein Ereignis zeitlich
verschieben.

## Zeit- und Cap-Konvention

Der Original Policy Anniversary zu Beginn von Policy Year `y` sei

\[
t_y = y, \qquad y=0,1,\ldots,Y.
\]

`C_y` bezeichnet den an `t_y` gewählten und bekannt gegebenen Cap für das
Crediting-Jahr `(t_y, t_{y+1}]`. Am Anniversary `t_y`, `y >= 1`, wird dagegen
zuerst der Return des gerade beendeten Jahres unter dem **alten** Cap
`C_{y-1}` gutgeschrieben. Erst danach wird `C_y` gewählt.

Am Issue Date `t_0` gibt es keinen alten Cap. `C_0` wird vor Initial-Hedge und
Crediting-Margin des ersten Jahres gewählt. Am finalen Projektionspunkt wird
kein Cap für ein Jahr gewählt, das nicht mehr projiziert wird; entsprechend
gibt es dort keinen neuen Hedge-/DVA-Start.

## Verbindliches Anniversary-Timing

Die Referenzen nennen stabile Ereignisblöcke und Hooks des Monatsprojektors;
konkrete Zeilennummern werden bewusst nicht festgeschrieben.

| Nr. | Ereignis am Anniversary `t_y` | Verwendeter Cap / Informationswirkung | Projektor-Referenz |
|---:|---|---|---|
| 0 | Start-of-month-Snapshots, darunter Phase, Locked Income, In-force Weight und Fee Base für das soeben beendete Monatsintervall | Noch keine neue Management Action | Beginn der monatlichen Hauptschleife |
| 1 | Annual Reference-Fund Return wird berechnet und dem Account Value gutgeschrieben | **Alter Cap `C_{y-1}`**. `year_idx = anniv_step // 12` wird vor dem Reset verwendet. Der vergangene Reference Return, Credited Return und Performance Gap werden jetzt beobachtbar. | Block `anniversary crediting` |
| 2 | Product Fee und Lifetime Income Premium werden für das letzte Intervall abgegrenzt und sämtliche accrued Fees gepostet | Die Fee Base des letzten Monats wurde vor dem Annual Credit fixiert. Posting erfolgt nach Credit und vor Election. | `post_fee_subledger(step)` |
| 3 | Gegebenenfalls wird der Age-Pension+-State aktualisiert und die neue jährliche Withdrawal Base fixiert | Transaktionszustand auf post-fee Account Value; keine Änderung der Cap-Reihenfolge | `activate_aps(...)` und Annual-Withdrawal-Base |
| 4 | Expected Mortality Decrement und Death Benefit für das beendete Intervall | Mortality verwendet den **pre-Election coverage state**. Death Benefit ist post-fee. Das In-force Weight wird vor allen Folgeereignissen reduziert. | Block `death decrement before the payment date` |
| 5 | Income Election der überlebenden, zulässigen Growth-Verträge | Election verwendet den post-credit, post-fee und post-mortality State. Der neue Cap ist nach dieser Konvention noch nicht bekannt. | `income_election_decision(...)`, `elect_income(...)` |
| 6 | Versicherung wählt und veröffentlicht `C_y` | Expliziter, read-only Control-/Announcement-Hook unmittelbar zwischen `elect_income(...)` und `restart_dva_period(step)`. | `observe_cap_decision(...)` |
| 7 | Hedge Execution, Crediting-Margin und DVA-/Crediting-Period-Restart | **Neuer Cap `C_y`**. Die Buchungen erfolgen nur für die nach Mortality noch in force befindlichen Verträge. | `restart_dva_period(step)` |
| 8 | Monatliches Lifetime Income in arrears | Nur Lives, die bis zum Payment Date überlebt haben. Im Election Month erfolgt wegen `just_elected` noch keine Zahlung. | Block `income payment` |
| 9 | Zulässige Partial/Excess Withdrawals | Nach neuem DVA-Start und Income Payment | `_apply_partial_withdrawals(...)` |
| 10 | Full-Withdrawal-Entscheidung und Auszahlung | Nach Bekanntgabe von `C_y`, Hedge-/DVA-Restart, Income und Partial Withdrawals. Der Policyholder-Hook erhält den aktuellen Cap explizit. | `SurrenderDecisionContext` / `surrender_mask(...)` |
| 11 | Expenses, erschöpfte Growth-Verträge, In-force- und Diagnosepfade | End-of-step-State; nicht als pre-action State für die Cap-Wahl wiederverwenden | End-of-step-Blöcke der Hauptschleife |

### Same-Anniversary-Beobachtbarkeit

Ein Policyholder, der bereits vor `t_y` in der Income Phase war, beobachtet den
neu angekündigten `C_y` bei seiner Full-Withdrawal-Entscheidung am selben
Anniversary. Das ist keine Vorwegnahme zukünftiger Information: `C_y` ist zu
diesem Zeitpunkt bereits veröffentlicht und der DVA-/Hedge-Restart ist bereits
erfolgt.

Diese Beobachtbarkeit muss explizit sein. Eine nur indirekte Wirkung über den
post-restart Account Value reicht nicht aus, insbesondere weil sie bei
deaktiviertem DVA verschwinden würde. Der Policyholder-Entscheidungskontext
muss deshalb `announced_cap=C_y` enthalten.

Folgende Ereignisse am selben Anniversary liegen dagegen **vor** der
Bekanntgabe und dürfen `C_y` nicht verwenden:

- Credit des abgelaufenen Jahres;
- Fee Posting;
- Mortality und Death Benefit des abgelaufenen Intervalls;
- Income Election.

Ein an `t_y` neu gewählter Income-Vertrag darf nicht gleichzeitig Full
Withdrawal ausüben. Der bestehende `just_elected`-Gate bleibt maßgeblich. Auch
Growth Surrender bleibt ausgeschlossen.

## Informationsmengen und Zustände

### Versicherer-State vor der Cap-Wahl

`X_y^-` ist der State unmittelbar nach Income Election und unmittelbar vor der
Wahl von `C_y`. Er darf nur an `t_y` bekannte Größen enthalten. Mindestens sind
zu repräsentieren:

- Short Rate, relevante Zero-/Forward-Rate-Information und Heston-Varianz;
- aktueller und vergangener Reference-Fund-State;
- vergangener Reference Return, Credited Return und Performance Gap;
- vergangene Caps, jedoch weder `C_y` noch spätere Caps;
- In-force-, Growth- und Income-Exposure;
- Account-Value- und Locked-Income-Exposure;
- Surrender-Value- und Garantie-Moneyness-Exposure;
- Exposure von Income-Verträgen mit erschöpftem Account Value;
- Policy Year beziehungsweise Duration und relevante Kohortenmerkmale.

Die am Monatsende aufgezeichneten `iv_paths`, `income_paths` und `phase_paths`
sind hierfür nicht geeignet: Sie liegen nach Restart, Payments und Full
Withdrawal. Der State muss am oben definierten Einfügepunkt separat erfasst
werden.

### Policyholder-State nach Cap-Bekanntgabe

Für jede Policy-Signature sei `Z_{m,y}(c)` der beobachtbare State am bestehenden
Full-Withdrawal-Ereignispunkt, nachdem der Kandidat `c` bekannt gegeben und der
vorhergehende Projektorablauf ausgeführt wurde. Er enthält mindestens:

- Account Value und post-fee Surrender Value;
- Locked Annual Income;
- Garantie-PV oder Garantie-Moneyness;
- Short Rate und relevante Zinsinformation;
- Heston-Varianz;
- Policy Year / Duration;
- `current_announced_cap=c`;
- vergangenen Reference Return und Credited Return beziehungsweise Performance
  Gap;
- Phase, `just_elected`, In-force Weight und sonstige Eligibility-Gates.

Hedge-P&L, Backing Assets, Crediting Margin und insurer-only cost information
sind keine Policyholder-Information und dürfen weder Features noch Targets der
Policyholder-Regression sein. Ein Entscheidungskontext sollte nur aktuelle und
vergangene Beobachtungen bereitstellen; das vollständige zukünftige
`ScenarioSet` darf nicht als frei auswertbares Policy-Input dienen.

## Mathematische Gleichgewichtsdefinition

### Zulässige Aktionen

Die Cap-Menge ist

\[
\mathcal C = \{0{,}0025, 0{,}01, 0{,}02, \ldots, 0{,}20\}.
\]

Für Policy-Signature `m` ist die grundsätzlich mögliche Policyholder-Aktion

\[
a_{m,y} \in \mathcal A_{m,y}=\{\text{CONTINUE},
\text{FULL\_WITHDRAWAL}\}.
\]

`FULL_WITHDRAWAL` ist jedoch nur zulässig, wenn der Vertrag bereits in der
Income Phase ist, in force ist, nicht am selben Timestamp Income gewählt hat
und einen positiven vertraglichen Surrender Value besitzt. Bei Growth Phase,
`just_elected`, Termination oder Surrender Value null reduziert sich die
Aktionsmenge auf `{CONTINUE}`. Ein positiver verbleibender Income-Guarantee-PV
darf nicht gegen einen Surrender Value null aufgegeben werden.

### Policyholder-Ziel

Sei `B^PH` die Summe der Policyholder-Cashflows:

\[
B^{PH} = \text{Income Payments}
       + \text{Death Benefits}
       + \text{Surrender Benefits}
       + \text{zulässige Partial Withdrawals}
       + \text{Terminal Closeout}.
\]

Gebühren wirken über den Account Value und dessen spätere Cashflows. Die bei
Issue gezahlte Prämie ist bei späteren Surrender-Entscheidungen versunken und
wird in der Aktionsentscheidung nicht erneut abgezogen.

Mit dem risikoneutralen Diskontfaktor `D(s,t)` und der Policyholder-
Informationsmenge `\mathcal I^{PH}_{m,y}(c)` sei

\[
Q^{PH}_{m,y}(z,c,a)
=
\mathbb E^{\mathbb Q}\!\left[
  \Delta B^{PH}_{m,y}(a)
  + D(t_y,t_{y+1})
    V^{PH}_{m,y+1}(Z_{m,y+1})
  \mid \mathcal I^{PH}_{m,y}(c),\,a
\right].
\]

`\Delta B^{PH}_{m,y}` enthält nur Cashflows, die am Entscheidungspunkt noch
nicht erfolgt sind. Insbesondere ist ein am selben Anniversary bereits
gezahltes Income für beide Aktionen gleich und daher kein künstlicher
Exercise-Anreiz. Die Best Response auf einen angekündigten Cap ist

\[
a^*_{m,y}(z;c)
\in \arg\max_{a\in\mathcal A_{m,y}(z)}
Q^{PH}_{m,y}(z,c,a).
\]

Numerisch instabile oder wirtschaftlich nicht validierte Exercise-Signale
fallen auf `CONTINUE` zurück. Ein Tie innerhalb der festgelegten Exercise-
Toleranz wird ebenfalls als `CONTINUE` behandelt.

### Versicherer-Ziel

Der periodische Versicherer-Reward verwendet ausschließlich den vorhandenen
New-Business-CSM-Proxy:

\[
\begin{aligned}
R^I ={}& \text{Product Fees} + \text{LIP Fees}
       + \text{Crediting Margin}
       + \text{MVA Retained} + \text{APS Retained} \\
      &- \text{Guarantee Claims}
       - \text{sonstige insurer-finanzierte Leistungen}
       - \text{Expenses} - \text{Hedge Execution Costs}.
\end{aligned}
\]

Account-Value-finanzierte Income-, Death-, Surrender- oder Partial-Withdrawal-
Zahlungen werden nicht noch einmal als Versichereraufwand abgezogen. Der
Terminal Closeout ist ebenfalls kein zusätzlicher Versichereraufwand. Der
Crediting-Margin-/Hedge-Gewinn-Schalter kann die betreffenden Versicherer-
Cashflows deaktivieren, darf aber niemals die Policyholder-Best-Response bei
identischen Kundencashflows verändern.

Für Portfolio-State `x=X_y^-` und Cap-Kandidat `c` lautet die rekursive
Versicherer-Q-Funktion

\[
Q^I_y(x,c)
=
\mathbb E^{\mathbb Q}\!\left[
  R^I_y\bigl(x,c,a^*_{1,y}(c),\ldots,a^*_{M,y}(c)\bigr)
  + D(t_y,t_{y+1})V^I_{y+1}(X^-_{y+1})
  \mid \mathcal I^I_y
\right].
\]

Die Leader-Aktion ist

\[
C_y^*(x) \in \arg\max_{c\in\mathcal C} Q^I_y(x,c),
\qquad
V^I_y(x)=Q^I_y(x,C_y^*(x)).
\]

Für **jeden** Cap-Kandidaten wird somit zuerst die Policyholder-Best-Response
unter der Policyholder-Zielfunktion bestimmt. Erst danach vergleicht die
Versicherung die resultierenden Versichererwerte. Policyholder-Aktionen dürfen
niemals anhand von `Q^I` gewählt werden, und die beiden Wertfunktionen dürfen
nicht zu einem gemeinsamen Target vermischt werden.

Zukünftige Schritte verwenden dieselben Best-Response- und Leader-Regeln. Das
ist das gesuchte Markov-perfecte Stackelberg-Gleichgewicht innerhalb der
gewählten State- und Regressionsklasse.

### Portfolioaggregation und Policy-Signatures

Die Policyholder-Best-Response wird vor jeder Portfolioaggregation getrennt je
Policy-Signature gefittet und angewandt. Joint-Life- und Single-Life-Fallback-
Branches werden ebenfalls getrennt behandelt und erst nach ihrer individuellen
Best Response gemäß der bestehenden spouse-survival conditioning kombiniert.

Mit den normalisierten Vertragsgewichten `w_m` gilt für den Versichererwert

\[
Q^{I,\mathrm{portfolio}}_y(x,c)
= \sum_m w_m\,Q^I_{m,y}\bigl(x_m,c,a^*_{m,y}(c)\bigr).
\]

`contract_weight` wird genau einmal angewandt. `premium_volume_weight` ist ein
Reconciliation-Control und kein zweites Bewertungsgewicht.

## Numerische Lösung mit zwei Fitted-Q-Wertfunktionen

Ein gemeinsamer rückwärts laufender Control-Randomisation-/Fitted-Q-Algorithmus
muss mindestens zwei getrennte Approximationen führen:

1. `Q_PH`: Policyholder-Continuation beziehungsweise Action Value je
   Policy-Signature, Cap und zulässiger Policyholder-Aktion;
2. `Q_INSURER`: Versicherer-Continuation Value je Portfolio-State und Cap,
   nachdem die aus `Q_PH` bestimmte Best Response angewandt wurde.

An jedem rückwärts durchlaufenen Anniversary gilt:

1. Für jeden Cap `c` werden die cap-konsistenten Policyholder-Action Values
   geschätzt.
2. Daraus wird `a^*(c)` mit den vertraglichen Eligibility-Gates bestimmt.
3. Unter genau dieser Reaktion wird der Versichererwert für `c` geschätzt.
4. Der Cap mit dem höchsten Versichererwert bestimmt die Leader-Policy.
5. Die ausgewählten Werte werden als Targets des vorherigen Jahres verwendet.

### Implementierte fold-reine Rekursion

Die Produktionsimplementierung bildet `K` voneinander getrennte äußere
Policy-Ketten und zusätzlich eine Vollstichprobenkette. Für äußere Falte `k`
werden sämtliche aktuellen **und zukünftigen** Follower- und Leader-Modelle
ohne die vollständigen Pfade dieser Falte gefittet. Die OOF-Action-Values eines
Pfads stammen damit aus einer gesamten Policy-Kette, die diesen Pfad nie als
Trainingstarget gesehen hat; ein indirektes Leck über ein späteres Refit ist
ausgeschlossen. Die separate Vollstichprobenkette liefert ausschließlich die
eingefrorenen Deployment-Modelle.

Je Policy-Signature werden ein pre-cap `CONTINUE`-Q, ein pre-cap
`FULL_WITHDRAWAL`-Q und die kanonische after-cap Continuation-Regression
geschätzt. Für den tatsächlich beobachteten Explorations-Cap verwendet die
Rekursion den exakten post-DVA-Entscheidungszustand und die vertragliche
Eligibility. Genau dasselbe after-cap Regressionsobjekt wird ohne nachträgliches
Refit oder abweichendes Clipping im `OptimalSurrenderPolicy` gespeichert. Ist
dieses Modell instabil, wird in der betroffenen Kette `CONTINUE` gesetzt. Fehlt
für die Vollstichprobenkette ein endlicher OOF-RMSE, wird die Signatur bereits
vor dem zugehörigen Leader-Fit auf `CONTINUE` eingefroren.

Der Versicherer fittet Product/LIP Fees, Crediting Margin, MVA/APS retained,
Claims und Kosten als getrennte Komponenten. Der CSM-Proxy wird erst danach
mit den dokumentierten Vorzeichen hergeleitet; dadurch bleibt die
Cashflow-Reconciliation prüfbar. Numerische Ties werden deterministisch zum
niedrigeren Cap aufgelöst.

Für jeden fixen Benchmark-Cap, einschließlich Null-Crediting und uncapped
positive Crediting, wird ein neues cap-konsistentes Policyholder-LSMC auf dem
Training-Sample geschätzt. Die adaptive und die fixe Policy werden anschließend
mit Common Random Numbers direkt im Monatsprojektor validiert und evaluiert.

Eine einmal unter einem Referenz-Cap trainierte Policyholder-Policy darf nicht
unverändert auf andere fixe oder flexible Caps übertragen werden. Umgekehrt
darf nicht für jede Kombination aus Pfad, Jahr und Cap ein vollständiger neuer
Portfolio-Subprozess gestartet werden. Kontrollpfade, gemeinsame State-
Matrizen und gemeinsame Cashflow-Primitiven sind über die Cap-Alternativen zu
nutzen.

Im LSMC-Modus werden statistische Ordinary-/Performance-Lapses und freiwillige
Withdrawals nicht zusätzlich zur optimalen Exercise-Policy angewandt. Die
finale wirtschaftliche Bewertung erfolgt immer als unabhängiger Forward-
Rollout durch den monatlichen Produktprojektor. Regressions- oder Bellman-Werte
sind Diagnostik und dürfen nicht als realisierter CSM ausgegeben werden.

## Cashflowzuordnung zu einem Cap-Jahr

Die Zuordnung folgt dem wirtschaftlichen Ereignis innerhalb eines Anniversary-
Timestamps und nicht allein der Spaltennummer des monatlichen Cashflow-Arrays.

| Cashflow / State-Änderung | Zugeordneter Control-Zeitraum |
|---|---|
| Annual Credit an `t_y` unter `C_{y-1}`, Fee Posting, Mortality und Election vor der neuen Cap-Wahl | Konsequenz des beendeten Jahres unter `C_{y-1}`; pre-action für `C_y` |
| Crediting Margin und Hedge Execution Cost beim Restart an `t_y` | Neuer Cap `C_y` |
| Income, Partial Withdrawal, Full Withdrawal und daraus entstehende Fee-/MVA-/APS-Buchungen nach der Cap-Bekanntgabe an `t_y` | Neuer Cap `C_y`, weil diese Cashflows beziehungsweise Aktionen nach dessen Bekanntgabe liegen |
| Cashflows im Intervall `(t_y,t_{y+1})` | Neuer Cap `C_y` |
| Fees, Claims und sonstige End-of-year-Flows an `t_{y+1}`, soweit sie vor der Wahl von `C_{y+1}` entstehen | Beendetes Jahr unter `C_y` |
| Time-zero Acquisition Expense | Cap-unabhängiger New-Business-Cashflow; für Reconciliation konventionell dem ersten Control-Jahr zugeordnet |
| Finaler Closeout ohne neues Projektionsjahr | Letztes tatsächlich gelaufenes Cap-Jahr; kein fiktiver neuer Cap/Hedge-Start |

Weil mehrere Vor- und Nach-Action-Ereignisse dieselbe monatliche Spalte teilen,
muss die gekoppelte Backward Induction diese Eventblöcke getrennt erfassen.
Die bestehende Auszahlungstiming- und Cashflowreihenfolge des Projektors wird
dabei nicht geändert. Der unabhängige Forward-Rollout muss weiterhin exakt auf
die normalen Cashflowkomponenten und die Portfolioaggregation reconciliieren.

## Sample-Trennung, Common Random Numbers und Fallbacks

Es werden mindestens drei disjunkte Mengen vollständiger Markt- und
Kontrollpfade verwendet:

| Sample | Zulässige Verwendung | Unzulässige Verwendung |
|---|---|---|
| Training / Cross-Fitting | Regressionen beider Wertfunktionen, Fold-interne Targets und Diagnose | Finale Policywahl anhand Evaluationsergebnissen |
| Validation | Stabilitätsprüfung, Hyperparameter-/Fallback-Entscheidungen, Vergleich flexible Policy gegen bestes fixes Cap | Nachträgliches Refit auf Evaluationpfaden |
| Evaluation | Einmaliger finaler Out-of-sample-Forward-Rollout und berichtete Werte/Standardfehler | Regression, Policy-Screening oder Fallback-Auswahl |

Folds beziehen sich auf vollständige Markt-/Kontrollpfade, nicht auf einzelne
Jahre oder Cap-Beobachtungen. Die drei Samples müssen unterschiedliche,
berichtete Scenario-Fingerprints besitzen. Innerhalb eines Samples werden für
faire Vergleiche Common Random Numbers verwendet; Differenzen und
Standardfehler werden gepaart berechnet.

Für jeden fixen Cap wird die Policyholder-LSMC cap-konsistent neu trainiert.
Insbesondere gelten folgende konservative Fallbacks:

- Ist eine Policyholder-Regression instabil, nicht ausreichend belegt oder im
  Validation Sample schlechter als `CONTINUE`, wird für die betroffene
  Signature/Entscheidung `CONTINUE` eingesetzt.
- Übertrifft die adaptive Cap-Policy das auf dem Validation Sample gewählte
  beste fixe Cap nicht hinreichend deutlich, wird das beste fixe Cap als
  deployte Policy verwendet.
- Ein statistisch nicht belastbarer Vorteil, ein Rand-Cap oder ein
  Regressions-/Policy-Tie wird nicht in einen künstlich positiven
  Flexibilitätswert umgedeutet.
- Jeder Fallback, sein Auslöser und der tatsächlich deployte Policytyp werden
  in Provenienz und Outputs explizit ausgewiesen.

## Nichtantizipation und erforderliche Invarianten

Die implementierte Policy muss folgende Eigenschaften konstruktiv und durch
Tests einhalten:

- Änderungen zukünftiger Returns, Discount Factors oder Caps verändern keine
  frühere Versicherer- oder Policyholder-Aktion.
- `C_y` verändert den pre-action Versicherer-State `X_y^-` nicht, darf aber den
  nach Bekanntgabe liegenden Policyholder-State `Z_{m,y}(C_y)` beeinflussen.
- Growth Surrender ist null.
- Full Withdrawal am Income-Election-Timestamp ist null.
- Full Withdrawal bei Surrender Value null gegen Aufgabe einer positiven
  Income-Garantie ist null, auch für einen externen LSMC-Hook.
- Mortality, In-force Weights, Fees und Payments bleiben die des bestehenden
  Monatsprojektors.
- Ein Hedge-/Crediting-Margin-Toggle verändert bei identischen
  Policyholder-Cashflows keine Policyholder-Best-Response.
- Im LSMC-Modus werden statistische Lapses nicht parallel zur optimalen
  Full-Withdrawal-Policy angewandt.

## Modellgrenzen

- Die Bewertung ist risikoneutral und verwendet standardmäßig
  Heston-Hull-White. Das Stackelberg-Ergebnis ist eine markt-konsistente
  Design-/Bewertungsgröße, keine Real-World-Verhaltensprognose.
- Die Marktpfade laufen bis der jüngste Covered Policyholder 120 Jahre alt
  wäre. Die bestehende Mortality-Tabelle besitzt jedoch den harten
  `q_x=1`-Sentinel bei Alter 115; deshalb ist die vertragliche In-force-
  Exposure danach null. Das Markt-Horizon-Ende erzeugt keinen zusätzlichen
  Cap-/Hedge-Start.
- Der DVA ist der bestehende moment-matched Proxy auf den vollständigen
  Reference Fund. Der Hedge-Volatility-Spread ist eine separate insurer-only
  Execution-Cost-Annahme.
- Der Bond Sleeve bleibt der monatlich rollierende fünfjährige nominale
  australische Staatsanleihen-Proxy. Es werden keine Credit Spreads, Ausfälle,
  FX-Kosten oder zusätzliche Term Premia eingeführt.
- Caps werden nur jährlich und ausschließlich aus der dokumentierten diskreten
  Menge gewählt. Intra-year Cap-Änderungen sind ausgeschlossen.
- Die flexible Cap-Studie ist ein Gegenfaktual zur vertraglichen 6%-Case-Study-
  Konvention und muss entsprechend gekennzeichnet werden.
- Regressionen approximieren das Gleichgewicht nur innerhalb der gewählten
  State-, Basis- und Policyklasse. Out-of-sample-Validation und Fallbacks sind
  deshalb Teil der Gleichgewichtsimplementierung, kein optionales Reporting.
- Der direkt projizierte adaptive Rollout friert die Caps exakt kausal über
  aufeinanderfolgende Zeitpräfixe ein. Das vermeidet Look-ahead, ist mit dem
  derzeit monolithischen Projektor aber quadratisch in der Zahl der
  Policyjahre. Ein schnellerer exakt äquivalenter Rollout würde einen
  synchronisierten, checkpointbaren Monatsprojektor für alle Portfoliozweige
  erfordern; diese Architektur ist noch nicht implementiert.
- Joint-Life- und Single-Life-Fallback-Policys bleiben bis zu ihrer jeweiligen
  Best Response getrennt. Die bestehende Einschränkung fehlender separater
  p11/p10/p01 Account-Value-Kohorten ist offenzulegen.
- Der aktuell angekündigte Cap wird explizit als `announced_cap` im read-only
  `SurrenderDecisionContext` übergeben; der separate Leader-State wird davor
  über `CreditingCapDecisionContext` beobachtet. Beide Schnittstellen enthalten
  weder Future-Pfade noch Hedge-P&L oder Backing Assets.
