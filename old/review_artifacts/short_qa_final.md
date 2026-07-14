# Finale unabhängige QA der AGILE-Kurzfassung

**Geprüfter, eingefrorener Stand**

- Markdown: `AGILE_Modelling_Fachpaper_reviewed_kurzfassung.md`  
  SHA-256 `9E012543DB1EFE96BABAFFFB4FE2BD971196784EA7992CC389EDC6FF052D66EC`
- PDF: `AGILE_Modelling_Fachpaper_reviewed_kurzfassung.pdf`  
  SHA-256 `262A459923194996CCA4950D64AA95D6D2689C24881C7F171FB36A46048F964C`
- Prüfgrundlage: `_review_work/short_qa_requirements.md`, reviewed Langfassung,
  Review Report, Claim-to-Evidence-Matrix, reviewed Bibliografie und lokaler
  instrumentierter Ergebnispack

## Gesamturteil

Die Kurzfassung ist in Aufbau, fachlicher Stoßrichtung, Zahlenbestand und
Use Limitations gelungen. Alle zentralen Produktmechaniken, Executive KPIs,
HOCH-Befunde und die beiden ausdrücklich offenen Produktfragen sind enthalten.
Es wurde **keine falsche materielle Ergebniszahl**, keine ungerenderte Formel,
kein fehlender Citekey und kein technischer PDF-Integritätsfehler gefunden.

Vor einer finalen Abnahme sind jedoch vier inhaltliche Restpunkte mittlerer
Schwere zu korrigieren. Sie betreffen nicht die Basiszahlen, sondern die
Reproduzierbarkeit und die korrekte Interpretation einzelner Szenarien. Vier
niedrige Restpunkte betreffen Quellenpräzision, eine Produktdefinition, die
quantitative Dokumentation der Seed-Studie und die Drucklesbarkeit kleiner
Tabellenschrift.

**Reststatus:** 0 KRITISCH, 0 HOCH, 4 MITTEL, 4 NIEDRIG.

## 1. Restbefunde MITTEL

### QA-M-01 — Withdrawal-Sensitivität wird als isolierter 2-%-Stress dargestellt

- **Fundstelle:** Markdown Z. 409–435; PDF S. 11, Tabelle und Interpretation.
- **Ist-Zustand:** Die Zeile `Excess Withdrawals 2 % p. a.` berichtet Gross
  VNB AUD 2.521 und Änderung +AUD 3.745. Der Text erläutert nur allgemein,
  dass Withdrawals die Garantie reduzieren.
- **Befund:** Das Runner-Szenario setzt zugleich die Free-Withdrawal-
  Utilisation auf 100 %. Die Zeile ist damit kein isolierter
  2-%-Excess-Withdrawal-Stress. Ohne diesen Hinweis wird der gesamte Effekt
  fälschlich dem 2-%-Parameter zugerechnet.
- **Erforderliche Korrektur:** Zeilenlabel oder unmittelbar folgenden Text
  ergänzen, zum Beispiel: „kombiniert mit 100 % Free-Withdrawal-Utilisation;
  kein isolierter 2-%-Stress“.

### QA-M-02 — Basismodellpunkt ist für die Ergebnisreproduktion unvollständig

- **Fundstelle:** Markdown Z. 287–310; PDF S. 8, Abschnitt 2.3.
- **Ist-Zustand:** Alter, Prämie, Funding, Allocation, Cap, Income, Markt,
  Gebühren, Kosten, Verhalten, Profit und Pfadzahlen sind vorhanden.
- **Befund:** Es fehlen in der Basismodellpunkt-Tabelle vier für Scope und
  Reproduktion relevante Angaben: Guaranteed Minimum 0,25 % für Total
  Protection, keine geplanten Withdrawals, Adviser Fee 0 und Bonus 0. Das
  Guaranteed Minimum erscheint zwar zuvor als allgemeiner Produktfakt, wird
  aber nicht dem konkreten Modellpunkt zugeordnet. Adviser Fee, Bonus und
  geplante Withdrawals sind nur indirekt oder gar nicht als Basisinputs
  erkennbar.
- **Erforderliche Korrektur:** Die Vertrags-/Allocation-Zeilen um
  `Guaranteed Minimum 0,25 %`, `geplante Withdrawals: keine`,
  `Adviser Fee: 0` und `Bonus: 0` ergänzen.

### QA-M-03 — Run- und Outcome-Provenienz bleibt zu allgemein

- **Fundstelle:** Markdown Z. 438–455 sowie 510–520; PDF S. 11–12 und 14.
- **Ist-Zustand:** Effektiver Outcome-Seed 2027 und die generelle
  Manifestlücke werden jeweils genannt.
- **Befund:** Nicht offengelegt wird, dass das Manifest im serialisierten
  Settings-Objekt nur den Ausgangsseed 2026 zeigt und die Outcome-Funktion
  tatsächlich `seed+1=2027` verwendet. Die Provenienz-Tabelle nennt Runner,
  Patch, CLI und Outputs, lässt aber Tests, externe Inputs und effektive
  Sub-Seeds aus. Gerade der Seed-Fall ist ein konkretes Beispiel des
  HOCH-Befunds zur unvollständigen Laufattestierung.
- **Erforderliche Korrektur:** Beim Outcome-Satz ergänzen: „effektiv 2027 aus
  `settings.seed+1`; im Manifest ist nur 2026 serialisiert“. Die
  Provenienzzeile sollte außerdem Tests, externe Inputs, effektive Sub-Seeds
  und Output-Hashes als nicht gemeinsam gebundene Bestandteile nennen.

### QA-M-04 — Carry-Gegenlauf wird ohne isolierten Effekt und Archivgrenze berichtet

- **Fundstelle:** Markdown Z. 540–545; PDF S. 15.
- **Ist-Zustand:** Der kontrollierte Gegenlauf wird gerundet mit +AUD 1.879
  genannt; der Gesamtvergleich wird richtig als Versionsattribution und nicht
  als reines Implementation Risk bezeichnet.
- **Befund:** Der independently reproduzierte Wert +AUD 1.879,32, der daraus
  abgeleitete Carry-Effekt von rund −AUD 3.106,96 und die fehlende separate
  CSV-/Manifest-Archivierung des Gegenlaufs fehlen. Ohne den letzten Hinweis
  erscheint die Provenienz dieser zentralen Attribution vollständiger, als
  sie ist.
- **Erforderliche Korrektur:** Einen Satz ergänzen: „Der Gegenlauf wurde
  unabhängig mit +AUD 1.879,32 beziehungsweise einem Effekt von rund
  −AUD 3.106,96 bestätigt, ist aber nicht als separates CSV-/Manifest-Artefakt
  archiviert.“

## 2. Restbefunde NIEDRIG

### QA-N-01 — Zentrale FIA-/GLWB-Analogie ist nicht methodisch belegt

- **Fundstelle:** Markdown Z. 25–30; PDF S. 3.
- **Befund:** Die funktionale FIA-/GLWB-Einordnung ist korrekt als nicht
  rechtliche Analogie qualifiziert. Der dortige PDS-Nachweis belegt jedoch
  Issuer/Group Policy, nicht die wissenschaftliche GMxB-Terminologie.
- **Erforderliche Korrektur:** Bei der Analogie mindestens Bauer et al. 2008,
  optional zusätzlich Holz et al. 2012, zitieren. Der reviewed BibTeX-Bestand
  enthält beide Einträge bereits.

### QA-N-02 — PDS-`Gender` und Produktdetailquellen sind nicht vollständig präzisiert

- **Fundstelle:** Markdown Z. 173–184 und 217–225; PDF S. 6.
- **Befund:** Rating nach Gender am Product Commencement Date und die offenen
  Equal-age-/fractional-age-Ränder sind richtig. Die produktspezifische
  PDS-Definition als bei Geburt registriertes Geschlecht fehlt. Der Absatz zu
  Death Benefit, Spouse Default, Age-Pension+-Eligibility und Death-Cap-Sprung
  besitzt außerdem keinen eigenen PDS-Seitenbeleg; der vorangehende Nachweis
  S. 31–35/62–70 deckt diese Aussagen nur teilweise.
- **Erforderliche Korrektur:** `Gender` kurz mit der PDS-Definition ergänzen
  und am letzten Absatz mindestens PDS S. 15–17, 24–25, 38–40 und 65–70
  nachweisen.

### QA-N-03 — Seed-Stabilität ist nur grafisch, nicht numerisch zusammengefasst

- **Fundstelle:** Markdown Z. 547–554; PDF S. 15, Abbildung 6.
- **Befund:** Pfadzahl, fünf Seeds und Modellspanne sind vorhanden. Die
  für die MC-Plausibilisierung wichtigen Seed-Kennzahlen fehlen im Text und
  sind aus der verkleinerten Grafik nicht zuverlässig ablesbar.
- **Erforderliche Korrektur:** Einen kompakten Satz ergänzen: Mittelwert Gross
  VNB −AUD 1.209; Sample-SD AUD 96,64; mittlerer pfadweiser SE AUD 96,63;
  Spannweite −AUD 1.292 bis −AUD 1.049. Als Plausibilitätssignal, nicht als
  umfassende Konvergenzstudie, qualifizieren.

### QA-N-04 — Tabellen- und Literaturtext unterschreitet die Zielschriftgröße

- **Fundstelle:** PDF insbesondere S. 3–16 und 18–19.
- **Befund:** Haupttext ist mit rund 10,2 pt gut lesbar. Tabellen- und
  Literaturspans liegen jedoch überwiegend bei rund 7,8 pt; Bildlabels sind
  teilweise noch kleiner. Das Dokument ist digital zoombar und aktuell
  lesbar, verfehlt aber das QA-Ziel von ungefähr 9 pt für eine robuste
  A4-Druckfassung.
- **Erforderliche Korrektur:** Tabellen- und Bibliografieschrift auf möglichst
  8,5–9 pt anheben oder Tabellen minimal entzerren. Der aktuelle Umfang von
  19 Seiten bietet dafür voraussichtlich eine Seite Reserve. Kleine
  Quellgrafiklabels müssen nicht rekonstruiert werden, sofern die
  entscheidenden Werte lesbar im Text beziehungsweise in Tabellen stehen.

## 3. Zahlenkontrolle

### Ergebnis

**PASS — keine falsche Zahl gefunden.** Die folgenden sichtbaren Zahlen wurden
gegen die lokalen CSVs beziehungsweise die reviewed Langfassung geprüft:

- Basis: Prämie AUD 100.000; Gross VNB −AUD 1.227,65; SE AUD 42,2495;
  95-%-Halbintervall AUD 82,809; Non-unit BEL +AUD 1.227,65;
  Guarantee Value AUD 10.079,74; Fair LIP 3,0041561 %; BSCR
  AUD 17.205,30; Risk Margin AUD 4.687,26; VNB nach RM −AUD 5.914,91;
  PVFP −AUD 12.898,96; IRR 3,5192 %; Payback Jahr 23; Identity Gap
  −0,168923 %.
- Wertüberleitung: Product Fees +2.269,84; LIP +8.701,07; Crediting Margin
  +9.923,45; MVA +217,37; Claims −18.780,81; Expenses −3.558,57.
- Kapital: Interest Down 15.812,66; Longevity 3.489,70; Lapse Down 818,45;
  Expenses 313,88; BSCR 17.205,30.
- Sensitivitäten: sämtliche zehn sichtbaren Gross-VNB- und Delta-Zeilen
  stimmen gerundet mit `sensitivities.csv`. Der Restbefund QA-M-01 betrifft
  ausschließlich das Szenariolabel beziehungsweise dessen Interpretation.
- Outcomes: IV-Mediane, Income-Median, Erschöpfungsquoten und In-force-
  Gewichte für Alter 70/82/83/84/86 stimmen; 50-%-Schwelle erstmals bei Alter
  84 mit 85,36 %.
- Designs und Timing: alle sechs sichtbaren Designzeilen sowie Startalter
  66/80 stimmen mit `product_designs.csv` und `income_start_timing.csv`.
- Version/Modelle: v1.2.0-/v1.3.0-Tabelle, Modellendpunkte −AUD 1.275 und
  −AUD 4.402 sowie Spannweite AUD 3.127 stimmen.

Rundung und Vorzeichen sind konsistent. Unterschiedliche Base-Zahlen aus
4.000-/1.500-/1.200-/600-Pfad-Blöcken werden nicht vermischt.

## 4. Quellen- und Zitationskontrolle

### Ergebnis

**PASS mit QA-N-01/QA-N-02 als Präzisierungsbedarf.** Pandoc/Citeproc lief
fehlerfrei. Es bestehen 27 Zitationsvorkommen mit 22 unterschiedlichen
Citekeys, 0 fehlende Citekeys und 0 ungerenderte `[@...]`-Fragmente im PDF.
Das erzeugte Literaturverzeichnis enthält nur tatsächlich zitierte Quellen.

Bestätigt vorhanden sind:

- PDS vom 19. Januar 2026;
- statische Juli-2026-Rate-Sheets für Lifetime Income Rates, Guaranteed
  Minimums und Maximum Returns;
- APRA LPS 110, 114, 115, 117 und 118;
- lokale Engine-, Methodology-, Audit- und Run-Artefakte mit korrekter
  Kennzeichnung als interne Quellen;
- Black--Scholes, Heston, Hull--White, Fang/Oosterlee und
  Longstaff--Schwartz/Huang--Kwok für die tatsächlich dargestellten Methoden;
  sowie
- korrigierter `deng2017`-Eintrag mit Geng Deng/Mike Yan und Publisher-URL
  ohne den nicht registrierten DOI-String.

Die falschen lokalen A19-/B3-Metadaten wurden nicht als Kernquelle
reimportiert. Keine externe Fair Fee oder Sensitivität wird auf AGILE
übertragen.

## 5. Formel- und Markdown-Kontrolle

### Ergebnis

**PASS.** Der finale Pandoc/Citeproc-Parse enthält 42 Inline- und 6
Display-Math-Knoten, 0 Raw-TeX-Knoten, 0 C0-Steuerzeichen, 0 lone-CR-Zeichen
und 0 Unicode-Replacement-Characters. Alle sechs Bildpfade existieren.

Visuell und semantisch geprüft wurden insbesondere:

- Total-/Partial-Protection-Payoffs;
- Income-Rate-Rechnung 7,05 % + 5 × 0,35 % = 8,80 %;
- $Q$-Barwertformel und Diskontfaktor;
- Non-unit-BEL-/Guarantee-Value-Definitionen;
- Gegenbeispiel $p_z=1{,}0449739$; und
- LSMC-Closeout $\max(IV,I\times AF)$.

Es bestehen keine beschädigten `tau`-/`rho`-/`varphi`-Sequenzen, kein
sichtbares Raw LaTeX und keine verlorenen Operatoren.

## 6. PDF-Technik und visuelle Kontrolle

### Ergebnis

**Technischer PASS; niedriger Typografiebefund QA-N-04.** Die PDF wurde
vollständig seitenweise gerendert, als Kontaktbogen und auf kritischen Seiten
in höherer Auflösung geprüft.

- 19 A4-Seiten, jeweils 594,96 × 841,92 pt;
- 0 leere Seiten;
- 0 Textblöcke außerhalb der MediaBox;
- 0 Seiten ohne Seitenzahl;
- 33 Outline-Einträge;
- 53 gültig auf Seiten auflösbare Named Destinations;
- 70 gültige interne TOC-/Zitationslinks und 24 externe Links;
- 6 Bildvorkommen, keine fehlende Bildressource;
- vollständige Titel-, Autoren-, Subject-, Keyword- und Datumsmetadaten;
- `/Lang de-DE`, PDF-Strukturtags und markierter Strukturbaum;
- keine sichtbaren abgeschnittenen Formeln, Tabellen oder Bildunterschriften;
  und
- keine Mojibake-, Ersatzzeichen- oder Rohzitationsreste.

Titel, Inhaltsverzeichnis, Produkt-/Payoffseite, Annahmen, KPI-/Waterfall-,
Sensitivity-, Outcome-, Timing-, Model-Risk-, Production-Blocker-, Notations-
und Literaturseite wurden visuell einzeln geprüft. Seitenumbrüche und
Tabellenkopf-Wiederholungen sind sachgerecht; die Leerfläche auf S. 13/17/18
ist kein Blankseiten- oder Layoutfehler.

## 7. Abschlussentscheidung

Die Kurzfassung ist **inhaltlich nahe an der Abnahme, aber noch nicht final
geschlossen**. Für die nächste Fassung sind QA-M-01 bis QA-M-04 zwingend und
QA-N-01 bis QA-N-04 als kleine, klar umgrenzte Qualitätskorrekturen
umzusetzen. Eine erneute QA kann sich danach auf folgende Delta-Prüfung
beschränken:

1. Szenarioqualifikation Excess Withdrawals;
2. Vollständigkeit des Basismodellpunkts;
3. Outcome-/Run- und Carry-Provenienz;
4. FIA-/GLWB- und PDS-Quellenpräzisierung;
5. Seed-Zusammenfassung; und
6. Seitenzahl, Tabellenlesbarkeit, Citeproc und PDF-Link-/Clipping-Checks nach
   Neurendering.

Alle übrigen Anforderungen der unabhängigen Kurzfassungs-Checkliste sind im
geprüften Stand erfüllt.
