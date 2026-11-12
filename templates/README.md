# Templates

TwinCAT 3 (4024) PLC objects for one NC axis on `Tc2_MC2`: a wrapper, and the two homing
options most shops start from. UTF-8 with BOM, CRLF, valid GUIDs.

**Compiled and run on simulated axes, not on a real one.** These templates pass twincat-st's
`tcpou.py check` and `st_review.py --pedantic` (twincat-st v0.6.0, no findings), and every
`Tc2_MC2` identifier was checked against the library documentation. In a field test on
TwinCAT 4024.55 with `Tc2_MC2` 3.3.59 they built with 0 errors and 0 warnings (called from a
program, so code was generated for them), and on a simulated drive and encoder:

- `FB_Axis`: power, reset, moves, retargeting a running move (no `bCommandAborted`), halt,
  a velocity change, and an override change (`bBusy` and `bDone` FALSE, `bCommandAborted`
  TRUE while the axis runs on, as the header says) all behaved as documented.
- `FB_HomePlc`: off the switch, on the switch, with and without the NC homed mark, and the
  search timeout (`nErrorID` 16#0001_0103, axis halted) all behaved as documented.
- `FB_HomeNc`: default homing completed with and without the faked cam. Its timeout path was
  **not** reached, because a simulated encoder always finds the sync pulse.

They have not moved a real axis. Run them on yours at reduced velocity, acceleration and
torque first. Nothing here is a safety function.

| File | What it is |
|---|---|
| `FB_Axis.TcPOU` | Axis wrapper: `MC_Power`, `MC_Reset`, `MC_MoveAbsolute`, `MC_MoveRelative`, `MC_MoveVelocity`, `MC_Halt` behind methods (`MoveAbsolute`, `MoveRelative`, `MoveVelocity`, `Halt`, `Reset`, `SetDynamics`). Refreshes `Axis.Status` once per cycle; one error path (axis error before command error before power error). |
| `E_AxisCmd.TcDUT` | The commands `FB_Axis` issues. |
| `FB_HomePlc.TcPOU` | Homing option 1, PLC-based: move off the switch if on it, search, halt, `MC_SetPosition` relative so the switch edge becomes the reference, then mark homed by **your own flag** or the **NC's homed state** (`MC_ForceCalibration`), chosen by a parameter. |
| `ST_HomePlcParams.TcDUT`, `E_HomePlcState.TcDUT` | Its parameters and steps. |
| `FB_HomeNc.TcPOU` | Homing option 2, `MC_Home` with `MC_DefaultHoming`: cam input every cycle, a faked cam for a sync-pulse-only axis, a run timeout that halts the axis. |
| `ST_HomeNcParams.TcDUT`, `E_HomeNcState.TcDUT` | Its parameters and steps. |
| `PRG_AxisExample.TcPOU` | How they fit together on one axis: call order, one homed record, edge-triggered commands, one error for the HMI. Every number in it is a placeholder. |

`references/homing.md` explains the homing sequences; `references/axis-lifecycle.md` covers the
`Tc2_MC2` behaviour the wrapper is built around.

## Design choices worth knowing

- **The caller owns the `AXIS_REF`** and passes it to every block as `VAR_IN_OUT`, so the
  wrapper, the homing blocks and any coupling block work on the same axis. Call `FB_Axis` first
  in the cycle: it calls `Axis.ReadStatus()`, so code after it reads a fresh `Axis.Status`.
- **Methods only record a request; the body issues it.** No method touches the axis, so methods
  are safe to call from anywhere in the cycle, before or after the body.
- **Two instances per move.** `Tc2_MC2` takes no new parameters while a move block is busy, and
  `MC_MoveVelocity` stays busy until something replaces it. Retargeting a move or changing speed
  triggers the other instance, which takes over (`Aborting`); the superseded one's
  `CommandAborted` is expected and not reported.
- **Every trigger is a real rising edge.** An instance is triggered only when it is not `Busy`
  and was given `Execute` FALSE at its last call; `Execute` is held until the block shows a result.
- **A stop wins.** `Halt` is always accepted and replaces a move that is still waiting; while a
  Halt waits, moves and `Reset` are refused. Moves with a velocity <= 0 are refused, and `bBusy`
  stays TRUE while any instance runs, so a rejected retarget cannot hide a move that goes on. `MC_Halt`, not `MC_Stop`, which would lock the axis.
- **Explicit where the library is easy to misread.** The homing blocks refuse a run without
  an explicit `MC_Halt` deceleration: 0 takes the last move's deceleration (seen on a simulated
  axis), which for a homing search is not a value anyone chose. `FB_Axis.Halt` never refuses a
  stop, so pass it a value > 0. They set both feed enables on `MC_Power` (a missing one gives
  only 0x4223 on the move, see `references/triage.md`), and clear and set the NC's homed state
  with explicit `MC_Home` calls, because `MC_SetPosition` neither sets nor clears it.
- **`FB_HomeNc`'s timeout.** It relies on `MC_Halt` stopping a running `MC_Home`, which the
  field test confirmed (`MC_Home` then reports 0x4B0A). To exercise the timeout on a simulated
  axis, hold `bCalibrationCam` FALSE with `stParams.bNoCam` FALSE, so the cam never arrives.
- **Don't simulate the reference switch from `ActPos` for NC homing.** A test switch such as
  `bRefSwitch := Axis.NcToPlc.ActPos <= fSwitchPos` works for `FB_HomePlc`, but during
  `MC_DefaultHoming` the NC sets the position to −1.0E10 while searching (`references/homing.md`),
  so that switch goes TRUE in the first cycle. Use a hand-written BOOL instead.
- **Own error codes are above 16#FFFF** (`16#0001_xxxx`), clear of every NC and ADS code. Any
  other code is the NC's: look it up with `scripts/nc_error.py`.
- **A homed flag is not retained.** After a restart an incremental axis is not homed; an
  absolute axis is homing option 6, not these blocks.

Not covered: `MC_Stop` (locking stop), `MC_Jog`, coupling, step homing, touch-probe and
drive-based homing. The wrapper is a starting point: add a method and an instance pair in the
same pattern.

## Using them

Use twincat-st's `tcpou.py` to bring them into a project. Don't copy the files: TwinCAT
identifies objects by GUID, and a copy keeps the template's. Scaffold each object, move the
parts across, register it, check it:

```bash
py -3 tcpou.py new --type fb --name FB_Axis --dir MyProject/PLC/POUs/
py -3 tcpou.py add-method MyProject/PLC/POUs/FB_Axis.TcPOU --name MoveAbsolute --returns BOOL
#   ... one add-method per method; --access PRIVATE for the M_ methods
py -3 tcpou.py get templates/FB_Axis.TcPOU --part decl --out decl.st
py -3 tcpou.py set MyProject/PLC/POUs/FB_Axis.TcPOU --part decl --from-file decl.st
#   ... the same for impl and every Method:decl / Method:impl part, and for each DUT
py -3 tcpou.py register MyProject/PLC/PLC.plcproj MyProject/PLC/POUs/FB_Axis.TcPOU
py -3 tcpou.py check MyProject/PLC/POUs/FB_Axis.TcPOU
py -3 st_review.py MyProject/PLC/POUs/
```

If a file was copied anyway, `tcpou.py reguid <file>` gives every object in it a fresh GUID. The
project needs the `Tc2_MC2` library. Match your project's naming where it differs; the structure
is the part that matters.
