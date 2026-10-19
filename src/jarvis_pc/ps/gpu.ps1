$smi = & nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null
$gpu = $null
if ($smi) {
  $p = ([string]($smi | Select-Object -First 1)).Split(',') | ForEach-Object { $_.Trim() }
  $gpu = [pscustomobject]@{ nome = $p[0]; temperatura_c = [int]$p[1]; uso_percent = [int]$p[2]; vram_usada_mb = [int]$p[3]; vram_total_mb = [int]$p[4] }
}
$z = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature 2>$null | Select-Object -First 1
$cpu_c = $null
if ($z) { $cpu_c = [math]::Round(($z.CurrentTemperature/10) - 273.15,1) }
[pscustomobject]@{ gpu = $gpu; cpu_temperatura_c = $cpu_c }
