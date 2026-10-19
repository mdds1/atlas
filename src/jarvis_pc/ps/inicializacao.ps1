$lista = @(Get-CimInstance Win32_StartupCommand | ForEach-Object {
  [pscustomobject]@{ nome = $_.Name; comando = $_.Command; local = $_.Location } })
[pscustomobject]@{ itens = $lista }
