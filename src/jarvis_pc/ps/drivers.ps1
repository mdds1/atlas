$prob = @(Get-CimInstance Win32_PnPEntity -Filter "ConfigManagerErrorCode<>0" | ForEach-Object {
  [pscustomobject]@{ nome = $_.Name; codigo_erro = $_.ConfigManagerErrorCode } })
$video = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  [pscustomobject]@{ nome = $_.Name; versao = $_.DriverVersion; data = if ($_.DriverDate) { $_.DriverDate.ToString('yyyy-MM-dd') } else { $null } } })
[pscustomobject]@{ com_problema = $prob; video = $video }
