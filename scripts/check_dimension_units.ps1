param([Parameter(Mandatory=$true)][string]$Dwg,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$cad=$null;$db=$null
try {
  $cad=[Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application')
  $major=([string]$cad.Version).Split('.')[0]
  $db=$cad.GetInterfaceObject('ObjectDBX.AxDbDocument.'+$major)
  $db.Open((Resolve-Path -LiteralPath $Dwg).Path)
  $vars=@{}
  foreach($name in @('INSUNITS','MEASUREMENT','LUNITS','LUPREC','DIMLFAC','DIMSCALE')) { try {$vars[$name]=$db.GetVariable($name)} catch {$vars[$name]=$null} }
  $checks=New-Object System.Collections.Generic.List[object]
  foreach($e in $db.ModelSpace) {
    if($e.ObjectName -notmatch 'Dimension$' -or $e.ObjectName -match 'Angular') {continue}
    if($checks.Count -ge 12) {break}
    $want=($e.Layer -eq 'GR' -and [Math]::Abs([double]$e.Measurement-6.0) -lt 0.001) -or ($e.Layer -eq 'dinding baru' -and [Math]::Abs([double]$e.Measurement-2.0) -lt 0.001) -or ($e.Layer -eq 'TANGGA' -and [Math]::Abs([double]$e.Measurement-1.2) -lt 0.001)
    if(-not $want){continue}
    try {
      $p1=@($e.XLine1Point);$p2=@($e.XLine2Point)
      $dx=[double]$p2[0]-[double]$p1[0];$dy=[double]$p2[1]-[double]$p1[1];$dz=[double]$p2[2]-[double]$p1[2]
      $checks.Add(@{handle=$e.Handle;layer=$e.Layer;type=$e.ObjectName;measurement=[double]$e.Measurement;endpoint_distance=[Math]::Sqrt($dx*$dx+$dy*$dy+$dz*$dz);p1=@([double]$p1[0],[double]$p1[1],[double]$p1[2]);p2=@([double]$p2[0],[double]$p2[1],[double]$p2[2])})
    } catch {$checks.Add(@{handle=$e.Handle;layer=$e.Layer;measurement=[double]$e.Measurement;endpoint_error=$_.Exception.Message})}
  }
  $result=@{source_sha256=(Get-FileHash -LiteralPath $Dwg -Algorithm SHA256).Hash;autocad_version=[string]$cad.Version;variables=$vars;dimension_checks=$checks.ToArray()}
  $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding utf8
  Get-Content -LiteralPath $Output -Raw
} finally { if($null -ne $db){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($db)}; if($null -ne $cad){[void][Runtime.InteropServices.Marshal]::ReleaseComObject($cad)} }
