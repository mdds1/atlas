# Mede se o leitor de texto embutido do Windows (OCR) funciona neste PC.
# Desenha uma frase numa imagem EM MEMORIA (nenhum arquivo e gravado) e pede ao OCR para le-la.
# Uso: powershell -File ocr-teste.ps1
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$tipos = @(
  '[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]',
  '[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]',
  '[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]',
  '[Windows.Media.Ocr.OcrEngine,Windows.Media.Ocr,ContentType=WindowsRuntime]',
  '[Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]'
)
foreach ($t in $tipos) { $null = Invoke-Expression $t }

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1

function Esperar($operacao, $tipoResultado) {
  $tarefa = $asTask.MakeGenericMethod($tipoResultado).Invoke($null, @($operacao))
  $null = $tarefa.Wait(-1)
  $tarefa.Result
}

$frase = "Erro 0x80070005: acesso negado ao arquivo do jogo"
$img = New-Object System.Drawing.Bitmap 900, 90
$g = [System.Drawing.Graphics]::FromImage($img)
$g.Clear([System.Drawing.Color]::White)
$g.DrawString($frase, (New-Object System.Drawing.Font 'Segoe UI', 22), [System.Drawing.Brushes]::Black, 10, 20)
$g.Dispose()
$ms = New-Object System.IO.MemoryStream
$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
$ms.Position = 0

$fluxo = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($ms)
$decoder = Esperar ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($fluxo)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Esperar ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$motor = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'pt-BR'))
if (-not $motor) { throw "OCR em pt-BR indisponivel" }
$resultado = Esperar ($motor.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

[pscustomobject]@{ esperado = $frase; lido = $resultado.Text; igual = ($resultado.Text.Trim() -eq $frase) } | ConvertTo-Json -Compress
