$s = New-Object -ComObject Microsoft.Update.Session
$r = $s.CreateUpdateSearcher().Search("IsInstalled=0 and IsHidden=0")
$lista = @(for ($i = 0; $i -lt $r.Updates.Count; $i++) {
  $u = $r.Updates.Item($i)
  [pscustomobject]@{ titulo = $u.Title; critica = ($u.MsrcSeverity -eq 'Critical') } })
[pscustomobject]@{ pendentes = $lista }
