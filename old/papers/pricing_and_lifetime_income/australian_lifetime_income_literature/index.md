# Kuratierte Literatur: Pricing, Hedging & Design australischer investment-linked / lifetime Retirement-Income-Produkte

Stand: 2026-07-09 · Zusammengestellt für die Produktklasse **investment-linked lifetime annuities, participating/longevity-linked annuities, pooled / group-self-annuitisation (GSA)/CDC** (u. a. Generation Life LifeIncome, Allianz Retire+ AGILE, Challenger Liquid Lifetime, AMP MyNorth Lifetime, ART Lifetime Pension).

## Methodik & Grenzen (wichtig)
- Recherche über Google Scholar, SSRN, arXiv, RePEc/IDEAS, Verlagsseiten (Wiley, Elsevier, Cambridge/ASTIN, Springer, T&F), MDPI, sowie Actuaries Institute / Treasury / APRA-ASIC / CEPAR-UNSW. Kandidaten dedupliziert (Preprint + Journalfassung = ein Eintrag mit beiden Fundstellen).
- **Zugangsprüfung**: frei/OA (arXiv, SSRN, RePEc, institutionelle Repositorien, Working-Paper- und Konferenzfassungen, autorisierte AAM) vs. paywalled. Es wurden **keine** Paywalls, Logins oder Captchas umgangen und keine Piraterie-Quellen genutzt.
- **Speicherformat**: Meine Tools können keine Original-PDF-Binärdateien speichern (jeder Web-Zugriff läuft über einen Text-Extraktions-Fetch). Auf Wunsch „Textextrakte für alles" liegen die frei verfügbaren Volltexte daher als **durchsuchbare `.md`-Textfassungen** in `open_access/` — nicht als Original-PDF. Für die Version of Record bitte den jeweiligen Link nutzen.
- **Bibliografie-Verifikation**: DOIs/Jahr/Band gegen die Crossref-API geprüft. Ein Teil der Prüfungen und Downloads lief in ein sitzungsweites `web_fetch`-Rate-Limit (HTTP 429); betroffene Angaben sind als ⚠ markiert und die Texte als „lokal ausstehend" — sie sind über die genannten OA-Links legal beschaffbar und können in einem Folgelauf nachgezogen werden.

## Legende
- **Verifikation:** ✓ = DOI/Venue via Crossref bestätigt · ✎ = DOI korrigiert (und bestätigt) · ⚠ = Kandidatangabe, noch nicht verifiziert (Rate-Limit)
- **Zugang:** `OPEN — lokal: <datei>` = Textfassung gespeichert · `OPEN — lokal ausstehend` = OA-Quelle identifiziert, Textextrakt wegen Drossel/Anti-Bot noch offen · `PAYWALLED` = nur Metadaten in `paywalled_or_unavailable/`
- **Einordnung:** `[produktnah]` = inhaltlich nah an der Produktklasse · `[verwandt]` = methodisch verwandte GMxB/Variable-Annuity-Literatur, **nicht produktspezifisch**

## Gruppierung nach Risikoarchitektur (Begründung)
Gegliedert wird nach der **Risiko-/Wirkungsschicht des Produkts**, weil genau diese Schichten die Designentscheidungen der australischen Produkte bestimmen: (A) das **Longevity-Pooling** liefert die Mortality/Survival-Credits der nicht-garantierten Pool-Produkte; (B) die **Auszahlungsmechanik (Hurdle-Rate/AIR)** übersetzt Kapitalmarkt- und Sterblichkeitsabweichungen in die jährliche Einkommensanpassung; (C) die **Hedging-/Kapitalschicht** managt Langlebigkeits- und Marktrisiko auf Bestandsebene; (D) **Teilgarantien & Partizipation** (Floor/Cap, GLWB) sind die versicherten Overlays; (E) **Decumulation & intergenerationelles Risk-Sharing** liefern die Nachfrage-/Haushaltssicht (inkl. Age-Pension-Interaktion und CDC); (F) der **regulatorische Rahmen** (Retirement Income Covenant) steckt den Möglichkeitsraum ab. Mehrere Arbeiten berühren zwei Schichten — sie stehen in der primären Schicht, mit Querverweis im Relevanztext.

---

## A. Longevity-Pooling & Mortality Credits (GSA / Pooled Annuity Funds / Tontines)
*Mechanismus hinter nicht-garantierten Pool-Produkten wie ART Lifetime Pension; „survival credits", jährliche Pool-Anpassung, Fairness, Poolgröße.*

**A1. The Simple Analytics of a Pooled Annuity Fund** — Piggott, Valdez & Detzel (2005). *J. Risk & Insurance* 72(3):497–520. DOI 10.1111/j.1539-6975.2005.00134.x ✓. **PAYWALLED** (Metadaten: `paywalled_or_unavailable/2005_Piggott_...md`; VoR: Wiley). *Relevanz:* Gründungsmodell der GSA-/Pooled-Annuity-Auszahlung — die Mechanik der AU-Pool-Renten (Piggott = CEPAR-Gründungsdirektor). Risiko: **Longevity-Pooling / Mortality Credits**. [produktnah]

**A2. Demand and Adverse Selection in a Pooled Annuity Fund** — Valdez, Piggott & Wang (2006). *Insurance: Math. & Econ.* 39(2):251–266. DOI 10.1016/j.insmatheco.2006.02.011 ✓. **PAYWALLED** (Metadaten-Stub; VoR: ScienceDirect). *Relevanz:* Adverse Selektion in freiwilligen Pools — zentral für Take-up/Viabilität nicht-garantierter AU-Pool-Produkte. Risiko: **Adverse Selektion / Pooling**. [produktnah]

**A3. Optimal Consumption and Portfolio Choice for Pooled Annuity Funds** — Stamos (2008). *Insurance: Math. & Econ.* 43(1):56–68. DOI 10.1016/j.insmatheco.2007.09.010 ✓. **OPEN — lokal ausstehend** (nicht heruntergeladen; Quelle: SSRN:1024269 / UNSW-WP-PDF). *Relevanz:* zeitstetige optimale Entnahme + Asset-Allocation im Pool — informiert Design investmentgebundener Pool-Produkte. Risiko: **Drawdown / Pooling**. [produktnah]

**A4. Managing Systematic Mortality Risk with Group Self-Pooling and Annuitisation Schemes** — Qiao & Sherris (2013). *J. Risk & Insurance* 80(4):949–974. DOI 10.1111/j.1539-6975.2012.01483.x ✓. **OPEN — lokal ausstehend** (429; Quelle: SSRN:1791162 / RePEc:asb/wpaper/201104, UNSW-WP 2011). *Relevanz:* UNSW/CEPAR-Analyse, wie systematische Sterblichkeitsverbesserung + schrumpfende Poolzahlen die GSA-Effektivität erodieren — zentrales AU-Design-Problem. Risiko: **Systematisches Mortalitätsrisiko / Poolgröße**. [produktnah]

**A5. Actuarial Fairness and Solidarity in Pooled Annuity Funds** — Donnelly (2015). *ASTIN Bulletin* 45(1):49–74. DOI 10.1017/asb.2014.18 ✓. **OPEN — lokal: `2015_Donnelly_Actuarial-Fairness-Pooled-Annuity.md`** (arXiv:1311.5120). *Relevanz:* endliche Pools sind nicht exakt fair (Quersubventionen) — relevant für kleine/heterogene AU-Pools. Risiko: **Actuarial Fairness / Poolgröße**. [produktnah]

**A6. Bringing Cost Transparency to the Life Annuity Market** — Donnelly, Guillén & Nielsen (2014). *Insurance: Math. & Econ.* 56:14–27. DOI 10.1016/j.insmatheco.2014.02.003 ✎ (früher zitierte 2014.03.002 war falsch). **PAYWALLED** (Metadaten-Stub; VoR: ScienceDirect). *Relevanz:* „instantaneously fair" Pooled-Annuity-Overlay, das Mortality Credits, Renditen und Gebühren trennt — Transparenz-Template. Risiko: **Actuarial Fairness / Kostentransparenz**. [produktnah]

**A7. Optimal Retirement Income Tontines** — Milevsky & Salisbury (2015). *Insurance: Math. & Econ.* 64:91–105. DOI 10.1016/j.insmatheco.2015.05.002 ✓. **OPEN — lokal: `2015_Milevsky_Optimal-Retirement-Income-Tontines.md`** (arXiv). *Relevanz:* nutzenoptimale Tontinen-Auszahlung („natural tontine") — theoretisches Rückgrat tontinenartiger AU-Decumulation. Risiko: **Pooling / Drawdown**. [produktnah]

**A8. Equitable Retirement Income Tontines: Mixing Cohorts Without Discriminating** — Milevsky & Salisbury (2016). *ASTIN Bulletin* 46(3):571–604. DOI 10.1017/asb.2016.19 ✓. **OPEN — lokal: `2016_Milevsky_Equitable-Retirement-Income-Tontines.md`** (arXiv). *Relevanz:* faires Poolen heterogener Alter/Beiträge via Auf-/Abschlag — löst Multi-Kohorten-Fairness in AU-Pools. Risiko: **Actuarial Fairness / Mortality Credits**. [produktnah]

**A9. Fair Tontine Annuity** — Sabin (2010). SSRN Working Paper 1579932. Keine DOI. **OPEN — lokal ausstehend** (SSRN-Delivery/Shell; Quelle: SSRN:1579932). *Relevanz:* faire Survivor-Credit-Reallokation für beliebig heterogene Mitglieder — praktische Fairness-Engine (in AU/Tontinen-Design breit zitiert, u. a. Fullmer-Sabin/MyNorth-nahe Logik). Risiko: **Actuarial Fairness / Mortality Credits**. [produktnah]

**A10. Individual Tontine Accounts** — Fullmer & Sabin (2019). *J. Accounting & Finance* 19(8). DOI 10.33423/jaf.v19i8.2615 ✓. **OPEN — lokal ausstehend** (OJS-Galley; Quelle: articlegateway / SSRN:3217551). *Relevanz:* individuelle Konten mit fairem Tontinen-Pooling und wählbaren Investments/Auszahlungen — nächste Analogie zu einem investmentgebundenen Pool-Produkt. Risiko: **Produktdesign / Pooling**. [produktnah]

**A11. Tonuity: A Novel Individual-Oriented Retirement Plan** — Chen, Hieber & Klein (2019). *ASTIN Bulletin* 49(1):5–30. DOI 10.1017/asb.2018.33 ✓. **OPEN — lokal ausstehend** (SSRN-Shell; Quelle: SSRN:3043013). *Relevanz:* Umschalten Tontine→Annuität mit garantiertem Floor — Design-Option für AU-Lifetime-Income mit Untergrenze. Risiko: **Produktdesign / Pooling + Floor**. [produktnah]

**A12. On the Optimal Combination of Annuities and Tontines** — Chen, Rach & Sehner (2020). *ASTIN Bulletin* 50(1):95–129. DOI 10.1017/asb.2019.37 ✎ (früher zitierte asb.2019.24 war ein anderer Artikel). **OPEN — lokal ausstehend** (SSRN-Shell; Quelle: SSRN:3430546). *Relevanz:* Annuität+Tontine-Portfolio dominiert Hybrid-Einzelprodukte unter Nutzen — Blend aus garantiertem vs. gepooltem Einkommen. Risiko: **Produktdesign / Drawdown**. [produktnah]

**A13. Modern Tontine with Bequest** — Bernhardt & Donnelly (2019). *Insurance: Math. & Econ.* 86:168–188. DOI 10.1016/j.insmatheco.2019.03.002 ⚠✎ (aus zitierenden Arbeiten; Kandidat 2019.02.005 vermutlich falsch — bitte final prüfen). **OPEN — lokal: `2019_Bernhardt_Modern-Tontine-with-Bequest.md`** (arXiv). *Relevanz:* Tontine + Bequest-Konto → Todesfallleistung; adressiert den Vererbungs-Einwand gegen Pool-Produkte (vgl. Death Benefit Period bei Gen Life/Challenger). Risiko: **Produktdesign / Bequest**. [produktnah]

**A14. The Modern Tontine** — Weinert & Gründl (2021). *European Actuarial Journal* 11(1):49–86. DOI 10.1007/s13385-020-00253-y ⚠. **OPEN — lokal: `2021_Weinert_The-Modern-Tontine.md`** (Springer/EconStor). *Relevanz:* verhaltensbasierte (Prospect-Theory) Bewertung von Tontinen als Annuitäts-Komplement/-Substitut — Nachfragesicht für Pool-Produkte. Risiko: **Pooling / Nachfrage**. [produktnah]

**A15. Quantifying the Trade-off Between Income Stability and the Number of Members in a Pooled Annuity Fund** — Bernhardt & Donnelly (2021). *ASTIN Bulletin* 51(1):101–130. DOI 10.1017/asb.2020.33 ⚠. **OPEN — lokal: `2021_Bernhardt_Income-Stability-vs-Pool-Size.md`** (arXiv:2010.16009). *Relevanz:* analytischer Zusammenhang Poolgröße ↔ Einkommensstabilität — Sizing-Leitplanke für viable AU-Pools. Risiko: **Poolgröße / Einkommensstabilität**. [produktnah]

**A16. Modern Life-Care Tontines** — Hieber & Lucas (2022). *ASTIN Bulletin* 52(2):563–589. DOI 10.1017/asb.2022.6 ⚠. **OPEN — lokal ausstehend** (DIAL-JS-SPA blockiert; Quelle: SSRN:3688386 / RePEc:aiz/louvad/2020026). *Relevanz:* poolt Mortalität + Long-Term-Care (Morbidität) — erweitert Pool-Einkommen um Pflege-/Gesundheitsrisiko. Risiko: **Pooling / Morbidity Credits**. [produktnah]

**A17. Facing Up to Longevity with Old Actuarial Methods: Pooled Funds vs. Income Tontines** — Bräutigam, Guillén & Nielsen (2017). *Geneva Papers on Risk & Insurance* 42(3):406–422. DOI 10.1057/s41288-017-0056-1 ⚠. **OPEN — lokal ausstehend** (ETH-JS-Shell; OA-Kopie: ETH Research Collection). *Relevanz:* direkter Vergleich Pooled-Annuity-Overlay (Fairness) vs. equitable Tontine — rahmt die zwei AU-Produktphilosophien. Risiko: **Actuarial Fairness / Pooling**. [produktnah]

**A18. Modern Tontines as a Pension Solution: A Practical Overview** — Winter & Planchet (2022). *European Actuarial Journal* 12(1):3–32. DOI 10.1007/s13385-021-00297-8 ⚠. **PAYWALLED** (Metadaten-Stub; Autorenseite winter-aas.com evtl. OA — unbestätigt). *Relevanz:* formalisiert den Fullmer-Sabin-Mechanismus für die Umsetzung (Joint Lives, „term dilemma", Biases) — Praktiker-Referenz. Risiko: **Produktdesign / Poolgröße**. [produktnah]

**A19. Benefit Volatility-Targeting Strategies in Lifetime Pension Pools** — Bégin & Sanders (2024). *Insurance: Math. & Econ.* 118:72–94. DOI 10.1016/j.insmatheco.2024.04.001 ⚠. **OPEN — lokal: `2024_Begin_Benefit-Volatility-Targeting-Pension-Pools.md`** (AFIR-ERM/actuaries.org). *Relevanz:* Volatilitäts-Targeting über **Investment- UND Mortalitätsrisiko** zur Glättung gepoolter Leistungen — direkt die Glättung investmentgebundener Pool-Einkommen. Risiko: **Drawdown / Einkommensstabilität**. [produktnah]

**A20. Wealth Heterogeneity in a Closed Pooled Annuity Fund** — Bernhardt & Qu (2023). *Scandinavian Actuarial Journal* 2023(9):838–861. DOI 10.1080/03461238.2023.2234916 ⚠. **OPEN — lokal: `2023_Bernhardt_Wealth-Heterogeneity-Pooled-Annuity.md`** (arXiv:2110.13467). *Relevanz:* Wirkung ungleicher Beiträge auf Einkommensstabilität („implied number of homogeneous members") — praktische Regel, wer zusammen poolen sollte. Risiko: **Poolgröße / Fairness**. [produktnah]

**A21. Target Volatility Strategies for Group Self-Annuity Portfolios** — Olivieri, Thirurajah & Ziveyi (2022). *ASTIN Bulletin* 52(2):591–617. DOI 10.1017/asb.2022.7 ⚠. **PAYWALLED** (Metadaten-Stub; kein legales OA gefunden). *Relevanz:* Target-Vol-Overlay (Equity/Cash) zur Stabilisierung/Steigerung von GSA-Living-Benefits — Marktrisiko-Seite gepoolter Produkte (vgl. auch C). Risiko: **Marktrisiko / Investment-Overlay**. [produktnah]

---

## B. Investment-linked Lifetime-Income-Mechanik: Hurdle-Rate / AIR & jährliche Einkommensanpassung
*Kern der ILA-Produkte (Gen Life LifeIncome, Allianz AGILE, MyNorth): wie Kapitalmarkt- und Sterblichkeitsabweichungen relativ zur „assumed investment return" (AIR)/Hurdle Rate in die jährliche Einkommens­anpassung übersetzt werden. Diese Schicht ist überwiegend australische Aktuars-Grauliteratur.*

**B1. Investment Linked Lifetime Annuity** — Orford / Optimum Pensions, Actuaries Institute (2014). Actuaries Digital (Grauliteratur), keine DOI. **OPEN — lokal: `2014_Orford_Investment-Linked-Lifetime-Annuity.md`**. *Relevanz:* australische Grundlagen-Darstellung der ILLA mit durchgerechnetem „unit-reduction factor" (z. B. 3,88 %, um bei 7 % Rendite 3 % p. a. Anstieg auszuschütten) — die Hurdle-/AIR-Mechanik in Reinform. Risiko: **Hurdle-Rate/AIR / Einkommensanpassung**. [produktnah]

**B2. What is an Investment-Linked Annuity?** — Orford / Optimum Pensions, Actuaries Institute (2021). Actuaries Digital (Grauliteratur), keine DOI. **OPEN — lokal: `2021_Orford_What-is-an-Investment-Linked-Annuity.md`**. *Relevanz:* aktualisiertes ILLA-Primer; Beispiel 2 ist die explizite Hurdle-Demonstration (3 % p. a. „forgone" → höheres Startseinkommen, danach Anstieg = Rendite − 3 %); Abgrenzung zu GSA-Pooling und Age-Pension-Uplift. Risiko: **Hurdle-Rate/AIR / Einkommensanpassung**. [produktnah]

**B3. Optimal Hurdle Rate and Investment Policy in Lifetime Pension Pools** — Bégin, Sanders & Sun (2025/2026). *ASTIN Bulletin* (forthcoming; DOI ⚠ noch offen). **OPEN — lokal: `2025_Begin_Optimal-Hurdle-Rate-Lifetime-Pension-Pools.md`** (SFU-Thesis-Fassung, identische Autoren/Thema; Journalfassung paywalled). *Relevanz:* optimiert per Dynamic Programming **beide** Designhebel eines Lifetime Pension Pools — Investmentpolitik UND Hurdle Rate — nach Risikoaversion; die zentrale akademische Behandlung der Hurdle-Wahl. Risiko: **Hurdle-Rate/AIR / Einkommensanpassung**. [produktnah]

**B4. Case Study: How Innovative Retirement Income Streams Compare to CPI-linked Annuities** — Actuaries Institute (2025). Actuaries Digital (Grauliteratur), keine DOI. **OPEN — lokal ausstehend** (429; Quelle: actuaries.asn.au). *Relevanz:* vergleicht investmentgebundene/innovative Income Streams mit CPI-Annuitäten und zeigt, wie der AIR-Hurdle (z. B. 4 %) den Trade-off Startseinkommen vs. künftige Indexierung treibt. Risiko: **Hurdle-Rate/AIR / Einkommensanpassung**. [produktnah]

---

## C. Longevity- & Markt-Risiko-Hedging, Mortalitätsmodelle, Kapital/Reservierung
*Risiko-Management-Schicht auf Bestandsebene (CEPAR-UNSW-Strang stark vertreten): Hedgen von Langlebigkeits- und Zinsrisiko, Mortalitätsmodellierung, Solvenz/Kapital.*

**C1. Optimal Hedging of Longevity Risks for Group Self-Annuity Portfolios** — Shen, Sherris, Wang & Ziveyi (2025). *J. Risk & Insurance* 92(4):1013–1058. DOI 10.1111/jori.70024 ✓. **OPEN — lokal ausstehend** (Preprint = CEPAR-Konferenzpapier „Dynamic Hedging…", cepar.edu.au). *Relevanz:* dynamischer S-Forward-Hedge des systematischen Langlebigkeitsrisikos zur Glättung von GSA-Survival-Benefits mit Population-Basis-Risk — direkt das gepoolte Produkt. Risiko: **Longevity-Hedging / Basis-Risk**. [produktnah]

**C2. Managing Systematic Mortality Risk in Life Annuities: An Application of Longevity Derivatives** — Fung, Ignatieva & Sherris (2019). *Risks* 7(1):2. DOI 10.3390/risks7010002 ✓. **OPEN — lokal: `2019_Fung_Managing-Systematic-Mortality-Longevity-Derivatives.md`** (MDPI OA; auch arXiv:1508.00090). *Relevanz:* indexbasierter Longevity-Swap + Longevity-Cap-Hedge, traktables affines Mortalitätsmodell auf **australischen** Daten. Risiko: **Longevity-Hedging / Mortalitätsmodell**. [produktnah]

**C3. Immunization and Hedging of Post-Retirement Income Annuity Products** — Liu & Sherris (2017). *Risks* 5(1):19. DOI 10.3390/risks5010019 ✓. **OPEN — lokal: `2017_Liu_Immunization-Hedging-Post-Retirement-Income.md`** (MDPI OA). *Relevanz:* Immunisierung + Delta-Gamma-Hedging australischer Post-Retirement-Annuitätsportfolios mit Coupon-/Annuity-/Longevity-Bonds, VaR-basiert. Risiko: **Kapital/Reservierung / Natural Hedging**. [produktnah]

**C4. Delta and Gamma Hedging of Mortality and Interest Rate Risk** — Luciano, Regis & Vigna (2012). *Insurance: Math. & Econ.* 50(3):402–412. DOI 10.1016/j.insmatheco.2012.01.006 ✎ (Kandidat …01.007 war falsch). **OPEN — lokal ausstehend** (carloalberto.org blockiert Bots; Quelle: Carlo Alberto Notebook / SSRN:1749426). *Relevanz:* geschlossene Delta-Gamma-Hedges von Annuitäten unter stochastischer Mortalität + Zins — Hedging-Werkzeugkasten für Decumulation. Risiko: **Natural / Delta-Gamma-Hedging**. [produktnah]

**C5. Single- and Cross-Generation Natural Hedging of Longevity and Financial Risk** — Luciano, Regis & Vigna (2017). *J. Risk & Insurance* 84(3):961–986. DOI 10.1111/jori.12104 ✎ (der zuvor gelistete ASTIN-Titel/DOI asb.2017.2 gehört zu einem anderen Paper — Venue ist **JRI**, nicht ASTIN). **OPEN — lokal ausstehend** (Preprint-Zuordnung ICER/SSRN prüfen). *Relevanz:* natürliches Hedging über gegenläufige Langlebigkeits-/Finanzexposures, auch kohortenübergreifend. Risiko: **Natural Hedging**. [produktnah]

**C6. Key q-Duration: A Framework for Hedging Longevity Risk** — Li & Luo (2012). *ASTIN Bulletin* 42(2):413–452. DOI 10.2143/AST.42.2.2182803 ✓. **PAYWALLED** (Metadaten-Stub; evtl. Pensions-Institute-WP1109 — unbestätigt). *Relevanz:* q-Forward-Hedge über Key-q-Durationen inkl. Kohorten-/Population-Basis-Risk. Risiko: **Longevity-Hedging / Basis-Risk**. [produktnah]

**C7. Consistent Dynamic Affine Mortality Models for Longevity Risk Applications** — Blackburn & Sherris (2013). *Insurance: Math. & Econ.* 53(1):64–73. DOI 10.1016/j.insmatheco.2013.04.007 ✓. **OPEN — lokal ausstehend** (429; Quelle: SSRN:1832014 / UNSW-WP 2011/07). *Relevanz:* arbitragefreies Mehrfaktor-Affinmodell mit geschlossenen Survival-Kurven zum Pricing/Hedging von Longevity-Bonds/-Derivaten. Risiko: **Mortalitätsmodell**. [produktnah]

**C8. Continuous-time Multi-cohort Mortality Modelling with Affine Processes** — Xu, Sherris & Ziveyi (2020). *Scandinavian Actuarial Journal* 2020(6):526–552. DOI 10.1080/03461238.2019.1696223 ✓. **OPEN — lokal ausstehend** (429; AAM: UNSWorks-Repositorium). *Relevanz:* affines Multi-Kohorten-Modell für die gesamte Mortalitätsfläche bei Rentenaltern — Basis für AU-Longevity-Pricing/Hedging. Risiko: **Mortalitätsmodell / Basis-Risk**. [produktnah]

**C9. Market Price of Longevity Risk for a Multi-cohort Mortality Model (Longevity Bond Option Pricing)** — Xu, Sherris & Ziveyi (2020). *J. Risk & Insurance* 87(3):571–595. DOI 10.1111/jori.12273 ✓. **OPEN — lokal ausstehend** (429; Quelle: SSRN:3121520). *Relevanz:* risikoneutrale Kalibrierung + Longevity-Bond-Optionspricing unter dem Multi-Kohorten-Affinmodell. Risiko: **Mortalitätsmodell / Longevity-Hedging**. [produktnah]

**C10. Mortality Surface by Means of Continuous-time Cohort Models** — Jevtić, Luciano & Vigna (2013). *Insurance: Math. & Econ.* 53(1):122–133. DOI 10.1016/j.insmatheco.2013.04.005 ✓. **OPEN — lokal ausstehend** (carloalberto.org blockiert; Quelle: Carlo Alberto Notebook). *Relevanz:* affine zeitstetige Kohorten-Mortalitätsfläche zur Bewertung/Hedging von Longevity-Liabilities. Risiko: **Mortalitätsmodell**. [verwandt→produktnah]

**C11. Pricing Death: Frameworks for the Valuation and Securitization of Mortality Risk** — Cairns, Blake & Dowd (2006). *ASTIN Bulletin* 36(1):79–120. DOI 10.2143/AST.36.1.2014145 ✓. **OPEN — lokal: `2006_Cairns_Pricing-Death-Valuation-Securitization.md`** (Autor-Kopie Uni Ulm). *Relevanz:* Fundament der Bewertung/Verbriefung von Longevity-/Mortalitäts-Securities — Basis aller nachgelagerten Hedges. Risiko: **Longevity-Hedging / Securitisation**. [verwandt]

**C12. Longevity Hedge Effectiveness: A Decomposition** — Cairns, Dowd, Blake & Coughlan (2014). *Quantitative Finance* 14(2):217–235. DOI 10.1080/14697688.2012.748986 ✓. **OPEN — lokal ausstehend** (429; direkter PDF: MPRA 34236). *Relevanz:* zerlegt Effektivität indexbasierter q-Forward-/Longevity-Swap-Hedges inkl. Population-Basis-Risk. Risiko: **Basis-Risk / Longevity-Hedging**. [verwandt→produktnah]

**C13. Natural Hedging Strategies for Life Insurers: Impact of Product Design and Risk Measure** — Wong, Sherris & Stevens (2017). *J. Risk & Insurance* 84(1):153–175. DOI 10.1111/jori.12079 ✓ (Ko-Autor ist Stevens, nicht Ziveyi wie teils falsch zitiert). **OPEN — lokal ausstehend** (Preprint-URL unbestätigt; UNSW/Netspar-WP). *Relevanz:* Kapitalreduktion für Longevity/Annuity via Natural Hedging, Solvency-II vs. Mehrperioden-Risikomaß. Risiko: **Natural Hedging / Kapital**. [produktnah]

**C14. Longevity Risk Management and Shareholder Value for a Life Annuity Business** — Blackburn, Hanewald, Olivieri & Sherris (2017). *ASTIN Bulletin* 47(1):43–77. DOI 10.1017/asb.2016.32 ✓. **OPEN — lokal ausstehend** (429; Quelle: SSRN:2359222). *Relevanz:* Solvenzkapital, marktkonsistente Bewertung & Shareholder Value zurückbehaltenen Langlebigkeitsrisikos im Renten-Buch. Risiko: **Kapital/Reservierung**. [produktnah]

**C15. Individual Post-Retirement Longevity Risk Management under Systematic Mortality Risk** — Hanewald, Piggott & Sherris (2013). *Insurance: Math. & Econ.* 52(1):87–97. DOI 10.1016/j.insmatheco.2012.11.002 ✓. **OPEN — lokal ausstehend** (429; Quelle: RePEc:asb/wpaper/201113 / CEPAR). *Relevanz:* optimale Decumulation/Produktwahl (Annuität vs. Drawdown vs. Pool) unter systematischem Mortalitätsrisiko — australische Rahmung. Risiko: **Longevity-Hedging / Decumulation**. [produktnah]

**C16. A Flexible Longevity Bond to Manage Individual Longevity Risk** — Zhou, Sherris, Ziveyi & Xu (2020, WP). CEPAR/UNSW Working Paper. DOI 10.2139/ssrn.3580488 ⚠ (Journalfassung nicht bestätigt). **OPEN — lokal ausstehend** (429; Quelle: SSRN:3580488). *Relevanz:* kombiniertes Investment-+Versicherungs-Longevity-Bond als flexibles individuelles Retirement-Instrument — investmentgebundenes Lifetime-Design. Risiko: **Longevity-Hedging / Produktdesign**. [produktnah]

<!-- MORE -->

