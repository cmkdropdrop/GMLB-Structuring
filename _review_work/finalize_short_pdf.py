from pathlib import Path

import fitz


PDF = Path(__file__).resolve().parent.parent / "AGILE_Modelling_Fachpaper_reviewed_kurzfassung.pdf"


def deduplicate(title: str) -> str:
    if len(title) % 2 == 0:
        middle = len(title) // 2
        if title[:middle] == title[middle:]:
            return title[:middle]
    return title


document = fitz.open(PDF)
metadata = document.metadata
metadata.update(
    {
        "title": "AGILE Modelling — Kurzfassung",
        "author": "Interne Fach- und Lernunterlage",
        "subject": "Wichtigste Produktmechaniken, Modellergebnisse und Model-Risk-Befunde des reviewed Research Prototype 1.3.0",
        "keywords": "AGILE, Kurzfassung, actuarial modelling, longevity, GLWB, model risk",
        "creator": "Independent review workflow / Chromium",
    }
)
document.set_metadata(metadata)
document.set_toc(
    [[level, deduplicate(title), page] for level, title, page in document.get_toc(simple=True)]
)
document.saveIncr()
document.close()

print(f"FINALIZED={PDF}")

