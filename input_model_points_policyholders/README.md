# Modellpunkte für die generische Portfoliobewertung

`model_points_policyholders_4_point_proxy.csv` ist der operative Default für
alle Portfolio-, Risiko- und Crediting-Strategy-Runner. Er enthält vier
gewichtete New-Business-Modellpunkte für schnelle Research-Läufe und erhält
den gewichteten durchschnittlichen Einmalbeitrag der ausführlichen Variante.

`model_points_policyholders.csv` bleibt als explizit wählbare 48-Point-
Detailvariante verfügbar. Sie stammt aus der früheren AGILE-Modellierung und
bildet vier Eintrittsalter, zwei Geschlechter, Single-/Joint-Life und drei
Einmalbeiträge ab. Beide Dateien werden ausschließlich als demografische und
prämienbezogene Portfolioeingabe für das generische Produkt verwendet. Ein
abweichender Bestand kann weiterhin über `--model-points` gewählt werden.

## Gewichtung

- `contract_weight` ist das Aggregationsgewicht für Barwerte.
- `premium_volume_weight` ist nur eine Exposure- und Kontrollgröße. Es darf
  nicht zusätzlich zum Vertragsgewicht zur Skalierung desselben Barwerts
  verwendet werden.
- Die Gewichte werden mit zwölf Nachkommastellen gespeichert. In beiden
  gelieferten Dateien summieren sich `contract_weight` und
  `premium_volume_weight` jeweils auf 1. Der Rundungsausgleich von
  0,000000000003 im letzten Prämienanteil betrifft die 48-Point-Datei.
- Der gewichtete durchschnittliche Einmalbeitrag beträgt in beiden Dateien
  AUD 336.982,1762.
- Da sich `contract_weight` auf 1 summiert, ergibt die unmittelbare Aggregation
  einen gewichteten Barwert je Durchschnittsvertrag. Absolute
  Portfoliobarwerte erfordern zusätzlich die gesamte Vertragsanzahl `N_total`:

  `PV_portfolio = N_total * sum(contract_weight_i * PV_i)`.

  `N_total` ist in der CSV nicht enthalten. Ohne eine extern vorgegebene
  Vertragsanzahl dürfen Ergebnisse daher nur als normalisierte
  Durchschnittsvertragswerte ausgewiesen werden.

Der Loader akzeptiert zusätzlich die optionale Spalte `exposure_count`. Wird
sie geliefert, muss sie je Modellpunkt positiv sein und mit `contract_weight`
reconciliieren. Dann kann der Runner die absoluten Modellpunkt- und
Portfoliobarwerte direkt aus `sum(exposure_count_i * PV_i)` bestimmen. Ohne
diese Spalte ist `--portfolio-contract-count` die einzige Quelle einer
absoluten Bestandsgröße; die Zahl der CSV-Zeilen wird nicht als Vertragsanzahl
interpretiert.

## Verwendung im generischen Portfolio-Runner

Für die generische Portfoliobewertung werden insbesondere Demografie, Prämie,
Single-/Joint-Life-Ausprägung und Spouse-Daten verwendet. Standardmäßig sind
dies die vier Proxy-Modellpunkte; für detailliertere Läufe können explizit die
48 Modellpunkte geladen werden. Alle Zeilen beider Dateien beschreiben derzeit
New Business mit Policendauer null und Start in der Growth-Phase.

Der generische Reference Fund ist eine feste 50/50-Kombination aus Global
Equity und nominalen australischen Staatsanleihen mit fünfjähriger konstanter
Restlaufzeit. Deshalb gelten folgende Felder als Legacy-AGILE-
Metadaten:

- `product_id` und `product_pds_version`,
- `allocation_aus_tp`, `allocation_aus_pp10`,
  `allocation_global_tp` und `allocation_global_pp10`.

Der Portfolio-Runner validiert diese Felder auf konsistente Legacy-Eingaben,
verwendet sie aber weder zur Auswahl des generischen Produkts noch zur
Bestimmung der Fondsallokation. Insbesondere wird die in der Datei enthaltene
100-%-AGILE-Allokation nicht als Kundenallokation des generischen Produkts
interpretiert.

Weitere einheitliche Merkmale des gelieferten New-Business-Bestands sind:

- Commencement Mitte 2026, Vertragsdauer null und Phase `growth`;
- Superannuation-Funding, Fixed Income nach fünf vollständigen Growth-Jahren;
- kein Age Pension+, Adviser Fee, Bonus oder geplante Partial Withdrawal;
- bei Joint Life wird die Fortsetzung des Einkommens nach Tod der primären
  versicherten Person unterstellt;
- produktweite Kosten- und Gebührenannahmen sind bewusst nicht Teil der
  Modellpunkte;
- die AGILE-PDS-, Ratecard- und Cap-Angaben bleiben ausschließlich als
  nachvollziehbare Herkunfts- und Kontrollfelder erhalten.

`income_start_year` ist im aktuellen Portfolio-Runner ein expliziter,
deterministischer Election-Termin und hat Vorrang vor dem dynamischen
Take-up-Hazard. Der effektive Termin ist das Minimum aus diesem Quellwert und
dem vertraglichen automatischen Start nach Alter 100. Für Joint-Life-
Modellpunkte wird die Spouse-Survival-Wahrscheinlichkeit bis zu diesem Termin
berechnet; der nicht mehr für Spouse Income qualifizierte Anteil wird als
Single-Life-Fallback bewertet. Im bedingt gemeinsamen Continue-Income-Zweig
werden state-unabhängige statische Behaviour-Basisraten verwendet; der
Single-Life-Fallback bleibt dynamisch.

`derived_lifetime_income_rate_at_start` ist ein aus der Juli-2026-Ratecard
abgeleitetes Legacy-Kontrollfeld, kein eigenständiger Input der generischen
Bewertung.

## AGILE-spezifische Abgrenzung

Die primäre und gegebenenfalls sekundäre Person sind versicherte Personen;
sie sind nicht mit Investor, Trustee oder rechtlichem Group-Policyholder
gleichzusetzen.

AGILE besitzt keinen separaten klassischen GMWB-Guarantee-Base-State.
Deshalb enthält die Datei `investment_value_0_aud` und
`locked_income_0_aud`, aber kein künstliches `guarantee_base_0`. Das
Lifetime Income wird beim späteren Income Start aus dem dann vorhandenen
Investment Value und der Ratecard festgesetzt.

## Marktmodell-Referenzen

Marktdaten und Marktmodellparameter werden nicht in dieser Datei dupliziert.
Die Spalten `market_parameter_set_id` und `yield_curve_id` verweisen auf:

- `../AGILE_Modelling_Engine/input_market_data/model_parameters.csv`
- `../AGILE_Modelling_Engine/input_market_data/australian_zero_curve.csv`

Die referenzierten IDs sind `realistic_base_2026-06-30` und
`aud_government_zero_2026-06-30`.
