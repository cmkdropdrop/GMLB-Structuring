# Aktienallokation

`equity_allocation.csv` ist die zentrale Eingabedatei für die Aktienquote des
generischen Reference Fund.

Die Spalten bedeuten:

- `allocation_id`: eindeutige ID des Allokationssatzes;
- `equity_weight`: Aktienquote als Dezimalzahl zwischen `0` und `1`;
- `allocation_basis`: fachliche Einordnung der Eingabe;
- `description`: beschreibender Text.

Der mitgelieferte Basiswert `0.30` entspricht 30 % Global Equity. Der
Bondanteil wird nicht redundant eingegeben, sondern in den Analysen immer als
`1 - equity_weight` abgeleitet. Bei `0.30` ergeben sich somit 70 % nominale
australische Staatsanleihen.

Die Aktienquote ist eine Produkteigenschaft und kein Marktmodellparameter oder
kalibrierter Marktwert. Die CSV ändert nur die Aufteilung zwischen dem
vorhandenen Global-Equity-Sleeve und dem vorhandenen Bond-Sleeve. Sie führt
keine zusätzliche regionale Aktienaufteilung ein. Die monatliche
Rücksetzung auf die Zielallokation und die konstante fünfjährige Restlaufzeit
des Bond-Sleeves bleiben unverändert.
