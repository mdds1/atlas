$os = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average
$discos = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
  [pscustomobject]@{ unidade = $_.DeviceID; total_gb = [math]::Round($_.Size/1GB,1); livre_gb = [math]::Round($_.FreeSpace/1GB,1) } })
[pscustomobject]@{
  cpu_percent = [math]::Round([double]$cpu,1)
  ram_total_gb = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
  ram_livre_gb = [math]::Round($os.FreePhysicalMemory/1MB,1)
  ligado_desde = $os.LastBootUpTime.ToString('s')
  discos = $discos
}
