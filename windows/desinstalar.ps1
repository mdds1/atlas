# Remove a Jarvis do PC. So apaga uma pasta que seja mesmo uma instalacao da Jarvis.
# Uso: powershell -File desinstalar.ps1 [-Pasta C:\Jarvis] [-RemoverOllama]
param(
  [string]$Pasta = "C:\Jarvis",
  [switch]$RemoverOllama
)
$ErrorActionPreference = "Stop"

function Recusar($motivo) { throw "$motivo; nada foi apagado" }

$achada = Resolve-Path -LiteralPath $Pasta -ErrorAction SilentlyContinue
if (-not $achada) {
  Write-Output "Nada a remover: $Pasta nao existe"
} else {
  $raiz = $achada.Path.TrimEnd('\')
  if ([IO.Path]::GetPathRoot($raiz + '\').TrimEnd('\') -eq $raiz) { Recusar "$raiz e a raiz de um disco" }
  foreach ($protegida in @($env:USERPROFILE, $env:SystemRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)) {
    if ($protegida -and ($raiz -ieq $protegida.TrimEnd('\'))) { Recusar "$raiz e uma pasta protegida" }
  }
  $item = Get-Item -LiteralPath $raiz -Force
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Recusar "$raiz e um link (junction ou symlink)" }
  $bat = Join-Path $raiz "iniciar.bat"
  if (-not (Test-Path -LiteralPath $bat)) { Recusar "$raiz nao parece uma instalacao da Jarvis (falta iniciar.bat)" }
  if (-not (Select-String -LiteralPath $bat -Pattern "jarvis_pc" -SimpleMatch -Quiet)) {
    Recusar "$raiz nao parece uma instalacao da Jarvis (o iniciar.bat nao chama jarvis_pc)"
  }
  $prefixo = $raiz + '\'
  Get-CimInstance Win32_Process |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($prefixo, [StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Remove-Item -LiteralPath $raiz -Recurse -Force
  Write-Output "Removida a pasta $raiz"
}
if ($RemoverOllama) {
  winget uninstall --id Ollama.Ollama -e --silent
  Write-Output "Ollama removido. Os modelos baixados continuam em $env:USERPROFILE\.ollama"
}
