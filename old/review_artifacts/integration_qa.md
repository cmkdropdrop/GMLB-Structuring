# Unabhängige Integrations-QA der Review-Artefakte

**Prüfstand:** 11. Juli 2026  
**Geprüft:** `AGILE_Modelling_Fachpaper_reviewed.md`,
`AGILE_Modelling_references_reviewed.bib`,
`AGILE_Modelling_Claim_Evidence_Matrix.csv` sowie die drei vollständigen
Teilmemos `product_regulatory.md`, `code_numeric.md` und `literature.md`.

## Gesamturteil

Die Revision übernimmt sämtliche HOCH-Befunde inhaltlich richtig. Es wurde
kein neuer KRITISCHER oder HOHER Fehler und keine falsche neue Ergebniszahl,
URL oder Zitationsverknüpfung gefunden. Vier MITTEL-Befunde sind jedoch nur
teilweise umgesetzt; damit ist die inhaltliche Integration noch nicht ganz
abgeschlossen. Zusätzlich verbleiben zwei redaktionelle NIEDRIG-Punkte.

**Reststatus:** 0 KRITISCH, 0 HOCH, 4 MITTEL, 2 NIEDRIG.

## Verbleibende Befunde

### IQ-M-01 — Age-Pension+-Investor-Eligibility bleibt zu unbestimmt

**Priorität:** P2 / MITTEL  
**Fundstelle:** `AGILE_Modelling_Fachpaper_reviewed.md`, Z. 512–519;
Matrix-Zeile 32; `product_regulatory.md`, MITTEL-PROD-07.

Election, Unwiderruflichkeit und funding-spezifischer Beginn sind korrekt
eingearbeitet. Der Satz „Die Option steht nicht jeder Investor-Struktur offen“
setzt den Eligibility-Befund aber nicht konkret um. Das Teilmemo nennt die
fehlende Vertragsregel ausdrücklich: Non-superannuation-Trustee- und
Company-Investors sind grundsätzlich ausgeschlossen; ausgenommen sind
Non-super-Platform-Trustees.

**Erforderlich:** Diese Investorgruppen und die Ausnahme ausdrücklich nennen,
statt nur pauschal auf eingeschränkte Verfügbarkeit hinzuweisen.

### IQ-M-02 — Spouse-Designmodellpunkt legt die Death Election nicht offen

**Priorität:** P2 / MITTEL  
**Fundstelle:** `AGILE_Modelling_Fachpaper_reviewed.md`, Z. 1475–1480;
Matrix-Zeile 82; `code_numeric.md`, C-10.

Alter und Gender des zweiten Lebens sind nun korrekt offengelegt
(Frau, 63). Der ebenfalls ergebnisrelevante Runner-Input
`spouse_death_election="continue_income"` fehlt weiterhin unmittelbar vor der
Design-Tabelle. Der allgemeine Produktabschnitt über Wahlrecht und PDS-Default
ersetzt die Offenlegung des konkret gerechneten Szenarioinputs nicht.

**Erforderlich:** Den Modellpunkt zu „Frau, 63, Continue Income“ ergänzen.

### IQ-M-03 — LSMC-Grenzen nur teilweise aus C-08 übernommen

**Priorität:** P2 / MITTEL  
**Fundstelle:** `AGILE_Modelling_Fachpaper_reviewed.md`, Z. 1173–1188;
Matrix-Zeile 67; `code_numeric.md`, C-08.

Alter-105-/40-Jahre-Horizont und ab Issue gebildete Joint-Life-Dekremente sind
korrekt ergänzt. Nicht konkret übernommen wurden zwei weitere Befunde:

- Der Tail verwendet einen pauschalen 30-jährigen Zero Rate und den Closeout
  `max(account, income * annuity_factor)`.
- Die Static Policy ist der im LSMC implementierte feste Startpfad, nicht das
  vollständige dynamische Verhalten des Monatsmotors.

„Approximiert … Tail Closeout“ ist hierfür zu unspezifisch und widerspricht
auch der Matrixforderung „Grenzen vollständig ergänzen“.

**Erforderlich:** Beide Implementierungsgrenzen in Abschnitt 9.4 explizit
ergänzen.

### IQ-M-04 — Automatischer Start: Konsequenz fehlender Kontakt-/Bankdaten fehlt

**Priorität:** P2 / MITTEL  
**Fundstelle:** `AGILE_Modelling_Fachpaper_reviewed.md`, Z. 235–242 und
1823–1825; Matrix-Zeile 7; `product_regulatory.md`, MITTEL-PROD-02.

Automatischer Income Start und Default Fixed ohne Spouse sind richtig
übernommen. Das Paper erwähnt am Production-Blocker nur unspezifisch eine
„Kontakt-/Bankdatenlogik“. Nicht offengelegt wird der im Teilmemo aus dem PDS
festgehaltene Vorbehalt, bei fehlenden Kontakt- oder Bankdaten einen Full
Withdrawal vorzunehmen.

**Erforderlich:** Diese mögliche Vertragsfolge ausdrücklich und als
PDS-Vorbehalt ergänzen; nicht als deterministische Engine-Regel formulieren.

### IQ-N-01 — Verbleibende Pseudo-Mathematik in runden Klammern

**Priorität:** P3 / NIEDRIG  
**Fundstelle:** insbesondere Z. 362 `(g)`, 644 `(z(t))`, 760 `(x)`,
784 `(i(x))`/`(s)`, 975 `Time-(s)` und 2016 `(PVFP)`.

Die eigentlichen Formeln sind technisch sauber, diese Reststellen werden aber
als Prosa statt Mathematik gerendert und sind gegenüber der sonst
vereinheitlichten `$…$`-Notation inkonsistent.

**Erforderlich:** In `$g$`, `$z(t)$`, `$x$`, `$i(x)$`, `$s$`, Time-$s$ und
`$PVFP$` ändern.

### IQ-N-02 — Sichtbares `APS` bleibt außerhalb reiner Codebezeichner stehen

**Priorität:** P3 / NIEDRIG  
**Fundstelle:** `AGILE_Modelling_Fachpaper_reviewed.md`, Z. 1685 und 1808;
vgl. `product_regulatory.md`, NIEDRIG-TERM-01.

Die Design-Tabelle verwendet korrekt „Age Pension+“, und das Runner-Kürzel
wird bei der Abbildung erklärt. In Auditliste und Production-Blocker steht
dennoch wieder unqualifiziert `APS`. Das ist weder offizieller Produktbegriff
noch dort ein sichtbarer Codefeldname.

**Erforderlich:** An diesen Stellen „Age Pension+“ verwenden; `aps`/`APS` nur
bei ausdrücklich als intern bezeichneten Code- oder Abbildungslabels lassen.

## Nachweis der vollständig umgesetzten materiellen Befunde

- **Produkt/Regulatorik:** Group-Policy-/Garantiequalifikation,
  Commencement-/Anniversary-Vintage, Guaranteed-Minimum-Begriff,
  Fixed-Return-Branch, DVA-Mindestwerte, Age-Pension+-Lower-of-Withdrawal,
  Spouse-Default, Fee-Änderungsrecht und vollständige LPS-110/114/115/117/118-
  Architektur sind widerspruchsfrei übernommen. Equal-age-/fractional-age-
  Rating und APRA-VA-Klassifikation bleiben richtigerweise OFFEN.
- **Code/Numerik:** Greek-`FrozenInstanceError`, unvollständige
  Run-Provenienz, negativer Heston--HW-Term, effektiver Outcome-Seed 2027,
  Off-anniversary-IV/SV-Abweichung, bedingtes `p_z<=1`, statistische
  LSMC-Lower-Bound-Qualifikation, Maintenance-Expense-Scope, fehlende
  MC-Fehlermaße und symmetrische Steuerentlastung sind korrekt dargestellt.
- **Literatur:** `deng2017` hat Geng Deng/Mike Yan, keinen `doi`-Eintrag und
  die stabile Publisher-URL; das Juli-2026-Maximum-Returns-PDF ist statisch
  bibliografiert; Methodology und Run werden im Text zitiert; lokale Quellen
  sind als interne Artefakte qualifiziert; Goudenège- und Mortalitätsclaims
  sind auf die zitierten Modelle begrenzt. Die beiden Fehler des lokalen
  Literaturindex werden korrekt dokumentiert.

## Technische QA

### CSV

- UTF-8 ohne BOM; 94 physische Zeilen = Header + 93 Datensätze.
- Strikter CSV-Parse erfolgreich; jede Zeile hat exakt sieben Felder.
- Header entsprechen dem Auftrag; alle vier Typwerte sind zulässig.
- Keine leeren Pflichtfelder, keine doppelten Datensätze, keine Steuerzeichen.

### Zitation/BibTeX

- 35 unterschiedliche In-text-Schlüssel und 35 BibTeX-Schlüssel.
- 0 fehlende, 0 doppelte und 0 unzitierte Schlüssel.
- Pandoc 3.7.0.2 mit Citeproc: Exit Code 0.
- `deng2017` enthält den nicht registrierten Publisher-String nur erklärend im
  `note`, nicht fälschlich als DOI-Feld.
- Sämtliche neu eingeführten URLs stimmen exakt mit den in den Teilmemos
  verifizierten Primärquellen überein; keine fremde oder syntaktisch fehlerhafte
  URL gefunden.

### Markdown/Formeln/Dateien

- Alle drei Artefakte sind strikt valides UTF-8 ohne BOM, NUL oder sonstige
  C0-/DEL-Steuerzeichen. Die im Original vorhandenen Einzelzeichen `CR` und
  `VT` wurden in der Review-Fassung beseitigt.
- Pandoc-Parse mit `markdown+tex_math_single_backslash`: 49 Display-Math- und
  101 Inline-Math-Knoten, 0 Raw-TeX-Reste; Citeproc- und DOCX-Writer-Pipeline
  jeweils Exit Code 0.
- Alle zehn Bildpfade und der YAML-Bibliografiepfad existieren.
- Der neu berichtete Runner-Hash wurde bytegenau bestätigt:
  `8ea89d2f1c99940e74551402288d8835c4799fdbac18b9c9784c79433b63a244`.
- Neue Zahlen und DOI-/URL-Angaben sind auf Teilmemo, Ergebnisartefakt oder
  unmittelbare Nachrechnung zurückführbar; keine neue falsche Zahl gefunden.

## Integrität der Originaldateien

Die in `_review_work/technical_diagnostics.txt` vor der Revision protokollierten
Hashes stimmen weiterhin bytegenau:

| Original | SHA-256 | Status |
|---|---|---|
| `AGILE_Modelling_Fachpaper.md` | `b27fea58845c7a6f7bbf8b5de953c7cb273e8969b5e4b9bae1be7c8ed0eea41e` | unverändert |
| `AGILE_Modelling_Fachpaper.docx` | `6992976907be4eecc509add05e4c9ab9aa9a84f24505a030681a2f6f168434ab` | unverändert |
| `AGILE_Modelling_Fachpaper.pdf` | `ab0afd6bdbffab3390679abfb2ff41910cbf54e63691b1a9f4ff0bcb80480cce` | unverändert |

Für `AGILE_Modelling_references.bib` enthält das Vorabdiagnostikprotokoll
keinen Baseline-Hash. Der aktuelle Hash lautet
`a6befec73ad7c7525ea3260b88a24b27a3830cceccd7c32d88c8ea37f8513240`;
Größe (11.773 Bytes) und Änderungszeit (11.07.2026 07:26:20) liegen vor allen
drei Teilmemos und vor den Review-Artefakten. Es gibt daher keinen Hinweis auf
eine Änderung, aber ohne gespeicherten Vorher-Hash keinen gleich starken
kryptografischen Nachweis wie bei den drei Fachpaper-Originalen.

## Freigabeempfehlung

Nach Schließung von IQ-M-01 bis IQ-M-04 sind die drei geprüften Artefakte aus
Integrationssicht fachlich konsistent. IQ-N-01 und IQ-N-02 sollten vor einer
DOCX-/PDF-Erzeugung mitbereinigt werden. Bis dahin lautet der Status:
**inhaltlich weitgehend bestanden, redaktionelle Nacharbeit erforderlich**.
