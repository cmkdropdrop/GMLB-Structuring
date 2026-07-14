# Unabhängiger Review Report: AGILE Modelling

**Prüfstichtag:** 11. Juli 2026  
**Prüfrollen:** wissenschaftlicher Gutachter, Aktuar, Quantitative-Finance-Spezialist, Modellvalidierer und Fachlektor  
**Geprüfter Engine-Stand:** 1.3.0  
**Gesamturteil:** reviewed research prototype; nicht freigabefähig für Pricing, Reservierung, APRA/LAGIC, Hedging oder Portfolioaussagen

## 1. Gesamturteil

Die zentralen Juli-2026-Produktfakten und sämtliche im Fachpaper berichteten
1.2.0-/1.3.0-Ergebniszahlen sind gegen Primärquellen beziehungsweise die
lokalen CSV-/JSON-Dateien erfolgreich geprüft worden. Insbesondere stimmen
Caps, Guaranteed Minimums, die Basis-Lifetime-Income-Rate von 8,80 %, Fees,
Gross VNB, Non-unit BEL, Guarantee Value, Fair LIP, Kapitalproxy, Risk Margin,
PVFP, IRR, Payback, Sensitivitäten, Customer Outcomes, Designs, Timing,
Modellvergleich, Seed-Studie und Versionsdifferenzen bis auf die ausgewiesene
Rundung. Es wurde **keine falsche materielle Basiszahl** gefunden.

Eine Produktionsfreigabe ist dennoch nicht vertretbar. Der unveränderte
Standard-Runner bricht in der öffentlichen `greeks()`-API ab; das Manifest
attestiert den erfolgreichen Lauf nicht vollständig; der Heston--Hull--White-
COS-Cross-Term ist mathematisch nicht die behauptete unabhängige exakte
Gauß-Varianz; mehrere Produktzweige und APRA-Komponenten fehlen; Mortalität,
Verhalten, Kosten und Marktparameter sind illustrativ. Der instrumentierte
Workaround reproduziert die Zahlen stark, ersetzt aber keinen geprüften
Sourcefix und keine vollständige Provenienz.

Die neue Datei `AGILE_Modelling_Fachpaper_reviewed.md` korrigiert die
materiellen Aussagen, trennt Produktfakt, Modellannahme, Ergebnis und
Interpretation deutlicher und kennzeichnet verbleibende offene Punkte. Die
Engine und alle Ausgangsdateien wurden nicht verändert.

## 2. Scope und Dateiinventur

| Datei/Artefakt | Bytes | SHA-256 des geprüften Originals |
|---|---:|---|
| `AGILE_Modelling_Fachpaper.md` | 75.082 | `B27FEA58845C7A6F7BBF8B5DE953C7CB273E8969B5E4B9BAE1BE7C8ED0EEA41E` |
| `AGILE_Modelling_Fachpaper.docx` | 1.783.805 | `6992976907BE4EECC509ADD05E4C9AB9AA9A84F24505A030681A2F6F168434AB` |
| `AGILE_Modelling_Fachpaper.pdf` | 1.458.887 | `AB0AFD6BDBFFAB3390679ABFB2FF41910CBF54E63691B1A9F4FF0BCB80480CCE` |
| `AGILE_Modelling_references.bib` | 11.773 | `A6BEFEC73AD7C7525EA3260B88A24B27A3830CCECCD7C32D88C8EA37F8513240` |
| `AGILE.md` | 42.266 | `184A7446F2E2C8D0F334FC91F28F874D36947B65A613326BA79302A501E52E9D` |
| Engine-Runner `run_insurer_analysis.py` | 65.115 | `8EA89D2F1C99940E74551402288D8835C4799FDBAC18B9C9784C79433B63A244` |
| manifestierter Engine-Source-Bestand `agile_engine/*.py` | — | `503B509175810F3E7A9105C372D7AE6E6741D3CB4178461382305DCBAA360E46` |

Vollständig gelesen beziehungsweise geprüft wurden das Paper, `AGILE.md`,
README, METHODOLOGY, AUDIT_REPORT, relevante Engine-Module, Tests, Runner,
beide Ergebnisverzeichnisse, Bibliografie und der lokale Literaturindex. Die
Produktprüfung verwendete das PDS vom 19. Januar 2026, alle drei statischen
Juli-2026-Rate-Sheets einschließlich Maximum Returns sowie die aktuellen APRA-
Standards LPS 110, 114, 115, 117 und 118.

Die Claim-to-Evidence-Matrix enthält 93 materielle Claims: 31 Produktfakten,
26 Modellannahmen, 30 Ergebnisse und 6 Interpretationen.

Neu erzeugt wurden die reviewed Markdown-, BibTeX-, DOCX- und PDF-Fassung,
dieser Report, die Claim-to-Evidence-Matrix und das Änderungsprotokoll. Die
Originale und die Engine blieben bytegenau unverändert.

## 3. Befunde HOCH

### H-01 — `greeks()` und unveränderter Standard-Runner brechen ab

- **Fundstelle:** Paper Abschnitt 12.4; `pricing.py:251–265`; `esg.py`-Definition von `ScenarioSet`; Runner Greek-Block.
- **Geprüfte Aussage:** 122 grüne Tests belegten einen lauffähigen Analysepack.
- **Evidenz:** `ScenarioSet` ist frozen; `greeks()` weist nach `copy.copy` an `scen.index_levels` zu. Direktlauf mit Originalpfaden: Exit 1 nach 18,5 s, `FrozenInstanceError`.
- **Begründung:** Tests rufen weder `greeks()` noch den End-to-End-Runner auf. Der Pack ist nur instrumentiert erzeugbar.
- **Korrektur:** Paper bezeichnet den Lauf als instrumentiert; empfohlener Sourcefix ist `dataclasses.replace` plus API- und Runner-Regressionstest. Engine-Code blieb unverändert.

### H-02 — Manifest und Source Hash binden den tatsächlichen Lauf nicht

- **Fundstelle:** Paper Abschnitt 2.2/12.4; Runner `source_hash()` und Manifestaufbau.
- **Geprüfte Aussage:** Manifest/Hash ermöglichten vollständige Reproduktion.
- **Evidenz:** Der Hash umfasst nur Dateinamen und Bytes von `agile_engine/*.py`. Runner, Prozesspatch, Kommandozeile, Tests, externe Inputs und Output-Hashes fehlen. Die Provenienz-IDs decken nur Valuation/Capital.
- **Begründung:** Derselbe Hash beschreibt sowohl den abstürzenden Originalrunner als auch den erfolgreichen Patchlauf.
- **Korrektur:** Vollständiges Run-Bundle-Manifest mit Engine-, Runner-, Patch-, CLI-, Input- und Output-Hashes sowie blockweisen Provenienz-IDs fordern.

### H-03 — Heston--Hull--White-COS-„Gaussian add-on“ ist nicht exakt

- **Fundstelle:** METHODOLOGY; `esg.py:rate_gauss_var`; `crediting.py`; `projection.py`; `test_heston_cos.py`; reviewed Paper Abschnitt 5.6.
- **Geprüfte Aussage:** unabhängige Gauß-Varianz, exakte Komposition, martingalerhaltend.
- **Evidenz:** Für AUS/1 Jahr gilt im Default `Var_r=2,0860e−5`, `2Cov=−2,5346e−4`, also `w=−2,3260e−4`. Der CF-Faktor verwendet das negative `w`; nur das Truncation-Intervall clippt auf null. Der „exact“-Test deckt nur einen positiven Black--Scholes-Grenzfall ab.
- **Begründung:** Eine negative Größe ist keine Varianz eines unabhängigen Gauß-Faktors. Es liegt eine hybride Näherung vor.
- **Korrektur:** „exact composition“ streichen; Ratevarianz und Cross-Effekt trennen; Joint-Monte-Carlo- oder gemeinsame Transform-Benchmark verlangen. Heston--HW-Ergebnisse nur als Näherung interpretieren.

### H-04 — APRA-Architektur war unvollständig belegt

- **Fundstelle:** Ausgangspaper Abschnitt 8.3 und Bibliografie.
- **Geprüfte Aussage:** Einzelpolicen-SII-Proxy sei kein APRA/LAGIC-Ergebnis.
- **Evidenz:** LPS 110 definiert PCA-Komponenten/Aggregation; LPS 114 Asset Risk; LPS 115 stressed policy liabilities; LPS 117 Konzentrationen; LPS 118 Operational Risk.
- **Begründung:** Schlussfolgerung war richtig, aber drei unmittelbar einschlägige Standards fehlten. Ob AGILE Attachment-A-Variable-Annuity-Business ist, ist öffentlich nicht belegt.
- **Korrektur:** Alle fünf Standards ergänzt; APRA-Klassifikation als OFFEN gekennzeichnet.

### H-05 — `deng2017` hatte falsche Autorenvornamen und nicht auflösenden DOI

- **Fundstelle:** Ausgangsbibliografie `deng2017`.
- **Evidenz:** Offizielle Risk.net-Seite nennt Geng Deng und Mike Yan. `10.21314/JCF.2017.331` lieferte bei doi.org, doiRA und Crossref am 11.07.2026 keinen Datensatz.
- **Korrektur:** Namen korrigiert, DOI-Feld entfernt, stabile Publisher-URL verwendet. Titel/Journal/Band/Heft/Seiten bleiben bestätigt.

### H-06 — Falscher DOI im lokalen Literaturindex

- **Fundstelle:** Index A19.
- **Evidenz:** `10.1016/j.insmatheco.2024.04.001` gehört zu einem anderen Paper. Für Bégin/Sanders, *Benefit Volatility-Targeting Strategies*, ist `10.1016/j.insmatheco.2024.05.006` korrekt.
- **Korrektur:** Fehler im reviewed Paper dokumentiert; nicht in die Kernbibliografie übernommen, weil kein Claim diese Quelle benötigt.

### H-07 — Lokale B3-Datei ist keine Drei-Autoren-Journalfassung

- **Fundstelle:** `2025_Begin_Optimal-Hurdle-Rate-Lifetime-Pension-Pools.md`.
- **Evidenz:** Datei ist Yingfei Suns MSc-Thesis; Bégin/Sanders sind Supervisors. Die echte VOR erschien 2026 in *ASTIN Bulletin* 56(2), 389–419, DOI `10.1017/asb.2026.10090`.
- **Korrektur:** Metadatenrisiko konkret im reviewed Paper beschrieben; keine unbelegte Zitation aufgenommen.

## 4. Befunde MITTEL

| ID | Fundstelle | Geprüfte Aussage | Evidenz/Begründung | Umgesetzte Korrektur |
|---|---|---|---|---|
| M-01 | Zusammenfassung/3.1 | Garantie/Group Policy verkürzt | PDS S. 2, 83–85: specified beneficiary, verfügbare Fund-Assets, Cessation, keine Allianz-SE-Garantie | Rollen und Garantieumfang präzisiert |
| M-02 | 3.1/12.6 | nur freiwilliger Income Start | PDS S. 17/75: automatische Transition, Default Fixed ohne Spouse, möglicher Full Withdrawal bei fehlenden Kontakt-/Bankdaten | Vertragsevent, PDS-Vorbehalt und Engine-Lücke ergänzt |
| M-03 | 3.2 | Juli-Caps nur für Commencement; Minimum als Renditefloor | statische Juli-Sheets | Anniversary-Vintage und Begriffskorrektur |
| M-04 | 3.3 | Payoffformeln universell | PDS Fixed-Return-Zweig | Formeln auf marktgebundene Branch begrenzt |
| M-05 | 3.8 | DVA nur YTD-Return | PDS S. 62–63: Derivatewert, pro-rata Cap/Protection/Fixed Return | Detailmechanik und Engine-Lücke ergänzt |
| M-06 | 3.8/3.9 | gewöhnliche Withdrawal-Proportionalität gilt auch mit Age Pension+ | PDS Lower-of-/MWV-Mechanik | gesonderte Logik, Limits und MVA-Behandlung ergänzt |
| M-07 | 3.9 | Age Pension+ jederzeit aktivierbar | PDS funding-/release-/age-spezifische Election/Commencement; Non-super-Trustee-/Company-Ausschluss mit Platform-Trustee-Ausnahme | Timing, konkrete Eligibility, CAS-Vintage ergänzt |
| M-08 | 3.9 | Spouse-Pfad nur Modellinput | PDS: Inhaber/Eligibility/Default vom Ownership-Pfad | Wahlrecht und Default präzisiert |
| M-09 | 11.7 | Spouse-Resultate ohne Zusatzmodellpunkt | Runner: Frau 63, `continue_income` | Annahme vor Tabelle offengelegt |
| M-10 | 3.7 | Fees dauerhaft vertraglich fix | PDS Änderungsrecht; Engine konstant | Konstanz als Modellannahme |
| M-11 | 6.3 | Off-anniversary Moneyness nutzt Surrender Value | Helper nutzt IV bis nächsten Anniversary | Pfadabweichung/Proxy erklärt |
| M-12 | 7.4 | `p_z≤1` ist Identität | BS-Gegenbeispiel Cap 50 %: `p_z=1,0449739` | nur für finanzierbaren Basisfall; negative Margin zugelassen |
| M-13 | 7.2 | `bel_total` ist regulatorischer Total BEL | interne Engine-Konvention; AGILE nicht unit-linked | kein APRA/AASB/IFRS-Label |
| M-14 | 9.3 | LSMC-Ausgabe ist strikter Lower Bound | MC-Schätzer plus samplebasierter `max(opt,static)` | Population-/Schätzerunterschied und Selection Bias erklärt |
| M-15 | 9.4 | LSMC entspricht Monatsmotor-Tail | Alter 105, 30Y-Zero, $\max(IV,I\times AF)$-Closeout, Joint Life ab Issue; Static Policy nicht voller Monatsmotor | Grenzen und fehlende Like-for-like-Vergleichbarkeit ergänzt |
| M-16 | 11.5 | Expenses +10 % stresst alle Kosten | nur Maintenance-Komponenten ×1,1 | Tabellenzeile umbenannt |
| M-17 | 8.5/11.4 | 30-%-Tax berücksichtigt Verlustvorträge | sofort symmetrische Entlastung auch bei Verlusten | Tax-Annahme offengelegt |
| M-18 | 11.1 ff. | Cent-/Vierdezimalwerte sind statistisch präzise | SEs fehlen für Fair LIP/Capital/RM/PVFP/IRR/Designs | KPI-Tabelle gerundet; Warnhinweis ergänzt |
| M-19 | 11.10 | 600-Pfad-Modellspanne ist reines Modellrisiko | keine modellweisen SEs; Quotient 37,761≈38 | „unbereinigte Spanne“, 38, starke Qualifikation |
| M-20 | 11.6/Manifest | Outcome-Seed 2026 | Funktion nutzt `seed+1=2027` | effektiven Seed und Manifestlücke erklärt |
| M-21 | 11.12 | Versionsdelta ist reines Implementation Risk | bündelt Code, Annahmen, Definitionen | als Versionsattribution bezeichnet |
| M-22 | Literatur | lokale Methodology/Run-Einträge unzitiert | konkrete Aussagen beruhten darauf | `agilemethodology2026`/`agilerun2026` zitiert |
| M-23 | Literatur | qualitative externe „Materialität“ sei AGILE-spezifisch | Originalstudien untersuchen andere GLWB-Modellpunkte | Scope ausdrücklich begrenzt |

## 5. Befunde NIEDRIG und OFFEN

### NIEDRIG

- `APS` war als sichtbares Produktlabel missverständlich; es ist nur internes
  Engine-Kürzel. Fließtext und Tabellen verwenden jetzt Age Pension+.
- `Gender` wurde auf die PDS-Definition präzisiert.
- Die Modellspanne wurde von „rund 37“ auf mathematisch gerundete 38 geändert.
- `reconciliations.csv` zeigt `1,96×SE`, während der PASS-Test die weitere
  Schwelle `max(0,25 %,3SE)` nutzt; Status bleibt unter beiden korrekt.
- Online-first-/Issue-Datum bei Fang/Oosterlee und Körperschaftsurheber des
  Actuaries-Institute-Papers wurden bibliografisch präzisiert.

### OFFEN

1. **Equal-age-/fractional-age-Rating:** Öffentliche Unterlagen regeln weder
   die Gender-Tie-Regel für gleich alte Ehepartner noch die Interpolation
   nichtganzzahliger Commencement-Alter. Engine-Regeln sind nicht als
   Produktfakt freigegeben.
2. **APRA-Klassifikation:** Öffentliche Quellen belegen nicht, ob AGILE als
   `variable annuity business` nach LPS 110 Attachment A behandelt wird oder
   welche Methode APRA gegebenenfalls genehmigt hat.

## 6. Numerische Reconciliation

| Größe | unabhängige Rekonstruktion | Status |
|---|---:|---|
| Gross VNB | `2.269,8434 + 8.701,0665 + 9.923,4505 + 217,3672 − 18.780,8056 − 3.558,5689 = −1.227,6468` | PASS |
| Non-unit BEL | `+1.227,6468` | PASS |
| Guarantee Value | `18.780,8056 − 8.701,0665 = 10.079,7392` | PASS |
| Fair-LIP-Lücke | `185,4156 bp` | PASS |
| Customer Benefit PV | `69.417,9605 + 12.537,7998 + 15.544,3950 = 97.500,1553` | PASS |
| Q-finanzierter PV | `99.831,0774`; Residual `−168,9226`; Gap `−0,1689226 %` | PASS innerhalb beider Run-Schwellen |
| Life SCR | `3.896,0212` aus Manifest-Korrelation | PASS |
| BSCR | `17.205,2994` | PASS |
| Risk Margin | `0,06 × Σ LifeSCR×Pattern×P(0,t+1) = 4.687,2625` | PASS |
| VNB nach RM | `−5.914,9093` | PASS |
| PVFP | `Σ DE_y/1,08^y = −12.898,9599` | PASS |
| IRR | `3,5191988 %`, NPV etwa `1,26e−7` AUD | PASS |
| Payback | Jahr 23 | PASS |

Alle Sensitivitäts-, Outcome-, Design-, Timing-, Behaviour-, Modell-, Seed-
und Versionszeilen wurden zellweise gegen die jeweiligen CSVs geprüft und
stimmen gerundet. Der Carry-Gegenlauf wurde unabhängig mit +AUD 1.879,3178 und
Delta −AUD 3.106,9647 reproduziert, ist aber nicht als eigenes Manifest/CSV im
publizierten Pack archiviert.

## 7. Monte-Carlo-, Parameter-, Modell- und Implementierungsrisiko

- Basis-Gross-VNB-SE: AUD 42,2495; approximatives 95-%-Halbintervall AUD 82,8090.
- Mortalität und Lapse sind Decrementgewichte; der SE misst primär Marktpfad-
  Sampling, nicht Experience Risk.
- CRN reduzieren Differenzrauschen, ersetzen aber keine gepaarten SEs.
- Fair LIP, BSCR, RM, PVFP, IRR, Designs und Sensitivitätsdifferenzen benötigen
  eigene Batch-/Seed-Fehlermaße.
- Die 600-Pfad-Modellspanne darf nicht ohne modellweise SEs mit dem 4.000-Pfad-
  Basis-SE als reine Modellunsicherheit normiert werden.
- Parameter-, Kalibrierungs-, Vertrags-, Admin-, Modell- und Code-Risiko sind
  in keinem MC-Band enthalten.

## 8. Reproduzierbarkeitsprotokoll

### Umgebung

`Python 3.11.9`; `NumPy 2.2.3`; `SciPy 1.13.1`; `pandas 2.2.3`;
`Matplotlib 3.9.4`; `pytest 8.4.2`; Windows; Engine 1.3.0. Die Versionen stimmen
mit dem instrumentierten Manifest.

### Tests

```powershell
python -m pytest -p no:cacheprovider -q
```

Ergebnis: 122 bestanden, Exit 0, 140,13 s; separate Collection 122 Tests in
1,20 s. Die historische 108,24-s-Laufzeit wurde nicht reproduziert, ist aber
kein fachlicher Fehler.

### Unveränderter Runner

```powershell
python examples/run_insurer_analysis.py --output ..\_review_work\runner_unmodified_1_3
```

Ergebnis: Exit 1 nach 18,5 s, `FrozenInstanceError`; kein vollständiger Pack.

### Instrumentierter Runner

Prozesslokal wurde nur die Greek-Szenarioerzeugung durch die im Paper
dokumentierte `dataclasses.replace`-Variante ersetzt. Ergebnis nach 113,5 s:

- 14 CSVs zellgenau identisch;
- `model_comparison.csv` fachlich identisch, nur Laufzeiten verschieden;
- alle zehn PNGs byteidentisch;
- Manifest ohne `generated_utc` strukturell/wertmäßig identisch;
- Engine-Hash vor/nach Lauf unverändert.

## 9. Literatur- und Zitationsprüfung

Im Ausgangspaper wurden 53 Zitationsvorkommen mit 30 Schlüsseln gefunden;
keine Citeproc-Schlüssel fehlten. 20 von 21 DOI-Strings hatten einen passenden
Crossref-Datensatz; nur der Publisher-String bei `deng2017` war nicht
registriert. Keine fremde Fair-Fee- oder Sensitivitätszahl wurde unzulässig auf
AGILE übertragen. Die reviewed Bibliografie verwendet 35 tatsächlich zitierte
und geprüfte Quellen, ergänzt die statische Juli-Maximum-Returns-Quelle und
LPS 115/117/118 und entfernt unzitierte Einträge.

## 10. Visuelle und technische Dokumentprüfung

Das Ausgangs-PDF besitzt 48 Seiten; eine Bounding-Box-Prüfung fand keine
abgeschnittenen Textblöcke. Inhaltsverzeichnis, Tabellen, Abbildungen und
Literaturverzeichnis sind grundsätzlich vorhanden. Drei beschädigte
Escape-Sequenzen betrafen `\tau`, `\rho` und `\varphi`; dabei lagen im
Quelldokument unter anderem ein einzelnes CR- und VT-Steuerzeichen vor.
Zahlreiche weitere Inline-Formeln standen als ungerenderter Rohtext in
Klammern. Zudem fehlten dem Ausgangs-PDF Titel-/Autorenmetadaten, Outline und
Seitenzahlen; das DOCX verwendete implizite statt ausdrücklich gesetzter
Seitengröße und besaß veraltete App-Statistiken.

Die reviewed Markdown-Fassung parst mit Pandoc/Citeproc in 49 Display- und 110
Inline-Math-Knoten, ohne Raw-TeX- oder C0-Reste. Das reviewed DOCX ist ein
valider ZIP/OpenXML-Container mit 50 Seiten, explizitem A4-Format
(`11907 × 16839` Twips), Titel-/TOC-/Body-Trennung, `PAGE`-/`NUMPAGES`-Feldern,
24 Tabellen, 10 Zeichnungen, 161 OMML-Math-Knoten und vollständigen
UTF-8-Metadaten. Der finale DOCX-Hash lautet
`39AD26414A20BFA0F818C517CE81D7909D224708E1763AF71997EACA26C1F5D3`.

Der Word-PDF-Exporter gab trotz separatem 20-Minuten-Lauf keine Datei zurück.
Die PDF-Lieferfassung wurde deshalb reproduzierbar aus demselben reviewed
Markdown über ein selbstenthaltendes Pandoc-HTML mit MathML und Chromium
erzeugt. Sie umfasst 50 A4-Seiten (`594,96 × 841,92` pt), 104 bereinigte
Outline-Einträge, 231 Links, 10 Bildvorkommen, durchgehende Seitenzahlen und
PDF-Strukturtags. Parserprüfungen fanden 0 leere Seiten, 0 abgeschnittene
Textblöcke, 0 ungültige interne Links und 0 Seiten ohne Footer. Titel, TOC,
Formelseiten, KPI-/Grafikseiten, Quellenkritik und Literaturverzeichnis wurden
zusätzlich gerendert und visuell kontrolliert. Verbleibend sind lediglich die
bereits in den Quell-PNGs kleinen Diagrammbeschriftungen; dies ändert keine
Zahl und ist kein fachlicher Freigabebefund. Der finale PDF-Hash lautet
`F28F7575103761B56A5A347BCBB6E10B1BB9DE2A5E8A237661FB5D248ADE947F`.

## 11. Abschlussstatus und verbleibende Unsicherheiten

Erfüllt sind: Produktquellenabgleich, vollständige Zahlenreconciliation,
Formel-/Codeabgleich, Literatur-/DOI-Audit, Testsuite, Originalrunner-Nachweis,
instrumentierte Reproduktion und transparente Kennzeichnung der offenen
Punkte sowie die technische und visuelle Abnahme der reviewed Ausgaben. Die
abschließende Integrations-QA enthält 0 kritische, hohe, mittlere oder niedrige
Restbefunde. Nicht als gelöst ausgegeben werden die beiden OFFEN-Befunde, fehlende
Allianz-Admin-/Portfolio-/Experience-Daten, die APRA-Klassifikation und alle im
reviewed Paper aufgeführten Production-Blocker. Diese Grenzen verhindern eine
Produktionsfreigabe, nicht die Nutzung als wissenschaftlich eingeschränkte
Lern- und Research-Unterlage.
