# Änderungsprotokoll: AGILE Modelling Fachpaper

Dieses Protokoll bezieht sich auf die unveränderte Ausgangsdatei
`AGILE_Modelling_Fachpaper.md` und die neue Fassung
`AGILE_Modelling_Fachpaper_reviewed.md`. Rein mechanische House-Style-
Korrekturen sind am Ende gruppiert; jede materielle Änderung ist einzeln
aufgeführt.

| Fundstelle | Vorherige Aussage | Neue Aussage | Änderungsgrund | Schweregrad | Quelle oder Rechenbeleg |
|---|---|---|---|---|---|
| Titel/Dokumentstatus | wissenschaftliche Lernunterlage; keine explizite Reviewtrennung | unabhängig geprüfte Lernunterlage; Produktfakt, Annahme, Ergebnis und Interpretation getrennt | Status und Use Limitations transparent machen | NIEDRIG | Reviewauftrag |
| Zusammenfassung/3.1 | AGILE liege näher an FIA+GLWB; Garantie aus Statutory Fund No. 2 | FIA/GLWB nur funktionale US-geprägte Analogie; specified beneficiary, Fund-Assets, Top-up/Cessation, keine Allianz-SE-Garantie | Rechts-/Garantieumfang nicht überziehen | MITTEL | PDS S. 2, 83–85 |
| 3.1 Terminologie | keine systematische Abgrenzung GMWB/GLWB/GMLWB/FIA/VA | neue Terminologietabelle | vom Auftrag ausdrücklich verlangt; AGILE ist indexed, nicht unit-linked | MITTEL | PDS; Bauer 2008; Holz 2012 |
| 3.1/12.6 | freiwilliger Income Start nach einem Jahr | zusätzlich automatischer Start nach 100 bzw. Age-Pension+-LE; Default Fixed ohne Spouse; möglicher Full Withdrawal bei fehlenden Kontakt-/Bankdaten als PDS-Vorbehalt | fehlender Vertragszweig | MITTEL | PDS S. 17, 75 |
| 3.2 | Juli-Caps für Commencement Dates | Commencement **oder Anniversary Dates**; statisches Juli-PDF | Vintage-Nachweis reproduzierbar machen | MITTEL | Maximum Returns Jul26 S. 1 |
| 3.2 | Guaranteed Minimum als „Minimum“ neben Cap | Untergrenze des künftigen Maximum Return, nicht Rendite-/Protection-Floor | Begriffsverwechslung vermeiden | MITTEL | Guaranteed Minimums Jul26 S. 1; PDS S. 58 |
| 3.3 | Payoffformeln ohne Branch-Bedingung | nur marktgebundener Zweig; möglicher garantierter Fixed Return separat | Formeln waren keine vollständige Vertragsabbildung | MITTEL | PDS S. 58, 60, 62 |
| 3.4 | Replikation als allgemeine Produktformel | Replikation auf marktgebundenen Credit-Payoff begrenzt | Fixed-Return-Zweig nicht optional repliziert | MITTEL | crediting.py; PDS |
| 3.5 | Alter/Geschlecht am Commencement, jüngeres Leben | PDS-`Gender` definiert; Equal-age-/fractional-age-Regeln OFFEN | Engine-Tie/Interpolation öffentlich nicht bestätigt | OFFEN/NIEDRIG | PDS S. 18–19/90; Ratecard; product.py |
| 3.5 | Age-Pension+-Raten als fix | CAS-Änderungsvorbehalt bis tatsächlichem Option-Start | wesentlicher Vintage-Vorbehalt | MITTEL | PDS S. 15; Ratecard S. 1–2 |
| 3.7 | offizielle laufende Sätze | aktuelle PDS-Sätze; Engine-Konstanz als Annahme; Änderungsrecht mit Notice | Vertrag und Modell trennen | MITTEL | PDS S. 41–42 |
| 3.8 | Free/Excess/MVA nur grundlegend | AUD-100-Minimum, 95-%-Einzel-/Jahreslimit, AUD-2.000-Restwert und Age-Pension+-Lower-of ergänzt | vollständige Withdrawal-Mechanik | MITTEL | PDS S. 31–35, 68–70 |
| 3.8 | MVA-Proxy unkalibriert | zusätzlich Default-Termination-Loadings null; PDS-No-rate-move-Tabelle nicht automatisch getroffen | Proxyumfang konkretisieren | MITTEL | product.py MVASpec; PDS S. 60–61 |
| 3.8 | DVA als unterjährige Returnberechnung, PDS S. 33 | Derivatewert, nicht YTD-Return; pro-rata Cap/Protection/Fixed-Return-Floors, PDS S. 62–63 | Produktmechanik/Quelle präzisieren | MITTEL | PDS S. 62–63 |
| 3.9 | Spouse Election allgemein | Inhaber/Eligibility vom Ownership-Pfad; Default Income-Fortsetzung | Vertragswahlrecht nicht bloß Modellinput | MITTEL | PDS S. 22, 38–40 |
| 3.9 | Age Pension+ nur lineares MWV | funding-spezifische Election/Commencement, Non-super-Trustee-/Company-Ausschluss mit Platform-Trustee-Ausnahme und separater Half-LE-Death-Cap-Sprung | CAS unvollständig | MITTEL | PDS S. 15–17, 65–70 |
| 4/7/11/12 | sichtbares „APS“ | Age Pension+; `aps` nur einmal als internes Codekürzel | Verwechslungsgefahr mit Allianz Policy Services | NIEDRIG | PDS-Terminologie; Code |
| 5.1 | Einzelcashflowformel ohne Summe | $PV_Q=E_Q[\sum_tD_tCF_t]$ | Cashflowstrom mathematisch korrekt schreiben | NIEDRIG | pricing.py/projection.py |
| 5.3/6.1 | externe GLWB-„Materialität“ allgemein | ausdrücklich nur in zitierten Modellstudien; keine AGILE-Kalibrierung | keine Literaturresultate auf AGILE übertragen | MITTEL | Goudenège 2016; Piscopo 2011; Fung 2014 |
| 5.6 | Heston--HW-Zweig ohne genaue Cross-Term-Kritik | negatives Default-$w$, kein unabhängiger Gaussian variance add-on, hybride Näherung | „exact composition“ mathematisch falsch | HOCH | esg.py/crediting.py; Testsonderfall; unabhängige Rechnung |
| 6.3 | Moneyness $PV/SV$ allgemein | Anniversary korrekt; Off-anniversary Election nutzt vorübergehend IV; Zähler ist Annuitätenfaktor-/10Y-Zero-Proxy | Code/Dokumentation stimmen nicht vollständig überein | MITTEL | projection.py/behavior.py |
| 7.2 | `bel_total` als Total BEL | interne $P_0+$Non-unit-Konvention; kein APRA/AASB/IFRS-BEL | AGILE nicht unit-linked; regulatorische Überinterpretation | MITTEL | pricing.py; PDS |
| 7.4 | $p_z(s)\le1$ | gilt im Basis-Cap-Fall, nicht allgemein; negative Margin möglich | Gegenbeispiel Cap 50 % | MITTEL | BS-Pricer: 1,0449739 |
| 7.5/11.2 | PASS wegen „laufbezogener Schwelle“ | CSV 1,96SE vs. tatsächlicher Runner-Test `max(0,25%,3SE)` | Governancefeld unvollständig | NIEDRIG | Runner; reconciliations.csv |
| 8.3 | nur LPS 110/114 zitiert | LPS 115/117/118 ergänzt; PCA-Bausteine erklärt | regulatorische Herleitung vollständig machen | HOCH | APRA LPS 110/114/115/117/118 |
| 8.3 | Variable-Annuity-Regel ohne AGILE-Abgrenzung | AGILE-APRA-Klassifikation OFFEN | funktionale Analogie ist kein Aufsichtsnachweis | OFFEN | LPS 110 Attachment A; PDS |
| 8.5/10.3/11.4 | „30 % Tax“ | symmetrische sofortige Entlastung auch auf Verluste; kein Tax-Loss/DTA/Recoverability | PVFP-Annahme materiell | MITTEL | profitability.py |
| 9.3 | LSMC-Ausgabe ist Lower Bound | Populationwert einer fixen zulässigen Policy ist Lower Bound; berichteter MC-Max-Schätzer nicht strikt | Sampling-/Selection Bias | MITTEL | lsmc.py |
| 9.4 | bekannte LSMC-Grenzen allgemein | Alter 105, max. 40 Jahre, 30Y-Zero-Tail, Joint Life ab Issue, Static-Benchmark nicht voller Monatsmotor | Tail-/Spouse-Scope materiell | MITTEL | lsmc.py; projection.py |
| 10.1 | Basisinputs ohne Cap-/MVA-Managementannahmen | konstante Juli-Caps, kein Fixed Return, MVA-Loadings null explizit | Produktfakt vs. Annahme trennen | MITTEL | Manifest; Runner; product.py |
| 11.1 | KPIs auf Cent/0,01 bp | Management-KPIs gerundet; exakte CSV-Reconciliation separat; fehlende SEs genannt | Scheingenauigkeit reduzieren | MITTEL | CSVs; Fünf-Seed-Indikation |
| 11.4 | PVFP inklusive Tax | zusätzlich symmetrische Verlustentlastung erklärt | Ergebnisinterpretation | MITTEL | profitability.py |
| 11.5 | „Expenses +10 %“ | „Maintenance Expenses +10 %; Acquisition unverändert“ | Szenario stresst nicht alle Kosten | MITTEL | sensitivities.py |
| 11.6 | Seed 2027 ohne Manifesthinweis | effektiver `seed+1=2027`; Manifest serialisiert 2026 | Reproduzierbarkeitslücke | MITTEL | Runner; Manifest |
| 11.7 | Spouse-Werte ohne Model Point | Frau 63, jüngeres Leben, `continue_income`; Age-Pension+-LE 20 | Ergebnis sonst nicht auditierbar | MITTEL | Runner; Ratecard; product_designs.csv |
| 11.10 | Modellspanne rund 37× als Modellrisikoindikator | exakt 37,761≈38; unbereinigte 600-Pfad-Spanne ohne modellweise SEs | Model-/Sampling-Risk nicht vermischen | MITTEL/NIEDRIG | model_comparison.csv; executive_kpis.csv |
| 11.11 | Equity Delta „normalisiert“ | Einheit `dNAV/d(index scale)/premium`; +1 % ≈ AUD 0,50 | ungewöhnliche Einheit eindeutig machen | MITTEL | pricing.py; market_greeks.csv |
| 11.12/13.1 | Versionswechsel als Implementation Risk | Versionsattribution aus Codefix, Annahmen und Definitionen | keine reine Fehlerkomponente isoliert | MITTEL | beide Packs; unabhängiger Carry-Gegenlauf |
| 11.12 | Carry-Gegenlauf ohne Provenienzhinweis | +AUD 1.879,32/Delta −3.106,96 bestätigt, aber nicht separat manifestiert | Auditierbarkeit | MITTEL | unabhängiger 1.3-Gegenlauf |
| 12.1 | 122 Tests in 108,24 s | 122 Tests, Exit 0, aktuell 140,13 s; historische Laufzeit nicht reproduziert | Anzahl bestätigen, lastabhängige Zeit nicht als Fixwert | NIEDRIG | pytest-Lauf |
| 12.4 | Fehler/Workaround nur narrativ | Originalrunner Exit 1 nach 18,5 s; Workaround 113,5 s; CSV/PNG/Manifest-Vergleich dokumentiert | Reproduzierbarkeit konkret belegen | HOCH | unabhängige Runnerläufe |
| 2.2/12.4 | Engine Source Hash als Laufprovenienz | hasht nur `agile_engine/*.py`; Runner/Patch/CLI/Outputs fehlen | erfolgreicher Patchlauf nicht attestiert | HOCH | Runner `source_hash()`; Manifest |
| Literatur `deng2017` | Guowei Deng/Meng Yan; DOI | Geng Deng/Mike Yan; kein DOI-Feld, Publisher-URL | Metadaten falsch; DOI nicht registriert | HOCH | Risk.net; Crossref; doiRA |
| Literatur Fang/Actuaries/Langrené | knappe/uneinheitliche Metadaten | Online-first-Notiz; Working Group; arXiv v1/DataCite-DOI | präzisere Primärmetadaten | NIEDRIG | SIAM; Original Technical Paper; arXiv |
| Anhang D | allgemeine Warnung vor lokalem Index | falscher A19-DOI und Sun-Thesis konkret; echte 2026-VOR genannt | Metadatenrisiken konkret nachweisen | HOCH | Crossref/Elsevier/Cambridge/lokale Datei |
| gesamtes Dokument | drei beschädigte Escape-Sequenzen und zahlreiche rohe Inline-LaTeX-Klammern | gültige `\tau`, `\rho`, `\varphi` und `$…$`-Inline-Mathematik | sichtbare DOCX/PDF-Satzfehler | NIEDRIG/MITTEL | Byte-/Renderprüfung |

## Gruppierte redaktionelle Änderungen

- Deutsch/Englisch-Fachbegriffe beim ersten Auftreten vereinheitlicht und
  Abkürzungen eindeutig gemacht.
- `Q`/`P`, Zustandsgrößen und Formelsymbole konsequent als Inline-Mathematik
  gesetzt; C0-Steuerzeichen vollständig entfernt.
- Resultat, Interpretation und normative Aussage sprachlich getrennt.
- Überzogene Kausal-/Universalformulierungen auf den dokumentierten
  Modellpunkt beziehungsweise die zitierte Literaturstudie begrenzt.
- Tabellenlabels auf Einheiten, Scope und Rundung geprüft; Abbildungen behalten
  ihre Originaldaten und werden als illustrative Research-Outputs bezeichnet.
- Bibliografie auf tatsächlich zitierte, verifizierte Quellen reduziert und um
  statische Produkt-/APRA-Primärquellen ergänzt.
- Reviewed DOCX explizit auf A4, Titel-/TOC-/Body-Seitenumbrüche,
  Seitenzahlfelder, aktualisierte Dokumentstatistik und UTF-8-Metadaten
  gesetzt.
- Reviewed PDF aus derselben Markdown-Quelle über selbstenthaltendes
  HTML/MathML erzeugt, mit A4, Seitenzahlen, Outline, Strukturtags und
  Metadaten; 50 Seiten ohne Blankseite, Clipping oder ungültige interne Links
  parser- und renderseitig abgenommen.
- Kleine Beschriftungen der unverändert übernommenen 200-dpi-Quellgrafiken als
  verbleibende, nicht materielle Darstellungsgrenze dokumentiert.
