$ini = (Get-Date).AddHours(-24)
$ev = @(Get-WinEvent -FilterHashtable @{ LogName = 'System','Application'; Level = 1,2; StartTime = $ini } -MaxEvents 20 | ForEach-Object {
  $m = [string]$_.Message
  if ($m.Length -gt 200) { $m = $m.Substring(0,200) }
  [pscustomobject]@{ quando = $_.TimeCreated.ToString('s'); fonte = $_.ProviderName; id = $_.Id; mensagem = $m } })
[pscustomobject]@{ eventos = $ev }
