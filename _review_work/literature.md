# Unabhängiger Literatur- und Zitationsaudit

**Prüfgegenstand:** `AGILE_Modelling_Fachpaper.md` und
`AGILE_Modelling_references.bib`  
**Zusatzmaterial:** lokaler Literaturindex und lokale Volltexte unter
`Papers on Pricing/`  
**Stichtag:** 11. Juli 2026  
**Dateistatus:** Dieser Audit verändert keine bestehende Projektdatei.

## 1. Kurzurteil

Die wissenschaftliche Kernauswahl des Fachpapers ist überwiegend korrekt
bibliografiert und trägt die jeweils zitierten methodischen Aussagen. Erfasst
wurden **53 Zitationsvorkommen mit 30 verschiedenen Zitationsschlüsseln**. Die
`.bib` enthält zusätzlich drei nicht zitierte Einträge
(`fergusson2025`, `agilemethodology2026`, `agilerun2026`). Sämtliche **21 in
der Kernbibliografie vorhandenen DOI-Strings** wurden geprüft: 20 besitzen
einen passenden Crossref-Datensatz; der bei `deng2017` vom Verlag angezeigte
String besitzt weder dort noch bei doi.org einen auflösbaren Datensatz. Soweit
erreichbar, wurde zusätzlich die Verlagsseite oder ein Originalvolltext
geöffnet.
Ein vollständiger Pandoc/Citeproc-Lauf fand keinen fehlenden
Zitationsschlüssel; auch die neue BibTeX-Vorschlagsdatei wurde von Citeproc
fehlerfrei geparst.

Materielle Befunde:

1. **HOCH — `deng2017`: falsche Autorenvornamen und nicht auflösender DOI.**
   Der Verlag nennt **Geng Deng** und **Mike Yan**, nicht Guowei Deng und Meng
   Yan. Der auf der Verlagsseite angezeigte String
   `10.21314/JCF.2017.331` lieferte am Prüfdatum sowohl bei `doi.org` als auch
   in Crossref HTTP 404; die offizielle
   [doiRA-Abfrage](https://doi.org/doiRA/10.21314/JCF.2017.331) meldete
   ausdrücklich `DOI does not exist`. Titel, Journal, Band, Heft, Jahr und Seiten sind auf
   der [offiziellen Risk.net-Artikelseite](https://www.risk.net/journal-of-computational-finance/5316511/efficient-valuation-of-equity-indexed-annuities-under-levy-processes-using-fourier-cosine-series)
   bestätigt. Bis der Verlag den Resolverdatensatz repariert, sollte der
   Zeitschriftenartikel ohne `doi` und mit der stabilen Verlags-URL zitiert
   werden.
2. **MITTEL — nicht reproduzierbare Vintage-Zitation der Maximum Returns.**
   Die Juli-2026-Caps werden im Paper über die dynamische Rates-Centre-Seite
   (`allianz2026ratescentre`) belegt. Die Seite ist heute korrekt, wird aber
   monatlich umgestellt. Für die konkrete Juli-Vintage sollte zusätzlich bzw.
   stattdessen das offizielle, statische
   [Juli-2026-Maximum-Returns-PDF](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Maximum_Returns_Jul26.pdf)
   zitiert werden.
3. **MITTEL — fehlende Quellenverknüpfung zu zwei bereits vorhandenen
   `.bib`-Einträgen.** Die konkrete Behauptung über die Aussage der Methodology
   in Zeilen 983–987 sollte `@agilemethodology2026` zitieren. Die numerischen
   Resultate des instrumentierten Laufs sollten bei ihrer ersten Tabelle
   `@agilerun2026` zitieren. Beide Einträge sind derzeit unzitiert.
4. **NIEDRIG — `actuariesinstitute2024`: Körperschaftsurheber präzisieren.**
   Das Original nennt die *Retirement Incomes Working Group* als erstellende
   Gruppe. Die pauschale Körperschaftsautorschaft „Actuaries Institute“ ist
   nicht falsch, aber weniger präzise.
5. **NIEDRIG — `fang2008`: Publikationsjahr transparent machen.** SIAM nennt
   Online-Publikation am 14. November 2008 und Copyright 2008; Crossref führt
   die Band-/Heftpublikation als Januar 2009. `year = 2008` ist als
   Online-first-Konvention vertretbar. Ein vollständiges Datum oder eine Notiz
   verhindert scheinbare Inkonsistenz.
6. **MITTEL — lokale Projektquellen sind keine externen Gutachten.** Die
   Einträge `agileengine2026`, `agilemethodology2026`, `agileaudit2026` und
   `agilerun2026` sind nachvollziehbare lokale Artefakte, aber haben keinen
   benannten externen Autor oder Herausgeber. Das Paper begrenzt diesen Status
   in Abschnitt 2.1 bereits korrekt. Im Literaturverzeichnis sollten dennoch
   Pfad, Version/Datum und gegebenenfalls Hash genannt werden; insbesondere
   darf der Titel „Unabhängiger Audit“ nicht als externes Third-Party-Gutachten
   gelesen werden.

Es wurde **keine unzulässige Übertragung externer Fair-Fee- oder
Sensitivitätszahlen auf AGILE** gefunden. Die numerischen Fair-LIP-, VNB- und
Sensitivitätswerte werden als Resultate des lokalen Laufs ausgewiesen; der
Anhang warnt ausdrücklich vor einer Übertragung fremder Studien. Zwei
qualitative Sätze sollten gleichwohl noch enger auf die jeweiligen
Literaturmodelle begrenzt werden (siehe Abschnitt 4).

## 2. Prüfmethodik und Evidenz

- Alle `@key`-Vorkommen wurden direkt aus dem Markdown extrahiert und gegen
  alle BibTeX-Schlüssel abgeglichen.
- DOI-Metadaten wurden über die Crossref-Works-API abgefragt. Anschließend
  wurden DOI-/Verlagsseiten oder Originalvolltexte geöffnet. Ein bloßer
  Treffer in einem Suchindex wurde nicht als endgültiger Nachweis behandelt.
- Für arXiv wurde der offizielle arXiv-Datensatz und der von arXiv/Datacite
  vergebene DOI verwendet.
- Für Produkt- und Aufsichtsquellen wurden ausschließlich Allianz Retire+ bzw.
  APRA verwendet.
- Für die inhaltliche Claim-Prüfung wurden insbesondere folgende lokale
  Volltexte geöffnet: Bauer et al.; Kling et al.; Huang/Kwok;
  Shevchenko/Luo; Goudenège/Molent/Zanette; Alonso-García/Wood/Ziveyi;
  Piscopo/Haberman; Fung/Ignatieva/Sherris; Gudkov/Ignatieva/Ziveyi;
  Steinorth/Mitchell; Cairns/Blake/Dowd; Langrené et al.; Fergusson et al.;
  außerdem das Actuaries-Institute-Technical-Paper.
- Verlässliche Prüfendpunkte sind in den Tabellen als DOI-Link bzw. direkte
  Publisher-/Behörden-URL angegeben.

Bewertung: **KRITISCH**, **HOCH**, **MITTEL**, **NIEDRIG** und **OFFEN**
entsprechen der im Prüfauftrag vorgegebenen Skala. „OK“ bedeutet, dass kein
Korrekturbedarf gefunden wurde.

## 3. Vollständige Zitationsinventur

Die folgende Liste erfasst jeden im Text verwendeten Schlüssel und sämtliche
Zeilen, in denen er vorkommt. Zeilennummern beziehen sich auf die unveränderte
`AGILE_Modelling_Fachpaper.md` am Prüfdatum.

| Schlüssel | Zeile(n) | Kurzstatus |
|---|---:|---|
| `actuariesinstitute2024` | 1582 | Claim getragen; Körperschaftsurheber präzisieren |
| `agileaudit2026` | 156, 475 | lokaler Primärbeleg getragen; kein externes Gutachten |
| `agileengine2026` | 154 | lokaler Codebeleg getragen |
| `allianz2026minimums` | 151, 231 | offiziell und getragen |
| `allianz2026pds` | 32, 151, 201, 340, 351, 361, 370, 387, 401 | offiziell und überwiegend seitenpräzise; DVA-Seiten ergänzen |
| `allianz2026rates` | 151, 312 | offiziell und getragen |
| `allianz2026ratescentre` | 229 | aktuell getragen, aber dynamische URL; Vintage-PDF vorziehen |
| `alonsogarcia2018` | 604, 1762 | getragen |
| `apra2023lps110` | 879 | offiziell und getragen |
| `apra2026lps114` | 881 | offiziell und getragen |
| `bauer2008` | 153, 216, 1759 | getragen |
| `blackscholes1973` | 292 | getragen |
| `cairns2006` | 651 | methodischer Mortality-Risk-Rahmen getragen; nicht AGILE-spezifisch |
| `deng2017` | 1758 | Claim getragen; Metadaten HOCH zu korrigieren |
| `fang2008` | 588 | getragen; Jahreskonvention erläutern |
| `fung2014` | 651 | getragen; quantitative Höhe nicht auf AGILE übertragbar |
| `goudenege2016` | 550, 1761 | getragen mit Scope-Einschränkung |
| `gudkov2019` | 1761 | getragen |
| `heston1993` | 554 | getragen |
| `holz2012` | 1760 | getragen |
| `huangkwok2016` | 153, 951, 1762 | getragen |
| `hullwhite1990` | 573 | getragen |
| `kling2014` | 153, 691, 729, 1761 | getragen; Parameter ausdrücklich nicht AGILE-kalibriert |
| `langrene2026` | 988 | getragen; Preprintstatus korrekt benannt |
| `longstaffschwartz2001` | 951 | getragen |
| `merton1973` | 292 | getragen |
| `milevskysalisbury2006` | 1759 | getragen |
| `piscopo2011` | 651, 1760 | getragen mit Scope-Einschränkung |
| `shevchenkoluo2017` | 153, 963 | getragen |
| `steinorth2015` | 1265, 1582 | konzeptionell getragen; erster Claim zusätzlich durch Run/Engine belegen |

Nicht zitierte `.bib`-Schlüssel:

| Schlüssel | Bewertung | Empfehlung |
|---|---|---|
| `fergusson2025` | NIEDRIG | Entweder entfernen, wenn keine Aussage darauf beruht, oder bei einer konkreten Benchmark-Approach-Aussage zitieren. Nicht nur zur Verbreiterung des Verzeichnisses aufnehmen. |
| `agilemethodology2026` | MITTEL | In Zeilen 983–987 an der expliziten Methodology-Behauptung zitieren. |
| `agilerun2026` | MITTEL | Bei der ersten Ergebnistabelle bzw. dem Reproduzierbarkeitsabschnitt zitieren. |

## 4. Claim-to-source-Audit sämtlicher Zitationscluster

| Fundstelle | Zitierte Quelle(n) | Geprüfter Claim | Urteil / Severity | Korrekturvorschlag |
|---|---|---|---|---|
| 30–32 | `allianz2026pds` | Group Policy/Statutory Fund No. 2 und Garantieverpflichtung | **getragen / OK**. PDS S. 2 nennt Emittentin, Statutory Fund No. 2 und Group-Policy-Struktur ausdrücklich. | Keine. |
| 150–156 | PDS, Rate Sheets, Bauer, Kling, Huang/Kwok, Shevchenko/Luo, Engine, Audit | Evidenzhierarchie und methodische GMxB-/GLWB-Einordnung | **getragen / OK**. Die Literatur ist tatsächlich methodisch, nicht produktspezifisch; das Paper sagt dies. | Keine. |
| 199–201 | `allianz2026pds` | Investor, Life Insured, Surviving Spouse unterscheiden | **getragen / OK**. | Keine. |
| 214–216 | `bauer2008` | allgemeiner Rahmen mit Account, Guarantees, Tod, Surrender und Withdrawals | **getragen / OK**. Volltext führt Account Value, GMDB/GMLB, Partial Surrender und Withdrawal-Strategien aus. | Keine. |
| 227–231 | Rates Centre, Minimums | Juli-2026-Caps vor Fee/LIP/Steuern; Floors 0,25/0,50 % | **inhaltlich getragen; MITTEL wegen Vintage-URL**. | `allianz2026maximumreturns` (statisches Juli-PDF) ergänzen/ersetzen. |
| 290–292 | Black/Scholes, Merton | arbitragefreie Optionslogik der statischen Replikation | **getragen / OK**. | Keine. |
| 310–312 | Juli-2026 Income Rates | jüngeres Leben/Geschlecht bei Spouse; nur vollständige Escalator-Jahre | **getragen / OK**. Rate Sheet S. 1–2 sagt dies ausdrücklich. | Keine. |
| 338–340 | PDS | Rising Income sinkt nicht wegen negativer Marktbewegungen | **getragen / OK**. PDS nennt die Ausnahme Excess Withdrawals; der Satz begrenzt sich korrekt auf Marktbewegungen. | Optional „vorbehaltlich Excess Withdrawals“ ergänzen. |
| 349–351 | PDS | tägliche Fee-/LIP-Berechnung auf IV ohne DVA/accruals; Eventabzug | **getragen / OK**. | Keine. |
| 359–361 | PDS | Age Pension+: LIP endet erst ab späterem der einschlägigen Zeitpunkte | **getragen / OK**. | Keine. |
| 368–370 | PDS | MVA in ersten zehn Jahren; proportionaler Income-Rückgang einschließlich MVA | **getragen / OK**. | Keine. |
| 385–387 | PDS | DVA als unterjährige Return-/Derivatebewertung, deren echte Preisformel nicht publiziert ist | **getragen, aber Seitenzitat unvollständig / NIEDRIG**. PDS S. 33 definiert DVA; die Derivatebewertung steht erst S. 62–63. | Zitat auf „S. 33 und 62–63“ erweitern. Begriffsform ist **Daily Value Adjustment**, nicht „Dynamic“. |
| 400–401 | PDS | Death Benefit grundsätzlich positives IV am Zahlungstag, keine MVA | **getragen / OK**, mit den im Satz durch „grundsätzlich“ abgedeckten Age-Pension+/Spouse-Ausnahmen. | Keine. |
| 473–475 | `agileaudit2026` | Timing-Korrekturen im lokalen Audit | **getragen als lokaler Artefaktbeleg / OK**. | Im Bib-Eintrag klar „interner Projektaudit, kein externes Gutachten“ notieren. |
| 548–550 | `goudenege2016` | Black–Scholes vernachlässigt Stochastik/Skew; Modellwahl kann bei langem GLWB materiell sein | **getragen mit Scope / MITTEL**. Das Paper vergleicht GLWB-Fair-Fee/Greeks unter Heston und BS mit stochastischen Zinsen und zeigt Sensitivität. Es beweist keine AGILE-spezifische Materialität. | „… kann in den dort untersuchten GLWB-Modellpunkten materiell sein; die Höhe ist nicht auf AGILE übertragbar.“ |
| 554 | `heston1993` | Heston besitzt stochastische Varianz | **getragen / OK**. | Keine. |
| 572–574 | `hullwhite1990` | Einfaktor-Hull–White-Zinsmodell | **getragen / OK**. | Keine. |
| 586–588 | `fang2008` | COS-Methode aus Fourier-Cosinus-Expansion | **getragen / OK**. Spezifische konditionale Heston-Implementierung ist zusätzlich Codeevidenz, nicht Aussage des Grundsatzpapers. | Optional zusätzlich `@agileengine2026` an den Implementierungssatz. |
| 602–604 | `alonsogarcia2018` | COS-Verfahren für GMWB/GMxB etabliert | **getragen / OK**. Originalarbeit erweitert COS explizit auf GMWB-Pricing und Hedging. | Keine. |
| 649–651 | Piscopo/Haberman; Fung/Ignatieva/Sherris; Cairns/Blake/Dowd | systematisches Langlebigkeitsrisiko und Mortality Risk Premium können bei langfristigen Cashflows materiell sein | **getragen mit Scope / MITTEL**. Piscopo und Fung behandeln GLWB-Mortalität; Fung behandelt systematische Mortalität und deren Marktpreis; Cairns liefert den allgemeinen arbitragefreien Mortality-Risk-Rahmen. Keine Quelle kalibriert AGILE. | „… können in den zitierten GLWB-Modellen materiell sein; eine AGILE-spezifische Risikoprämie ist nicht kalibriert.“ |
| 689–691 | `kling2014` | tief im Geld liegende Garantie motiviert geringeres Storno; Parameter nicht AGILE-empirisch | **getragen / OK**. Kling modelliert Surrender als Funktion relativer Guarantee-Moneyness; der Text weist die fehlende AGILE-Schätzung ausdrücklich aus. | Keine. |
| 727–729 | `kling2014` | optimales Verhalten ist modellierte Wertmaximierung, nicht empirisch-psychologisches Verhalten | **getragen / OK**. | Keine. |
| 877–881 | APRA LPS 110/114 | vier Standardmodule; genehmigte VA-Methode; LPS 114 on-/off-balance sheet und ab 1.7.2026 | **getragen / OK**. LPS 110 Ziff. 29–31/Attachment A und LPS 114 bestätigen dies. | Keine. |
| 949–951 | Longstaff/Schwartz; Huang/Kwok | LSMC regressiert Continuation Value; VA-Anwendung | **getragen / OK**. | Keine. |
| 961–963 | `shevchenkoluo2017` | Dynamic Programming mit diskretisierten Withdrawal-Aktionen | **getragen / OK**. Volltext diskretisiert Guarantee Account und zulässige Withdrawal-Beträge ausdrücklich. | Keine. |
| 983–989 | Methodology (unzitiert), `langrene2026` | lokale LSMC-Limitation; Deep-LSMC nur Ausblick, kein Produktionsbenchmark | **inhaltlich getragen; MITTEL wegen fehlender lokaler Zitation**. arXiv v1 ist ein aktueller 2026-Preprint und kein unabhängiger Produktionsbenchmark. | Nach „Methodology“ `[@agilemethodology2026]` setzen; arXiv-Version/DOI ergänzen. |
| 1263–1266 | `steinorth2015` | Kundennutzen/Liquidität/Steuer/Social Security fehlen in lokaler Rangfolge | **konzeptionell getragen, evidenziell gemischt / MITTEL**. Steinorth/Mitchell modellieren Utility, flexible Liquidität, Bequest und US Social Security und legen Steuerannahmen offen. Dass diese Variablen *im AGILE-Lauf* fehlen, muss aber durch Engine/Run belegt werden. | `[@agilerun2026; @steinorth2015]` oder Engine/Run plus Literatur setzen. Nicht behaupten, die US-Ergebnisse seien auf Australien übertragbar. |
| 1580–1583 | Steinorth/Mitchell; Actuaries Institute | risikoneutraler PV misst Utility, Liquidität, Bequest, individuelle Steuer/Social Security nicht | **getragen / OK**. Erstere Quelle kontrastiert Risk-neutral- und Expected-Utility-Bewertung; das Technical Paper behandelt AU Age Pension, Withdrawals, Death Benefits und steuerliche Rahmenpunkte. | „misst … nicht *von sich aus*“ wäre mathematisch präziser. |
| 1756–1763 | Deng; Bauer; Milevsky/Salisbury; Holz; Piscopo; Goudenège; Gudkov; Kling; Huang/Kwok; Alonso-García | AGILE-Ansatz als Synthese, kein Einzelpaper deckt alle Features ab | **getragen / OK**, nach Korrektur der Deng-Metadaten. Deng behandelt Annual Point-to-Point EIA mit Floor/Cap und COS; die übrigen Quellen decken die genannten GMxB-, GLWB-, Markt-, Behaviour- und Numerikschichten ab. | Deng-Eintrag korrigieren. |

## 5. Vollständiger BibTeX-Metadatenaudit

### 5.1 Offizielle Produkt-, Aufsichts- und Projektquellen

| Schlüssel | Autor/Jahr/Titel/URL | Ergebnis |
|---|---|---|
| `allianz2026pds` | Allianz Australia Life Insurance Limited; 2026; *Allianz Guaranteed Income for Life (AGILE): Product Disclosure Statement*; [Original-PDF](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/pds-2026/AGILE_PDS_19%20Jan_2026_F1.pdf) | **OK.** Ausgabedatum 19.1.2026, 96 PDF-Seiten, Emittentin und Titel bestätigt. |
| `allianz2026rates` | Allianz Australia Life Insurance Limited; Juli 2026; Income Rates; [Original-PDF](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Lifetime_Income_Rates_Jul26.pdf) | **OK.** Titelparaphrase, Zeitraum und Körperschaft korrekt; drei Seiten. |
| `allianz2026minimums` | Allianz Australia Life Insurance Limited; Juli 2026; Guaranteed Minimums; [Original-PDF](https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Guaranteed_Minimums_Jul26.pdf) | **OK.** Werte und Zeitraum bestätigt. |
| `allianz2026ratescentre` | Allianz; 2026; AGILE Rates Centre; [offizielle Seite](https://www.allianzretireplus.com.au/adviser-resources/agile-rates.html) | **MITTEL.** Heute korrekt, aber dynamisch. Für konkrete Juli-Caps statisches Maximum-Returns-PDF ergänzen. |
| `apra2023lps110` | APRA; 2023; LPS 110 Capital Adequacy; [offizieller Standard](https://www.apra.gov.au/standards/lps-110) | **OK.** In force seit 1.7.2023; Titel, Körperschaft, Jahr und URL korrekt. |
| `apra2026lps114` | APRA; 2026; LPS 114 Capital Adequacy: Asset Risk Charge; [offizieller Standard](https://www.apra.gov.au/standards/lps-114) | **OK.** Fassung ab 1.7.2026 bestätigt. |
| `agileengine2026` | lokales Projekt, Version 1.3.0 | **NIEDRIG.** Inhalt/Version/Hash lokal bestätigt. Pfad und Stichtag im Eintrag ergänzen; „Project“ ist kein externer Körperschaftsautor. |
| `agilemethodology2026` | lokale `METHODOLOGY.md`, Stand 10.7.2026 | **OK als internes Artefakt**, aber derzeit unzitiert. Pfad im Eintrag ergänzen. |
| `agileaudit2026` | lokaler `AUDIT_REPORT.md`, Stand 10.7.2026 | **MITTEL.** Titel und Inhalt lokal bestätigt; explizit als interner Projektaudit ohne externen Autor/Herausgeber kennzeichnen. |
| `agilerun2026` | lokaler instrumentierter Ergebnispack, Manifest vom 11.7.2026 | **MITTEL.** Version, Datum, Seed, Source Hash und Pfade bestätigt. Das Manifest selbst dokumentiert den zur Laufzeit vorgenommenen Greek-Workaround nicht vollständig; der Eintrag darf nicht mehr Provenienz suggerieren, als das Manifest enthält. Derzeit unzitiert. |

### 5.2 Zeitschriftenartikel, Technical Paper und Preprint

| Schlüssel | Verifizierte Metadaten und Primärlink | Ergebnis |
|---|---|---|
| `blackscholes1973` | Black, Fischer; Scholes, Myron (1973), *The Pricing of Options and Corporate Liabilities*, *Journal of Political Economy* 81(3), 637–654, [doi:10.1086/260062](https://doi.org/10.1086/260062) | **OK.** |
| `merton1973` | Merton, Robert C. (1973), *Theory of Rational Option Pricing*, *The Bell Journal of Economics and Management Science* 4(1), 141–183, [doi:10.2307/3003143](https://doi.org/10.2307/3003143) | **NIEDRIG.** Inhaltlich korrekt; im Journalfeld nur optional „The“ ergänzen. Crossref liefert nur Startseite, Original/JSTOR und RePEc bestätigen 141–183. |
| `heston1993` | Heston, Steven L. (1993), *A Closed-Form Solution …*, *Review of Financial Studies* 6(2), 327–343, [doi:10.1093/rfs/6.2.327](https://doi.org/10.1093/rfs/6.2.327) | **OK.** |
| `hullwhite1990` | Hull, John; White, Alan (1990), *Pricing Interest-Rate-Derivative Securities*, *Review of Financial Studies* 3(4), 573–592, [doi:10.1093/rfs/3.4.573](https://doi.org/10.1093/rfs/3.4.573) | **OK.** |
| `bauer2008` | Bauer, Daniel; Kling, Alexander; Ruß, Jochen (2008), *A Universal Pricing Framework for Guaranteed Minimum Benefits in Variable Annuities*, *ASTIN Bulletin* 38(2), 621–651, [doi:10.2143/AST.38.2.2033356](https://doi.org/10.2143/AST.38.2.2033356) | **OK.** Volltext/Autorfassung geöffnet. |
| `longstaffschwartz2001` | Longstaff, Francis A.; Schwartz, Eduardo S. (2001), *Valuing American Options by Simulation: A Simple Least-Squares Approach*, *Review of Financial Studies* 14(1), 113–147, [doi:10.1093/rfs/14.1.113](https://doi.org/10.1093/rfs/14.1.113) | **OK.** |
| `fang2008` | Fang, Fang; Oosterlee, Cornelis W., *A Novel Pricing Method for European Options Based on Fourier-Cosine Series Expansions*, *SIAM Journal on Scientific Computing* 31(2), 826–848, [doi:10.1137/080718061](https://doi.org/10.1137/080718061); [SIAM record](https://epubs.siam.org/doi/10.1137/080718061) | **NIEDRIG.** 2008 online/copyright versus Crossref issue date 2009; kein inhaltlicher Fehler. |
| `kling2014` | Kling, Alexander; Ruez, Frederik; Ruß, Jochen (2014), *The Impact of Policyholder Behavior on Pricing, Hedging, and Hedge Efficiency of Withdrawal Benefit Guarantees in Variable Annuities*, *European Actuarial Journal* 4(2), 281–314, [doi:10.1007/s13385-014-0093-0](https://doi.org/10.1007/s13385-014-0093-0) | **OK.** Original-/Autorfassung lokal geöffnet. |
| `huangkwok2016` | Huang, Yao Tung; Kwok, Yue Kuen (2016), *Regression-Based Monte Carlo Methods for Stochastic Control Models: Variable Annuities with Lifelong Guarantees*, *Quantitative Finance* 16(6), 905–928, [doi:10.1080/14697688.2015.1088962](https://doi.org/10.1080/14697688.2015.1088962) | **OK.** Online-first 2015, Bandjahr 2016 korrekt. |
| `shevchenkoluo2017` | Shevchenko, Pavel V.; Luo, Xiaolin (2017), *Valuation of Variable Annuities with Guaranteed Minimum Withdrawal Benefit under Stochastic Interest Rate*, *Insurance: Mathematics and Economics* 76, 104–117, [doi:10.1016/j.insmatheco.2017.06.008](https://doi.org/10.1016/j.insmatheco.2017.06.008), [arXiv](https://arxiv.org/abs/1602.03238) | **OK.** |
| `goudenege2016` | Goudenège, Ludovic; Molent, Andrea; Zanette, Antonino (2016), *Pricing and Hedging GLWB in the Heston and in the Black–Scholes with Stochastic Interest Rate Models*, *Insurance: Mathematics and Economics* 70, 38–57, [doi:10.1016/j.insmatheco.2016.05.018](https://doi.org/10.1016/j.insmatheco.2016.05.018) | **OK.** |
| `alonsogarcia2018` | Alonso-García, Jennifer; Wood, Oliver; Ziveyi, Jonathan (2018), *Pricing and Hedging Guaranteed Minimum Withdrawal Benefits under a General Lévy Framework Using the COS Method*, *Quantitative Finance* 18(6), 1049–1075, [doi:10.1080/14697688.2017.1357832](https://doi.org/10.1080/14697688.2017.1357832) | **OK.** Online-first 2017, Bandjahr 2018 korrekt. |
| `holz2012` | Holz, Daniela; Kling, Alexander; Ruß, Jochen (2012), *GMWB for Life: An Analysis of Lifelong Withdrawal Guarantees*, *Zeitschrift für die gesamte Versicherungswissenschaft* 101(3), 305–325, [doi:10.1007/s12297-012-0193-3](https://doi.org/10.1007/s12297-012-0193-3) | **OK.** |
| `piscopo2011` | Piscopo, Gabriella; Haberman, Steven (2011), *The Valuation of Guaranteed Lifelong Withdrawal Benefit Options in Variable Annuity Contracts and the Impact of Mortality Risk*, *North American Actuarial Journal* 15(1), 59–76, [doi:10.1080/10920277.2011.10597609](https://doi.org/10.1080/10920277.2011.10597609) | **OK.** |
| `fung2014` | Fung, Man Chung; Ignatieva, Katja; Sherris, Michael (2014), *Systematic Mortality Risk: An Analysis of Guaranteed Lifetime Withdrawal Benefits in Variable Annuities*, *Insurance: Mathematics and Economics* 58, 103–115, [doi:10.1016/j.insmatheco.2014.06.010](https://doi.org/10.1016/j.insmatheco.2014.06.010) | **OK.** |
| `milevskysalisbury2006` | Milevsky, Moshe A.; Salisbury, Thomas S. (2006), *Financial Valuation of Guaranteed Minimum Withdrawal Benefits*, *Insurance: Mathematics and Economics* 38(1), 21–38, [doi:10.1016/j.insmatheco.2005.06.012](https://doi.org/10.1016/j.insmatheco.2005.06.012) | **OK.** |
| `gudkov2019` | Gudkov, Nikolay; Ignatieva, Katja; Ziveyi, Jonathan (2019), *Pricing of Guaranteed Minimum Withdrawal Benefits … via the Componentwise Splitting Method*, *Quantitative Finance* 19(3), 501–518, [doi:10.1080/14697688.2018.1490806](https://doi.org/10.1080/14697688.2018.1490806) | **OK.** Online-first 2018, Bandjahr 2019 korrekt. |
| `deng2017` | **Geng Deng; Tim Dulaney; Craig McCann; Mike Yan** (2017), *Efficient Valuation of Equity-Indexed Annuities under Lévy Processes Using Fourier Cosine Series*, *Journal of Computational Finance* 21(2), 1–27, [Publisher record](https://www.risk.net/journal-of-computational-finance/5316511/efficient-valuation-of-equity-indexed-annuities-under-levy-processes-using-fourier-cosine-series) | **HOCH.** Vornamen in `.bib` falsch. Publisher zeigt `10.21314/JCF.2017.331`, aber doi.org und Crossref liefern 404; DOI-Feld bis zur Resolverkorrektur entfernen. |
| `steinorth2015` | Steinorth, Petra; Mitchell, Olivia S. (2015), *Valuing Variable Annuities with Guaranteed Minimum Lifetime Withdrawal Benefits*, *Insurance: Mathematics and Economics* 64, 246–258, [doi:10.1016/j.insmatheco.2015.04.001](https://doi.org/10.1016/j.insmatheco.2015.04.001) | **OK.** |
| `cairns2006` | Cairns, Andrew J. G.; Blake, David; Dowd, Kevin (2006), *Pricing Death: Frameworks for the Valuation and Securitization of Mortality Risk*, *ASTIN Bulletin* 36(1), 79–120, [doi:10.2143/AST.36.1.2014145](https://doi.org/10.2143/AST.36.1.2014145) | **OK.** |
| `actuariesinstitute2024` | Retirement Incomes Working Group, Actuaries Institute (Juli 2024), *Technical Paper: Innovative Income Streams*, [Original-PDF](https://content.actuaries.asn.au/resources/resource-ce6yyqn64sx3-2093352434-60129), [offizielle Standards-/Guidance-Seite](https://www.actuaries.asn.au/professional-standards-and-regulation/standards-guidance/superannuation-investments-standards-guidance) | **NIEDRIG.** Inhalt/Jahr/Titel/URL korrekt; Working Group als Körperschaftsurheber ergänzen. |
| `langrene2026` | Langrené, Nicolas; Luo, Xiaolin; Shevchenko, Pavel V.; Zhang, Ruiyi (2026), *Deep Least Squares Monte Carlo Methods for the Valuation of Variable Annuities with Guarantees*, arXiv:2605.27182v1, eingereicht 26.5.2026, [arXiv](https://arxiv.org/abs/2605.27182), [doi:10.48550/arXiv.2605.27182](https://doi.org/10.48550/arXiv.2605.27182) | **NIEDRIG.** Metadaten korrekt; als `@misc`/Preprint mit `eprint`, `version` und DataCite-DOI präziser als `journal = arXiv preprint …`. |
| `fergusson2025` | Fergusson, Kevin; Sun, Jin; Platen, Eckhard; Shevchenko, Pavel V. (online 6.9.2025), *Fair Pricing and Reserving of Variable Annuities with Guarantees under the Benchmark Approach*, *Scandinavian Actuarial Journal*, 1–34, [doi:10.1080/03461238.2025.2549943](https://doi.org/10.1080/03461238.2025.2549943) | **NIEDRIG.** Autor/Jahr/Titel/Journal/DOI korrekt; `pages = {1--34}` ergänzen. Noch ohne Band/Heftzuweisung. Der Eintrag ist unzitiert. |

## 6. Audit des lokalen Literaturindex

Der lokale Index ist **keine belastbare Bibliografie in seinem derzeitigen
Zustand**. Das Fachpaper erkennt dies in Anhang D grundsätzlich richtig.

### 6.1 HOCH — falscher DOI bei Bégin/Sanders (2024)

Index A19 ordnet *Benefit Volatility-Targeting Strategies in Lifetime Pension
Pools* den DOI `10.1016/j.insmatheco.2024.04.001` zu. Crossref zeigt, dass
dieser DOI zu dem sachfremden Artikel *Robust Asset-Liability Management Games
for n Players under Multivariate Stochastic Covariance Models* gehört.

Korrekt ist:

- Jean-François Bégin und Barbara Sanders (2024), *Benefit
  Volatility-Targeting Strategies in Lifetime Pension Pools*, *Insurance:
  Mathematics and Economics* 118, 72–94,
  [doi:10.1016/j.insmatheco.2024.05.006](https://doi.org/10.1016/j.insmatheco.2024.05.006);
- [Elsevier-Version of Record](https://www.sciencedirect.com/science/article/pii/S0167668724000623).

### 6.2 HOCH — lokale Datei B3 ist keine Drei-Autoren-Journalfassung

Die Datei
`open_access/2025_Begin_Optimal-Hurdle-Rate-Lifetime-Pension-Pools.md` ist
eine Textextraktion von **Yingfei Suns MSc-Projekt/Thesis (SFU, 2025)**.
Jean-François Bégin und Barbara Sanders erscheinen dort als
Co-Supervisors, nicht als Mitautoren. Sie darf deshalb nicht als
Bégin/Sanders/Sun-Journalpaper zitiert werden.

Seit 30. März 2026 existiert allerdings eine echte, frei zugängliche
Zeitschriftenfassung:

- Jean-François Bégin, Barbara Sanders und Yingfei Sun (2026), *Optimal Hurdle
  Rate and Investment Policy in Lifetime Pension Pools*, *ASTIN Bulletin*
  56(2), 389–419,
  [doi:10.1017/asb.2026.10090](https://doi.org/10.1017/asb.2026.10090);
- [Cambridge-Version of Record](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/69FCD25AF21684B0E34BAC6175DC35BE/S0515036126100907a.pdf/optimal-hurdle-rate-and-investment-policy-in-lifetime-pension-pools.pdf).

Das Fachpaper zitiert diese Quelle derzeit nicht und übernimmt daher keinen
falschen Claim. Seine Warnung vor der lokalen 2025-Datei ist sachlich richtig,
sollte aber aktualisiert werden: Die Journalfassung ist nicht mehr
„forthcoming“, und DOI/Band/Heft/Seiten sind nun bekannt.

### 6.3 MITTEL — Index ist sichtbar abgebrochen

Die Datei endet nach Abschnitt C16 mit dem Literal `<!-- MORE -->`; die im
Titel/Intro angekündigten Abschnitte D–F fehlen. Das Fachpaper benennt dies
korrekt. Der Index darf nicht als vollständiger Suchraum oder als Nachweis
einer systematischen Literaturübersicht dargestellt werden.

### 6.4 NIEDRIG — veraltete Warnmarker

- A13 (*Modern Tontine with Bequest*) ist inzwischen eindeutig verifiziert:
  Thomas Bernhardt und Catherine Donnelly (2019), *Insurance: Mathematics and
  Economics* 86, 168–188,
  [doi:10.1016/j.insmatheco.2019.03.002](https://doi.org/10.1016/j.insmatheco.2019.03.002).
  Der vollständige Titel enthält den Untertitel *Innovation in Pooled Annuity
  Products*.
- Mehrere Einträge sind wegen eines früheren 429-Limits noch mit Warnsymbol
  versehen, obwohl die DOI-Metadaten heute abrufbar sind. Warnstatus und
  Prüfdatum sollten versioniert werden.
- Die Datei war zeitweise mit Mojibake sichtbar; die zugrunde liegende Datei
  ist UTF-8, sollte aber beim Export/Import explizit als UTF-8 behandelt
  werden.

## 7. Fair-Fee- und Sensitivitätsübertragung

### Ergebnis

**Keine verbotene Zahlenübertragung gefunden.** Goudenège et al., Piscopo und
Haberman, Fung et al., Gudkov et al., Kling et al. sowie Milevsky und Salisbury
enthalten jeweils modell- und vertragsabhängige Fair-Fee- oder
Sensitivitätsresultate. Das Fachpaper übernimmt daraus keine Prozentwerte oder
Vorzeichen als AGILE-Kalibrierung. Seine Zahlen in Abschnitt 11 werden dem
lokalen 1.3.0-Lauf zugeschrieben und mit Modellpunkt, Pfadzahl, Scope und
Limitationen versehen. Anhang D sagt ausdrücklich, dass fremde faire Gebühren
nicht auf AGILE übertragen werden.

Zwei Restpunkte:

1. Zeile 550 sollte die „Materialität“ explizit auf die in Goudenège et al.
   untersuchten GLWB-Modellpunkte beschränken.
2. Zeile 651 sollte klarstellen, dass Fung/Piscopo die mögliche Relevanz von
   Mortality Model/Risk Premium zeigen, aber keine AGILE-spezifische
   Risikoprämie liefern.

Damit bleibt die wissenschaftlich korrekte Trennung erhalten:

- **Literatur:** zeigt Mechanismus, mögliche Richtung und Modellrisiko;
- **lokaler Run:** liefert die dokumentierten AGILE-Engine-Zahlen;
- **nicht vorhanden:** empirische Allianz-Kalibrierung von Verhalten,
  Mortalitätsrisikoprämie, Marktparametern oder Adminformeln.

## 8. Offene bzw. nicht abschließend externe Zitate

1. **`agileengine2026`, `agilemethodology2026`, `agileaudit2026`,
   `agilerun2026`:** intern prüfbar, aber ohne externen Herausgeber,
   persistenten öffentlichen Identifier oder unabhängige Autorenschaft.
2. **`deng2017`:** der Verlag zeigt einen DOI-String, dessen Resolverdatensatz
   am Prüfdatum fehlt. Inhalt und Journalmetadaten sind über die Verlagsseite
   geklärt; der DOI bleibt technisch ungeklärt, bis der Verlag die
   Registrierung repariert.
3. **`fang2008`:** kein sachlicher Fehler, aber zwei zulässige
   Jahreskonventionen (Online-first 2008, issue/Crossref 2009). Im Projekt
   einmalig festlegen und konsistent anwenden.
4. **`fergusson2025`:** korrektes Online-first-Paper, noch ohne Band/Heft;
   falls es später paginiert wird, Metadaten aktualisieren. Es trägt aktuell
   keinen In-text-Claim.

## 9. Priorisierte Korrekturen für die Hauptredaktion

1. `deng2017` anhand der Vorschlagsdatei korrigieren; keinen funktionierenden
   DOI vortäuschen.
2. Neuen Eintrag `allianz2026maximumreturns` anlegen und in Zeile 229 zitieren.
3. In Zeilen 983–987 `@agilemethodology2026`, bei der ersten Ergebnistabelle
   `@agilerun2026` ergänzen.
4. DVA-Seitenzitat auf PDS S. 33 und 62–63 erweitern.
5. Goudenège-/Mortality-Sätze auf „in den zitierten Modellstudien“ begrenzen.
6. Working-Group-Urheberschaft bei `actuariesinstitute2024` präzisieren;
   arXiv-DOI/Version bei `langrene2026` und Seiten bei `fergusson2025`
   ergänzen.
7. Falls der lokale Index weiterverwendet wird: A19-DOI berichtigen, B3-Datei
   als Sun-Thesis umbenennen/metadatisieren und die neue 2026-VOR separat
   aufnehmen. Der Index sollte erst nach Ergänzung der fehlenden Abschnitte
   als „vollständig“ bezeichnet werden.
