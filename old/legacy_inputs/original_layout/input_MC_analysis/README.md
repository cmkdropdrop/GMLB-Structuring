# Monte-Carlo-Inputs

`portfolio_analysis.csv` enthält die zentralen Standardwerte für die
Monte-Carlo-Samples der Portfolioanalysen.

Die Spalten bedeuten:

- `sample_role`: fachliche Verwendung des Samples;
- `seed_set`: laufende Nummer eines verfügbaren Seed-Satzes innerhalb der
  Rolle;
- `n_paths`: Anzahl der Szenariopfade;
- `market_seed`: Seed des Marktmodells;
- `take_up_seed`: Seed für die Income-Election-Entscheidungen;
- `mortality_seed`: Seed für die pfadweisen Sterblichkeitszustände;
- `description`: rein beschreibender Text.

Die CSV legt **nicht** fest, wie viele LSMC-Trainings-Seeds aktiv sind. Diese
Anzahl bleibt eine Einstellung der aufrufenden Skripte. Der vereinfachte
Standardlauf verwendet einen Trainings-Seed-Satz; der explizite
Replikationslauf verwendet drei. Die CSV stellt dafür die nummerierten
Seed-Sätze 1 bis 3 bereit.

Die Bewertungs- und Risiko-Skripte lesen diese Datei für ihre Standardwerte.
Explizit auf der Kommandozeile gesetzte Pfadanzahlen oder Seeds überschreiben
weiterhin den jeweiligen CSV-Standard.
