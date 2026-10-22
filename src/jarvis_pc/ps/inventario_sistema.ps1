$reg = @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')
$apps = @(Get-ItemProperty $reg -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
  [pscustomobject]@{ origem = 'registro'; nome = [string]$_.DisplayName; versao = [string]$_.DisplayVersion; editor = [string]$_.Publisher; local = [string]$_.InstallLocation } })
$apps += @(Get-AppxPackage -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ origem = 'loja'; nome = [string]$_.Name; versao = [string]$_.Version; editor = [string]$_.Publisher; local = [string]$_.InstallLocation } })
$servicos = @(Get-CimInstance Win32_Service | ForEach-Object {
  [pscustomobject]@{ nome = [string]$_.Name; exibicao = [string]$_.DisplayName; estado = [string]$_.State; inicio = [string]$_.StartMode } })
$tarefas = @(Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ caminho = [string]$_.TaskPath; nome = [string]$_.TaskName; estado = [string]$_.State } })
$inicializacao = @(Get-CimInstance Win32_StartupCommand | ForEach-Object {
  [pscustomobject]@{ nome = [string]$_.Name; comando = [string]$_.Command; local = [string]$_.Location } })
$pythons = @(Get-ItemProperty 'HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath', 'HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath' -ErrorAction SilentlyContinue |
  ForEach-Object { [string]$_.'(default)' } | Where-Object { $_ })
$npm = ''
if ($env:APPDATA) { $c = Join-Path $env:APPDATA 'npm\node_modules'; if (Test-Path $c) { $npm = $c } }
[pscustomobject]@{ apps = $apps; servicos = $servicos; tarefas = $tarefas; inicializacao = $inicializacao; pythons = $pythons; npm = $npm }
