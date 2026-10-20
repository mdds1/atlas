# Instala a Jarvis do PC numa pasta propria, com ambiente Python isolado.
# Uso: powershell -File instalar.ps1 [-Pasta C:\Jarvis] [-Rodas <pasta com as 2 .whl>]
param(
  [string]$Pasta = "C:\Jarvis",
  [string]$Rodas = "C:\Users\Diniz\envio\jarvis-rodas",
  [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
)
$ErrorActionPreference = "Stop"

function Rodar($exe, $argumentos) {
  & $exe @argumentos
  if ($LASTEXITCODE -ne 0) { throw "falhou: $exe $($argumentos -join ' ') (codigo $LASTEXITCODE)" }
}

if (-not (Test-Path $Python)) { throw "Python 3.10 nao encontrado em $Python" }
$listaRodas = @(Get-ChildItem -Path $Rodas -Filter *.whl | ForEach-Object { $_.FullName })
if ($listaRodas.Count -ne 2) { throw "esperava 2 rodas (OpenJarvis e jarvis_pc) em $Rodas, achei $($listaRodas.Count)" }

New-Item -ItemType Directory -Force -Path $Pasta | Out-Null
$py = Join-Path $Pasta "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Rodar $Python @("-m", "venv", (Join-Path $Pasta "venv")) }
Rodar $py @("-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip")
Rodar $py (@("-m", "pip", "install", "--disable-pip-version-check") + $listaRodas)
Rodar $py (@("-m", "pip", "install", "--disable-pip-version-check", "--force-reinstall", "--no-deps") + $listaRodas)

$config = Join-Path $Pasta "config.json"
if (-not (Test-Path $config)) {
  Set-Content -Path $config -Value '{"modelo": "gemma4:12b-it-q4_K_M"}' -Encoding ASCII
}
$bat = Join-Path $Pasta "iniciar.bat"
# Sobe o servidor do Ollama, escondido e na sessao de quem clicou, se ele nao estiver respondendo.
$ollama = @'
powershell -NoProfile -WindowStyle Hidden -Command "try { Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags -TimeoutSec 2 | Out-Null } catch { Start-Process -WindowStyle Hidden -FilePath ($env:LOCALAPPDATA + '\Programs\Ollama\ollama.exe') -ArgumentList 'serve' }"
'@
$linhas = @('@echo off', $ollama, 'start "" "%~dp0venv\Scripts\pythonw.exe" -m jarvis_pc "%~dp0."')
Set-Content -Path $bat -Value $linhas -Encoding ASCII
Write-Output "Jarvis instalada em $Pasta. Para iniciar: $bat"
