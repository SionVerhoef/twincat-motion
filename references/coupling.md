# Coupling, superposition, registration and external set points

Everything on this page runs on classic NC with `Tc2_MC2`, plus `Tc2_MC2_Camming` for cam
plates. MC3 couplings use the same block names and behave differently: `out-of-scope.md`.

| The job | Use |
|---|---|
| Slave follows the master at a fixed ratio, coupled at standstill | `MC_GearIn` |
| Ratio changes while running (draw, winder, dancer trim) | `MC_GearInDyn` |
| Couple to a master that is already moving, or sum up to four masters | `MC_GearInMultiMaster` with `AdvancedSlaveDynamics`, or the flying-saw blocks |
| Slave meets the moving master at a given position (flying saw, flying shear) | `MC_GearInPos` / `MC_GearInVelo` in `Tc2_MC2_FlyingSaw` (TF5055) |
| Slave follows a non-linear profile of the master (rotary knife, cross sealer, cam) | `MC_CamIn` with a cam plate (TF5050) |
| Shift a running axis or slave by a distance without stopping it | `MC_MoveSuperImposed`, or `MC_PhasingRelative` / `MC_PhasingAbsolute` on a slave |
| Correct to a printed mark or product edge | `MC_TouchProbe` + one of the corrections above |
| The PLC computes the profile itself every cycle | `MC_ExtSetPointGenEnable` + `MC_ExtSetPointGenFeed` |

Coupling a slave never changes the master's state. The slave goes to
`SynchronizedMotion`. Both axes still need their own `MC_Power`: a slave without controller or
feed enable rejects the coupling start (look up 0x422A with the tool).

## The slave is protected

A coupled slave is in **protected mode**: `ST_AxisStatus.ProtectedMode` and `Coupled` are
TRUE, and `Axis.NcToPlc.CoupleState` reads 3 (slave), 2 (a slave that is itself a master),
1 (master) or 0 (single). What a direct motion command on it does depends on one axis
parameter, *Allow motion commands to slave axes*
(`.xti`: `AxisPara/OtherSettings@AllowMotionCmdToSlave`):

- **FALSE**: the command is refused with 0x4B08 and the slave stays coupled.
- **TRUE**: the command **decouples the slave first** and then runs. Only
  `BufferMode := MC_Aborting` is possible, and the move is limited to the axis's maximum
  dynamics.

Axes created in XAE 4024.55 come with it **TRUE** (all ten axes in our untouched test export
carry it). So on a new project a stray `MC_MoveAbsolute` or `MC_Halt` on a slave does not
fail: it silently drops the coupling. If a slave "falls out of sync" for no reason, look for
a motion block that also points at the slave. Whether to allow it is a design choice: TRUE suits
code that decouples by moving, FALSE turns a wiring mistake in the PLC into a visible error.

Decouple a slave before homing it.

## Gearing (`Tc2_MC2`)

**`MC_GearIn`**: fixed ratio, rising edge on `Execute`, `InGear` when coupled.

- Ratio = `RatioNumerator / RatioDenominator`. The denominator is a `UINT`; for a fractional
  ratio put it in the numerator as an `LREAL` with denominator 1 (1:4 is 1 and 4, or 0.25
  and 1). The numerator may be negative to reverse the slave.
- Couple **at standstill**. The block has no synchronisation phase; `Acceleration`,
  `Deceleration`, `Jerk`, `BufferMode` and `Options` are documented as not implemented. To
  catch a moving master use `MC_GearInMultiMaster` with `AdvancedSlaveDynamics` or the
  flying-saw blocks.

**`MC_GearInDyn`**: ratio as one `LREAL`, changeable every cycle while `Enable` is TRUE.
`Acceleration` limits the slave when the ratio jumps (0 = the axis parameter).

- `Enable` FALSE **ends the command but does not decouple**: the ratio freezes at its last
  value and the slave keeps following. Decouple with `MC_GearOut`.
- `MC_GearOut` while `Enable` is still TRUE decouples only briefly; the block couples again
  at once. Drop `Enable` first.
- Not supported by the phasing blocks.

**`MC_GearInMultiMaster`**: up to four masters, each with its own ratio; the slave moves by
the sum. Unused master inputs get an empty `AXIS_REF` (axis ID 0). With
`Options.AdvancedSlaveDynamics` TRUE it can couple to masters already in motion, limited by
`Acceleration`, `Deceleration` and `Jerk` (keep acceleration and deceleration equal).
`Options.SyncMode` (4024.11 and later) decides what happens when those limits bite:

| SyncMode | When the slave can't keep up |
|---|---|
| `VELOSYNC` (default) | matches velocity; the position lost while limited stays lost |
| `POSSYNC1` | catches up the position lost while limited; a position shift from a ratio change is not caught up |
| `POSSYNC2` | catches up both |

**`MC_GearOut`**, and decoupling in general: **the slave does not stop.** It continues at the
velocity it had, like after `MC_MoveVelocity`, indefinitely. Follow every decouple of a moving
slave with `MC_Halt` (or `MC_Stop`), or decouple only at standstill. Code that decouples and
then waits for the slave to stand still waits for ever.

**Flying saw** (`Tc2_MC2_FlyingSaw`, TF5055, a separate licence): `MC_GearInPos` synchronises
the slave so that a given slave position meets a given master position, then holds the
ratio; `MC_GearInVelo` synchronises velocity only. This skill does not detail their inputs;
read the TF5055 documentation.

## Phasing

`MC_PhasingRelative` and `MC_PhasingAbsolute` shift a coupled slave against its master by
`PhaseShift`, as a jerk-limited superimposed move with its own velocity, acceleration and
deceleration. They work on an `MC_GearIn` coupling, on `MC_GearInMultiMaster` with
`AdvancedSlaveDynamics`, and on `MC_CamIn_V2`; not on `MC_GearInDyn`. `MC_HaltPhasing` stops
a running phase shift. For a slave, these are the usual choice; `MC_MoveSuperImposed`
(below) also works on a slave and on single axes.

## Cam plates (`Tc2_MC2_Camming`, TF5050)

A cam plate maps master position to slave position. It needs the TF5050 licence on the
target, and library 3.4.0 or later needs runtime 4024.55 or later.

**Two kinds of table:**
- **Position table**: two columns, master ascending, slave beside it; the NC interpolates
  between points (`ST_CamInOptions.InterpolationType`, linear by default).
  `MC_TABLETYPE_EQUIDISTANT` or `MC_TABLETYPE_NONEQUIDISTANT` master spacing.
- **Motion function**: one column of `MC_MotionFunctionPoint`, each describing a whole segment
  as a function (polynomial, sine, ...). Few points, exact between them, and changeable at run
  time without a jump (`MC_WriteMotionFunction`, `MC_WriteMotionFunctionPoint`, when they
  take effect set by `MC_SetCamOnlineChangeMode`).

**Where the table comes from:**
- drawn in the XAE cam editor: it lives in the NC configuration with an ID; call `MC_CamIn`
  with that `CamTableID`, nothing else.
- built in the PLC: fill an array, describe it in an `MC_CAM_REF` (`pArray := ADR(arr)`,
  `ArraySize := SIZEOF(arr)`, table type, rows, columns: 2 for a position table, 1 for a
  motion function), and load it under a free ID with `MC_CamTableSelect` (`Periodic` TRUE for
  a repeating cam). Then `MC_CamIn` with that ID.

**`MC_CamIn`**: couples the slave to the cam, or switches to another cam while coupled.
`MasterOffset`, `SlaveOffset`, `MasterScaling`, `SlaveScaling` place the table in the axis
coordinates; `StartMode` makes master and slave each absolute or relative to their position
at coupling; `InSync` when the cam is active. `Active` TRUE with `InSync` FALSE means a cam
switch is queued (`ST_AxisStatus.CamTableQueued`).

**The slave must already be where the table says.** With an absolute start mode, the slave
position is computed straight from the table the moment the master moves: if it is somewhere
else, it **jumps**, which on a real axis means a lag error or a violent move. Before
coupling, move the slave to its table position:

```
MasterInTable := (MasterSetPos + MasterOffset) / MasterScaling;
// MC_ReadCamTableSlaveDynamics(CamTableID, MasterPosition := MasterInTable) -> SlavePosition
SlaveTarget   := SlavePosition * SlaveScaling + SlaveOffset;
```

Use **set** positions, not actual positions. `MC_ReadCamTableSlaveDynamics` reads the raw
table: offsets and scaling are yours to apply, and a non-equidistant table returns position
only (velocity and acceleration 0). A relative start mode avoids the jump at coupling instead,
at the price of the table no longer sitting at fixed axis positions.

**`ActivationMode`** (`ST_CamInOptions`, `MC_CamScaling`) says when a coupling, switch or
scaling takes effect: at once, at a master position in the table, at an absolute master axis
position (with direction-specific variants for a slow or noisy master), or at the next cycle
of a periodic cam. A position-based activation must be commanded **before** the master gets
there. Coupling at a table position or at the next cycle cannot be combined with a relative
master start mode.

**Changing a running cam without a jump:**
- switch cams at the next cycle, or at a table position where both cams agree
- scale with `MC_CamScaling`; with `MC_CAMSCALING_AUTOOFFSET` the NC recomputes the offset so
  the position does not jump. The velocity still steps unless the slave is at rest in the
  cam, so scale in a dwell (`CamScalingPending` while queued).
- master auto-offset is not available on the first coupling and not with a relative master
  start mode.

**Periodic cams with lift** (the slave end position differs from the start: a cam that
advances the slave every cycle): the NC adds the lift each cycle. Decoupling and coupling
again puts the slave back in the base cycle, so recompute `SlaveOffset` with the number of
lifts already travelled.

**`MC_CamIn_V2`** superimposes several cams on one slave (add, exchange, remove). It and
`MC_CamIn` cannot both drive the same slave. **`MC_CamOut`** decouples, and like
`MC_GearOut` it leaves the slave running at constant velocity.

## Superimposed moves

`MC_MoveSuperImposed` adds a relative `Distance` to an axis that is already moving, without
interrupting its current command. On a single axis or a slave it shifts that axis; on a
master, every slave follows the shift through the coupling. The base command's target moves
by `Distance` too.

- `Length`: the stretch over which the correction may happen. `Mode` (`E_SuperpositionMode`)
  is two choices in one name:
  - *what to minimise*: `VELOREDUCTION` uses the whole `Length` with the smallest velocity
    change, `LENGTHREDUCTION` finishes as soon as possible within `VelocityDiff`,
    `ACCREDUCTION` uses the whole `Length` with the smallest acceleration.
  - *whose travel `Length` measures*: `ADDITIVEMOTION` = a reference axis such as the master
    (the corrected axis travels `Length + Distance`); `LIMITEDMOTION` = the corrected axis
    itself (keep `Distance` well below `Length`).
- `VelocityDiff`: the velocity reserve. Speeding up, at most max velocity − current velocity;
  slowing down without reversing, at most the current velocity.
- If the parameters do not allow the full distance, the block does as much as it can and sets
  `Warning` with 0x4243; `ActualDistance` says how much. Decide whether that is an error for
  your process.
- The correction is tied to the base motion: it slows when the axis slows and pauses when it
  stops. By default it is dropped at a standstill; `Options.AbortOption` can resume it after
  the stop instead.
- `MC_AbortSuperposition` cancels the correction and leaves the base motion running.

## Registration: correcting to a mark

The usual print-mark or product-edge loop:

1. A sensor on a latch input of the drive or encoder terminal. `MC_TouchProbe` arms the latch
   on the axis that carries the material; `TRIGGER_REF` names encoder, probe unit, edge and
   mode. The latch is hardware: accurate regardless of PLC cycle.
2. **Window** the latch so dirt and other print do not count: `WindowOnly` with
   `FirstPosition`/`LastPosition`. With `TRIGGER_REF.ModuloPositions` TRUE the window repeats
   every modulo cycle, which is what a repeating product needs.
3. `TOUCHPROBEMODE_CONTINOUS` (the library's spelling) re-arms by itself, so every mark is
   caught without re-triggering; single mode records one edge and must be triggered again.
   Both need the probe unit set up as an *Extended NC Probe Unit*. A KL/EL5101 latches only
   one edge at a time and has no continuous mode.
4. Error = expected mark position − `RecordedPosition`. Filter it and limit it; one bad mark
   should not throw the tool.
5. Apply the correction while running: `MC_PhasingRelative` on a geared or cam slave,
   `MC_MoveSuperImposed` on a single axis or slave, or a new `SlaveOffset` through
   `MC_CamScaling` activated at a table position. Make it in the part of the cycle where the
   tool is not in the product (a rotary knife's non-synchronous zone).
6. To stop waiting for a mark, call `MC_AbortTrigger` with the same `TRIGGER_REF`; otherwise
   no new cycle can be armed.

The drive side of touch probe (0x60B8 / 0x60B9, SoE probe parameters) is **cia402-motion**
and the device's ESI (**ethercat-esi**). Touch-probe homing is in `homing.md`. Beckhoff's
TF5050 samples include a rotary knife with registration that shows the whole pattern.

## External set-point generator

The PLC computes position, velocity, acceleration and direction itself and the NC axis
follows them instead of its own generator: for a profile the NC blocks can't make, or an
online trajectory library.

1. `MC_ExtSetPointGenEnable` (rising edge). `Position` here does **not** move the axis; it
   arms target-position monitoring, and `InTargetPosition` comes TRUE when the axis gets
   there. `ST_AxisStatus.ExtSetPointGenEnabled` shows the state.
2. Every cycle: `MC_ExtSetPointGenFeed(Position, Velocity, Acceleration, Direction, Axis)`. It
   is a function that copies the values into `Axis.PlcToNc`; its return value means nothing.
   Direction is −1, 0 or 1. `MC_ExtSetPointGenFeedWithTorque` adds a torque offset, which
   only reaches the drive when the enable had `Options.UseTorqueOffset` TRUE.
3. `MC_ExtSetPointGenDisable` to give the axis back to the NC generator.

Points that trip people up:

- **Feed a consistent profile, every NC cycle.** The NC takes the values as they are: a
  position jump becomes a lag error or a jerk on the machine, and velocity and acceleration
  that don't match the position steps upset the feed-forward. Run the feeding PLC task at the
  NC SAF cycle (or derive the values for the NC cycle), and start from the axis's current set
  position.
- Normal motion commands on an axis fed externally are governed by a separate axis
  parameter (`Status.Opmode.AllowExtSetAxisCommands`); don't mix the two without knowing how
  it is set.

## When a coupling misbehaves

| Symptom | Look at |
|---|---|
| Coupling refused | the slave's `MC_Power` (0x422A), slave already coupled, wrong axis passed as master; look the `ErrorID` up with the tool |
| Slave dropped out of sync on its own | a motion block on the slave with motion commands allowed on slaves; `MC_GearInDyn` with `Enable` toggling; `CommandAborted` on the coupling block |
| Move on the slave fails with 0x4B08 | protected mode: decouple first, or allow motion commands on the slave |
| Slave runs away after decoupling | expected: decoupling keeps velocity; add `MC_Halt` |
| Slave jumps when the master starts | cam coupled with the slave off its table position, or a scaling/offset change without auto-offset |
| Lag error on the slave only | slave dynamics too low for ratio × master dynamics; cam velocity/acceleration beyond the slave's limits (`MC_ReadCamTableSlaveDynamics` at the steepest point) |
| Registration correction never completes | `Warning` 0x4243 on `MC_MoveSuperImposed`: not enough `Length` or `VelocityDiff` |

Nothing on this page has been run on a real axis; the behaviour is from the Tc2_MC2 and TF5050
documentation and the owner's 4024.55 axis export. Report at that precision.
