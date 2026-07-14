# Delta-QA der finalen AGILE-Kurzfassung

**Geprüfter, eingefrorener Stand**

- Markdown: `AGILE_Modelling_Fachpaper_reviewed_kurzfassung.md`  
  SHA-256 `6C32B7D2C979BD514E0B2AA1A16C9D3D94EC9C23D9645890F48F666ACE547F36`
- PDF: `AGILE_Modelling_Fachpaper_reviewed_kurzfassung.pdf`  
  SHA-256 `AFE22347DD958444D4E6DDD24E2399F7CC00BE74FB80948C19E39647B0805B6F`
- Delta-Basis: `_review_work/short_qa_final.md`

## Gesamturteil

Alle vier mittleren und alle vier niedrigen Restbefunde der vorangegangenen
QA sind geschlossen. Die fachlichen Ergänzungen sind korrekt, präzise und
ändern keine zuvor geprüfte Basiszahl. Die Tabellen- und Bibliografieschrift
wurde auf 8,5 pt angehoben, ohne neue Seiten-, Umbruch-, Clipping- oder
Linkfehler zu erzeugen.

**Finaler Reststatus: 0 KRITISCH, 0 HOCH, 0 MITTEL, 0 NIEDRIG.**

Die Kurzfassung ist damit gegen die unabhängige Kurzfassungs-Checkliste
abgenommen.

## 1. Schließung der vier MITTEL-Befunde

| Befund | Delta-Prüfung | Status |
|---|---|---|
| QA-M-01 Withdrawal-Szenariokopplung | Tabellenlabel lautet nun `Excess 2 % p. a. + Free-Utilisation 100 %`; der Text stellt zusätzlich klar, dass dies kein isolierter 2-%-Stress ist. | **GESCHLOSSEN** |
| QA-M-02 Basismodellpunkt | Guaranteed Minimum 0,25 %, keine geplanten Withdrawals, Adviser Fee 0 und Bonus 0 sind in Abschnitt 2.3 explizit ergänzt. | **GESCHLOSSEN** |
| QA-M-03 Run-/Outcome-Provenienz | Effektiver Outcome-Seed 2027 aus `settings.seed+1` und nur 2026 im serialisierten Manifest sind offengelegt. Die Provenienzzeile nennt nun Runner, Patch, CLI, Tests, externe Inputs, effektive Sub-Seeds und Output-Hashes als nicht gemeinsam gebundene Bestandteile. | **GESCHLOSSEN** |
| QA-M-04 Carry-Gegenlauf | +AUD 1.879,32, isolierter Effekt rund −AUD 3.106,96 und fehlendes separates CSV-/Manifest-Artefakt sind vollständig ergänzt. | **GESCHLOSSEN** |

## 2. Schließung der vier NIEDRIG-Befunde

| Befund | Delta-Prüfung | Status |
|---|---|---|
| QA-N-01 FIA-/GLWB-Analogie | Bauer et al. 2008 und Holz et al. 2012 belegen nun die funktionale Analogie; die Abgrenzung von rechtlicher/APRA-Klassifikation bleibt erhalten. | **GESCHLOSSEN** |
| QA-N-02 `Gender`/PDS-Seiten | PDS-Definition als bei Geburt registriertes Geschlecht ist ergänzt. Death Benefit, Spouse, Age-Pension+-Eligibility und CAS-Mechanik sind nun mit PDS S. 15–17, 24–25, 38–40 und 65–70 belegt. | **GESCHLOSSEN** |
| QA-N-03 Seed-Stabilität | Mittelwert −AUD 1.209, Sample-SD AUD 96,64, mittlerer pfadweiser SE AUD 96,63 und Spannweite −AUD 1.292 bis −AUD 1.049 sind im Text enthalten und korrekt als Plausibilitätssignal qualifiziert. | **GESCHLOSSEN** |
| QA-N-04 Typografie | Tabellen und Literaturverzeichnis verwenden nun 8,5 pt und sind in der A4-Gesamtansicht lesbar. Kleinere extrahierte Größen betreffen nur Footer und mathematische Sub-/Superskripte. | **GESCHLOSSEN** |

## 3. Zahlen- und Inhaltsdelta

Die Ergänzungen wurden gegen reviewed Langfassung, Review Report und lokale
Ergebnis-CSVs geprüft:

- Sensitivitätswert AUD 2.521 / Delta +AUD 3.745 bleibt unverändert und ist
  nun richtig als kombiniertes Szenario bezeichnet.
- Guaranteed Minimum 0,25 %, Adviser Fee 0, Bonus 0 und keine geplanten
  Withdrawals stimmen mit dem Basismodellpunkt überein.
- Effektiver Outcome-Seed 2027 bei manifestiertem Ausgangsseed 2026 stimmt mit
  Runner und Manifest überein.
- Carry-Gegenlauf +AUD 1.879,32 und Effekt −AUD 3.106,96 stimmen mit der
  unabhängigen Reproduktion überein.
- Die fünf Seed-Kennzahlen stimmen mit `mc_seed_stability.csv` und der
  reviewed Langfassung.
- Keine der bereits abgenommenen Executive-, Reconciliation-, Kapital-,
  Sensitivitäts-, Outcome-, Design-, Timing-, Modell- oder Versionszahlen
  wurde materiell verändert.

**Zahlendelta: PASS.**

## 4. Zitations-, Formel- und Assetprüfung

Pandoc/Citeproc parst den finalen Stand fehlerfrei:

- 30 Zitationsvorkommen mit 24 verschiedenen Citekeys;
- 0 fehlende Citekeys;
- 42 Inline- und 6 Display-Math-Knoten;
- 0 Raw-TeX-Knoten;
- 0 C0-, lone-CR- oder Unicode-Replacement-Zeichen;
- 6 vorhandene Bildressourcen; und
- 0 ungerenderte Zitate oder Raw-TeX-Fragmente im PDF.

Die neu aufgenommenen Quellen Bauer und Holz erscheinen korrekt im
Literaturverzeichnis. Produkt- und APRA-Primärquellen sowie interne
Projektartefakte bleiben vollständig und richtig gekennzeichnet.

**Zitations-/Formeldelta: PASS.**

## 5. PDF-Technik nach der 8,5-pt-Anhebung

Die PDF wurde technisch vollständig und auf allen geänderten Seiten visuell
geprüft:

- 19 A4-Seiten zu jeweils 594,96 × 841,92 pt;
- 0 leere Seiten;
- 0 Textblöcke außerhalb der MediaBox;
- 0 Seiten ohne Seitenzahl;
- 0 abgeschnittene Tabellen, Formeln, Bildunterschriften oder
  Literaturzeilen;
- 6 Bildvorkommen;
- 55 gültig auflösbare Named Destinations;
- 72 gültige interne Links und 27 externe Links;
- 0 ungültige interne Ziele;
- vollständige Titel-/Autoren-/Subject-/Keyword-Metadaten;
- `/Lang de-DE` und vorhandene PDF-Strukturtags; und
- Tabellen-/Bibliografieschrift 8,5 pt, Haupttext rund 10,2 pt.

Visuell kontrolliert wurden insbesondere Executive Summary/KPI-Tabellen,
Produktdetails, erweiterte Basisannahmen, Sensitivitätstabelle und -grafik,
Provenienztabelle, Versions-/Seed-Seite und das vollständige
Literaturverzeichnis. Die Anhebung erzeugt weder Überfüllung noch
unzweckmäßige Seitenumbrüche. Der Umfang von 19 Seiten erfüllt „ca. 20
Seiten“.

**PDF-Delta: PASS.**

## 6. Finale Entscheidung

Es verbleiben keine notwendigen Korrekturen. Die bewusst verdichtete
Detailtiefe ist für eine Kurzfassung angemessen und erzeugt keine falsche
materielle Aussage. Use Limitations, Instrumentierungsstatus,
Produktvintage, APRA-Abgrenzung, HOCH-/MITTEL-Befunde, offene Rating-/APRA-
Fragen und Production-Blocker bleiben sichtbar.

**Freigabe der Kurzfassung als reviewed research prototype: PASS.**
