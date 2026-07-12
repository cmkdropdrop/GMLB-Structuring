from __future__ import annotations

import collections
import hashlib
import io
import json
import re
import subprocess
import sys
import urllib.parse
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "_review_work"
MD = ROOT / "AGILE_Modelling_Fachpaper.md"
DOCX = ROOT / "AGILE_Modelling_Fachpaper.docx"
PDF = ROOT / "AGILE_Modelling_Fachpaper.pdf"
REPORT = WORK / "technical_diagnostics.txt"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

lines: list[str] = []


def emit(value: object = "") -> None:
    lines.append(str(value))


def section(title: str) -> None:
    emit()
    emit(f"[{title}]")


def walk_ast(value):
    if isinstance(value, dict):
        if "t" in value:
            yield value
        for child in value.values():
            yield from walk_ast(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_ast(child)


def ast_text(value) -> str:
    chunks: list[str] = []
    for node in walk_ast(value):
        typ = node.get("t")
        if typ == "Str":
            chunks.append(node.get("c", ""))
        elif typ in {"Space", "SoftBreak", "LineBreak"}:
            chunks.append(" ")
        elif typ in {"Code", "Math"}:
            c = node.get("c", [])
            if isinstance(c, list) and c:
                chunks.append(c[-1] if isinstance(c[-1], str) else "")
    return re.sub(r"\s+", " ", "".join(chunks)).strip()


def norm_words(text: str) -> collections.Counter[str]:
    words = re.findall(r"[^\W_]+(?:[’'-][^\W_]+)*", text.casefold(), re.UNICODE)
    return collections.Counter(words)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xpath_text(root: ET.Element, path: str, default: str = "") -> str:
    node = root.find(path, NS)
    return node.text if node is not None and node.text is not None else default


section("FILES")
for path in (MD, DOCX, PDF):
    data = path.read_bytes()
    emit(f"{path.name}: bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}")


section("MARKDOWN")
md_bytes = MD.read_bytes()
md_text = md_bytes.decode("utf-8", errors="strict")
emit(f"utf8_strict=yes; bom={md_bytes.startswith(bytes((0xEF, 0xBB, 0xBF)))}")
emit(
    "line_endings: "
    f"CRLF={md_bytes.count(bytes((13,10)))}; "
    f"LF_total={md_bytes.count(bytes((10,)))}; "
    f"CR_total={md_bytes.count(bytes((13,)))}; "
    f"lone_CR={md_bytes.count(bytes((13,))) - md_bytes.count(bytes((13,10)))}"
)
for offset, byte in enumerate(md_bytes):
    if byte < 32 and byte not in (9, 10):
        line_no = md_bytes[:offset].count(bytes((10,))) + 1
        last_lf = md_bytes.rfind(bytes((10,)), 0, offset)
        col_no = offset - last_lf
        context = md_bytes[max(0, offset - 35): offset + 55].decode("utf-8", errors="backslashreplace")
        emit(f"control: byte=0x{byte:02x}; offset={offset}; line={line_no}; col={col_no}; context={context!r}")

pandoc = subprocess.run(
    ["pandoc", str(MD), "--from=markdown", "--to=json", "--citeproc"],
    cwd=ROOT,
    capture_output=True,
    check=False,
)
emit(f"pandoc_parse_exit={pandoc.returncode}")
if pandoc.stderr:
    emit(f"pandoc_stderr={pandoc.stderr.decode('utf-8', errors='replace').strip()}")
ast = json.loads(pandoc.stdout.decode("utf-8")) if pandoc.returncode == 0 else {}
nodes = list(walk_ast(ast))
counts = collections.Counter(node.get("t") for node in nodes)
emit(
    "ast_counts: "
    + "; ".join(
        f"{key}={counts.get(key, 0)}"
        for key in ("Header", "Table", "Image", "Math", "Cite", "Link", "CodeBlock", "RawBlock", "RawInline")
    )
)
math_counts = collections.Counter()
for node in nodes:
    if node.get("t") == "Math":
        math_counts[node["c"][0]["t"]] += 1
emit(f"math_nodes: {dict(math_counts)}")

# The source deliberately uses \[...\] display delimiters. Pandoc's default
# markdown reader treats those as raw TeX; the explicit reader extension used
# for a robust build recognizes them as mathematics.
pandoc_math = subprocess.run(
    ["pandoc", str(MD), "--from=markdown+tex_math_single_backslash", "--to=json", "--citeproc"],
    cwd=ROOT,
    capture_output=True,
    check=False,
)
ast_math = json.loads(pandoc_math.stdout.decode("utf-8")) if pandoc_math.returncode == 0 else {}
nodes_math = list(walk_ast(ast_math))
counts_math = collections.Counter(node.get("t") for node in nodes_math)
math_counts_explicit = collections.Counter()
raw_tex_values = []
for node in nodes_math:
    if node.get("t") == "Math":
        math_counts_explicit[node["c"][0]["t"]] += 1
    if node.get("t") in {"RawInline", "RawBlock"} and node.get("c", [""])[0] == "tex":
        raw_tex_values.append(node["c"][1])
emit(
    f"explicit_math_reader_exit={pandoc_math.returncode}; "
    f"math_nodes={dict(math_counts_explicit)}; "
    f"RawInline={counts_math.get('RawInline', 0)}; RawBlock={counts_math.get('RawBlock', 0)}; "
    f"raw_tex_values={raw_tex_values}"
)

headers = []
for node in nodes:
    if node.get("t") == "Header":
        level, attrs, content = node["c"]
        headers.append((level, attrs[0], ast_text(content)))
dupe_ids = [key for key, n in collections.Counter(item[1] for item in headers).items() if n > 1]
emit(f"headers={len(headers)}; duplicate_header_ids={dupe_ids}")
bad_jumps = []
for before, after in zip(headers, headers[1:]):
    if after[0] > before[0] + 1:
        bad_jumps.append((before, after))
emit(f"heading_level_jumps={len(bad_jumps)}")

image_targets = []
for node in nodes:
    if node.get("t") == "Image":
        target = node["c"][2][0]
        image_targets.append(target)
        local = ROOT / urllib.parse.unquote(target)
        emit(f"markdown_image: target={target}; exists={local.exists()}")

citation_ids = set()
for node in nodes:
    if node.get("t") == "Cite":
        citation_ids.update(item["citationId"] for item in node["c"][0])
bib_text = (ROOT / "AGILE_Modelling_references.bib").read_text(encoding="utf-8")
bib_ids = set(re.findall(r"(?m)^\s*@[A-Za-z]+\s*\{\s*([^,\s]+)", bib_text))
emit(f"citation_ids={len(citation_ids)}; bib_ids={len(bib_ids)}; unresolved={sorted(citation_ids - bib_ids)}")

paren_tex = []
for line_no, line in enumerate(md_text.replace("\r", "\n").replace("\v", "\n").split("\n"), 1):
    if re.search(r"\([^)]*(?:_[A-Za-z{]|\{,\}|\\(?:alpha|beta|phi|rho|sigma|theta|varphi|kappa|tau|xi))", line):
        paren_tex.append((line_no, line.strip()))
emit(f"suspicious_parenthesized_tex_lines={len(paren_tex)}")
for item in paren_tex:
    emit(f"  line {item[0]}: {item[1]}")


section("DOCX_PACKAGE")
with zipfile.ZipFile(DOCX) as zf:
    names = set(zf.namelist())
    emit(f"zip_entries={len(names)}; testzip={zf.testzip()}")
    core = ET.fromstring(zf.read("docProps/core.xml"))
    app = ET.fromstring(zf.read("docProps/app.xml"))
    for path, key in (
        ("dc:title", "title"),
        ("dc:subject", "subject"),
        ("dc:creator", "creator"),
        ("cp:keywords", "keywords"),
        ("cp:lastModifiedBy", "lastModifiedBy"),
        ("dcterms:created", "created"),
        ("dcterms:modified", "modified"),
        ("cp:revision", "revision"),
    ):
        emit(f"core.{key}={xpath_text(core, path)!r}")
    for key in ("Application", "AppVersion", "Pages", "Words", "Characters", "Paragraphs", "Lines", "Company"):
        emit(f"app.{key}={xpath_text(app, 'ep:' + key)!r}")

    document = ET.fromstring(zf.read("word/document.xml"))
    rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    rel_map = {r.attrib["Id"]: r.attrib for r in rels}
    ext_rels = [r.attrib for r in rels if r.attrib.get("TargetMode") == "External"]
    emit(
        "document_counts: "
        f"tables={len(document.findall('.//w:tbl', NS))}; "
        f"drawings={len(document.findall('.//w:drawing', NS))}; "
        f"hyperlinks={len(document.findall('.//w:hyperlink', NS))}; "
        f"bookmarks={len(document.findall('.//w:bookmarkStart', NS))}; "
        f"oMath={len(document.findall('.//m:oMath', NS))}; "
        f"oMathPara={len(document.findall('.//m:oMathPara', NS))}; "
        f"sectPr={len(document.findall('.//w:sectPr', NS))}"
    )
    header_count = len([n for n in names if re.fullmatch(r"word/header\d+\.xml", n)])
    footer_count = len([n for n in names if re.fullmatch(r"word/footer\d+\.xml", n)])
    emit(f"headers={header_count}; footers={footer_count}")

    bookmarks = {node.attrib.get(f"{{{NS['w']}}}name", "") for node in document.findall(".//w:bookmarkStart", NS)}
    internal_links = [node.attrib.get(f"{{{NS['w']}}}anchor", "") for node in document.findall(".//w:hyperlink", NS) if node.attrib.get(f"{{{NS['w']}}}anchor")]
    emit(f"internal_link_anchors={len(internal_links)}; broken_internal_anchors={sorted(set(internal_links) - bookmarks)}")
    emit(f"external_relationships={len(ext_rels)}")
    for item in ext_rels:
        target = item.get("Target", "")
        emit(f"external_rel: id={item.get('Id')}; scheme={urllib.parse.urlsplit(target).scheme}; target={target}")

    field_codes = ["".join(node.itertext()).strip() for node in document.findall(".//w:instrText", NS)]
    emit(f"field_code_fragments={len(field_codes)}; field_types={dict(collections.Counter((x.split() or [''])[0].upper() for x in field_codes))}")

    font_table = ET.fromstring(zf.read("word/fontTable.xml"))
    font_names = sorted({node.attrib.get(f"{{{NS['w']}}}name", "") for node in font_table.findall(".//w:font", NS)})
    embedded_font_parts = sorted(n for n in names if n.startswith("word/fonts/"))
    emit(f"font_table={font_names}; embedded_font_parts={embedded_font_parts}")

    media_names = sorted(n for n in names if n.startswith("word/media/") and not n.endswith("/"))
    emit(f"media_parts={len(media_names)}")
    inline_records = []
    for idx, inline in enumerate(document.findall(".//wp:inline", NS), 1):
        blip = inline.find(".//a:blip", NS)
        extent = inline.find("./wp:extent", NS)
        doc_pr = inline.find("./wp:docPr", NS)
        rid = blip.attrib.get(f"{{{NS['r']}}}embed", "") if blip is not None else ""
        target = rel_map.get(rid, {}).get("Target", "")
        part = "word/" + target.lstrip("/")
        cx = int(extent.attrib.get("cx", 0)) if extent is not None else 0
        cy = int(extent.attrib.get("cy", 0)) if extent is not None else 0
        data = zf.read(part)
        im = Image.open(io.BytesIO(data))
        win = cx / 914400 if cx else 0
        hin = cy / 914400 if cy else 0
        dpi_x = im.width / win if win else 0
        dpi_y = im.height / hin if hin else 0
        descr = doc_pr.attrib.get("descr", "") if doc_pr is not None else ""
        record = (idx, Path(part).name, im.width, im.height, win, hin, dpi_x, dpi_y, descr)
        inline_records.append(record)
        emit(
            f"inline_image={idx}; part={Path(part).name}; pixels={im.width}x{im.height}; "
            f"display={win:.3f}x{hin:.3f}in; effective_dpi={dpi_x:.1f}x{dpi_y:.1f}; alt={descr!r}"
        )


section("PDF")
pdf = fitz.open(PDF)
emit(f"pages={pdf.page_count}; metadata={pdf.metadata}")
emit(f"toc_outline_entries={len(pdf.get_toc(simple=False))}; page_labels={pdf.get_page_labels()}")
catalog = pdf.pdf_catalog()
for key in ("MarkInfo", "Lang", "StructTreeRoot", "Outlines", "PageMode", "ViewerPreferences", "Metadata"):
    emit(f"catalog.{key}={pdf.xref_get_key(catalog, key)}")
emit(f"embedded_files={len(pdf.embfile_names())}; embedded_file_names={pdf.embfile_names()}")

link_kind_counts = collections.Counter()
bad_links = []
for pno, page in enumerate(pdf, 1):
    for link in page.get_links():
        link_kind_counts[link["kind"]] += 1
        if link["kind"] == fitz.LINK_GOTO and not (0 <= link.get("page", -1) < pdf.page_count):
            bad_links.append((pno, link))
        if link["kind"] == fitz.LINK_URI:
            uri = link.get("uri", "")
            if urllib.parse.urlsplit(uri).scheme not in {"http", "https", "mailto"}:
                bad_links.append((pno, link))
emit(f"link_kind_counts={dict(link_kind_counts)}; invalid_links={len(bad_links)}")

font_records = {}
for page in pdf:
    for record in page.get_fonts(full=True):
        xref, ext, font_type, basefont, name, encoding, referencer = record
        font_records[xref] = (ext, font_type, basefont, name, encoding)
emit(f"font_xrefs={len(font_records)}")
for xref, record in sorted(font_records.items()):
    extracted = pdf.extract_font(xref)
    data_len = len(extracted[3]) if extracted and extracted[3] else 0
    emit(f"font: xref={xref}; ext={record[0]}; type={record[1]}; base={record[2]}; encoding={record[4]}; embedded_bytes={data_len}")

pdf_image_seen = set()
for pno, page in enumerate(pdf, 1):
    for info in page.get_image_info(xrefs=True):
        xref = info.get("xref", 0)
        bbox = fitz.Rect(info["bbox"])
        width = info["width"]
        height = info["height"]
        dpi_x = width / (bbox.width / 72) if bbox.width else 0
        dpi_y = height / (bbox.height / 72) if bbox.height else 0
        key = (xref, pno, tuple(round(x, 2) for x in bbox))
        if key not in pdf_image_seen:
            pdf_image_seen.add(key)
            emit(f"pdf_image: page={pno}; xref={xref}; pixels={width}x{height}; bbox={bbox}; effective_dpi={dpi_x:.1f}x{dpi_y:.1f}")

clipped_spans = []
near_edge_spans = []
page_stats = []
printed_page_numbers = []
pdf_text_parts = []
for pno, page in enumerate(pdf, 1):
    data = page.get_text("dict", sort=True)
    spans = [span for block in data["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"] if span["text"].strip()]
    pdf_text = page.get_text("text", sort=True)
    pdf_text_parts.append(pdf_text)
    min_x = min((s["bbox"][0] for s in spans), default=0)
    max_x = max((s["bbox"][2] for s in spans), default=0)
    min_y = min((s["bbox"][1] for s in spans), default=0)
    max_y = max((s["bbox"][3] for s in spans), default=0)
    page_stats.append((pno, len(pdf_text.strip()), min_x, max_x, min_y, max_y))
    for span in spans:
        x0, y0, x1, y1 = span["bbox"]
        if x0 < -0.2 or y0 < -0.2 or x1 > page.rect.width + 0.2 or y1 > page.rect.height + 0.2:
            clipped_spans.append((pno, span["text"], span["bbox"]))
        if x0 < 35 or x1 > page.rect.width - 35 or y1 > page.rect.height - 25:
            near_edge_spans.append((pno, span["text"], span["bbox"]))
        if y0 > page.rect.height - 40 and span["text"].strip() == str(pno):
            printed_page_numbers.append(pno)
emit(f"clipped_spans={len(clipped_spans)}; near_edge_spans={len(near_edge_spans)}; printed_page_number_pages={printed_page_numbers}")
emit(f"blank_pages={[p[0] for p in page_stats if p[1] == 0]}")
for stat in page_stats:
    emit(f"page_extent: page={stat[0]}; chars={stat[1]}; x={stat[2]:.1f}..{stat[3]:.1f}; y={stat[4]:.1f}..{stat[5]:.1f}")

pdf_text_all = "\n".join(pdf_text_parts)
suspicious_pdf_lines = []
for pno, text in enumerate(pdf_text_parts, 1):
    for line in text.splitlines():
        if re.search(r"(?:_[{A-Za-z]|\{,\}|\b(?:sigma|phi|ho|arphi)\b)", line):
            suspicious_pdf_lines.append((pno, line))
emit(f"suspicious_pdf_math_lines={len(suspicious_pdf_lines)}")
for pno, line in suspicious_pdf_lines:
    emit(f"  page {pno}: {line}")


section("DOCX_PDF_CONSISTENCY")
docx_plain = subprocess.run(
    ["pandoc", str(DOCX), "--from=docx", "--to=plain", "--wrap=none"],
    cwd=ROOT,
    capture_output=True,
    check=True,
).stdout.decode("utf-8", errors="replace")
docx_words = norm_words(docx_plain)
pdf_words = norm_words(pdf_text_all)
common = sum((docx_words & pdf_words).values())
emit(f"word_pages_reported=48; pdf_pages={pdf.page_count}")
emit(f"docx_plain_tokens={sum(docx_words.values())}; pdf_tokens={sum(pdf_words.values())}; multiset_common={common}; coverage_docx={common/sum(docx_words.values()):.5f}; coverage_pdf={common/sum(pdf_words.values()):.5f}")

missing_headers = []
pdf_norm = re.sub(r"\s+", " ", pdf_text_all.replace("–", "-").replace("—", "-")).casefold()
for level, ident, text in headers:
    needle = re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).casefold()
    if needle and needle not in pdf_norm:
        missing_headers.append((level, ident, text))
emit(f"markdown_headers_not_found_in_pdf={missing_headers}")

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
print("\n".join(lines))
