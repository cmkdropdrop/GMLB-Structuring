# Repository-Anweisungen

## Eingabedaten

Marktdaten und Parameter für Marktmodelle sind aus
`C:\Users\user\Documents\GMLB Structuring\AGILE_Modelling_Engine\input_market_data`
zu verwenden. Die australische Zinskurve ist die einzige laufend einzulesende
Marktdatenquelle. Weitere Marktzeitreihen, Volatilitätsflächen, Credit-Spread-
Kurven oder separate Kalibrierungsdateien sollen für das vereinfachte
Basismodell nicht verlangt werden.

Für die marktkonsistente Bewertung soll standardmäßig das
Heston-Hull-White-Modell unter dem risikoneutralen Maß verwendet werden.

## Vereinfachte Real-World-Projektionen

Real-World-Projektionen sollen standardmäßig mit dem
Black-Scholes-Hull-White-Modell unter `Measure.REAL_WORLD` erzeugt werden. Ziel
ist eine transparente und robuste Baseline, die ausschließlich die vorhandene
australische Zinskurve und die bereits in `model_parameters.csv` enthaltenen
Parameter benötigt. Es soll keine zusätzliche physische Kalibrierung eingeführt
oder vorausgesetzt werden.

Dabei gelten folgende Annahmen:

1. **Aktien:** Für Australian Equity und Global Equity werden die vorhandenen
   Volatilitäten, Korrelationen und Equity Risk Premia aus
   `model_parameters.csv` verwendet. Unter Real World entspricht der Drift dem
   vom Modell vorgegebenen risikofreien Drift zuzüglich des vorhandenen Equity
   Risk Premium. Bei Total-Return-Indizes werden Ausschüttungen nicht nochmals
   separat addiert.

2. **Zinsen:** Die simulierte Zinsstruktur muss zum Projektionsstart exakt an die
   eingelesene australische Zinskurve anschließen. Mean Reversion,
   Zinsvolatilität und Rate-Equity-Korrelationen werden unverändert aus
   `model_parameters.csv` übernommen. In der vereinfachten Real-World-Baseline
   wird keine zusätzliche Bond Term Premium und kein separater Marktpreis des
   Zinsrisikos angesetzt. P- und Q-Zinsdynamik unterscheiden sich daher in
   diesem Basismodell nicht.

3. **Bond-Sleeve:** Der Bondanteil eines Mischfonds wird durch ein monatlich
   rollierendes Portfolio nominaler australischer Staatsanleihen mit konstanter
   Restlaufzeit von fünf Jahren approximiert. Der Total Return ist aus den
   pfadweisen Zero-Coupon-Preisen der Hull-White-Zinskurve abzuleiten und muss
   laufenden Ertrag, Preisänderung und Roll-down gemeinsam enthalten. Es werden
   keine Credit Spreads, Ausfälle, Ratingmigrationen oder Inflationsanleihen
   modelliert. Falls die technische Bond-Total-Return-Funktion noch nicht
   implementiert ist, darf vorübergehend die pfadweise Verzinsung zum Short Rate
   als klar gekennzeichneter Fallback verwendet werden.

4. **Mischfonds:** Aktien- und Bond-Sleeve werden zuerst zum Fondsreturn
   kombiniert. Für den monatlichen einfachen Return gilt

   `R_fund = w_equity * R_equity + (1 - w_equity) * R_bond`.

   Anschließend wird monatlich auf die Zielallokation zurückgesetzt. Ein
   kontinuierliches Rebalancing ist nicht zu unterstellen. Explizit in den
   Produktunterlagen angegebene Aktienquoten haben Vorrang und sind als
   Produkteigenschaft, nicht als Marktmodellparameter, zu behandeln.

5. **Feste Fallback-Allokationen:** Fehlt eine explizite Aktienquote, wird sie
   allein aus der Fondsbezeichnung abgeleitet:

   - Cash: 0 % Aktien; vollständig Short-Rate-Anlage
   - Conservative: 30 % Aktien / 70 % Bonds
   - Conservative Balanced: 45 % Aktien / 55 % Bonds
   - Balanced: 60 % Aktien / 40 % Bonds
   - Growth: 80 % Aktien / 20 % Bonds
   - Unbekannte oder nicht zuordenbare Mischfonds: 60 % Aktien / 40 % Bonds

   Ist die regionale Aktienaufteilung nicht angegeben, wird der Aktien-Sleeve
   zu 50 % aus Australian Equity und zu 50 % aus Global Equity gebildet. Diese
   Fallbacks sind feste Modellkonventionen und dürfen nicht als beobachtete
   Produktallokationen oder kalibrierte Marktdaten bezeichnet werden.

6. **Weitere Vereinfachungen:** Es werden keine zusätzlichen Parameter für
   Bond-Duration, Creditqualität, FX-Volatilität, Hedgekosten, taktische
   Allokation, Transaktionskosten oder fondsinterne Gebühren eingeführt. Global
   Equity wird als bereits in AUD ausgedrückter beziehungsweise AUD-abgesicherter
   Total-Return-Index behandelt. Nur bereits im Produktmodell vorhandene
   Gebühren werden berücksichtigt.

7. **Crediting-Reihenfolge:** Bezieht sich ein Cap, Floor oder Schutzmechanismus
   auf den Mischfonds, ist zunächst der vollständige Mischfondsreturn zu bilden
   und erst danach die nichtlineare Crediting-Funktion anzuwenden. Es darf nicht
   zuerst auf Aktien- und Bondreturn getrennt ein Cap oder Floor angewendet und
   anschließend gewichtet werden. Bezieht sich der Vertrag dagegen auf mehrere
   separat geschützte Investmentoptionen, erfolgt das Crediting je Option und
   erst danach die Gewichtung gemäß Vertrag.

8. **Kundenfonds und Backing Assets:** Mischfonds, deren NAV unmittelbar die
   Kundenleistung bestimmt, sind in der Kundenprojektion zu modellieren. Handelt
   es sich lediglich um das Backing- oder Hedgeportfolio des Versicherers, darf
   dessen Return nicht als Kunden-Crediting verwendet werden; er gehört dann nur
   in die Asset-/ALM- und Profitabilitätsrechnung.

9. **Kennzeichnung:** Ergebnisse dieses Ansatzes sind als vereinfachte
   Real-World-Projektionen mit festen Proxy-Annahmen zu bezeichnen. Insbesondere
   sind die fehlende Bond Term Premium, die feste Fünfjahreslaufzeit, das
   monatliche Rebalancing und die Fallback-Allokationen als Modellgrenzen zu
   dokumentieren. Sie dürfen nicht als vollständig kalibrierte Prognose
   dargestellt werden.

## Begriffe

Mit `Policyholder` ist hier die versicherte Person gemeint.

Mit `Modelpoint` ist ein Beispiel für eine versicherte Person gemeint, auch wenn
dies im Repo noch nicht überall konsequent umgesetzt ist.

## Allgemeines

Keine Scripte laufen lassen, ausser ich sage es spezifisch
Der Stack wurde ursprünglich für das AGILE Produkt konzipiert, soll nun aber schrittweise auf ein generisches, aber sehr ähnliches Produkt umgestellt werden
Die Produktlogik für das generische Produkt ist in Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md beschrieben
