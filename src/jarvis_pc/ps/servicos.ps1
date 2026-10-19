$lista = @(Get-CimInstance Win32_Service -Filter "StartMode='Auto' AND State<>'Running'" | ForEach-Object {
  [pscustomobject]@{ nome = $_.Name; exibicao = $_.DisplayName; estado = $_.State; codigo_saida = $_.ExitCode } })
[pscustomobject]@{ servicos = $lista }
