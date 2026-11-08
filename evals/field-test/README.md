# Field test: one XAE sitting

This protocol checks the claims in this skill that nobody has yet run against TwinCAT. It
is written for an agent that has only this repository, working with a person at a Windows PC
with TwinCAT XAE. Everything you need is in this folder and in the files it points to.

## Context

`twincat-motion` is an agent skill for classic TwinCAT NC axes (`Tc2_MC2`). Its references
(`references/`), templates (`templates/`) and scripts (`scripts/`) were written from the
Beckhoff documentation and public sample projects. The scripts are unit-tested, but nothing
has run against a real NC: the templates have not been compiled, and several statements
about NC behaviour come from the manual or from memory. This session settles those
statements on **simulated axes**, in one sitting.

Read `SKILL.md` first. Before each check, skim the reference section it names under
**Claim**: that is what the check confirms or refutes.

**Roles.** The **operator** is the person at XAE: they make every click, activation and
online write. **You** guide them through the checks in order, prepare files and code, run
the repository's scripts, look up codes, and write down the results. Sections A to F use
only simulated axes, so nothing physical moves. Section G is optional and uses a real drive.

**Your job is to record, not to fix.** Do not edit `references/`, `templates/` or
`scripts/`. The maintainer fixes the skill from your results afterwards. Where a template
needs a change to compile, make the smallest change in the test project and record it as a
diff (B1).

## Rules

- **Throwaway project only.** A new, empty XAE project with neutral names. Never a customer's
  or a production project.
- **Simulated axes only**, except section G. Even there the operator decides and runs every
  step, at reduced limits, within reach of the stop. Never bridge, force or simulate STO, an
  enable circuit or a limit switch, not even for a test.
- **Results go in `research/field-test-results.md`**: copy `results-template.md` there.
  `research/` is gitignored. Do not commit, push, or open issues from this session; the
  operator carries the file back to the maintainer.
- **Keep identities out of the results**, as `CLAUDE.md` asks: no AMS NetIDs, IP or MAC
  addresses, host or user names, local paths, serial numbers or licence keys. Attribute names
  and the default values of a fresh test axis are fine. Do not paste whole `.xti` files.
- **Never guess a result.** If a check can't run, mark it `NOT RUN` and say why. Record what
  you saw, with the raw error codes (hex, as XAE shows them), even if it matches.
- **Look up every NC code** with `py -3 scripts\nc_error.py <code>` and record whether the
  tool's meaning fits what happened. That tests the tool too.

## Before you start

| Need | For |
|---|---|
| Windows, TwinCAT 3.1.4024.x XAE, and a runtime to activate on (the local PC in run mode, or a test IPC) | everything |
| Python 3.8 or later (`py -3`) | `scripts/axis_xti.py`, `scripts/nc_error.py` |
| `Tc2_MC2`; `Tc2_MC2_Camming` with a TF5050 licence (a 7-day trial is enough) | B, C, D, E; E5 and E6 |
| Windows PowerShell 5.1 (not PowerShell 7) | A5 |
| Git, or another tool that diffs two files | raw diffs in A |
| Optional: an EtherCAT drive and motor on a bench, unloaded | G |

About 3 to 4 hours. If time runs short, do these first: A1–A3, B1–B3, C1–C5, D2, D4, E1–E3.

**Statuses** in the results: `CONFIRMED` (what the skill says happened), `DIFFERENT` (record
what happened instead), `PARTIAL`, `NOT RUN` (say why).

## 0. Set up the project

1. Create a new TwinCAT XAE project, for example `FieldTest`.
2. Add the NC task and four axes, all left at their defaults (a new axis is simulated):
   `Axis 1` and `Axis 2` for PLC tests, `Axis 3` for the templates, `Axis 4` for
   configuration experiments.
3. Save all. Check that each axis has its own file, `_Config\NC\Axes\Axis 1.xti` and so on.
   If not, right-click the axis and set *Independent Project File*, then save again.
4. Copy the folder `_Config\NC\Axes` to `axes-fresh\` next to the project, before anything
   changes. A1 reads it.
5. Add a PLC project with the library `Tc2_MC2` (and `Tc2_MC2_Camming` if licensed).
6. Fill in the header of the results file: TwinCAT build, library versions, where the
   runtime runs, NC SAF cycle time and PLC task cycle time.

## A. Configuration in XAE (no runtime needed)

**A1. What a new axis writes to its file.**
Claim: `references/coupling.md`, "The slave is protected": axes created in 4024.55 have
*Allow motion commands to slave axes* TRUE. `SKILL.md`, Tools: an `.xti` holds only
non-default values. Both can't be fully true if the file spells TRUE out.
Do: `py -3 scripts\axis_xti.py show "axes-fresh\Axis 1.xti"`. Open the file in an editor
and search for `AllowMotionCmdToSlave` and for `PosDiffControl`. In XAE, read the same two
settings on Axis 1's *Parameter* tab (allow motion commands to slave axes; position lag
monitoring enable).
Record: for each, present in the file or not, its value, and what XAE shows. The full list of
attributes `axis_xti.py show` prints for a fresh axis.

**A2. Does XAE accept a hand-edited `.xti`?**
Claim: `references/config-changes.md`, section 3: it is untested whether XAE loads a
hand-edited value unchanged, and whether it rewrites the file on save.
Do: in XAE set Axis 2's *Manual Velocity (Fast)* (or any velocity on the Parameter tab) to
123, save all, close XAE. Copy `Axis 2.xti` to `axis2-before.xti`. In an editor, change
that 123 to 124 and nothing else. Open the project in XAE.
Record: any warning on load; the value XAE shows. Then save all without touching anything
and run `py -3 scripts\axis_xti.py diff axis2-before.xti "_Config\NC\Axes\Axis 2.xti"`
and a raw diff (`git diff --no-index`). Did XAE rewrite or reformat the file? What changed
besides the value?

**A3. What an absent attribute means.**
Claim: same as A1, and `references/triage.md` step 4.
Do: with XAE closed, delete from `Axis 2.xti` the `AllowMotionCmdToSlave` attribute and the
position-lag enable attribute under `PosDiffControl`, if either is present. Open XAE.
Record: what XAE shows for both now; whether XAE writes them back on the next save. The
runtime value follows in C0. (If a fresh axis has neither attribute, the fresh axis already is
the "absent" case; record that.)

**A4. Where non-default settings land in the file.**
Claim: `references/axis-parameters.md`, dead-time compensation: an encoder setting on the
*Enc > Time Compensation* tab, separate from the drive's `Drive/DrvPara/TimeComp`.
`references/coupling.md`: the external set-point setting is named as
`Status.Opmode.AllowExtSetAxisCommands`, and the slave setting as
`AxisPara/OtherSettings@AllowMotionCmdToSlave`.
Do, on Axis 4, one change at a time: copy `Axis 4.xti` to a numbered backup, change the
setting in XAE, save, run `axis_xti.py diff` and a raw diff against the backup, then undo
the change.
1. *Enc > Time Compensation*: change each field on the tab. If the simulated encoder has no
   such tab, set the encoder type to an EL72x1 or AX8000 encoder (no hardware needed for the
   configuration) and record which type shows it.
2. *Allow motion commands to an external set-point axis* (exact name as XAE shows it).
3. *Allow motion commands to slave axes* set to FALSE.
4. Position lag monitoring off. (Scratch axis only; switch it back on.)
Record per change: XAE page and field name, the `.xti` element path, attribute and value, and
whether `axis_xti.py diff` shows it under that path. If the tool misses a change or names it
differently, that is a finding.

**A5. The Automation Interface script.**
Claim: `references/config-changes.md`, section 2: `axis-change.ps1` has not been run
against XAE; the XML from `ProduceXml` may not match the `.xti` layout.
Do: copy the script from that section, unchanged, into `axis-change.ps1`. With the project
open in XAE, in Windows PowerShell 5.1:
1. `.\axis-change.ps1 -Solution <path to the .sln> -Axis "Axis 4" -Produce`
2. Find Axis 4's maximum velocity (or manual velocity) in the produced XML. Write a
   `changes.csv` with one row (`XPath,Attribute,Old,New`) that changes it.
3. Run it again with `-Changes changes.csv`. Check the value on the axis in XAE.
4. Run once more with a wrong `Old` value: it must stop with "Nothing applied".
Record: whether it attached at all (if `TcXaeShell.DTE.15.0` failed, which ProgId worked);
whether the tree path `TINC^NC-Task 1 SAF^Axes^Axis 4` worked; the produced XML's root
element and the XPath and attribute of the value you changed, next to its `.xti` path from
A4; whether the change showed in XAE and marked the project modified; every error message
verbatim, with local paths removed.

**A6. Flying saw: library and product number.**
Claim: `references/coupling.md`: flying saw is `Tc2_MC2_FlyingSaw`, licence TF5055.
Do: search the PLC library repository for "FlyingSaw", and the licence list in XAE for the
flying saw product.
Record: the library name and the product number and title, as shown.

**A7. NC retain settings: where they are and what they're called.**
Claim: `references/homing.md`, section 6: NC retain data is set on the SAF task, and the
strictest setting is called *Load/Store* "in our sources".
Do: find in XAE where NC retain data is configured (task, NC or axis level), and any
per-encoder data-persistence setting.
Record: the menu path and the exact names of the options.

## B. Compile, link and start

**B1. The templates compile.**
Claim: `templates/README.md`: reviewed, never compiled.
Do: add all nine files from `templates/` to the PLC project (*Add > Existing Item*). In a
throwaway project the templates' GUIDs don't matter; in a real project use twincat-st's
`tcpou.py` as `templates/README.md` says. Build.
Record: every error and warning, verbatim, with object and line. Known risk points: reading
a block's `Execute` from inside a method of `FB_Axis`, the `16#0001_0001` literals, and
`DEFAULT_HOME_POSITION` as a default value in `ST_HomeNcParams`. For each fix you needed,
record a unified diff against the template.

**B2. The test program compiles.**
Do: create `PRG_FieldTest` from `PRG_FieldTest.st` as its header says. Build.
Record: errors and the fixes, as in B1.

**B3. A test copy of the example program.**
`PRG_AxisExample` reads a real reference switch. Simulate one in the project's copy:
1. Change `bRefSwitch AT %I* : BOOL;` to `bRefSwitch : BOOL;` and add
   `fSwitchPos : LREAL := -50.0;` to its `VAR` block.
2. Add as the first line of its code: `bRefSwitch := Axis1.NcToPlc.ActPos <= fSwitchPos;`
   The "switch" is then active below -50 and moves with the coordinates when homing sets a
   new position. That is fine for these tests.
3. Add a velocity command for D3, in the declarations
   `bVeloCmd : BOOL; fVeloCmd : LREAL := 50.0; fbVeloTrig : R_TRIG;` and after the other
   commands:
   `fbVeloTrig(CLK := bVeloCmd); IF fbVeloTrig.Q THEN bAccepted := fbAxis.MoveVelocity(fVelocity := fVeloCmd, eDirection := MC_Direction.MC_Positive_Direction); END_IF`
4. Call `PRG_FieldTest` and `PRG_AxisExample` from `MAIN`. Link Axis 1 and Axis 2 to
   `PRG_FieldTest.Axis1` and `Axis2`, and Axis 3 to `PRG_AxisExample.Axis1`.
5. Activate the configuration, log in, start the PLC.
Record: anything that did not work as described.

## C. One simulated axis (Axis 1, `PRG_FieldTest`)

Write `bClear := TRUE` before each check. Pulse a command means: write TRUE, then FALSE.

**C0. What the running NC holds.** (Completes A1 and A3.)
Record: `fbAllowSlave1.Value`, `fbAllowSlave2.Value`, `fbLagMon1.Value`,
`fbLagMon2.Value`, `fbAllowExt1.Value`, each with its `Valid`. Axis 2 is the one whose
attributes A3 removed.

**C1. `MC_Power` with only `Enable`.**
Claim: `references/triage.md` step 2: with only `Enable`, the first move is refused with
0x4357 or 0x4358, or 0x4223 / 0x422A at the start of a move.
Do: `bEnPos1 := FALSE`, `bEnNeg1 := FALSE`, `bEnable1 := TRUE`. Then pulse `bMoveA`
(a positive move, to 1000).
Record: `fbPower1.Status` before the move; `nErrMoveA` (the block) and `nAxisErr1` (the
axis); `bStatusDropped1`; whether the axis is in ErrorStop. Then set `bEnPos1 := TRUE` only:
does a positive move work now, without `MC_Reset`? Does a negative move (`bMoveB`) fail,
and with which code? Which code belongs to which direction, and does the tool agree?

**C2. `MC_Stop` locks the axis.**
Claim: `references/axis-lifecycle.md`, "MC_Stop locks the axis": `Done` at standstill,
`Busy` and `Active` stay TRUE, other commands get 0x42EF until `Execute` falls, release takes
some cycles, and `MC_Reset` also releases it.
Do: all enables TRUE. Pulse `bMoveVelo`, then set `bStop1 := TRUE` and hold it. After
`fbStop1.Done`, pulse `bMoveA`. Then set `bStop1 := FALSE`.
Record: `fbStop1.Done/Busy/Active` while held; `nErrMoveA`;
`Axis1.Status.MotionCommandsLocked`; `nStopRelease` after release, with the PLC cycle time.
Repeat, but while `bStop1` is held pulse `bReset1`: is the lock gone? Does a move work now?

**C3. `MC_Halt` with `Deceleration` 0.**
Claim: `references/axis-lifecycle.md`, "Zero means different things": 0 on `MC_Halt` takes
the last move's deceleration, and a stop never ramps more gently than the move it ends.
`templates/README.md` calls this unconfirmed.
Do: four runs. Each: set `fDec`, pulse `bMoveVelo`, wait for constant velocity, set
`fHaltDec1`, pulse `bHalt1`, read `fPeakDecel1` (the largest set deceleration of the ramp).
| Run | `fDec` | `fHaltDec1` |
|---|---|---|
| a | 500 | 500 (checks the measurement: expect about 500) |
| b | 500 | 0 |
| c | 200 | 0 |
| d | 500 | 100 |
Record: the four values and the axis's default deceleration (Parameter tab). b about 500 and c
about 200 means "last move's value"; b and c both at the axis default means "axis default".

**C4. Which commands set the NC's homed state.**
Claim: `references/homing.md`, option 1 and the `MC_Home` mode table: `MC_SetPosition` does
not set it; `MC_Direct` sets the position and marks homed; `MC_ForceCalibration` marks homed
without changing the position; `MC_ResetCalibration` clears it.
Do: `eHomeMode1 := MC_ResetCalibration`, pulse `bHome1`. `fSetPos1 := 10`, pulse
`bSetPos1`. Then `MC_Direct` with `fHomePos1 := 20`, then `MC_ForceCalibration`, then
`MC_ResetCalibration`, pulsing `bHome1` each time.
Record after each step: `Axis1.Status.Homed` and the actual position. Also: does
`MC_SetPosition` on a homed axis clear the homed state?

**C5. Default homing, and `MC_Halt` during `MC_Home`.**
Claim: `references/homing.md`, option 2, the default sequence and `HomingState`.
`templates/README.md`: `FB_HomeNc`'s timeout relies on `MC_Halt` stopping a running
`MC_Home`, which is untested.
Do: `eHomeMode1 := MC_DefaultHoming`, `bCam1 := FALSE`, pulse `bHome1`. Watch
`Axis1.NcToPlc.HomingState` and the motion. Set `bCam1 := TRUE` (cam found), then FALSE
(cam left). Does a simulated encoder ever give the sync pulse? Then start again, and while
the axis searches set `fHaltDec1 := 500` and pulse `bHalt1`. Repeat once while it waits for
the sync pulse, if it gets there.
Record: search direction and velocity, and the encoder parameters they came from; each
`HomingState` value and when; whether homing completes. On the halt: does the axis stop?
`nErrHome1`, `bAbortedHome1`, `nErrHalt1`, `nAxisErr1`, `HomingState` afterwards, and
whether the next homing run starts without `MC_Reset`.

**C6. Override.**
Claim: `templates/FB_Axis.TcPOU`, contract: `MC_MoveVelocity` ends with `CommandAborted`
when the override changes while the axis keeps moving. `references/triage.md` step 2: at
override 0 a move starts and nothing moves.
Do: pulse `bMoveVelo`, wait for `fbMoveVelo.InVelocity`, set `fOverride1 := 50`, then 0,
then 100. Then, with override 0, pulse `bMoveA`.
Record at each step: `InVelocity`, `Busy`, `bAbortedVelo`, whether the axis moves, and
`fbMoveA.Busy` / `Done` with override 0.

**C7. Zero velocity, zero acceleration.**
Claim: `references/axis-lifecycle.md`: a velocity of 0 is error 0x4231; an acceleration of
0 means the axis default.
Do: `fVelo := 0`, pulse `bMoveA`. Then `fVelo := 100`, `fAcc := 0`, pulse `bMoveA`.
Record: `nErrMoveA`; whether the second move runs.

**C8. Retargeting a running move.**
Claim: `references/axis-lifecycle.md`, "Inputs latch on the rising edge": a new rising edge
on a busy block is ignored without an error; a second instance takes over and the first
reports `CommandAborted`.
Do: pulse `bMoveA` (to 1000). While it runs, set `fPosA := 300` and pulse `bMoveA` again.
Then pulse `bMoveB` (to 400) while A still runs.
Record: what the second edge on A did, and any error; where the axis ends; `bAbortedA`.

## D. The templates on a simulated axis (Axis 3, `PRG_AxisExample`)

Hold `bHomeCmd` TRUE until the homing block reports done or error, then write FALSE. Pulse the
other commands.

**D1. Power and reset.**
Do: `bPowerOn := TRUE`. Then pulse `bResetCmd`.
Record: `fbAxis.bReady`; `bAccepted` for the reset; any error.

**D2. `FB_HomePlc`.**
Claim: `references/homing.md` option 1 and `templates/README.md`.
1. Start off the switch (position above -50), `stHomePlc.bMarkNcHomed` FALSE. Run homing.
   Record: the motion (search negative, halt at the edge), `fbHomePlc.bDone`, `bHomed`,
   `Axis1.Status.Homed` (expect FALSE), and the final position (expect a small negative
   value: the edge becomes 0 and the axis stopped a little beyond it).
2. The same with `stHomePlc.bMarkNcHomed := TRUE` (write it online). Expect
   `Axis1.Status.Homed` TRUE.
3. Start on the switch: after run 1 (moves need a homed axis), move to -100 with
   `fTarget := -100` and a pulse on `bMoveCmd`, then run homing. Expect a move off the switch in the positive direction, then the search.
4. Search timeout: `fSwitchPos := -100000`, `stHomePlc.tStepTimeout := T#5S`. Run homing.
   Expect `bError` with `nErrorID` 16#0001_0103 after 5 s, **and the axis halted**.
Record each run, and anything unexpected in the steps (`fbHomePlc.eState`).
Restore `fSwitchPos := -50` and `tStepTimeout` afterwards.

**D3. `FB_Axis` moves.**
Claim: `templates/README.md`, design choices.
1. `fTarget := 500`, pulse `bMoveCmd`. Expect `fbAxis.bDone`.
2. Retarget: `fTarget := 1000`, pulse `bMoveCmd`; while it moves, `fTarget := 200`, pulse
   again. Expect the axis to turn and stop at 200, `fbAxis.bCommandAborted` FALSE, no error.
3. Pulse `bHaltCmd` during a move. Expect a stop, `bDone`, no error.
4. Pulse `bVeloCmd` (from B3); while it runs set `fVeloCmd := 100` and pulse again. Expect
   the new speed, no error. Then pulse `bHaltCmd`.
5. With a velocity move running, write `fbAxis.fOverride := 50`. Record `bBusy`, `bDone`,
   `bCommandAborted`, `bError`.
Record: each step's outputs, and any refusal (`bAccepted` FALSE).

**D4. `FB_HomeNc`.**
Claim: `references/homing.md` option 2; `templates/README.md`: the timeout path relies on
`MC_Halt` stopping `MC_Home`.
Do: set `cUseNcHoming := TRUE` (a constant: change it and download), `stHomeNc.tTimeout :=
T#10S`.
1. With the simulated switch as cam: run homing. If it never completes (no sync pulse on a
   simulated encoder, see C5), it must time out: expect `bError`, `nErrorID` 16#0001_0202,
   and the axis halted.
2. `stHomeNc.bNoCam := TRUE`: run again. Expect the faked cam to start the sequence, then the
   same outcome.
Record: both runs, `Axis1.NcToPlc.HomingState` along the way, and whether the axis really
stood still after the timeout. If homing completed, the final position (the default takes the
reference position from the encoder parameters).

## E. Coupling (Axis 1 master, Axis 2 slave, `PRG_FieldTest`)

Enable both axes with all enables TRUE. Decouple (`bGearOut`, `bCamOut`) and halt the slave
between checks.

**E1. A move on a coupled slave, motion commands to slaves allowed.**
Claim: `references/coupling.md`, "The slave is protected", and `references/triage.md` step 4:
with the setting TRUE, a move on a slave decouples it without an error and runs.
Do: set Axis 2's *Allow motion commands to slave axes* to TRUE in XAE and activate (or
download it online). Pulse `bGearIn` at standstill, pulse `bMoveVelo` on the master, then
pulse `bMoveSlave`. Afterwards, couple again and pulse `bHalt2` (`fHaltDec2 := 500`).
Record: `nErrMoveSlave`, `Axis2.Status.Coupled` and `ProtectedMode` before and after,
`bAbortedGearIn`, where the slave ends; the same for the halt.

**E2. Decoupling a moving slave.**
Claim: `references/coupling.md`, `MC_GearOut`: the slave keeps its velocity indefinitely.
Do: couple, master at constant velocity, pulse `bGearOut`. Then halt the master.
Record: `Axis2.NcToPlc.SetVelo` after the decouple and after the master stopped;
`Axis2.Status.ContinuousMotion`.

**E3. `MC_Halt` with `Deceleration` 0 on a decoupled slave.**
Do: continue from E2 with `fHaltDec2 := 0`, pulse `bHalt2`, read `fPeakDecel2`. Repeat with
the master's `fDec` at 500 and at 200 before coupling.
Record: both values, and Axis 2's default deceleration. Whose dynamics did the halt use?

**E4. `MC_GearInDyn` with `Enable` FALSE.**
Claim: `references/coupling.md`: `Enable` FALSE ends the command but keeps the coupling;
`MC_GearOut` while `Enable` is TRUE decouples only briefly.
Do: `bGearInDyn := TRUE`, wait for `InGear`, master moving. `bGearInDyn := FALSE`. Then
`bGearInDyn := TRUE` again and pulse `bGearOut` while it stays TRUE.
Record: `Axis2.Status.Coupled` and whether the slave follows after Enable FALSE; what the
`bGearOut` pulse did over the next second.

**E5. `MC_CamIn` with the slave away from its table position.** (Needs TF5050.)
Claim: `references/coupling.md`, "The slave must already be where the table says", and its
formula `MasterInTable := (MasterSetPos + MasterOffset) / MasterScaling`. The test table is a
straight line, slave = master, over 0 to 360.
1. Master at 100, slave at 0, both at standstill and decoupled. Pulse `bCamSelect`, then
   `bCamIn` (offsets 0, scalings 1). Does the slave jump to 100 at once, or only when the
   master moves? Then move the master to 150.
2. Decouple. `fMasterOffset := 20`, `fMasterScaling := 2`, `fSlaveOffset := 5`. Master at
   100. Couple, then move the master to 120.
Record: slave set position after coupling and after each master move; `nAxisErr2`,
`nErrCamIn`. For step 2: the page's formula gives a slave at 65 with the master at 100 and 75
at 120; other orders give 45 / 55 or 75 / 85. Which matches?

**E6. Phasing on a plain `MC_CamIn` slave.**
Claim: `references/coupling.md`, "Phasing": phasing works on `MC_GearIn`,
`MC_GearInMultiMaster` with advanced slave dynamics and `MC_CamIn_V2`, not on
`MC_GearInDyn`; the registration section suggests it on any cam slave.
Do: pulse `bPhasing` (`fPhaseShift := 10`) on: an `MC_CamIn` slave (E5), an `MC_GearIn`
slave, an `MC_GearInDyn` slave.
Record per coupling: `nErrPhasing`, whether the slave shifted by 10.

**E7. The same move with motion commands to slaves not allowed.** (Last, as it may need an
activation.)
Claim: as E1: with the setting FALSE, the move is refused with 0x4B08 and the slave stays
coupled.
Do: set the setting FALSE on Axis 2, activate or download, and repeat E1.
Record: as E1.

## F. Retain and the first start (best effort)

**F1. 0x4002 on the first start.**
Claim: `references/homing.md`, section 6: without valid retain data the NC either refuses to
start (strictest setting) or starts with 0x4002 and absolute axes not homed; 0x4002 on the
very first start is expected and should not repeat.
Do: only if the runtime has retain storage: switch NC retain on with the settings found in
A7, activate, restart the runtime twice.
Record: the codes at each start (the TwinCAT logger shows them), and whether Axis 1 is homed.
If this needs hardware you don't have, mark `NOT RUN`; A7 still counts.

## G. A real drive (optional, operator only)

Only with a drive and motor on a bench, the motor unloaded and free to turn, the stop in
reach, and the operator's agreement to every step. Velocity, acceleration and torque reduced.

**G1. A mapped torque limit left unlinked.**
Claim: `references/triage.md` step 0: an output that is mapped but not linked is sent as 0.
With a torque limit, the axis enables and `MC_Power.Status` is TRUE, but the motor gives no
torque, and the position lag grows until 0x4550 or 0x435D.
Do: map the drive's torque-limit object into its outputs and leave it unlinked. Activate,
enable, command a short slow move.
Record: drive type (product name only), `MC_Power.Status`, whether the motor moved, the NC
code and the drive's own error. Then remove the mapping and activate again.

## H. Wrap up

1. Fill every row of the results file, including `NOT RUN` rows with their reason.
2. Put the compile fixes from B1 and B2 in it as diffs.
3. Add anything in this protocol that was wrong or unclear: menu names, steps that didn't
   work, missing checks. That improves the next run.
4. Read the file once more for identities (Rules). Then hand it to the operator. Leave the
   test project on the PC; do not commit it.
