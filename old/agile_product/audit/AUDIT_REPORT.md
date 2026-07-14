# Unabhängiger Audit der AGILE Modelling Engine

> **Historischer Stand:** Dieser Bericht dokumentiert den früheren
> AGILE-spezifischen Research-Stand. Er beschreibt weder das aktive generische
> Fallprodukt noch den neuen Portfolio-Bewertungspfad. Maßgeblich sind heute
> `README.md`, `METHODOLOGY.md` und
> `portfolio_simulations/README.md`.

Stand: 10. Juli 2026  
Geprüfter Scope: Produktspezifikation, Pricing/ESG/DVA, Mortalität, Verhalten,
LSMC, Kapital, Profitabilität, Sensitivitäten, Tests und Paketierbarkeit.

> **Letzter Stand dieses historischen Audits (Version 1.5.0):** Dieser Audit dokumentiert auch den
> historischen LSMC-Forschungsstand. LSMC ist inzwischen aus öffentlicher API,
> CLI und allen verwendeten Bewertungs-/Projektionspfaden ausgeklammert; nur der
> archivierte Quellcode bleibt erhalten. Maßgeblich für den aktuellen
> dynamischen Behaviour-Pfad ist
> `../documentation_and_background_info/Policy_Behaviour_Modellierung.md`.

## Gesamturteil

Die ursprüngliche Implementierung war ein anspruchsvoller Research-Prototyp,
aber keine Production-Level-Engine. Mehrere Fehler konnten Ergebnisse materiell
verändern. Besonders gravierend waren die falsche Lifetime-Income-Ratecard,
abgeschnittene Joint-Life-Cashflows, eine zu hohe Anniversary-Income-Basis,
ein doppelt gezählter LSMC-Terminalwert und die falsche Behauptung, das
Solvency-II-artige Kapitalmodul könne durch Parameterwechsel APRA/LAGIC werden.

Version 1.3 behebt die klar determinierbaren Implementierungsfehler. Sie bleibt
bewusst als **Research Engine** gekennzeichnet, weil mehrere erforderliche
Produkt-, Bestands-, Admin- und Regulierungsdaten nicht vorliegen.

### Nachprüfung und zusätzliche Korrekturen in Version 1.3

Eine zweite, unabhängige Prüfung gegen das PDS vom 19. Januar 2026, die
Juli-2026-Rate-Sheets, die Paper-Methodik und den tatsächlich ausgeführten Code
hat weitere materielle Fehler gefunden und behoben:

- Die Vertragsindizes sind Return-Indizes. Die früheren Dividend-Yield-Defaults
  von 4%/2% zählten Dividenden doppelt und verzerrten Forward und Optionskosten;
  der Default-Carry ist jetzt null.
- Age Pension+ beginnt funding-spezifisch. Partial/Full Withdrawals verwenden
  den korrekten Lower-of-Test, buchen bei bindendem MWV kein MVA und reduzieren
  IV/Income gemäß PDS-Beispiel; frühere Withdrawals reduzieren auch den Death
  Cap, der bei Half Life Expectancy auf den MWV springt.
- Die 95%-Grenze je Growth-Withdrawal und die zusätzliche kumulative
  95%-Grenze pro Anniversary Year werden inklusive MVA durchgesetzt.
- Der Cat-Schock ist vom Kalenderoffset der Mortality-Tabelle getrennt und
  wirkt nun tatsächlich in den ersten zwölf Projektionsmonaten.
- Nachschüssiges Income wird nur an zum Zahlungstermin Überlebende gezahlt;
  Todesfälle erhalten den pre-payment Investment Value.
- Fremde Szenarien werden auf Seed, Pfadzahl, Horizont und Heston-Substeps
  geprüft und als immutable Snapshots gehalten. Kapital-Provenienz umfasst
  Stresssatz und Risk-Margin-Schalter; `include_capital=False` ist bindend.
- Stochastische Zinsen gehen pfadweise in Behaviour-Moneyness ein; IRR und
  Integer-/Boolean-Validierungen wurden gehärtet.
- Das kapazitätsbegrenzte 2%-Bonusangebot kann über
  `PolicySpec.bonus_interest_pct` modelliert werden, bleibt wegen möglicher
  vorzeitiger Erschöpfung bewusst kein Default und wird als Akquisitionskosten
  des Versicherers erfasst.

## Durchgeführte Korrekturen

1. **Offizielle Juli-2026-Ratecard**
   - Guaranteed Minimums auf 0,25 % (Total Protection) und 0,50 % (Partial
     Protection) korrigiert.
   - Vollständige Male/Female-, Fixed/Rising-, Single/Spouse- und
     Age-Pension+-Matrix für Alter 50–80 aufgenommen.
   - Age-Based Rate verwendet jetzt Alter und Geschlecht am Product
     Commencement; bei Spouse die jüngere Person.
   - Alters- und Fixed/Rising-abhängige Annual Income Escalators ersetzen den
     früheren pauschalen 10-bp-Escalator und die unbelegte 20-Jahres-Grenze.

2. **Joint-Life-Tail**
   - Default-Projektionshorizont reicht beim Continue-Income-Pfad bis zum
     terminalen Alter des jüngeren Lebens.
   - Der Joint-Life-Annuity-Factor verwendet ebenfalls die längere der beiden
     Restlebensdauern. Damit ist er nicht mehr kleiner als der Faktor des
     jüngeren Single Life.

3. **Income-Commencement-Reihenfolge**
   - Am Anniversary werden Return und die bis dahin modellierte Gebühr zuerst
     verarbeitet; erst danach werden Lifetime Income und CAS Base fixiert und
     die neue DVA-Periode gestartet.
   - Gebührenbasis ist Investment Value ohne den aktuellen DVA-Anteil.

4. **Mortalität**
   - `PolicySpec.commencement_year` verankert Mortality Improvements korrekt am
     `MortalityTable.base_year` (Default-Tabelle 2022, Default-Commencement
     2026,5).
   - Qx-Tabellen werden defensiv kopiert, validiert und read-only gehalten.

5. **Marktdaten und Provenienz**
   - ESG und Optionsbewertung verwenden dieselbe Dividend-Yield-Basis;
     abweichende doppelte Eingaben werden abgewiesen.
   - Fremde ScenarioSets werden auf ESG-Konfiguration und Modell geprüft.
   - Valuation- und Capital-Ergebnisse tragen einen Assumptions-Fingerprint;
     Profitability verweigert die Wiederverwendung unter anderen Annahmen.
   - Nichtmonatliche Horizonte und ungültige Pfadzahlen werden früh abgewiesen.

6. **LSMC**
   - Terminalwert zählt nicht mehr vollständigen IV plus sämtliche künftigen
     Income-Zahlungen doppelt; er verwendet einen account-aware Closeout.
   - Partial-Withdrawal-Actions beachten 95 %, AUD 2.000 Restwert und AUD 100
     Mindestentnahme.
   - Age Pension+ und off-grid Starts werden als nicht unterstützt abgewiesen.
   - Bei einem Out-of-sample-Fallback auf Static Behaviour stammen auch die
     ausgegebenen Exercise-Raten aus der tatsächlich berichteten Strategie.

7. **Kapital und Profitabilität**
   - `with_risk_margin=False` entfernt nicht mehr versehentlich den SCR-Runoff.
   - Der Risk-Margin-Runoff wird als Liability/Reserve und nicht als SCR
     behandelt.
   - PVFP diskontiert Distributable Earnings einschließlich Reserve- und
     optionaler Kapitalstrains statt bloßer Margencashflows.
   - Sensitivitäten berichten bei eingeschaltetem Kapital den VNB nach Risk
     Margin.
   - Vega wird korrekt auf einen Volatilitätspunkt normiert.

8. **Softwarequalität**
   - Wesentliche Raten, Korrelationen, Allokationen, Gebühren, Lapses,
     Take-up- und Expense-Annahmen werden validiert.
   - Mutable Maps/Arrays werden soweit praktisch defensiv eingefroren.
   - Ein `pyproject.toml` macht das Projekt installierbar.

## Verbleibende Production-Blocker

### 1. APRA/LAGIC fehlt

`capital.py` bleibt ein Solvency-II-artiger Research-Proxy. Die aktuelle
APRA-Architektur erfordert unter anderem Insurance Risk, Asset Risk, Asset
Concentration und Operational Risk Charges, Aggregation Benefit und Combined
Stress Scenario Adjustment. Dafür fehlen Statutory-Fund-Bilanz, Assets,
Derivate, Hedgepositionen, Konzentrationen, Credit/Default, FX und Inflation.
Das kann nicht durch Austausch von `CapitalStresses` behoben werden.

Offizielle Grundlagen:

- [APRA LPS 110 Capital Adequacy](https://www.apra.gov.au/standards/lps-110)
- [APRA LPS 114 Asset Risk Charge, in force 1 July 2026](https://www.apra.gov.au/standards/lps-114)
- [APRA LPS 115 Insurance Risk Charge](https://www.apra.gov.au/standards/lps-115)
- [APRA LPS 117 Asset Concentration Risk Charge](https://www.apra.gov.au/standards/lps-117)
- [APRA LPS 118 Operational Risk Charge](https://www.apra.gov.au/standards/lps-118)

### 2. Kein In-force Model Point

Jede Projektion startet bei Issue in der Growth Phase. Für Bestandsbewertung
fehlen unter anderem Duration, aktuelle Phase, IV, Locked Income, laufendes
Index-Fixing, Certificate Cap, Issue Curve/MVA State, CAS State und bereits
verbrauchter Free Withdrawal Amount.

### 3. Vertragliche Optionalität unvollständig

Fixed/Rising, Spouse, Age Pension+, Death Election und Growth Allocation sind
bedingte Szenarioeingaben. Die späteren Wahlrechte und jährliche Reallokation
werden nicht in einem gemeinsamen Vertragswert optimiert. Separate
Option-Balances fehlen; zukünftige Caps bleiben konstant, sofern keine
explizite Schedule geliefert wird.

### 4. DVA/MVA und Gebühren benötigen Admin-Reconciliation

DVA und MVA sind Bewertungsproxies, keine bestätigten Allianz-Adminformeln.
Insbesondere fehlen der vertragliche zeitanteilige DVA-Protection-Floor und
die garantierte Fixed-Return-Verzweigung; die MVA-Parameter müssen gegen echte
Transaction Quotes kalibriert werden. Gebühren werden weiterhin monatlich
direkt approximiert; der Vertrag sieht tägliche Accruals und Anniversary-/
Event-Deduction vor.

### 5. Age Pension+ und weitere Cashflows

Funding Source, Relevant Condition of Release, Growth-Phase-APS-Start und die
spezielle APS-Withdrawal-Reduktionslogik sind jetzt modelliert. Production
Model Points müssen die regulatorische CAS Life Expectancy weiterhin explizit
liefern; der rechtliche Investor-Subtyp und damit einzelne Eligibility-Regeln
fehlen weiterhin. Ongoing Adviser Service Fees, PAYG/Withholding, Cooling-off
und Reinsurance fehlen.

### 6. Kalibrierung und Model Risk

Mortality, Behaviour, Expenses, P-/Q-Market-Parameter und zukünftige
Management Actions sind nicht auf Produktionsdaten kalibriert. Es fehlen
Portfolio-Aggregation, Monte-Carlo-Standardfehler, Konfidenzintervalle,
Backtesting, Quote-Reconciliation und formale Model Governance.
P und Q teilen derzeit insbesondere Heston-Volatilitäts- und Zinsdynamik; für
Profitability fehlen Volatilitätsrisiko- und Term-Premia. Außerdem werden lange
Projektionen nicht gestreamt oder gechunked und können im Capital-Revaluation-
Lauf mehrere GB Arbeitsspeicher benötigen.

## Was fachlich bereits tragfähig war

Die Annual-Return-Payoffs für Total und Partial Protection, der AUS-TP-Ratchet
für Rising Income, die Fortzahlung nach IV-Erschöpfung, die Grundmechanik der
proportionalen Income-Reduktion sowie mehrere Martingal-/Buchungsidentitäten
waren im Kern sinnvoll implementiert. Die Paper-Auswahl für GMxB/GLWB,
stochastische Volatilität/Zinsen und Behaviour ist als Research-Basis plausibel;
sie ersetzt jedoch keine vertragliche oder regulatorische Spezifikation.
Insbesondere existiert weiterhin kein automatisierter GHQC-/Paper-Code-
Crosscheck für die LSMC-Werte; der Static-Fallback und die jährliche
Diskretisierung machen `optimal >= static` allein noch nicht zu einer
ausreichenden Validierung.

## Verifikation nach den Korrekturen

- `python -m pytest -q`: **122 passed** in 267,46 Sekunden (finaler Lauf).
- `python -m compileall -q agile_engine examples tests`: erfolgreich.
- `python -m pip install . --dry-run --no-deps`: Wheel-Metadaten erfolgreich,
  Paket `agile-modelling-engine==1.3.0` installierbar.
- Import-/Versionscheck einschließlich des neuen `FundingSource`-Exports:
  erfolgreich (`agile_engine.__version__ == "1.3.0"`).

Frühere illustrative Fair-LIP-/VNB-Zahlen werden nicht fortgeschrieben: Der
korrigierte Return-Index-Carry, das Arrears-/Death-Timing und die APS-Logik
ändern die Ergebnisse materiell. Ohne produktive Kalibrierung und APRA-Modul
wäre eine neue einzelne Base-Case-Zahl weiterhin keine belastbare Preis- oder
Profitabilitätsaussage über den realen AGILE-Bestand.

## Offizielle Produktquellen der Korrekturen

- [AGILE Lifetime Income Rates, July 2026](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Lifetime_Income_Rates_Jul26.pdf)
- [AGILE Guaranteed Minimums, July 2026](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Guaranteed_Minimums_Jul26.pdf)
- [AGILE Product Disclosure Statement, 19 January 2026](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/pds-2026/AGILE_PDS_19%20Jan_2026_F1.pdf)
- [AGILE 2% Bonus Offer, 18 May–31 July 2026 / capacity-limited](https://www.allianzretireplus.com.au/about-us/certainty.html)
