$ErrorActionPreference = 'Stop'

$workspace = Split-Path -Parent $PSScriptRoot
$source = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.md'
$reference = Join-Path $workspace 'AGILE_Modelling_Fachpaper.docx'
$docx = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.docx'
$pdf = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.pdf'

if (-not (Test-Path -LiteralPath $source)) {
    throw "Reviewed Markdown source not found: $source"
}
if (-not (Test-Path -LiteralPath $reference)) {
    throw "Reference DOCX not found: $reference"
}
if ((Test-Path -LiteralPath $docx) -or (Test-Path -LiteralPath $pdf)) {
    throw 'Refusing to overwrite an existing reviewed DOCX or PDF.'
}

Push-Location $workspace
try {
    Write-Output 'STAGE=pandoc_start'
    & pandoc $source `
        --from='markdown+tex_math_single_backslash' `
        --to=docx `
        --standalone `
        --toc `
        --toc-depth=3 `
        --citeproc `
        --reference-doc=$reference `
        --resource-path=$workspace `
        --output=$docx
    if ($LASTEXITCODE -ne 0) {
        throw "Pandoc failed with exit code $LASTEXITCODE."
    }
    Write-Output 'STAGE=pandoc_done'
}
finally {
    Pop-Location
}

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    $document = $word.Documents.Open($docx, $false, $false)
    Write-Output 'STAGE=word_opened'

    # Explicit A4 geometry and printable margins in every section.
    foreach ($section in $document.Sections) {
        $section.PageSetup.PaperSize = 7       # wdPaperA4
        $section.PageSetup.TopMargin = 56.7   # 20 mm
        $section.PageSetup.BottomMargin = 56.7
        $section.PageSetup.LeftMargin = 56.7
        $section.PageSetup.RightMargin = 56.7
        $section.PageSetup.HeaderDistance = 28.35
        $section.PageSetup.FooterDistance = 28.35
        $section.PageSetup.DifferentFirstPageHeaderFooter = $false
        $section.PageSetup.OddAndEvenPagesHeaderFooter = $false

        $footer = $section.Footers.Item(1)    # wdHeaderFooterPrimary
        $footer.LinkToPrevious = $false
        $footer.Range.Text = 'Seite '

        $range = $footer.Range.Duplicate
        $range.SetRange($footer.Range.End - 1, $footer.Range.End - 1)
        [void]$footer.Range.Fields.Add($range, 33) # wdFieldPage

        $range = $footer.Range.Duplicate
        $range.SetRange($footer.Range.End - 1, $footer.Range.End - 1)
        $range.InsertAfter(' von ')

        $range = $footer.Range.Duplicate
        $range.SetRange($footer.Range.End - 1, $footer.Range.End - 1)
        [void]$footer.Range.Fields.Add($range, 26) # wdFieldNumPages
        $footer.Range.ParagraphFormat.Alignment = 1 # wdAlignParagraphCenter
    }

    Write-Output 'STAGE=page_geometry_done'

    # Separate title page, table of contents and body. Word Find avoids a slow
    # paragraph-by-paragraph COM round trip across the full document.
    foreach ($headingText in @('Inhaltsverzeichnis', 'Zusammenfassung')) {
        $findRange = $document.Content.Duplicate
        $find = $findRange.Find
        $find.ClearFormatting()
        $find.Text = $headingText
        $find.Forward = $true
        $find.Wrap = 0 # wdFindStop
        if ($find.Execute()) {
            $findRange.ParagraphFormat.PageBreakBefore = -1
        }
    }
    Write-Output 'STAGE=page_breaks_done'

    # Keep headings with their first following paragraph and avoid orphan lines.
    foreach ($styleName in @('Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4')) {
        try {
            $style = $document.Styles.Item($styleName)
            $style.ParagraphFormat.KeepWithNext = -1
            $style.ParagraphFormat.KeepTogether = -1
        }
        catch {
            # Style names can be localized; Pandoc's English style IDs are normally present.
        }
    }
    $document.Styles.Item('Normal').ParagraphFormat.WidowControl = -1

    # Searchable metadata used by the PDF exporter.
    # Numeric WdBuiltInProperty identifiers are independent of the Office UI language.
    $metadata = @(
        @(1, 'AGILE Modelling'),
        @(2, 'Unabhängig geprüfte Lernunterlage zur AGILE Modelling Research Engine 1.3.0'),
        @(3, 'Interne Fach- und Lernunterlage'),
        @(4, 'AGILE, actuarial modelling, longevity, GLWB, review, research prototype'),
        @(5, 'Reviewed 11 July 2026; not a pricing, reserving, capital or product approval.')
    )
    foreach ($entry in $metadata) {
        try {
            $document.BuiltInDocumentProperties.Item([int]$entry[0]).Value = [string]$entry[1]
        }
        catch {
            Write-Warning "Could not set built-in document property $($entry[0]): $($_.Exception.Message)"
        }
    }
    Write-Output 'STAGE=metadata_done'

    foreach ($toc in $document.TablesOfContents) {
        [void]$toc.Update()
    }
    Write-Output 'STAGE=toc_done'
    [void]$document.Fields.Update()
    Write-Output 'STAGE=fields_done'
    [void]$document.Repaginate()
    Write-Output 'STAGE=repaginate_done'
    $document.Save()
    Write-Output 'STAGE=docx_saved'

    # PDF: print quality, document properties, heading bookmarks and structure tags.
    $document.ExportAsFixedFormat(
        $pdf, 17, $false, 0, 0, 1, 9999, 0,
        $true, $true, 1, $true, $true, $false
    )
    Write-Output 'STAGE=pdf_exported'

    $pages = $document.ComputeStatistics(2) # wdStatisticPages
    Write-Output "DOCX=$docx"
    Write-Output "PDF=$pdf"
    Write-Output "WORD_PAGES=$pages"
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch {}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
