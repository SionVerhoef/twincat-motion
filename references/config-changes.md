# Proposing axis configuration changes

This skill reads axis configuration directly (`scripts/axis_xti.py`). A change goes out in
one of three forms:

1. **A parameter-change table** that someone applies by hand in XAE. This is the default.
2. **An Automation Interface script** that someone runs on the engineering PC, for many axes
   or a repeatable change.
3. **A direct edit of the `.xti` file**, only after the user has explicitly agreed to it
   (section 3).

Default to 1 or 2. XAE owns the `.xti` file: it rewrites it on save, it keeps only non-default
values, and the running system takes nothing from it until someone activates the
configuration. A hand edit can be overwritten without warning, rejected when XAE loads the
project, or activated without anyone reviewing it. So **never edit an `.xti` without an
explicit go-ahead** for that file and those changes.

**Never activate a configuration, write parameters to a running NC over ADS, or move an
axis.** Propose; the person at the machine decides when, and stays in reach of the stop.

## 1. Parameter-change table

One row per parameter. Give the old value from the current file (`axis_xti.py show`; an
absent parameter is "default"), so the person can see they are editing the right axis. The
`.xti` path column is there to find and check the parameter with `axis_xti.py`, not to edit
the file.

| Axis | Page | Parameter (as XAE shows it) | `.xti` path (to check) | Old | New | Why |
|---|---|---|---|---|---|---|
| Axis_X | Encoder | Scaling Factor Numerator | `Encoder/EncPara@ScaleFactorNumerator` | 0.0001 | 10 | exact ratio: 10 mm lead |
| Axis_X | Encoder | Scaling Factor Denominator | `Encoder/EncPara@ScaleFactorDenominator` | default | 3145728 | 3:1 gearbox × 2^20 |
| Axis_X | Parameter | Maximum Position Lag Value | `Controller/CtrPara/PosDiffControl@Range` | 0.5 | 2.0 | measured peak lag 1.4 at full acceleration |

Then tell the person how to apply and check it:

1. Change the values in XAE and save.
2. Activate the configuration at a moment that suits the machine.
3. Test with reduced velocity and torque limits before anything runs at full speed.
4. Commit the changed `.xti` and run `axis_xti.py diff` against the previous version: only
   the rows in the table should show up.

Values in the example are illustrative. Real values come from the machine; say where each
new value came from (a calculation, a measurement, the drive's documentation).

## 2. Automation Interface script

The TwinCAT Automation Interface drives XAE from a script through COM, on Windows, with XAE
installed. For an NC axis the calls that matter are:

- `LookupTreeItem("TINC^NC-Task 1 SAF^Axes^<axis name>")` finds the axis. The path uses the
  names in the solution tree, joined with `^`.
- `ProduceXml()` returns the axis's settings as XML.
- `ConsumeXml(xml)` applies an XML fragment to the axis.

The XML from `ProduceXml` is the authority on element and attribute names; it is not
guaranteed to match the `.xti` layout. So a safe script works in two passes: **produce**
writes the current XML to a file for review; **apply** changes only named attributes, checks
each old value first, keeps a copy of the before and after XML, and calls `ConsumeXml` on the
project the person has open in XAE. It never saves and never activates: the person reviews
the change in XAE and does both.

```powershell
# axis-change.ps1  -  propose, review, then apply NC axis parameter changes in XAE.
# Open the project in XAE first; the script attaches to that instance and leaves it open.
# Pass 1:  .\axis-change.ps1 -Solution C:\proj\Machine.sln -Axis "Axis_X" -Produce
# Pass 2:  .\axis-change.ps1 -Solution C:\proj\Machine.sln -Axis "Axis_X" -Changes changes.csv
# changes.csv columns: XPath,Attribute,Old,New   (XPath into the produced XML)
# Windows PowerShell 5.1 (GetActiveObject is not available in PowerShell 7).
# Never saves and never activates: review in XAE, then save and activate yourself.
# Aborts unless the attached XAE has exactly this solution open. Close other XAE instances.
param(
    [Parameter(Mandatory)] [string] $Solution,
    [string] $Project,                         # TwinCAT project name, if the solution has several
    [Parameter(Mandatory)] [string] $Axis,
    [switch] $Produce,
    [string] $Changes,
    [string] $ProgId = "TcXaeShell.DTE.15.0"   # XAE Shell on 4024; other shells use another id
)
$ErrorActionPreference = "Stop"
$dte = [Runtime.InteropServices.Marshal]::GetActiveObject($ProgId)
$want = (Resolve-Path $Solution).Path
if ($dte.Solution.FullName -ne $want) {
    throw "XAE has '$($dte.Solution.FullName)' open, not '$want'. Nothing done."
}
$tc = @($dte.Solution.Projects | Where-Object {
    $_.FullName -like '*.tsproj' -and (-not $Project -or $_.Name -eq $Project) })
if ($tc.Count -ne 1) { throw "Found $($tc.Count) matching TwinCAT projects; name one with -Project. Nothing done." }
$sysMan = $tc[0].Object
$item = $sysMan.LookupTreeItem("TINC^NC-Task 1 SAF^Axes^$Axis")
[xml] $xml = $item.ProduceXml()
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$xml.Save("$PWD\$Axis-before-$stamp.xml")
if ($Produce) { Write-Host "Wrote $Axis-before-$stamp.xml. Review it, then write changes.csv."; return }

$rows = Import-Csv $Changes
foreach ($c in $rows) {                      # check everything before changing anything
    $node = $xml.SelectSingleNode($c.XPath)
    if ($null -eq $node) { throw "Not found: $($c.XPath). Nothing applied." }
    $current = $node.GetAttribute($c.Attribute)
    if ($current -ne $c.Old) { throw "$($c.XPath)@$($c.Attribute) is '$current', expected '$($c.Old)'. Nothing applied." }
}
foreach ($c in $rows) { $xml.SelectSingleNode($c.XPath).SetAttribute($c.Attribute, $c.New) }
$xml.Save("$PWD\$Axis-after-$stamp.xml")
$item.ConsumeXml($xml.OuterXml)
Write-Host "Applied to $Axis in XAE. Not saved, not activated: review it there."
```

When you hand this out:

- Say that it has **not been run against XAE** as part of this skill: run the produce pass
  first, and try the apply pass on a copy of the project.
- Fill `changes.csv` from the produced XML, never from the `.xti` layout or from memory.
- The script checks every old value before it changes anything, so a stale table fails
  instead of half-applying.
- After applying: review the axis in XAE, then the same steps as for a table (save,
  activate when it suits, test at reduced limits, commit, `axis_xti.py diff`).

## 3. Direct `.xti` edit, after acknowledgement

Only when the user asks for it or accepts it after you have named the risks above. The
go-ahead must cover this file and these changes; a general "go ahead" earlier in the
conversation is not enough. Then:

1. **Before**: the project is closed in XAE (XAE overwrites the file when it saves), and the
   `.xti` is committed to version control, so the edit can be reverted.
2. **Change only values of parameters already in the file.** A parameter at its default is
   absent; adding it means adding XML in the right place, which has not been verified. Use a
   table or the script for those.
3. **Touch nothing else**: not the `DataTypes` or `Vars` blocks, not links, ids or names.
4. **After**: `axis_xti.py diff` between the committed and the edited file must show exactly
   the intended changes. Show that diff to the user.
5. The person opens the project in XAE, checks the values on the axis's parameter pages,
   saves (XAE may reformat the file; diff again), and activates when it suits the machine,
   then tests at reduced limits.

Whether XAE loads a hand-edited value unchanged has not been tested as part of this skill.
Say so when you make the edit.

## Runtime parameter writes are not configuration

`MC_WriteParameter` (and ADS writes to NC parameters) change the running NC only. The project
is unchanged, so the value is gone after the next activation or restart. That is right for a
value the application sets on purpose at runtime, and wrong as a way to "fix" the
configuration. If the code must change parameters at runtime, write it as PLC code for review
(twincat-st), not as something the agent runs.
