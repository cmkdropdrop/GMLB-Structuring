# Technische Dokument- und Darstellungsprüfung

## Kurzurteil

Die vorhandenen Dateien sind **layoutseitig weitgehend konsistent**, aber wegen der
Formeldarstellung **noch nicht freigabefähig**. Der zentrale Blocker liegt bereits in
`AGILE_Modelling_Fachpaper.md`: Inline-Mathematik ist fast durchgehend nicht als
Mathematik ausgezeichnet, zwölf TeX-Befehle werden beim DOCX-Satz still entfernt und
zwei rohe Steuerzeichen verstümmeln `\rho` beziehungsweise `\varphi`. Diese Fehler
erscheinen übereinstimmend in DOCX und PDF; die gute DOCX↔PDF-Konsistenz ist daher kein
Richtigkeitsnachweis.

Abgesehen davon ist das Rendering stabil: Word und PDF haben jeweils 48 Seiten, alle
101 Markdown-Überschriften sind im PDF auffindbar, 23 Tabellen und 10 Abbildungen sind
enthalten, es gibt keine leeren Seiten und keinen geometrisch abgeschnittenen Text.

Severity: **Blocker** = vor Freigabe zwingend; **Hoch** = wesentlicher technischer
Qualitätsmangel; **Mittel** = klarer Satz-/Navigationsmangel; **Niedrig** = Optimierung.

## Befunde

### DV-01 — Blocker: Inline-LaTeX wird nicht als Mathematik gesetzt und verliert Inhalt

Mit dem für die Display-Formeln notwendigen Reader
`markdown+tex_math_single_backslash` erkennt Pandoc **48 DisplayMath-, aber 0
InlineMath-Knoten**. Gleichzeitig verbleiben zwölf rohe TeX-Inlines:
`\ge 0`, `\le 1`, `\times`, `\max`, `\ge 1`, `\ge1`, `\rho`, `\sigma`,
`\times`, `\max`, `\times`, `\max`. Word verwirft diese Befehle außerhalb eines
Mathematikknotens. Das ist teilweise semantischer, nicht nur typografischer Verlust.

Konkrete PDF-Fundstellen:

- Seite 9, Markdown-Zeile 243: `(C\ge 0)` wird zu `(C)`; die Nebenbedingung fehlt.
- Seite 10: `X=S_T/S_0`, `Call(K)` und `Put(K)` erscheinen als normaler Text mit
  sichtbaren Unterstrichen statt als Inline-Formeln.
- Seiten 12 und 14: `e_t`, `W_t`, `S_t`, `v_t`, `r_t`, `CF_t`, `q_i` erscheinen als
  Rohnotation.
- Seiten 15–16: `sigma_{AUS}`, `sigma_{Global}`, `phi(t)`, `sigma_r`, `v_t`,
  `U_k` und weitere Variablen bleiben Rohtext; siehe zusätzlich DV-02.
- Seite 19, Zeilen 788/801: `(f^*_{LIP})` bleibt Rohnotation; aus
  `(p_z(s)\le 1)` wird `(p_z(s))`, also ohne Ungleichung.
- Seite 20, Zeile 859: aus `40\%\times\max(NAV,0)` wird `40%(NAV,0)`.
- Seite 21, Zeilen 904/912: aus `y\ge 1` beziehungsweise `y\ge1` wird jeweils nur
  `(y)`; der Gültigkeitsbereich fehlt.
- Seite 23, Zeilen 1023–1024: `\rho_{Sv}` und `\sigma_r` werden zu `_{Sv}` und `_r`;
  die Parameternamen fehlen in der Annahmentabelle.
- Seite 24, Zeile 1065: `(1{,}96\times SE)` wird zu `(1{,}96SE)`; die sichtbaren
  TeX-Klammern bleiben, das Multiplikationszeichen fehlt.
- Seite 27, Zeilen 1141/1143: `\max(0,Loss)` wird zu `((0,Loss))` und
  `40\%\times\max(NAV,0)` zu `40%(NAV,0)`.
- Seiten 29–30, Zeilen 1177–1178/1203: `q_x` erscheint als Rohtext; die schmale
  Tabellenspalte verstärkt die schlechte Lesbarkeit.
- Seite 42, Zeile 1643: `(SE=42{,}25)` zeigt die TeX-Dezimalklammern sichtbar.
- Seiten 43–44, Zeilen 1701–1715: die gesamte Notationstabelle zeigt Symbole wie
  `(S_t)`, `(BEL_{NU})` und `(VNB_{gross})` als Rohtext.

Maßnahme: sämtliche mathematischen Inline-Ausdrücke explizit als `$...$` oder
`\(...\)` auszeichnen; `$...$` ist hier robuster, da Geldbeträge ohnehin als `AUD`
geschrieben werden. Im Preflight müssen danach `InlineMath > 0` und — abgesehen von
bewusst erlaubtem Raw-OpenXML — `RawInline(tex) = 0` gelten.

### DV-02 — Blocker: Zwei rohe Steuerzeichen verstümmeln mathematische Bezeichner

Die UTF-8-Datei enthält genau zwei unerlaubte Steuerzeichen:

- Byte-Offset 24.227, LF-basierte Zeile 567, Spalte 2: `0x0D` (lone carriage return)
  anstelle des Backslashs in `\rho_{Sv}`. Im PDF steht auf Seite 15
  `(ho_{Sv}=-0{,}60)`.
- Byte-Offset 25.128, LF-basierte Zeile 589, Spalte 30: `0x0B` (vertical tab) in
  `\varphi(u)`. Im PDF steht auf Seite 16 `(arphi(u))`.

Ein Editor, der den lone CR als Zeilenende zählt, kann die zweite Fundstelle als Zeile
590 anzeigen. Maßnahme: Steuerzeichen ersetzen und im Build alle Zeichen aus
`U+0000–U+0008`, `U+000B`, `U+000C`, `U+000E–U+001F` sowie lone CR hart ablehnen.

### DV-03 — Hoch: PDF-Navigation und Metadaten sind unvollständig

Das PDF ist erfreulich gut getaggt (`/Marked true`, `/StructTreeRoot`, Sprache `de`) und
enthält 166 gültige interne GoTo-Links sowie 32 syntaktisch gültige URI-Links. Dennoch:

- PDF-Titel, Autor, Betreff und Keywords sind leer, obwohl die DOCX-Core-Properties
  `AGILE Modelling` und `Interne Fach- und Lernunterlage` enthalten.
- Es gibt **keinen PDF-Outline-/Bookmark-Baum**.
- Es gibt keine PDF-Seitenlabels und auf keiner der 48 Seiten eine sichtbare
  Seitenzahl; DOCX enthält weder Header noch Footer.

Das sichtbare Inhaltsverzeichnis ist intern verlinkt, ersetzt bei einem 48-seitigen
Fachpaper aber weder Outline noch Seitenzahlen. Beim Word-Export sind
`IncludeDocProps=true`, `CreateBookmarks=wdExportCreateHeadingBookmarks` und
`DocStructureTags=true` zu setzen; der Referenz-DOCX braucht einen PAGE-Feld-Footer.

### DV-04 — Mittel: DOCX-Paginierung hängt von impliziten Word-Defaults ab

Das DOCX enthält im finalen `sectPr` keine expliziten `w:pgSz`-/`w:pgMar`-Werte. Auf
diesem Rechner löst Word das als **US Letter 612×792 pt** mit Rändern
70,9/70,9/70,9/56,7 pt (links/rechts/oben/unten) auf. Auf einem anderen Word-Profil
können Defaultformat und -ränder abweichen und dadurch TOC, Tabellen- und
Abbildungsumbrüche verändern. Für ein deutschsprachiges beziehungsweise australisches
Fachpaper wäre zudem zu klären, ob statt US Letter ausdrücklich A4 gewollt ist.

Maßnahme: Seitenformat und Ränder im dedizierten `reference-doc` explizit speichern und
die Ausgabe immer auf derselben Word-/Font-Umgebung neu paginieren.

### DV-05 — Mittel: DOCX-Statistik ist stale und widerspricht dem tatsächlichen Umfang

`docProps/app.xml` meldet `Pages=1`, `Words=83`, `Characters=475`, obwohl Word live
48 Seiten, 9.760 Wörter und 68.478 Zeichen berechnet. Die Core-Metadaten sind dagegen
plausibel. Das ist typisch für ein von Pandoc erzeugtes, anschließend nur exportiertes,
aber nicht nochmals gespeichertes DOCX.

Maßnahme: nach TOC-/Field-Update `Repaginate()` und `Save()` ausführen, erst danach das
PDF exportieren und die Package-Statistik im Postflight erneut prüfen.

### DV-06 — Mittel: Titel, TOC und Haupttext sind satztechnisch nicht sauber getrennt

Der Titel steht auf Seite 1 direkt über dem Inhaltsverzeichnis; das TOC läuft über die
Seiten 1–4. Auf Seite 4 folgen nach den letzten TOC-Zeilen unmittelbar
`Dokumentstatus` und `Zusammenfassung`, ohne Seitenumbruch. Das funktioniert, wirkt aber
nicht wie ein abgeschlossenes Fachpaper. TOC-Tiefe 3 nimmt zudem generische Einträge wie
`Interpretation`, `Interne Validität` oder `Statistische Validität` auf und verlängert das
TOC auf vier Seiten.

Maßnahme: eigenständige Titelseite, Seitenumbruch vor dem TOC und vor dem Haupttext;
TOC-Tiefe 2 erwägen oder H3-Einträge qualifizieren.

### DV-07 — Mittel: Abbildungen sind technisch ausreichend, bei 100 % aber klein

Die zehn DOCX-PNGs liegen effektiv bei etwa 400–532 dpi. Word reduziert sie im PDF auf
jeweils 1.108 Pixel Breite beziehungsweise rund **200 dpi**. Das ist kein
Pixelierungsblocker, und keine Abbildung ist abgeschnitten. Die in den Rastergrafiken
eingebetteten Achsen-, Legenden- und Fußnotenschriften sind auf den Seiten 25–36 bei
100-%-Ansicht jedoch deutlich kleiner als der Fließtext, besonders in den mehrteiligen
Abbildungen auf Seiten 25, 31, 34 und 35.

Maßnahme: Plot-Schriften vergrößern, komplexe Panels aufteilen oder SVG/EMF verwenden;
für hochwertigen Druck 300 dpi im finalen PDF anstreben.

### DV-08 — Niedrig: Einzelne Tabellen und technische Pfade sind unnötig schwer lesbar

- Seite 29: die erste Spalte der sechs-spaltigen Sensitivitätstabelle bricht Labels wie
  `Longevity`, `Mortality` und `Free Withdrawal` in viele kurze Zeilen.
- Seiten 44–46: sehr lange Codepfade und Allianz-URLs werden korrekt umbrochen, dominieren
  aber optisch. Kürzere Linktexte bei unverändertem Linkziel wären lesbarer.
- Tabellenköpfe wiederholen sich korrekt über Seitenumbrüche; aktuell wurde keine Zeile
  sichtbar geteilt oder abgeschnitten.

## Bestätigte Positivbefunde und DOCX↔PDF-Konsistenz

- Quelle unverändert geprüft; SHA-256:
  - Markdown `b27fea58845c7a6f7bbf8b5de953c7cb273e8969b5e4b9bae1be7c8ed0eea41e`
  - DOCX `6992976907be4eecc509add05e4c9ab9aa9a84f24505a030681a2f6f168434ab`
  - PDF `ab0afd6bdbffab3390679abfb2ff41910cbf54e63691b1a9f4ff0bcb80480cce`
- Word und PDF: jeweils 48 Seiten; PDF-Format 1.7, Letter 612×792 pt.
- Markdown/Pandoc/DOCX: 101 Überschriften, 23 Tabellen, 10 Bilder; keine doppelten
  Heading-IDs und keine Sprünge in der Überschriftenhierarchie. Alle Überschriften sind
  im PDF auffindbar.
- Das Word-TOC spannt die Seiten 1–4 auf, nutzt Heading-Level 1–3 und Hyperlinks. Alle
  53 internen DOCX-Linkanker besitzen ein Bookmark-Ziel.
- Word meldet 48 Office-Math-Objekte; PDF enthält 52 von Word angelegte
  `equation-*.xml`-Accessibility-Anhänge. Die 48 Display-Formeln werden sichtbar als
  Formeln gesetzt; das Problem betrifft die nicht ausgezeichneten Inline-Formeln.
- Alle 13 im PDF verwendeten Font-XRefs sind als Teilmengen eingebettet; DOCX selbst
  bettet keine Fonts ein und setzt unter anderem Aptos, Aptos Display, Cambria Math und
  Consolas voraus.
- Alle zehn Markdown-Bildziele existieren. DOCX enthält zehn Inline-Bilder und keine
  Floating Shapes. PDF enthält dieselben zehn Abbildungen auf Seiten 25, 26, 28 und
  30–36.
- 30 zitierte Schlüssel, 33 BibTeX-Einträge, keine unaufgelösten Zitate. Das
  Literaturverzeichnis beginnt auf Seite 45 und endet auf Seite 48.
- PDF: 198 gültige Links, keine ungültigen Seitenziele oder Schemes; keine leere Seite,
  kein Text-Span außerhalb der MediaBox und kein Element näher als 35 pt an der linken
  oder rechten Kante.
- Tokenbasierter DOCX↔PDF-Abgleich: 95,3 % der DOCX- und 91,3 % der PDF-Tokens liegen in
  der Multiset-Schnittmenge; die Differenz stammt überwiegend aus TOC-Dopplungen,
  mathematischer Extraktionsreihenfolge und Layouttext. Zusammen mit identischer
  Seitenzahl, vollständigen Überschriften und Objektzählungen gibt es keinen Hinweis auf
  eine zusätzliche Exportabweichung.

## Robuste, nicht überschreibende spätere Erzeugungskette

Die folgende Kette wurde **nicht** auf einer unfertigen `reviewed.md` ausgeführt.

1. **Explizite Zielnamen und Guards.** Als neue Dateien etwa
   `AGILE_Modelling_Fachpaper.reviewed.docx` und `.reviewed.pdf` verwenden. Vor jedem
   Schritt bei vorhandenen Zielen abbrechen; zunächst auf eindeutige `.partial`-Namen
   schreiben und erst nach bestandenem Postflight umbenennen.
2. **Markdown-Preflight.** UTF-8 strict lesen; verbotene Steuerzeichen und lone CR
   ablehnen; alle lokalen Bildziele prüfen; Pandoc-AST mit
   `markdown+tex_math_single_backslash` und `--citeproc` erzeugen. Erwartungswerte nach
   der Korrektur: 23 Tabellen, 10 Bilder, 48 DisplayMath, sinnvoll viele InlineMath,
   keine ungewollten Raw-TeX-Inlines und keine unaufgelösten Zitate.
3. **Dediziertes Referenz-DOCX.** Explizites A4- oder Letter-Format, feste Ränder,
   Aptos-/Cambria-Math-Stile, Caption-/Table-Stile, wiederholte Tabellenköpfe,
   PAGE/NUMPAGES-Footer sowie Seitenumbrüche für TOC und Haupttext speichern. Das
   bestehende Fachpaper nicht als stillschweigenden Default verwenden, solange dessen
   Seitengeometrie und Footer nicht bereinigt sind.
4. **Pandoc in ein neues DOCX.** Sinngemäß:

   ```powershell
   pandoc .\AGILE_Modelling_Fachpaper.reviewed.md `
     --from=markdown+tex_math_single_backslash `
     --to=docx --standalone --toc --toc-depth=2 --citeproc `
     --reference-doc=.\_review_work\reference-review.docx `
     --resource-path=".;AGILE_Modelling_Engine" `
     --output=.\_review_work\AGILE_Modelling_Fachpaper.reviewed.partial.docx
   ```

   `--number-sections` nicht zusätzlich setzen, solange die Überschriften bereits
   Nummern enthalten.
5. **Word-COM-Finalisierung.** Nur das neu erzeugte DOCX öffnen; alle Story-/TOC-Felder
   aktualisieren, neu paginieren, speichern und anschließend mit
   `IncludeDocProps=true`, Heading-Bookmarks und Document-Structure-Tags als neues PDF
   exportieren. Kernaufruf:

   ```powershell
   $doc.Repaginate()
   $doc.Fields.Update() | Out-Null
   foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
   $doc.Save()
   $doc.ExportAsFixedFormat(
       $partialPdf, 17, $false, 0, 0, 1, 9999, 0,
       $true, $true, 1, $true, $true, $false
   )
   ```

   COM-Objekte in `finally` schließen; niemals bestehende DOCX/PDF-Ziele öffnen oder
   speichern. Der equationsreiche Word-Export kann mehrere Minuten beanspruchen und
   sollte mit kontrolliertem Polling statt einem kurzen Blind-Timeout überwacht werden.

   Operative Stichprobe: die read-only Word-Inspektion paginierte das vorhandene DOCX
   erfolgreich auf 48 Seiten. Ein zusätzlicher temporärer PDF-Re-Export wurde nach 120
   Sekunden kontrolliert beendet, bevor Word eine Zieldatei geschrieben hatte. Das ist
   kein Konsistenzfehler, zeigt aber, dass der spätere Automationslauf ein längeres,
   überwachtes Exportfenster benötigt. Die unfertige `reviewed.md` wurde nicht benutzt.
6. **Postflight vor Umbenennung.** Word- und PDF-Seitenzahl vergleichen; PDF-Titel und
   Autor, Outline, Tags, Sprache, Linkziele, 23 Tabellen/10 Bilder/Formelanzahl und
   Seitengeometrie prüfen; Kontrollseiten und Contact Sheet rendern; SHA-256-Manifest
   schreiben. Nur wenn alle harten Checks bestehen und die finalen Zielnamen weiterhin
   frei sind, `.partial` in `.reviewed.docx/.reviewed.pdf` umbenennen.

## Prüfartefakte

- `technical_diagnostics.txt`: maschinelle Detailausgabe zu Markdown, DOCX-XML und PDF.
- `word_inspection.txt`: Word-Live-Zählungen, Section-Setup und vollständiger TOC-Text.
- `document_visual_formula_contact.png`: Seiten 9, 10, 15, 16, 23, 24, 29, 43, 44.
- `document_visual_layout_contact.png`: Seiten 1, 4, 25, 29, 33, 36, 44, 45, 48.

Der read-only Word-Lauf und alle XML/PDF-Prüfungen ließen die drei vorhandenen
Quelldateien unverändert.
