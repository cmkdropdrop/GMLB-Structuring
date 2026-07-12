from __future__ import annotations

import os
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import fitz
from lxml import etree


WORKSPACE = Path(__file__).resolve().parent.parent
DOCX = WORKSPACE / "AGILE_Modelling_Fachpaper_reviewed.docx"
PDF = WORKSPACE / "AGILE_Modelling_Fachpaper_reviewed.pdf"

CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def set_or_create(root: etree._Element, qname: str, value: str) -> None:
    node = root.find(qname)
    if node is None:
        node = etree.SubElement(root, qname)
    node.text = value


def finalize_docx() -> None:
    temp = DOCX.with_suffix(".docx.finalizing")
    with zipfile.ZipFile(DOCX, "r") as source, zipfile.ZipFile(
        temp, "w", allowZip64=True
    ) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                root = etree.fromstring(data)
                set_or_create(root, f"{{{DC_NS}}}title", "AGILE Modelling")
                set_or_create(
                    root,
                    f"{{{DC_NS}}}creator",
                    "Interne Fach- und Lernunterlage",
                )
                set_or_create(
                    root,
                    f"{{{DC_NS}}}subject",
                    "Unabhängig geprüfte Lernunterlage zur AGILE Modelling Research Engine 1.3.0",
                )
                set_or_create(
                    root,
                    f"{{{DC_NS}}}description",
                    "Reviewed research prototype; keine Pricing-, Reservierungs-, Kapital- oder Produktfreigabe.",
                )
                set_or_create(
                    root,
                    f"{{{CORE_NS}}}keywords",
                    "AGILE, actuarial modelling, longevity, GLWB, review, research prototype",
                )
                set_or_create(
                    root,
                    f"{{{CORE_NS}}}lastModifiedBy",
                    "Independent review workflow",
                )
                set_or_create(root, f"{{{CORE_NS}}}revision", "3")
                modified = root.find(f"{{{DCTERMS_NS}}}modified")
                if modified is None:
                    modified = etree.SubElement(root, f"{{{DCTERMS_NS}}}modified")
                modified.set(f"{{{XSI_NS}}}type", "dcterms:W3CDTF")
                modified.text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
                    "+00:00", "Z"
                )
                data = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            elif info.filename == "docProps/app.xml":
                root = etree.fromstring(data)
                pages = root.xpath('//*[local-name()="Pages"]')
                if pages:
                    pages[0].text = "50"
                data = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            elif info.filename.startswith("word/footer") and info.filename.endswith(".xml"):
                root = etree.fromstring(data)
                namespace = {
                    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                }
                cached_total_pages = root.xpath(
                    './/w:fldSimple[contains(@w:instr, "NUMPAGES")]//w:t',
                    namespaces=namespace,
                )
                for node in cached_total_pages:
                    node.text = "50"
                data = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            elif info.filename == "word/settings.xml":
                root = etree.fromstring(data)
                word_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                update = root.find(f"{{{word_ns}}}updateFields")
                if update is None:
                    update = etree.SubElement(root, f"{{{word_ns}}}updateFields")
                update.set(f"{{{word_ns}}}val", "true")
                data = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            target.writestr(info, data)
    os.replace(temp, DOCX)


def deduplicate_outline_title(title: str) -> str:
    if len(title) % 2 == 0:
        middle = len(title) // 2
        if title[:middle] == title[middle:]:
            return title[:middle]
    return title


def finalize_pdf() -> None:
    document = fitz.open(PDF)
    metadata = deepcopy(document.metadata)
    metadata.update(
        {
            "title": "AGILE Modelling — unabhängig geprüfte Fassung",
            "author": "Interne Fach- und Lernunterlage",
            "subject": "Reviewed research prototype zur AGILE Modelling Research Engine 1.3.0; keine Produktionsfreigabe",
            "keywords": "AGILE, actuarial modelling, longevity, GLWB, review, research prototype",
            "creator": "Independent review workflow / Chromium",
        }
    )
    document.set_metadata(metadata)
    outline = document.get_toc(simple=True)
    cleaned = [[level, deduplicate_outline_title(title), page] for level, title, page in outline]
    document.set_toc(cleaned)
    document.saveIncr()
    document.close()


def main() -> None:
    if not DOCX.exists() or not PDF.exists():
        raise FileNotFoundError("Reviewed DOCX and PDF must both exist.")
    finalize_docx()
    finalize_pdf()
    print(f"DOCX={DOCX}")
    print(f"PDF={PDF}")


if __name__ == "__main__":
    main()
