$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'AGILE_Modelling_Fachpaper_reviewed.docx'
$target = Join-Path $PSScriptRoot 'reviewed_docx_render_final.pdf'
$stats = Join-Path $PSScriptRoot 'reviewed_docx_word_stats.txt'
if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite $target" }
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.Options.BackgroundSave = $false
    $doc = $word.Documents.Open($source, $false, $true, $false)
    $values = @(
        "WordVersion=$($word.Version)",
        "Pages=$($doc.ComputeStatistics(2))",
        "Words=$($doc.ComputeStatistics(0))",
        "Characters=$($doc.ComputeStatistics(3))",
        "Paragraphs=$($doc.Paragraphs.Count)",
        "Sections=$($doc.Sections.Count)",
        "Tables=$($doc.Tables.Count)",
        "InlineShapes=$($doc.InlineShapes.Count)",
        "FloatingShapes=$($doc.Shapes.Count)",
        "Hyperlinks=$($doc.Hyperlinks.Count)",
        "Fields=$($doc.Fields.Count)",
        "TOCs=$($doc.TablesOfContents.Count)",
        "OMaths=$($doc.OMaths.Count)",
        "Comments=$($doc.Comments.Count)",
        "Revisions=$($doc.Revisions.Count)",
        "TrackRevisions=$($doc.TrackRevisions)"
    )
    foreach ($section in $doc.Sections) {
        $ps = $section.PageSetup
        $values += "PageSetup=$($ps.PageWidth)x$($ps.PageHeight)pt;Margins=$($ps.LeftMargin),$($ps.RightMargin),$($ps.TopMargin),$($ps.BottomMargin);HeaderFooter=$($ps.HeaderDistance),$($ps.FooterDistance);PaperSize=$($ps.PaperSize)"
    }
    $values | Set-Content -LiteralPath $stats -Encoding UTF8
    $values
    $doc.ExportAsFixedFormat(
        $target, 17, $false, 0, 0, 1, 9999, 0,
        $true, $true, 1, $true, $true, $false
    )
    "Rendered=$target"
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close($false) } catch {}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
