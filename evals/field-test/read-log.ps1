# Read-only: reads PRG_FieldTestSeq.fbLog from the first PLC runtime on the local router
# (port 851) and prints it, optionally to a file. It never writes a variable.
#
# Needs Windows PowerShell 5.1 (powershell.exe): under PowerShell 7 the .NET Framework
# TwinCAT.Ads.dll does not load. The DLL path is the TwinCAT 3 default install location.
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File read-log.ps1 -Out log.txt
#
# -From skips the lines already read. Run it again until the last line reads IDLE or TIMEOUT.
param([int]$From = 1, [string]$Out)
Add-Type -Path 'C:\TwinCAT\AdsApi\.NET\v4.0.30319\TwinCAT.Ads.dll'
$c = New-Object TwinCAT.Ads.TcAdsClient
$c.Connect(851)
try {
  function ReadStr($name, $len) {
    $h = $c.CreateVariableHandle($name)
    try { $c.ReadAny($h, [string], [int[]]@($len)) } finally { $c.DeleteVariableHandle($h) }
  }
  function ReadVal($name, $type) {
    $h = $c.CreateVariableHandle($name)
    try { $c.ReadAny($h, $type) } finally { $c.DeleteVariableHandle($h) }
  }
  $n = ReadVal 'PRG_FieldTestSeq.fbLog.nLines' ([int16])
  $run = ReadStr 'PRG_FieldTestSeq.sRun' 4
  $lines = @("# nLines=$n sRun='$run'")
  for ($i = $From; $i -le $n; $i++) { $lines += ReadStr "PRG_FieldTestSeq.fbLog.aLog[$i]" 160 }
  if ($Out) { $lines | Set-Content -Encoding UTF8 $Out }
  $lines
} finally { $c.Dispose() }
