# Unabhängige QA-Anforderungen für die AGILE-Kurzfassung

**Prüfgegenstand:** eine auf ungefähr 20 Seiten verdichtete Fassung von
`AGILE_Modelling_Fachpaper_reviewed.md` beziehungsweise
`AGILE_Modelling_Fachpaper_reviewed.pdf`  
**Referenzstand:** 11. Juli 2026; Engine 1.3.0; reviewed research prototype  
**Zweck dieser Datei:** verbindliche Inhalts-, Zahlen-, Quellen- und
Darstellungsanforderungen für Erstellung und Endabnahme der Kurzfassung

## 1. Harte Abnahmekriterien

Die Kurzfassung ist nur abnahmefähig, wenn alle folgenden Punkte erfüllt sind:

- [ ] Der Umfang liegt ungefähr bei 20 A4-Seiten. Ein sinnvoller Zielkorridor
  sind 18 bis 22 Seiten einschließlich Titel, Inhaltsverzeichnis und
  Literaturverzeichnis.
- [ ] Titel beziehungsweise Untertitel enthalten gut sichtbar
  **„Kurzfassung“** und **„reviewed research prototype“**.
- [ ] Der Verwendungszweck ist unmissverständlich begrenzt: keine Freigabe für
  Pricing, Reservierung, APRA/LAGIC, Hedging, Portfolioaussagen oder
  persönliche Kundenberatung.
- [ ] Die Kurzfassung behauptet nicht, eine vollständige Vertrags-, Admin-,
  Steuer-, Kapital- oder Portfolioabbildung zu sein.
- [ ] Produktfakt, Modellannahme, numerisches Ergebnis und Interpretation sind
  sprachlich und optisch unterscheidbar.
- [ ] Alle Resultate sind dem **instrumentierten** 1.3.0-Lauf zugeordnet; der
  unveränderte Standard-Runner wird nirgends als erfolgreich bezeichnet.
- [ ] Der Basismodellpunkt, Ergebnisstichtag, Pfadzahlen und wesentliche
  Kalibrierungsgrenzen stehen vor oder unmittelbar bei den Ergebnissen.
- [ ] Sämtliche in den Abschnitten 3 bis 8 dieser Checkliste als Pflichtinhalt
  markierten Aussagen, Zahlen, Befunde, offenen Punkte und Quellen sind
  vorhanden.
- [ ] Es gibt keine neue materielle Aussage ohne belegbare Entsprechung im
  reviewed Paper, Review Report oder in der Claim-to-Evidence-Matrix.
- [ ] Alle Zahlen sind gegen den reviewed Langtext beziehungsweise die
  Ergebnis-CSVs geprüft; unterschiedliche Base-Zahlen aus Analyseblöcken mit
  unterschiedlichen Pfadzahlen werden nicht vermischt.
- [ ] Zitate sind im Text aufgelöst, die Bibliografie enthält nur zitierte
  Quellen, und jede im Text verwendete Quelle ist in der Bibliografie
  vorhanden.
- [ ] PDF-Endabnahme: keine leeren Seiten, keine abgeschnittenen Tabellen oder
  Formeln, keine ungültigen internen Links, lesbare Grafiken, A4, Seitenzahlen,
  Inhaltsverzeichnis/Outline und vollständige Titelmetadaten.

Ein Fehlen des Use-Limitations-Hinweises, der Juli-2026-Vintage, der
Minimum-versus-Floor-Abgrenzung, der Runner-/Provenienzbefunde, der
Heston--Hull--White-Einschränkung, der APRA-Abgrenzung, der beiden offenen
Sachfragen oder der Executive-KPI-Tabelle ist ein **Stopper**.

## 2. Empfohlene Verdichtungsstruktur und Seitenbudget

Die folgende Struktur ist nicht als starre Paginierung, sondern als
Vollständigkeitskontrolle zu verwenden:

| Inhalt | Zielumfang |
|---|---:|
| Titel, Dokumentstatus, Executive Summary und Use Limitations | 1–2 Seiten |
| Produktökonomik, offizielle Juli-2026-Raten und wesentliche Vertragsmechanik | 3–4 Seiten |
| Modellarchitektur, Bewertungslogik und zentrale Modellgrenzen | 3 Seiten |
| Basismodellpunkt und Annahmen | 1–2 Seiten |
| Executive KPIs, Reconciliation, Kapital und Profitabilität | 3–4 Seiten |
| Sensitivitäten, Outcomes, Design-/Timing- und Modellvergleich | 2–3 Seiten |
| Validierung, HOCH-/MITTEL-Befunde, offene Punkte und Production-Blocker | 3–4 Seiten |
| Schlussfolgerung und selektive Bibliografie | 1–2 Seiten |

Ohne Informationsverlust entfallen können: ausführliche Lehrübungen und
Kontrollfragen, vollständige Notation, vollständiges Kennzahlen-Mapping,
sämtliche Herleitungen von Standardmodellen, Wiederholungen derselben
Use-Limitation, alle zehn Ergebnisabbildungen, die vollständige
Literaturübersicht sowie technische Dateihashes. Literaturmetadatenfehler mit
HOCH-Einstufung müssen jedoch wenigstens als Bibliografie-QA eingehalten
werden.

## 3. Produktfakten, die nicht verloren gehen dürfen

### 3.1 Rechtliche und ökonomische Einordnung

- [ ] Issuer ist Allianz Australia Life Insurance Limited; die Group Policy
  wird an Allianz Australia Life Policy Services Pty Limited ausgegeben; der
  Investor ist specified beneficiary und erwirbt ein Interesse unter der
  Group Policy.
- [ ] Die Investments sind Statutory Fund No. 2 zugeordnet. Garantien sind
  vertragliche Zusagen von Allianz Australia Life aus den verfügbaren
  Fund-Assets unter den PDS-Top-up- und begrenzten Cessation-Regeln; **keine
  Garantie von Allianz SE oder anderen Konzerngesellschaften**.
- [ ] Investor, Life Insured, beneficiary und Surviving Spouse werden nicht
  gleichgesetzt; bei Trustee-, Plattform- oder Company-Strukturen ist der
  Ownership-/Anspruchspfad entscheidend.
- [ ] AGILE ist **indexed, nicht unit-linked**. FIA plus GLWB ist nur eine
  funktionale, US-geprägte Modellanalogie, keine rechtliche Produkt- oder
  APRA-Klassifikation.
- [ ] Growth Phase und Lifetime Income Phase werden erklärt. Das lebenslange
  Einkommen kann nach Erschöpfung des Investment Value weiterlaufen und wird
  dann zum Garantieclaim.
- [ ] Freiwilliger Income Start ist frühestens nach einem Jahr möglich und
  irreversibel. Zusätzlich bestehen automatische Commencement-/Default-Regeln:
  grundsätzlich nächstes Anniversary nach Alter 100 beziehungsweise mit Age
  Pension+ nach der festgelegten Life Expectancy; Default Fixed ohne Spouse.
  Der mögliche Full Withdrawal bei fehlenden Kontakt- oder Bankdaten ist
  ausdrücklich nur ein PDS-Vorbehalt, keine deterministische Engine-Regel.

### 3.2 Juli-2026-Ratevintage und Payoffs

- [ ] Die vier Maximum Returns für Commencement **oder Anniversary Dates** vom
  1. bis 31. Juli 2026 sind korrekt:

  | Option | Total Protection | Partial Protection 10 % |
  |---|---:|---:|
  | Australian Equity | 6,20 % | 13,00 % |
  | Global Equity | 6,00 % | 12,80 % |

- [ ] Guaranteed Minimums sind 0,25 % für Total Protection und 0,50 % für
  Partial Protection. Sie sind Untergrenzen des künftig festgesetzten
  **Maximum Return**, keine Mindestjahresrendite und kein Protection Floor.
- [ ] Die Maximum Returns werden an jedem Anniversary neu festgesetzt; aktuelle
  New-Business-Raten dürfen nicht pauschal auf In-force-Policen übertragen
  werden.
- [ ] Total Protection wird im marktgebundenen Engine-Zweig als
  `min(max(R,0),C)` und Partial Protection 10 % als Cap plus 10-%-Buffer
  beschrieben. Ein Beispiel wie −18 % Indexrendite → −8 % bei Partial
  Protection muss die asymmetrische Mechanik greifbar machen.
- [ ] Das PDS erlaubt bei Total Protection alternativ einen garantierten
  einjährigen Fixed Return. Dieser Zweig und dessen zeitanteilige DVA sind in
  der Engine **nicht implementiert**; Payoff-/Replikationsformeln dürfen daher
  nicht als universelle Vertragsformel bezeichnet werden.

### 3.3 Lifetime Income, Fees und Transaktionen

- [ ] Die Lifetime Income Rate wird aus Alter und PDS-`Gender` am **Product
  Commencement Date**, Optionen und vollständigen Growth-Jahren bestimmt;
  nicht aus dem Alter am späteren Income Start.
- [ ] Bei Spouse Income bestimmt das eindeutig jüngere Leben einschließlich
  Gender die Rate. Equal-age-Tie-Regel und fractional-age-Interpolation
  bleiben offen.
- [ ] Die Basisrechnung bleibt sichtbar:
  **7,05 % + 5 × 0,35 % = 8,80 %** für Mann 65, Single Fixed, fünf vollständige
  Growth-Jahre. 8,80 % wird auf das Investment Value beim Income Start
  angewandt und ist keine Rendite auf die ursprüngliche Prämie.
- [ ] Fixed Income ist nominal konstant, sofern keine reduzierende Excess
  Withdrawal erfolgt. Rising Income hat eine niedrigere Startrate und steigt
  nur mit positivem Australian-Equity-Total-Protection-Credit; es ist keine
  CPI-Indexierung.
- [ ] Aktuelle Gebühren: Product Fee 0,30 % p. a. und Lifetime Income Premium
  1,15 % p. a. Das PDS enthält ein begrenztes Änderungsrecht mit Notice; die
  konstante Engine-Fortschreibung ist eine Modellannahme. Tägliche
  Vertragsabgrenzung versus monatliche Engine-Approximation ist kenntlich.
- [ ] Ohne Age Pension+ bestehen 5 % jährlicher Free Withdrawal Amount in der
  Growth Phase, MVA-Möglichkeit in den ersten zehn Jahren, AUD-100-Minimum,
  95-%-Einzel-/Jahresgrenzen und AUD-2.000-Restwert. Eine Kurzfassung darf die
  Details tabellarisch verdichten, aber nicht eine universelle einfache
  Proportionalität behaupten.
- [ ] DVA ist ein Wert der relevanten Derivatekontrakte, nicht die realisierte
  Year-to-date-Indexrendite. Vertragliche pro-rata Cap-, Protection- und
  gegebenenfalls Fixed-Return-Mindestwerte sind zu nennen. Der Engine-DVA ist
  ein Hedgewertproxy ohne vollständigen Protection Floor und Fixed-Return-
  Zweig; die MVA ist ebenfalls unkalibriert und keine bestätigte
  Allianz-Adminformel.
- [ ] Death Benefit ist grundsätzlich der positive Investment Value ohne MVA.
  Bei wirksamem Spouse Insured hängen Fortsetzung/Lump Sum und Default vom
  Ownership- und Eligibility-Pfad ab; der Runner vereinfacht dies zum
  Szenarioinput.
- [ ] Age Pension+ ist keine jederzeit frei aktivierbare Option. Election und
  Commencement sind funding-, release- und altersspezifisch, unwiderruflich
  und eligibility-abhängig. Der Withdrawal Amount folgt einer Lower-of-/MWV-
  Logik; der Maximum Benefit on Death bleibt bis Half Life Expectancy auf der
  Basis und springt dann auf den MWV-Pfad. Ratecard- und CAS-Vintage müssen
  gemeinsam gespeichert werden.

## 4. Modell- und Bewertungsrahmen, der erhalten bleiben muss

- [ ] Die Architektur wird knapp als monatliche State Machine mit getrennten
  $Q$-Pricing- und $P$-Profitabilitätsprojektionen dargestellt. Die
  Marktwert-/Buchungsidentität ist eine interne Reconciliation, kein Nachweis
  korrekter nicht veröffentlichter Adminformeln.
- [ ] Black--Scholes ist das Basismodell; Heston, Hull--White und
  Heston--Hull--White sind Modellvergleich beziehungsweise Erweiterungen. Die
  COS-Methode und statische Optionsreplikation dürfen knapp erklärt, aber
  nicht als produktspezifisch kalibriert dargestellt werden.
- [ ] Mortalität und Verhalten sind illustrative Decrementmodelle. Kein
  stochastisches Langlebigkeitsmodell und keine Allianz-Experience-
  Kalibrierung liegen vor.
- [ ] Dynamisches Storno, Income Take-up, Withdrawals und später Income Start
  sind wertrelevante Optionen. Off-anniversary Income-Lapse verwendet bis zum
  nächsten Anniversary einen IV- statt Surrender-Value-Nenner.
- [ ] Der LSMC-Populationswert einer festen zulässigen Policy kann ein Lower
  Bound sein; der ausgegebene MC-Max-Schätzer ist wegen samplebasiertem
  `max(opt,static)` kein strikter numerischer Lower Bound. Alter-105-/40-Jahre-
  Horizont, 30Y-Zero-Tail, Closeout und ab Issue konditioniertes Joint Life
  sind nicht like-for-like zum Monatsmotor.
- [ ] `bel_total` ist nur die interne Engine-Konvention $P_0+$ Non-unit BEL,
  kein regulatorischer Total BEL und kein APRA-/AASB-/IFRS-Ergebnis.
- [ ] Die Aussage $p_z\le 1$ ist keine allgemeine Identität; ein 50-%-Cap-
  Gegenbeispiel liefert $p_z=1{,}0449739$. Sie gilt höchstens im
  finanzierbaren Basis-Cap-Fall.
- [ ] Der Solvency-II-artige Kapital- und Risk-Margin-Proxy ist ausdrücklich
  **kein APRA/LAGIC-Ergebnis**.
- [ ] Die 30-%-Tax-Annahme gewährt sofort symmetrische Entlastung auch auf
  Verluste; Verlustvorträge, Deferred Tax und Recoverability fehlen.

## 5. Basismodellpunkt und Annahmen

Vor der ersten Ergebnistabelle müssen mindestens folgende Angaben stehen:

- [ ] Commencement Mitte 2026; Mann, Alter 65; Non-superannuation; AUD 100.000.
- [ ] 100 % Australian Equity Total Protection; Juli-Cap 6,20 %;
  Guaranteed Minimum des künftigen Maximum Return 0,25 %.
- [ ] Fixed Income nach fünf Jahren mit Alter 70; Rate 8,80 %; kein Spouse,
  kein Age Pension+, keine geplanten Withdrawals, kein Adviser Fee/Bonus.
- [ ] Der Juli-Cap wird mangels Schedule in allen Folgejahren wiederholt;
  Fixed-Return-Zweig aus; MVA-Termination-Loadings null. Das sind
  Modellannahmen, keine Produktfakten.
- [ ] Basismarktannahmen mindestens: Zero Curve 1/2/5/10/20/30 Jahre
  3,80/3,90/4,10/4,30/4,40/4,40 %, AUS-Volatilität 16 %, Return-Index-Carry
  0 %, ERP unter $P$ 4,50 %.
- [ ] Kosten/Profitabilität mindestens: Acquisition Expense 2,00 % der
  Prämie; Maintenance AUD 80 p. a. + 5 bp IV; Inflation 2,50 %; Hurdle Rate
  8 %; Tax 30 % mit der oben genannten symmetrischen Verlustentlastung.
- [ ] Pfadzahlen sind blockweise kenntlich: 4.000 Basispricing/Kapital/
  Profitabilität; 1.200 Sensitivitäten; 1.500 Design/Timing; 600 Behaviour;
  2.500 Outcomes; 600 je Modell; fünf Seeds zu je 800 Pfaden.

## 6. Ergebniszahlen, die nicht verloren gehen dürfen

### 6.1 Executive KPIs

Mindestens eine kompakte Tabelle enthält, mit sinnvoller Rundung:

| Kennzahl | Pflichtwert | Pflichtqualifikation |
|---|---:|---|
| Gross VNB | −AUD 1.228 | −1,228 % der Prämie; vor Risk Margin |
| pfadweiser MC-Standardfehler | AUD 42,25 | approximatives 95-%-Halbintervall ±AUD 82,81 |
| Non-unit BEL | +AUD 1.228 | negatives Vorzeichen zum Gross VNB; interne Konvention |
| Guarantee Value | +AUD 10.080 | Claims minus LIP |
| fairer / belasteter LIP | 3,00 % / 1,15 % | exakt 3,0041561 %; Lücke rund 185 bp; kein Gesamtprodukt-Break-even |
| BSCR-Proxy | AUD 17.205 | nicht APRA/LAGIC |
| Risk-Margin-Proxy | AUD 4.687 | 6-%-CoC auf Life-SCR-Runoff |
| VNB nach RM | −AUD 5.915 | Proxygröße |
| PVFP @ 8 % | −AUD 12.899 | inklusive Reserve, Kapital und symmetrischer Tax-Annahme |
| IRR / Payback | 3,52 % / Jahr 23 | IRR ist niedrigste gefundene Wurzel; Payback undiskontiert |
| Q-Identity Gap | −0,169 % | innerhalb der Run-Schwelle; nur Reconciliation |

Keine Cent- oder Vierdezimaldarstellung darf ökonomische Präzision suggerieren.
Für Fair LIP, BSCR, RM, PVFP, IRR, Designs und Stressdifferenzen fehlen
outputseitige Standardfehler.

### 6.2 Wertüberleitung und Kapital

- [ ] Die Gross-VNB-Reconciliation ist entweder vollständig tabelliert oder
  rechnerisch prüfbar angegeben: Product Fees +2.269,84; LIP +8.701,07;
  Crediting Margin +9.923,45; MVA Retained +217,37; Guarantee Claims
  −18.780,81; Expenses −3.558,57; Summe −1.227,65 AUD.
- [ ] LIP deckt 46,3 % der Claims; Guarantee Value ist
  18.780,81 − 8.701,07 = 10.079,74 AUD.
- [ ] Optional kann die Kundenleistungs-Reconciliation verdichtet werden;
  wenn verwendet, müssen Income 69.417,96, Death 12.537,80, Surrender
  15.544,39 und Summe 97.500,16 AUD stimmen.
- [ ] Interest Down ist bindender Hauptstress mit AUD 15.812,66; Life SCR
  rund AUD 3.896; BSCR nach Korrelation AUD 17.205,30. Nullwerte anderer
  Stresse bedeuten nur keinen positiven Loss nach Floor, nicht Abwesenheit des
  jeweiligen Risikos.
- [ ] Der späte nominale Payback und negative PVFP werden konsistent erklärt:
  frühe Strains/Kapitalbindung versus stark diskontierte späte Freisetzungen;
  kein Widerspruch.

### 6.3 Sensitivitäten, Outcomes, Designs und Timing

Die Kurzfassung muss nicht jede Ergebniszeile übernehmen, aber mindestens die
folgenden Muster samt Scope zeigen:

- [ ] Sensitivitäten beruhen auf 1.200 Pfaden **ohne Kapital und Risk Margin**;
  ihre Base-PVFP-Zahl von −AUD 66 ist daher nicht mit −AUD 12.899 zu
  vergleichen.
- [ ] Zinsrisiko dominiert: −100 bp verändern Gross VNB um −AUD 11.483;
  +100 bp um +AUD 9.773.
- [ ] Income Start zwei Jahre später verbessert den modellierten Gross VNB um
  AUD 3.261; zwei Jahre früher verschlechtert ihn um AUD 2.805. Dies ist keine
  Kundenempfehlung.
- [ ] Longevity ($q_x$ −10 %) verändert Gross VNB um −AUD 1.629. Maximum
  Returns −100 bp verbessern ihn um AUD 2.232; der Kunde erhält dabei weniger
  Upside.
- [ ] „Expenses +10 %“ betrifft nur Maintenance, nicht Acquisition Expense.
  „Excess Withdrawals 2 %“ schaltet zugleich 100 % Free-Withdrawal-
  Utilisation ein und ist kein isolierter Stress.
- [ ] Outcomes: Unter den 2.500 illustrativen $P$-Pfaden überschreitet die
  IV-Erschöpfungsquote erstmals mit Alter 84 die 50-%-Marke (85,36 %); Fixed
  Income läuft weiter. Outcome-Seed ist effektiv 2027, obwohl Settings im
  Manifest 2026 zeigen. Quantile sind keine persönliche Prognose.
- [ ] Mindestens ein Design-/Timingbeispiel verdeutlicht den Trade-off, etwa
  Spouse Fixed Gross VNB −AUD 5.149 versus Age Pension+ Rising +AUD 7.207 oder
  Start nach 1 Jahr −AUD 6.150 versus 15 Jahren +AUD 15.066. Dabei sind
  unterschiedliche Modellpunkte, 1.500 Pfade, fehlende Kundenutility und der
  fehlende gemeinsame spätere Wahlrechtswert ausdrücklich genannt.

### 6.4 Modell-, Seed- und Versionsrisiko

- [ ] Der 600-Pfad-Modellvergleich reicht von Black--Scholes −AUD 1.275 bis
  Heston--Hull--White −AUD 4.402; die unbereinigte Spanne ist AUD 3.127.
  Der Vergleich mit dem Basis-MC-Halbintervall ergibt ungefähr Faktor 38,
  **ist aber kein reiner Model-Risk-Schätzer**, weil modellweise/gepaarte SEs
  fehlen und Pfadzahlen abweichen.
- [ ] Fünf Seeds zu je 800 Pfaden ergeben Gross-VNB-Mittel −AUD 1.209,
  Seed-SD AUD 96,64 und Spannweite −AUD 1.292 bis −AUD 1.049. Dies ist ein
  Plausibilitätssignal, keine umfassende Konvergenzstudie.
- [ ] Versionsvergleich: Gross VNB v1.2.0 +AUD 1.743 versus instrumentierte
  v1.3.0 −AUD 1.228; Delta −AUD 2.970. Der Carry-Gegenlauf liefert
  +AUD 1.879,32 beziehungsweise einen isolierten Effekt von etwa
  −AUD 3.106,96, ist aber nicht separat manifestiert.
- [ ] Der Versionsvergleich bündelt Codefixes, Annahmen- und
  Definitionsänderungen. Er heißt **Versionsattribution**, nicht reines
  Implementation Risk.

## 7. HOCH- und MITTEL-Befunde, die nicht verschwinden dürfen

### 7.1 HOCH

Alle sieben HOCH-Befunde bleiben entweder im Haupttext oder, bei reinen
Literaturmetadaten, als explizite Bibliografie-QA erhalten:

- [ ] **H-01 Runner:** 122 grüne Tests, aber unveränderter Standard-Runner
  Exit 1 nach 18,5 s mit `FrozenInstanceError` in `greeks()`. Die Suite ruft
  weder die öffentliche Greek-API noch den End-to-End-Runner auf.
- [ ] **H-02 Provenienz:** Source Hash umfasst nur `agile_engine/*.py`, nicht
  Runner, Runtime-Patch, CLI, Tests, Inputs oder Outputs. Derselbe Hash kann
  den abbrechenden und den instrumentierten Lauf beschreiben.
- [ ] **H-03 Heston--Hull--White:** Das COS-„Gaussian add-on“ ist im Default
  wegen $w=-2{,}3260\times10^{-4}$ keine unabhängige positive Varianz und
  keine exakte Komposition. Ergebnisse sind hybride Näherung; gemeinsamer
  MC-/Transform-Benchmark fehlt.
- [ ] **H-04 APRA:** LPS 110/114/115/117/118 sind relevant; der lokale
  Einzelpolicenproxy bildet weder PCA noch LAGIC ab. Attachment-A-
  Klassifikation von AGILE bleibt offen.
- [ ] **H-05 `deng2017`:** korrekte Autoren Geng Deng und Mike Yan;
  `10.21314/JCF.2017.331` nicht als DOI verwenden; offizielle Publisher-URL.
- [ ] **H-06 lokaler A19-Index:** für Bégin/Sanders, *Benefit
  Volatility-Targeting Strategies*, ist DOI
  `10.1016/j.insmatheco.2024.05.006` korrekt; der lokale `.04.001`-DOI darf
  nicht übernommen werden.
- [ ] **H-07 lokale B3-Datei:** sie ist Yingfei Suns MSc-Thesis, nicht die
  Drei-Autoren-Journalfassung. Die echte Bégin/Sanders/Sun-VOR erschien 2026
  in *ASTIN Bulletin* 56(2), 389–419, DOI `10.1017/asb.2026.10090`.

### 7.2 MITTEL

Die 23 MITTEL-Themen dürfen stark verdichtet werden. Die Endabnahme muss aber
prüfen, dass keine der folgenden korrigierten Aussagen wieder in ihre alte,
überzogene Form zurückfällt:

- [ ] **M-01 bis M-03:** Group-Policy-/Garantieumfang; automatischer Income
  Start samt PDS-Vorbehalt; Anniversary-Vintage und Guaranteed-Minimum-
  Begriff.
- [ ] **M-04 bis M-10:** Fixed-Return-Zweig; DVA; Age-Pension+-Lower-of/MWV;
  Election/Eligibility/CAS-Vintage; Spouse-Ownership/Default und zusätzlicher
  Modellpunkt Frau 63/`continue_income`; Fee-Änderungsrecht.
- [ ] **M-11 bis M-13:** Off-anniversary IV-/Surrender-Value-Abweichung;
  $p_z\le1$ nicht allgemein; `bel_total` ohne regulatorisches Label.
- [ ] **M-14/M-15:** LSMC-Schätzer nicht strikt numerischer Lower Bound;
  Tail-, Static-Policy- und Joint-Life-Scope nicht like-for-like zum
  Monatsmotor.
- [ ] **M-16/M-17:** Expense-Stress nur Maintenance; Tax mit sofortiger
  symmetrischer Verlustentlastung und ohne DTA/Loss-Carry.
- [ ] **M-18/M-19:** keine Scheingenauigkeit; 600-Pfad-Spanne ist
  unbereinigtes Gemisch aus Modell-, Parameter-, Diskretisierungs- und
  Samplingeffekten.
- [ ] **M-20/M-21:** effektiver Outcome-Seed 2027 trotz manifestierter 2026;
  Versionsattribution statt reinem Implementation Risk.
- [ ] **M-22/M-23:** Methodology/Run werden als lokale interne Artefakte
  zitiert; externe GLWB-Studien liefern keine AGILE-spezifische
  Materialitätskalibrierung.

Zusätzlich muss bei einer Aufnahme der Greeks erklärt werden: Sie sind
instrumentierte technische Vor-Kosten-Diagnostik, nicht freigegebene
Risikokennzahlen. Der Greek NAV liegt um Expenses über Gross VNB; Equity Delta
ist ungewöhnlich normiert und entspricht bei +1 % lokal nur rund AUD 0,50.
Die sicherste Kurzfassungsoption ist, die Greek-Tabelle wegzulassen und den
API-Befund im Validierungsteil zu behalten.

## 8. Offene Punkte und Production-Blocker

### 8.1 Ausdrücklich OFFEN

Diese beiden Punkte müssen wörtlich oder sinngleich als **OFFEN** erscheinen,
nicht als gelöst oder als bestätigte Engine-Regel:

1. **Equal-age-/fractional-age-Rating:** Öffentliche Unterlagen regeln weder
   die Gender-Tie-Regel für gleich alte Ehepartner noch die Interpolation
   nichtganzzahliger Commencement-Alter. Primary-Life-Priorität und lineare
   Interpolation sind Engine-Annahmen.
2. **APRA-Klassifikation:** Öffentliche Quellen belegen nicht, ob AGILE als
   `variable annuity business` nach LPS 110 Attachment A behandelt wird oder
   welche Methode APRA gegebenenfalls genehmigt hat.

### 8.2 Mindestliste der Production-Blocker

Die zwölf Langtextpunkte können in einer kompakten Tabelle gruppiert werden,
müssen inhaltlich aber erhalten bleiben:

- [ ] kein vollständiger In-force-Modellpunkt und keine Portfolioaggregation;
- [ ] gemeinsame spätere Optionalität für Fixed/Rising, Spouse, Age Pension+,
  Death Election und Reallokation fehlt;
- [ ] DVA/MVA unkalibriert; Protection Floor und Fixed-Return-Zweig fehlen;
- [ ] kein APRA/LAGIC-Modul mit Fund Assets, Hedges, Credit, Concentration,
  Operational Risk und Combined Stress;
- [ ] keine Markt-, Mortalitäts-, Lapse-, Take-up-, Withdrawal-, Expense- oder
  Experience-Produktionskalibrierung;
- [ ] fehlende Cashflows/Regeln, unter anderem Adviser Fees, Tax/Withholding,
  Cooling-off, Reinsurance und Teile der Eligibility;
- [ ] kein systematisches stochastisches Langlebigkeitsmodell;
- [ ] Skalierungs-/Speichergrenzen langer Capital-Revaluation-Projektionen;
- [ ] automatische Vertragsereignisse nicht vollständig in der State Machine;
- [ ] Rating-Randfälle nicht gegen Admin-Spezifikation bestätigt;
- [ ] unvollständige Run-Provenienz; und
- [ ] Tax-Loss-, Deferred-Tax- und Recoverability-Logik fehlt.

## 9. Quellen, die nicht verloren gehen dürfen

### 9.1 Produktprimärquellen

Jeder materielle Produktfakt wird nahe an der Aussage, nicht nur gesammelt am
Ende, gegen mindestens eine der folgenden Quellen belegt:

- [ ] `allianz2026pds`: AGILE Product Disclosure Statement, 19. Januar 2026.
- [ ] `allianz2026rates`: Lifetime Income Rates, Commencement
  01.07.–31.07.2026.
- [ ] `allianz2026minimums`: Guaranteed Minimums, Juli 2026.
- [ ] `allianz2026maximums`: Maximum Returns für Commencement **oder
  Anniversary Date**, Juli 2026.

Die statischen Juli-PDFs sind zu verwenden, nicht eine dynamische Rates-
Landingpage ohne reproduzierbaren Vintage.

### 9.2 Regulatorische Primärquellen

- [ ] APRA LPS 110 (Capital Adequacy).
- [ ] APRA LPS 114 (Asset Risk Charge).
- [ ] APRA LPS 115 (Insurance Risk Charge).
- [ ] APRA LPS 117 (Asset Concentration Risk Charge).
- [ ] APRA LPS 118 (Operational Risk Charge).

Die Quellen stützen die Abgrenzung des Proxys; sie dürfen nicht als Beweis
einer öffentlich unbekannten AGILE-Klassifikation verwendet werden.

### 9.3 Methoden- und Laufquellen

- [ ] `agileengine2026`, `agilemethodology2026` und `agilerun2026` belegen
  Code-, Methoden- und Ergebnisclaims. Sie sind als **lokale interne
  Projektartefakte**, nicht als externe Publikationen oder unabhängige
  Assurance, gekennzeichnet.
- [ ] Wenn Audit-Historie erwähnt wird, gilt dasselbe für `agileaudit2026`:
  lokaler Projektaudit ohne benannten externen Autor/Publisher.
- [ ] Für die im Kurztext tatsächlich beschriebenen Methoden bleiben die
  einschlägigen Originalquellen erhalten, mindestens Bauer et al. für den
  GMxB-Rahmen, Black--Scholes/Merton für Optionsbewertung, Heston,
  Hull--White, Fang/Oosterlee für COS und Longstaff--Schwartz für LSMC.
- [ ] Externe GLWB-/Retirement-Income-Literatur wird nur für allgemeine
  Mechanismen beziehungsweise Utility-/Behaviour-Kontext verwendet, nie als
  empirische AGILE-Kalibrierung.

### 9.4 Bibliografie- und Linkkontrolle

- [ ] Keine fehlenden Citekeys und keine unzitierten Bibliografieeinträge.
- [ ] Keine Rückkehr zu den drei in H-05 bis H-07 dokumentierten falschen
  Metadaten.
- [ ] PDS- und Rate-Sheet-Datum/Vintage erscheinen im sichtbaren Quellentitel.
- [ ] DOI-Links werden auflösbar und passend zu Titel/Autor geprüft; URLs
  verweisen direkt auf Primärquelle beziehungsweise Publisherseite.
- [ ] Ein Literaturverzeichnis darf für die Kurzfassung selektiv sein; es muss
  nicht alle 35 Quellen des Langtexts übernehmen.

## 10. Darstellungs- und PDF-QA

- [ ] Höchstens vier bis fünf wirklich aussagekräftige Abbildungen; empfohlen
  sind Executive KPI/Waterfall, Sensitivitäten, Customer Outcomes und ein
  Design-/Modell-/Versionsvergleich. Redundante Runner-Grafiken entfallen.
- [ ] Jede Abbildung nennt Modell, Pfadzahl, Einheit und mindestens eine
  zentrale Einschränkung. Kleine Beschriftungen der Quell-PNGs werden nicht
  weiter verkleinert; nötigenfalls wird eine lesbare Tabelle statt der Grafik
  verwendet.
- [ ] Ergebnis-Tabellen verwenden konsequent AUD, Prozent, Basispunkte und
  Vorzeichen. „Kundenwert“ und „Versichererwert“ sind nicht vertauscht.
- [ ] Tabellenumbrüche wiederholen Kopfzeilen und trennen keine Überschrift
  von der folgenden Tabelle. Keine Schrift unter etwa 9 pt.
- [ ] Formeln sind nur enthalten, wenn sie Mechanik oder Befund wesentlich
  erklären; alle mathematischen Zeichen werden als MathML/OMML beziehungsweise
  sauber gerenderte PDF-Mathematik ausgegeben. Kein Raw TeX und keine C0-
  Steuerzeichen.
- [ ] Das PDF ist A4, hat Titel-/Autoren-/Subject-Metadaten, Seitenzahlen auf
  jeder Inhaltsseite, eine nutzbare Outline und valide interne TOC-Links.
- [ ] Automatische Prüfung auf 0 leere Seiten, 0 abgeschnittene Textblöcke,
  0 ungültige interne Links und 0 fehlende Bildressourcen; zusätzlich visuelle
  Stichprobe von Titel, TOC, Produkt-/KPI-Tabelle, Formelseite,
  Validierungstabelle und Literaturverzeichnis.

## 11. Inhaltliche Schlusskontrolle

Die Schlussfolgerung der Kurzfassung muss inhaltlich auf folgende Aussage
hinauslaufen:

> Unter genau den dokumentierten illustrativen Annahmen ist der modellierte
> Einzelpolicenwert vor und nach Risk Margin negativ. Das ist weder ein
> Nachweis realer AGILE-Portfolio-Unprofitabilität noch eine
> Produktionsfreigabe. Die Engine ist ein wissenschaftlich nützlicher,
> stark reconciliierter Research-Prototyp; Vertrags-/Admin-Reconciliation,
> Kalibrierung, In-force-Fähigkeit, APRA/LAGIC, Portfolioaggregation,
> unabhängige Benchmarks und vollständige Model Governance fehlen.

Abschließend ist zu prüfen:

- [ ] „Keine falsche materielle Basiszahl gefunden“ wird nicht mit
  „Produktionsmodell validiert“ verwechselt.
- [ ] Interest-Down-Dominanz, Tail-Charakter der Garantie, Wertrelevanz des
  Income-Start-Timings, nicht monotones Verhalten und die Begrenztheit des
  reinen MC-Fehlers bleiben als zentrale Lernpunkte erhalten.
- [ ] Der negative Basis-VNB wird weder als reales Portfolioergebnis noch als
  Kundenempfehlung interpretiert.
- [ ] Kundennutzen, Liquidität, Bequest Motive, persönliche Steuer und
  Social-Security-Effekte werden nicht aus risikoneutralen Barwerten
  abgeleitet.
- [ ] Der BSCR-Proxy wird nur für modellinterne Risikotreiber verwendet, nie
  als APRA PCA, Kapitalquote, Hedgebudget oder Reservierungsanforderung.
- [ ] Der Zusammenhang aus Definition, Datenvintage, Codeversion,
  Laufprovenienz und Ergebnis wird als Teil der Modellgovernance benannt.

## 12. Empfohlener finaler Prüfablauf

1. [ ] Kurzfassung gegen diese Pflichtliste und die
   `AGILE_Modelling_Claim_Evidence_Matrix.csv` lesen.
2. [ ] Alle sichtbaren Zahlen maschinell oder zellweise gegen reviewed Paper
   und Ergebnis-CSVs vergleichen.
3. [ ] Citekeys/Bibliografie auf fehlend, unzitiert und H-05–H-07 prüfen.
4. [ ] Markdown-/Pandoc-Parse auf Raw TeX, C0-Zeichen und fehlende Assets
   prüfen.
5. [ ] PDF erzeugen und technische Seiten-/Link-/Bounding-Box-Prüfung
   durchführen.
6. [ ] Kontaktbogen plus gezielte Vollauflösungsprüfung der kritischen Seiten.
7. [ ] Erst freigeben, wenn sämtliche Stopper geschlossen und alle
   ausdrücklich OFFENEN Punkte weiterhin als offen gekennzeichnet sind.
