# Finale Integrations-QA nach Umsetzung der IQ-Befunde

**Prüfstand:** 11. Juli 2026  
**Geprüfte Dateien:**

- `AGILE_Modelling_Fachpaper_reviewed.md`
- `AGILE_Modelling_Claim_Evidence_Matrix.csv`
- `AGILE_Modelling_Review_Report.md`
- `AGILE_Modelling_Changes.md`
- ergänzend `AGILE_Modelling_references_reviewed.bib`

**Änderungsbeschränkung:** Im Rahmen dieser Reprüfung wurde ausschließlich
`_review_work/integration_qa_final.md` neu angelegt.

## Gesamturteil

IQ-M-01 bis IQ-M-04 sowie IQ-N-01 und IQ-N-02 sind fachlich und
artefaktübergreifend vollständig umgesetzt. Das frühere Formelsymbol `APS_y`
wurde durch `APPlus_y` ersetzt und unmittelbar als die vom Versicherer
einbehaltene Age-Pension+-Komponente definiert. Es verbleibt kein Restbefund.

**Finaler Reststatus:** 0 KRITISCH, 0 HOCH, 0 MITTEL, 0 NIEDRIG.

## Reprüfung der sechs IQ-Punkte

| IQ-Punkt | Paper | Matrix | Review Report | Changes | Urteil |
|---|---|---|---|---|---|
| IQ-M-01 Age-Pension+-Eligibility | Z. 515–524 nennt Non-superannuation-Trustee-/Company-Ausschluss und Non-super-Platform-Trustee-Ausnahme | Zeile 32 enthält dieselbe konkrete Regel | M-07 dokumentiert Evidenz und Umsetzung | Z. 26 protokolliert Ausschluss und Ausnahme | **GESCHLOSSEN** |
| IQ-M-02 Spouse-Designinput | Z. 1486–1492 nennt Frau 63 und `continue_income` unmittelbar vor der Tabelle | Zeile 82 enthält beide Inputs | M-09 nennt Frau 63 und `continue_income` | Z. 45 protokolliert beide Inputs | **GESCHLOSSEN** |
| IQ-M-03 LSMC-Tail/Static Policy | Z. 1180–1194 nennt 30Y-Zero, $\max(IV,I\times AF)$, Static-vs.-Monatsmotor, Alter 105/40 Jahre und Joint Life ab Issue | Zeile 67 enthält alle Grenzen und fehlende Like-for-like-Vergleichbarkeit | M-15 dokumentiert alle Punkte | Z. 39 dokumentiert Tail-, Joint-Life- und Static-Scope | **GESCHLOSSEN** |
| IQ-M-04 automatische Folge bei fehlenden Daten | Z. 235–245 nennt möglichen Full Withdrawal ausdrücklich als PDS-Vorbehalt, nicht als deterministische Engine-Regel; Production-Blocker Z. 1835–1837 konsistent | Zeile 7 enthält Vorbehalt und Modellabgrenzung | M-02 dokumentiert die Umsetzung | Z. 14 protokolliert die Vertragsfolge | **GESCHLOSSEN** |
| IQ-N-01 Pseudo-Mathematik | `$g$`, `$z(t)$`, `$x$`, `$i(x)$`, `$s$`, Time-$s$ und `$PVFP$` werden korrekt als Mathematik geparst | kein eigener materieller Claim erforderlich | technische Dokumentprüfung bestätigt gültige Inline-Mathematik | Z. 56 und 62–63 dokumentieren Satzkorrektur | **GESCHLOSSEN** |
| IQ-N-02 sichtbares `APS` | Die beanstandeten Stellen verwenden Age Pension+; internes `aps` und das Abbildungslabel werden ausdrücklich erklärt. Z. 1090 verwendet nun `APPlus_y`, unmittelbar definiert in Z. 1093–1094. | kein eigener materieller Claim erforderlich | Z. 139–140 ist mit dem Paper konsistent | Z. 27 ist mit dem Paper konsistent | **GESCHLOSSEN** |

Die Matrix bewahrt in `Prüfstatus` und `erforderliche Änderung` teilweise den
historischen Zustand des Ausgangsclaims. Das widerspricht der Umsetzung nicht:
Report und Changes übernehmen die Funktion des Umsetzungsnachweises, während
die Matrix den geprüften Ausgangsclaim und die daraus abgeleitete Änderung
nachvollziehbar hält.

## Abschluss des letzten Terminologiepunkts

`AGILE_Modelling_Fachpaper_reviewed.md`, Z. 1089–1094, verwendet jetzt

```text
Signature_y=Fees_y+CM_y+MVA_y+APPlus_y-Claims_y-Expenses_y
```

und definiert `$APPlus_y$` direkt als die vom Versicherer einbehaltene
Age-Pension+-Komponente. Das Symbol ist ausdrücklich kein offizieller
Produktcode. `APS_y` kommt in keinem der vier geprüften Finalartefakte mehr vor.
Die verbleibenden Treffer `aps_retained`, `aps` bei `product.py` und `APS` im
unveränderten Runner-Bild sind jeweils ausdrücklich als interne Bezeichner
erklärt und deshalb terminologisch unproblematisch.

## Technische Counts und Parse-Ergebnisse

### Dateien und Encoding

| Datei | Bytes | logische Zeilen | BOM | CR/CRLF | unzulässige C0-/DEL-Zeichen |
|---|---:|---:|---|---:|---:|
| `AGILE_Modelling_Fachpaper_reviewed.md` | 96.474 | 2.089 | nein | 0 | 0 |
| `AGILE_Modelling_references_reviewed.bib` | 13.862 | 365 | nein | 0 | 0 |
| `AGILE_Modelling_Claim_Evidence_Matrix.csv` | 23.774 | 94 | nein | 0 | 0 |
| `AGILE_Modelling_Review_Report.md` | 17.566 | 263 | nein | 0 | 0 |
| `AGILE_Modelling_Changes.md` | 10.543 | 70 | nein | 0 | 0 |

Alle fünf Dateien sind strikt valides UTF-8 mit einheitlichen LF-Zeilenenden.

### Claim-Evidence-Matrix

- 93 Datenzeilen plus Header, exakt sieben Felder in jeder Zeile.
- 0 leere Pflichtfelder, 0 doppelte Datensätze, 0 CSV-Parsefehler.
- Typverteilung unverändert korrekt: 31 Produktfakten, 26 Modellannahmen,
  30 Ergebnisse, 6 Interpretationen.

### Zitation und Bibliografie

- 35 unterschiedliche In-text-Schlüssel und 35 BibTeX-Schlüssel.
- 0 fehlende, 0 doppelte und 0 unzitierte Schlüssel.
- Pandoc 3.7.0.2 plus Citeproc: Exit Code 0.
- Die Bibliografie wurde durch die IQ-Nacharbeit nicht verändert.

### Markdown, Mathematik und Assets

- Pandoc-AST mit `markdown+tex_math_single_backslash`:
  49 Display-Math-Knoten, 110 Inline-Math-Knoten, 0 Raw-TeX-Reste.
- Zusätzlich: 47 Cite-Knoten, 24 Tabellen, 10 Bilder, 101 Überschriften.
- DOCX-Writer-Pipeline über Pandoc/Citeproc: Exit Code 0.
- `AGILE_Modelling_Review_Report.md` und `AGILE_Modelling_Changes.md`:
  Markdown-Parse jeweils Exit Code 0.
- Alle zehn Bildpfade und der YAML-Bibliografiepfad existieren.
- Keine der zuvor beanstandeten Formen `(g)`, `(z(t))`, `(x)`, `(i(x))`,
  `(s)`, `Time-(s)` oder `(PVFP)` verbleibt.

## Integrität der Originaldateien

Die Originalhashes stimmen nach der Nachprüfung weiterhin bytegenau:

| Original | SHA-256 | Status |
|---|---|---|
| `AGILE_Modelling_Fachpaper.md` | `b27fea58845c7a6f7bbf8b5de953c7cb273e8969b5e4b9bae1be7c8ed0eea41e` | unverändert |
| `AGILE_Modelling_Fachpaper.docx` | `6992976907be4eecc509add05e4c9ab9aa9a84f24505a030681a2f6f168434ab` | unverändert |
| `AGILE_Modelling_Fachpaper.pdf` | `ab0afd6bdbffab3390679abfb2ff41910cbf54e63691b1a9f4ff0bcb80480cce` | unverändert |
| `AGILE_Modelling_references.bib` | `a6befec73ad7c7525ea3260b88a24b27a3830cceccd7c32d88c8ea37f8513240` | unverändert |
| `AGILE.md` | `184a7446f2e2c8d0f334fc91f28f874d36947b65a613326ba79302a501e52e9d` | unverändert |

## Abschlussstatus

Alle materiellen und redaktionellen Integrationsreste sind geschlossen. Aus
fachlicher, numerischer, bibliografischer und technischer Sicht bestehen keine
KRITISCHEN, HOHEN, MITTLEREN oder NIEDRIGEN Restbefunde. Die geprüften
Markdown-Artefakte sind aus Integrationssicht bereit für die finale
DOCX-/PDF-Erzeugung und deren visuelle Abschlusskontrolle.
