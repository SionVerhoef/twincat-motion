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

When the change already exists in another version of the axis (a test copy, another machine),
`axis_xti.py diff old.xti new.xti --table` prints this table with Axis, the `.xti` path, Old
and New filled in from the files. Add the XAE page and name and the *Why*; a parameter going
back to its default shows "default (value not known to this tool)", so look the value up in
XAE.

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
- `ConsumeXml(xml)` applies XML to the axis.

The XML from `ProduceXml` is the authority on names, and it does **not** match the `.xti`
layout. Observed on TwinCAT 4024.55 with a simulated axis:

- The root is `<TreeItem>`, and the axis data sits under `<NcAxisDef>`.
- **Every value is element text**; the XML has no attributes at all. Where the `.xti` has
  `<Velo FastManual="600"/>`, the produced XML has `<Velo><FastManual>600</FastManual></Velo>`.
- The parameter groups are named differently: `AxisParam`, `CtrParam`, `EncParam`,
  `DrvParam` (the `.xti` has `AxisPara`, `CtrPara`, `EncPara`, `DrvPara`).
- It lists every parameter with its current value, defaults included, and none of the
  `.xti`'s `ParameterChanged` bookkeeping.

Paths seen in that XML, for orientation (check them against your own produced XML):

| Setting | Produced-XML path |
|---|---|
| Manual velocity, fast | `/TreeItem/NcAxisDef/AxisParam/Velo/FastManual` |
| Motion commands to slave axis | `/TreeItem/NcAxisDef/AxisParam/OtherSettings/AllowMotionCmdToSlave` |
| Motion commands to external set-point axis | `/TreeItem/NcAxisDef/AxisParam/OtherSettings/AllowMotionCmdToExtSetGenAxis` |
| Position lag monitoring | `/TreeItem/NcAxisDef/Controller/CtrParam/PosDiffControl/Enable` |
| Encoder time compensation | `/TreeItem/NcAxisDef/Encoder/EncParam/TimeComp/` `TimeCompMode`, `IoTimeAbsolute`, `EncDelayCycles`, `AdditionalTimeShift` |
| Drive time compensation | `/TreeItem/NcAxisDef/Drive/DrvParam/TimeComp/` `TimeCompMode`, `IoTimeAbsolute`, `DriveDelayCycles`, `TaskDelayCycles`, `AdditionalTimeShift` |
| Axis dead time | `/TreeItem/NcAxisDef/AxisParam/Dynamic/DelayTime` |

So a safe script works in two passes: **produce** writes the current XML to a file for
review; **apply** changes only the named value elements, checks each old value first, keeps a
copy of the before and after XML, and calls `ConsumeXml` on the project the person has open
in XAE. It never saves and never activates: the person reviews the change in XAE and does
both.

```powershell
# axis-change.ps1  -  propose, review, then apply NC axis parameter changes in XAE.
# Open the project in XAE first; the script attaches to that instance and leaves it open.
# Pass 1:  .\axis-change.ps1 -Solution C:\proj\Machine.sln -Axis "Axis_X" -Produce
# Pass 2:  .\axis-change.ps1 -Solution C:\proj\Machine.sln -Axis "Axis_X" -Changes changes.csv
# changes.csv columns: XPath,Old,New   (XPath to the value element in the produced XML,
#   e.g. /TreeItem/NcAxisDef/AxisParam/Velo/FastManual,600,601)
# Windows PowerShell 5.1 (GetActiveObject is not available in PowerShell 7).
# Every run saves <Axis>-before-<stamp>.xml (on apply: the state it started from).
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
    $nodes = $xml.SelectNodes($c.XPath)
    if ($nodes.Count -ne 1) { throw "$($c.XPath) matches $($nodes.Count) elements, not 1. Nothing applied." }
    $node = $nodes[0]
    if ($node.SelectNodes("*").Count -ne 0) { throw "$($c.XPath) is a group, not a value. Nothing applied." }
    if ($node.InnerText -ne $c.Old) { throw "$($c.XPath) is '$($node.InnerText)', expected '$($c.Old)'. Nothing applied." }
}
foreach ($c in $rows) { $xml.SelectSingleNode($c.XPath).InnerText = $c.New }
$xml.Save("$PWD\$Axis-after-$stamp.xml")
$item.ConsumeXml($xml.OuterXml)
Write-Host "Applied to $Axis in XAE. Not saved, not activated: review it there."
```

What has been run, on TwinCAT 4024.55 with a simulated axis: the produce pass of this script
(attach, solution check, tree path, `ProduceXml`); and, from a separate test script, the
apply method it uses: set the element text of one value in the full produced XML,
`ConsumeXml` that XML, and the new value appears offline in XAE, with the axis marked
modified and nothing saved. This version of the apply pass has not been run as a whole.
`ConsumeXml` with a partial XML fragment has not been tried; the script always passes the
full XML.

When you hand this out:

- Say what has and has not been run (above): run the produce pass first, and try the apply
  pass on a copy of the project.
- Fill `changes.csv` from the produced XML, never from the `.xti` layout or from memory. Each
  `XPath` names one value element, not its group.
- To carry a change from one version of an axis to another, let the tool fill it: run the
  produce pass on the target axis, then
  `axis_xti.py diff old.xti new.xti --ai-csv <Axis>-before-<stamp>.xml changes.csv`. It
  looks each changed parameter up in the produced XML and takes **Old** from there (the
  target's current value, defaults included). If any change cannot be found there, or goes
  back to a default it cannot name, it writes nothing. A `NOTE` says where the target's
  value differs from the old file. The `.xti`-to-produced-XML name mapping is checked against
  the produced XML on every run, but has been tested only on XML shaped like the table above,
  not on one captured from XAE.
- The script checks every old value before it changes anything, so a stale table fails
  instead of half-applying.
- After applying: review the axis in XAE, then the same steps as for a table (save,
  activate when it suits, test at reduced limits, commit, `axis_xti.py diff`). After a
  `ConsumeXml` and save, XAE dropped all `ParameterChanged` entries from the `.xti`; expect
  them in the diff.

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
   saves (diff again), and activates when it suits the machine, then tests at reduced limits.

Observed on TwinCAT 4024.55 (one changed value, simulated axis): XAE loaded the hand-edited
value unchanged, without a warning, and a *Save All* with no change left the file alone.
When XAE did rewrite the file later, it kept the layout and the CRLF line endings, but it
added or removed bookkeeping: `ParameterChanged` elements, and once a
`Drive/DrvPara/TimeComp@TaskDelayCycles="1"` nobody had set (see
[axis-parameters.md](axis-parameters.md)). Expect those in the second diff. Other values and
other XAE builds are untested; say so when you make the edit.

## Online parameter download

On an NC axis's *Parameter* tab, **Download** writes the offline values to the running NC
without an activation. XAE then asks in a *Persistent Changes* dialog how long they should
last. Observed on 4024.55:

- **OK**: the change holds until the next TwinCAT restart.
- **Save now**: the change is also stored in that runtime's boot configuration (the dialog
  says it is saved in the registry; it takes a few seconds), so it survives a restart.

Either way the project is not changed by the download: save it too, or the next activation
from the project, or from another copy of it, overwrites the value. Not every parameter can
be downloaded: *Data Persistence* (*Other Settings*) keeps the Download button greyed and
takes effect only with an activation. Like an activation, a download changes a running
machine: propose it, and let the person at the machine do it.

## Runtime parameter writes are not configuration

`MC_WriteParameter` (and ADS writes to NC parameters) change the running NC only. The project
is unchanged, so the value is gone after the next activation or restart. That is right for a
value the application sets on purpose at runtime, and wrong as a way to "fix" the
configuration. If the code must change parameters at runtime, write it as PLC code for review
(twincat-st), not as something the agent runs.
