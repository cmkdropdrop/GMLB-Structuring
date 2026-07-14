$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'AGILE_Modelling_Fachpaper.docx'
$render = Join-Path $PSScriptRoot 'docx_render_check.pdf'
$report = Join-Path $PSScriptRoot 'word_inspection.txt'
$word = $null
$doc = $null
$lines = [System.Collections.Generic.List[string]]::new()
function Add-Line([string]$value) { $script:lines.Add($value) }
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($source, $false, $true)
    $doc.Repaginate()
    Add-Line "WordVersion=$($word.Version)"
    Add-Line "Pages=$($doc.ComputeStatistics(2))"
    Add-Line "Words=$($doc.ComputeStatistics(0))"
    Add-Line "Characters=$($doc.ComputeStatistics(3))"
    Add-Line "Paragraphs=$($doc.Paragraphs.Count)"
    Add-Line "Sections=$($doc.Sections.Count)"
    Add-Line "Tables=$($doc.Tables.Count)"
    Add-Line "InlineShapes=$($doc.InlineShapes.Count)"
    Add-Line "FloatingShapes=$($doc.Shapes.Count)"
    Add-Line "Hyperlinks=$($doc.Hyperlinks.Count)"
    Add-Line "Fields=$($doc.Fields.Count)"
    Add-Line "TOCs=$($doc.TablesOfContents.Count)"
    Add-Line "OMaths=$($doc.OMaths.Count)"
    Add-Line "Comments=$($doc.Comments.Count)"
    Add-Line "Revisions=$($doc.Revisions.Count)"
    Add-Line "TrackRevisions=$($doc.TrackRevisions)"
    foreach ($name in @('Title','Subject','Author','Keywords','Comments','Category','Company','Manager','Template','Last author','Creation date','Last save time','Revision number','Application name','Application version','Pages','Words','Characters','Security')) {
        try { Add-Line "Property[$name]=$($doc.BuiltInDocumentProperties.Item($name).Value)" }
        catch { Add-Line "Property[$name]=<unavailable>" }
    }
    for ($i = 1; $i -le $doc.Sections.Count; $i++) {
        $s = $doc.Sections.Item($i)
        $ps = $s.PageSetup
        $usable = $ps.PageWidth - $ps.LeftMargin - $ps.RightMargin
        Add-Line ("Section[{0}]=size {1:N1}x{2:N1}pt; margins L/R/T/B {3:N1}/{4:N1}/{5:N1}/{6:N1}pt; usable {7:N1}pt; orientation {8}; header/footer {9:N1}/{10:N1}pt" -f $i,$ps.PageWidth,$ps.PageHeight,$ps.LeftMargin,$ps.RightMargin,$ps.TopMargin,$ps.BottomMargin,$usable,$ps.Orientation,$ps.HeaderDistance,$ps.FooterDistance)
    }
    for ($i = 1; $i -le $doc.TablesOfContents.Count; $i++) {
        $toc = $doc.TablesOfContents.Item($i)
        Add-Line ("TOC[{0}]=page {1}; headings {2}-{3}; hyperlinks {4}; text {5}" -f $i,$toc.Range.Information(3),$toc.UpperHeadingLevel,$toc.LowerHeadingLevel,$toc.UseHyperlinks,(($toc.Range.Text -replace '[\r\a]',' | ' -replace '[\t\v]',' ').Trim()))
    }
    $lines | Set-Content -LiteralPath $report -Encoding UTF8
    $doc.ExportAsFixedFormat($render, 17)
    $lines
} finally {
    if ($doc) { $doc.Close(0); [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null }
    if ($word) { $word.Quit(); [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
