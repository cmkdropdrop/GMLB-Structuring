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

    Add-Line ''
    Add-Line '[BUILTIN_PROPERTIES]'
    foreach ($name in @('Title','Subject','Author','Keywords','Comments','Category','Company','Manager','Template','Last author','Creation date','Last save time','Revision number','Application name','Application version','Pages','Words','Characters','Security')) {
        try {
            $value = $doc.BuiltInDocumentProperties.Item($name).Value
            Add-Line "$name=$value"
        } catch {
            Add-Line "$name=<unavailable>"
        }
    }

    Add-Line ''
    Add-Line '[SECTIONS]'
    for ($i = 1; $i -le $doc.Sections.Count; $i++) {
        $s = $doc.Sections.Item($i)
        $ps = $s.PageSetup
        $usable = $ps.PageWidth - $ps.LeftMargin - $ps.RightMargin
        Add-Line ("Section {0}: startPage={1}; size={2:N1}x{3:N1}pt; margins L/R/T/B={4:N1}/{5:N1}/{6:N1}/{7:N1}pt; usableWidth={8:N1}pt; orientation={9}; headerDistance={10:N1}; footerDistance={11:N1}" -f $i,$s.Range.Information(3),$ps.PageWidth,$ps.PageHeight,$ps.LeftMargin,$ps.RightMargin,$ps.TopMargin,$ps.BottomMargin,$usable,$ps.Orientation,$ps.HeaderDistance,$ps.FooterDistance)
    }

    Add-Line ''
    Add-Line '[HEADINGS]'
    for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
        $p = $doc.Paragraphs.Item($i)
        $styleName = ''
        try { $styleName = $p.Range.Style.NameLocal } catch { $styleName = [string]$p.Range.Style }
        if ($styleName -match '^(Überschrift|Heading) [1-6]$' -or $styleName -eq 'Title' -or $styleName -eq 'Titel' -or $styleName -eq 'Subtitle' -or $styleName -eq 'Untertitel') {
            $txt = ($p.Range.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim()
            Add-Line ("p={0}; page={1}; style={2}; text={3}" -f $i,$p.Range.Information(3),$styleName,$txt)
        }
    }

    Add-Line ''
    Add-Line '[TOC]'
    for ($i = 1; $i -le $doc.TablesOfContents.Count; $i++) {
        $toc = $doc.TablesOfContents.Item($i)
        Add-Line ("TOC {0}: page={1}; useHeadingStyles={2}; upper={3}; lower={4}; hyperlinks={5}; text={6}" -f $i,$toc.Range.Information(3),$toc.UseHeadingStyles,$toc.UpperHeadingLevel,$toc.LowerHeadingLevel,$toc.UseHyperlinks,(($toc.Range.Text -replace '[\r\a]',' | ' -replace '[\t\v]',' ').Trim()))
    }

    Add-Line ''
    Add-Line '[FIELDS]'
    for ($i = 1; $i -le $doc.Fields.Count; $i++) {
        $f = $doc.Fields.Item($i)
        $code = ($f.Code.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim()
        $result = ($f.Result.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim()
        if ($result.Length -gt 180) { $result = $result.Substring(0,180) + '…' }
        Add-Line ("field={0}; page={1}; type={2}; locked={3}; code={4}; result={5}" -f $i,$f.Result.Information(3),$f.Type,$f.Locked,$code,$result)
    }

    Add-Line ''
    Add-Line '[HYPERLINKS]'
    for ($i = 1; $i -le $doc.Hyperlinks.Count; $i++) {
        $h = $doc.Hyperlinks.Item($i)
        $label = ($h.Range.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim()
        Add-Line ("link={0}; page={1}; label={2}; address={3}; subaddress={4}" -f $i,$h.Range.Information(3),$label,$h.Address,$h.SubAddress)
    }

    Add-Line ''
    Add-Line '[TABLES]'
    for ($i = 1; $i -le $doc.Tables.Count; $i++) {
        $t = $doc.Tables.Item($i)
        $page = $t.Range.Information(3)
        $endPage = $t.Range.Duplicate.Information(3)
        $width = 0.0
        foreach ($c in $t.Columns) { $width += $c.Width }
        $sec = $t.Range.Sections.Item(1)
        $usable = $sec.PageSetup.PageWidth - $sec.PageSetup.LeftMargin - $sec.PageSetup.RightMargin
        $first = ''
        try { $first = ($t.Cell(1,1).Range.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim() } catch {}
        Add-Line ("table={0}; page={1}; rows={2}; cols={3}; width={4:N1}pt; usable={5:N1}pt; ratio={6:N3}; autofit={7}; preferredType={8}; preferredWidth={9}; first={10}" -f $i,$page,$t.Rows.Count,$t.Columns.Count,$width,$usable,($width/$usable),$t.AllowAutoFit,$t.PreferredWidthType,$t.PreferredWidth,$first)
    }

    Add-Line ''
    Add-Line '[INLINE_SHAPES]'
    for ($i = 1; $i -le $doc.InlineShapes.Count; $i++) {
        $sh = $doc.InlineShapes.Item($i)
        $alt = ''
        try { $alt = $sh.AlternativeText } catch {}
        Add-Line ("inline={0}; page={1}; type={2}; size={3:N1}x{4:N1}pt; alt={5}" -f $i,$sh.Range.Information(3),$sh.Type,$sh.Width,$sh.Height,$alt)
    }

    Add-Line ''
    Add-Line '[FLOATING_SHAPES]'
    for ($i = 1; $i -le $doc.Shapes.Count; $i++) {
        $sh = $doc.Shapes.Item($i)
        Add-Line ("shape={0}; page={1}; type={2}; pos={3:N1},{4:N1}pt; size={5:N1}x{6:N1}pt; wrap={7}; alt={8}" -f $i,$sh.Anchor.Information(3),$sh.Type,$sh.Left,$sh.Top,$sh.Width,$sh.Height,$sh.WrapFormat.Type,$sh.AlternativeText)
    }

    Add-Line ''
    Add-Line '[OMATHS]'
    for ($i = 1; $i -le $doc.OMaths.Count; $i++) {
        $m = $doc.OMaths.Item($i)
        $txt = ($m.Range.Text -replace '[\r\a]','' -replace '[\t\v]',' ').Trim()
        Add-Line ("math={0}; page={1}; type={2}; text={3}" -f $i,$m.Range.Information(3),$m.Type,$txt)
    }

    $doc.ExportAsFixedFormat($render, 17, $false, 0, 0, 1, 9999, 0, $true, $true, 1, $true, $true, $false)
    $lines | Set-Content -LiteralPath $report -Encoding UTF8
    $lines
} finally {
    if ($doc) {
        $doc.Close(0)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
    }
    if ($word) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
