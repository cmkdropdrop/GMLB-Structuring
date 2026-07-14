$ErrorActionPreference = 'Stop'

$workspace = Split-Path -Parent $PSScriptRoot
$docx = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.docx'
$pdf = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.pdf'
if (-not (Test-Path -LiteralPath $docx)) {
    throw "Reviewed DOCX not found: $docx"
}
if (Test-Path -LiteralPath $pdf) {
    throw 'Refusing to overwrite an existing reviewed PDF.'
}

$word = $null
$document = $null
try {
    Write-Output 'STAGE=word_start'
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.Options.BackgroundSave = $false

    $document = $word.Documents.Open($docx, $false, $true, $false)
    Write-Output 'STAGE=document_opened'

    # Print-quality PDF with properties, heading bookmarks and structure tags.
    $document.ExportAsFixedFormat(
        $pdf, 17, $false, 0, 0, 1, 9999, 0,
        $true, $true, 1, $true, $true, $false
    )
    Write-Output 'STAGE=pdf_exported'
    Write-Output "PDF=$pdf"
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

