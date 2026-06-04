# update_d3_fields.ps1
# Proposito: abrir la memoria D3 en Word y actualizar los campos calculados
#   (tres indices, numeracion SEQ de figuras/tablas y paginacion Pagina X de Y)
#   para que el .docx quede completo sin intervencion manual (F9).
# Entrada/Salida: output/D3_Memoria_TFG_NESP.docx (se sobrescribe in situ).
$ErrorActionPreference = 'Stop'
$docx = Join-Path (Resolve-Path "$PSScriptRoot\..\..").Path 'output\D3_Memoria_TFG_NESP.docx'
if (-not (Test-Path $docx)) { throw "No existe $docx" }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0  # wdAlertsNone
try {
    $doc = $word.Documents.Open($docx, $false, $false)

    # 1) Actualizar todos los campos en todas las historias (cuerpo, cabeceras, pies).
    foreach ($story in $doc.StoryRanges) {
        $s = $story
        while ($null -ne $s) {
            try { $null = $s.Fields.Update() } catch {}
            $s = $s.NextStoryRange
        }
    }

    # 2) Actualizar indices de contenido, de figuras y de tablas.
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    foreach ($tof in $doc.TablesOfFigures) { $tof.Update() }

    # 3) Repaginar y una segunda pasada de campos para que la paginacion
    #    de los indices quede consistente.
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    foreach ($tof in $doc.TablesOfFigures) { $tof.Update() }
    foreach ($story in $doc.StoryRanges) {
        $s = $story
        while ($null -ne $s) {
            try { $null = $s.Fields.Update() } catch {}
            $s = $s.NextStoryRange
        }
    }

    $doc.Save()
    $pages = $doc.ComputeStatistics(2)  # wdStatisticPages
    Write-Output "OK paginas=$pages"
    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
