$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$workspace = Split-Path -Parent $PSScriptRoot
$docx = Join-Path $workspace 'AGILE_Modelling_Fachpaper_reviewed.docx'
if (-not (Test-Path -LiteralPath $docx)) {
    throw "Reviewed DOCX not found: $docx"
}

function Read-ZipXml {
    param([System.IO.Compression.ZipArchiveEntry]$Entry)
    $stream = $Entry.Open()
    try {
        $reader = New-Object IO.StreamReader($stream, [Text.UTF8Encoding]::new($false), $true)
        try { return [xml]$reader.ReadToEnd() }
        finally { $reader.Dispose() }
    }
    finally { $stream.Dispose() }
}

function Write-ZipXml {
    param(
        [System.IO.Compression.ZipArchiveEntry]$Entry,
        [xml]$Xml
    )
    $stream = $Entry.Open()
    try {
        $stream.SetLength(0)
        $settings = New-Object Xml.XmlWriterSettings
        $settings.Encoding = [Text.UTF8Encoding]::new($false)
        $settings.Indent = $false
        $settings.OmitXmlDeclaration = $false
        $writer = [Xml.XmlWriter]::Create($stream, $settings)
        try { $Xml.Save($writer) }
        finally { $writer.Dispose() }
    }
    finally { $stream.Dispose() }
}

$zip = [IO.Compression.ZipFile]::Open($docx, [IO.Compression.ZipArchiveMode]::Update)
try {
    $documentEntry = $zip.GetEntry('word/document.xml')
    $documentXml = Read-ZipXml $documentEntry
    $wordNs = New-Object Xml.XmlNamespaceManager($documentXml.NameTable)
    $wordNs.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')

    $summary = $documentXml.SelectSingleNode(
        "//w:p[w:pPr/w:pStyle[@w:val='Heading1'] and .//w:t[normalize-space(.)='Zusammenfassung']]",
        $wordNs
    )
    if ($null -eq $summary) {
        throw 'Could not locate the body heading Zusammenfassung.'
    }
    $paragraphProperties = $summary.SelectSingleNode('w:pPr', $wordNs)
    if ($null -eq $paragraphProperties.SelectSingleNode('w:pageBreakBefore', $wordNs)) {
        $pageBreak = $documentXml.CreateElement(
            'w', 'pageBreakBefore',
            'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        )
        [void]$paragraphProperties.AppendChild($pageBreak)
    }
    Write-ZipXml $documentEntry $documentXml

    $coreEntry = $zip.GetEntry('docProps/core.xml')
    $coreXml = Read-ZipXml $coreEntry
    $coreNs = New-Object Xml.XmlNamespaceManager($coreXml.NameTable)
    $coreNs.AddNamespace('cp', 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties')
    $coreNs.AddNamespace('dc', 'http://purl.org/dc/elements/1.1/')

    $values = @(
        @('dc', 'title', 'http://purl.org/dc/elements/1.1/', 'AGILE Modelling'),
        @('dc', 'creator', 'http://purl.org/dc/elements/1.1/', 'Interne Fach- und Lernunterlage'),
        @('dc', 'subject', 'http://purl.org/dc/elements/1.1/', 'Unabhängig geprüfte Lernunterlage zur AGILE Modelling Research Engine 1.3.0'),
        @('dc', 'description', 'http://purl.org/dc/elements/1.1/', 'Reviewed research prototype; keine Pricing-, Reservierungs-, Kapital- oder Produktfreigabe.'),
        @('cp', 'keywords', 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties', 'AGILE, actuarial modelling, longevity, GLWB, review, research prototype'),
        @('cp', 'lastModifiedBy', 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties', 'Independent review workflow')
    )
    foreach ($item in $values) {
        $node = $coreXml.SelectSingleNode("//$($item[0]):$($item[1])", $coreNs)
        if ($null -eq $node) {
            $node = $coreXml.CreateElement($item[0], $item[1], $item[2])
            [void]$coreXml.DocumentElement.AppendChild($node)
        }
        $node.InnerText = $item[3]
    }
    Write-ZipXml $coreEntry $coreXml
}
finally {
    $zip.Dispose()
}

Write-Output "FINALIZED_DOCX=$docx"

