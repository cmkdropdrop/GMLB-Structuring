from pathlib import Path

import chrome_print_pdf as renderer


workspace = Path(__file__).resolve().parent.parent
renderer.HTML = workspace / "_review_work" / "AGILE_Modelling_Fachpaper_reviewed_kurzfassung.html"
renderer.PDF = workspace / "AGILE_Modelling_Fachpaper_reviewed_kurzfassung.pdf"
renderer.PROFILE = workspace / "_review_work" / "chrome_short_pdf_profile"


if __name__ == "__main__":
    renderer.main()

