$lista = @(Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 | ForEach-Object {
  [pscustomobject]@{ nome = $_.ProcessName; pid = $_.Id; ram_mb = [math]::Round($_.WorkingSet64/1MB); cpu_s = [math]::Round([double]$_.CPU,1) } })
[pscustomobject]@{ processos = $lista }
