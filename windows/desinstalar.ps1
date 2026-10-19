# Remove a Jarvis do PC. So apaga uma pasta que tenha o iniciar.bat dela.
# Uso: powershell -File desinstalar.ps1 [-Pasta C:\Jarvis] [-RemoverOllama]
param(
  [string]$Pasta = "C:\Jarvis",
  [switch]$RemoverOllama
)
$ErrorActionPreference = "Stop"

$achada = Resolve-Path -LiteralPath $Pasta -ErrorAction SilentlyContinue
if (-not $achada) {
  Write-Output "Nada a remover: $Pasta nao existe"
} else {
  $raiz = $achada.Path
  if (-not (Test-Path (Join-Path $raiz "iniciar.bat"))) {
    throw "$raiz nao parece uma instalacao da Jarvis (falta iniciar.bat); nada foi apagado"
  }
  Get-CimInstance Win32_Process |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($raiz, [StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Remove-Item -LiteralPath $raiz -Recurse -Force
  Write-Output "Removida a pasta $raiz"
}
if ($RemoverOllama) {
  winget uninstall --id Ollama.Ollama -e --silent
  Write-Output "Ollama removido. Os modelos baixados continuam em $env:USERPROFILE\.ollama"
}
