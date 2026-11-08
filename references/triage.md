# Triage: the axis won't enable, won't move, or faults

Work down the steps in order. Each step rules out one layer, so advice from a later step
is wrong while an earlier one is still open. Most "won't move" questions end at step 2, 3
or 4.

## What to ask for first

- **Library and build.** Tc2_MC2 on TwinCAT 3.1.4024 or similar? `Tc3_Mc3*` or `McToPlc` mean
  MC3, and 0x81xx codes MC3 or the Advanced Motion Pack; this skill covers neither:
  `out-of-scope.md`.
- **The drive and its interface.** Simulated axis, AX5000/AX8000 (SoE), EL72x1/EL70x7
  terminal, or a third-party CoE drive. For a CoE drive: does it run in position mode
  (CSP) or velocity mode (CSV)?
- **The `MC_Power` outputs**: `Status`, `Error`, `ErrorID`. And the move block's outputs.
- **The axis status**, from `MC_ReadStatus` or `Axis.ReadStatus()` called this cycle, or
  from the axis's Online tab in XAE. A status that nobody refreshes is stale.
- **Every NC error code.** Look each one up with `scripts/nc_error.py`; never from memory.
- **What changed** since it last worked: new configuration activated, drive swapped,
  TwinCAT updated, PLC code changed, process data mapping changed, hardware or wiring work
  on the machine.

## 0. Is it an NC2 axis, and is anything arriving?

- **The PLC's `AXIS_REF` is linked to an NC axis.** In XAE the axis's Settings tab names
  the PLC instance it is linked to. Unlinked, the blocks cannot address the axis: they
  report an error that no `MC_Reset` clears, because it is configuration, not an axis
  fault. Re-link, activate, and trigger again.
- **The NC is updating the PLC.** `ST_AxisStatus.NcCycleCounter` should change every NC
  cycle. If it stands still, the NC task is not running or the link is wrong.
- **The NC axis is linked to I/O.** A simulated axis needs no I/O. A real axis must have
  its drive and encoder linked to the drive's process data (the axis's *Link To I/O*). If
  it was linked to the wrong channel, the wrong motor moves or nothing does.
- **The bus is up.** `ST_AxisStatus.IoDataInvalid` TRUE, or codes 0x4466, 0x4651 or 0x4655,
  mean the I/O data is not valid: the drive slave is not in OP or its working counter is
  bad. That is a bus problem: hand to **ethercat-diagnostics** and stop here.
- **Every mapped output in the drive's process data is linked.** An output entry that is
  mapped but linked to nothing is sent as 0 every cycle. The NC links only the entries it
  needs (controlword, set point); anything extra that was added to the mapping, such as a
  torque or current limit, a mode of operation or a digital output, is the user's to link.
  The classic case: a torque limit is mapped and left unlinked, so the drive gets a limit
  of 0. The axis enables and `MC_Power.Status` is TRUE, but the motor produces no torque:
  it does not move, or sags, and the position lag grows until 0x4550 or 0x435D. In XAE,
  look for output variables of the drive without a link, or an online value stuck at 0.
  Fix it by linking the entry to a PLC variable with a sensible value, or by removing it
  from the mapping and setting the value once in the drive's startup parameters, where the
  drive allows that. What the object means and its units are **cia402-motion**'s; which
  entries this drive can map, **ethercat-esi**'s.

## 1. Is an axis error pending?

`ST_AxisStatus.Error` and `ErrorId`, or `MC_ReadStatus.ErrorStop`. Look the code up.

- An axis error needs `MC_Reset` with a rising edge on `Execute`. Many drives are reset with
  it; some need their own reset as well. For a CoE drive whose fault stays latched, hand
  the drive side to **cia402-motion**.
- If the error comes back straight after the reset, the cause is still there. Don't loop
  the reset in code; find the cause.
- A function-block error (raised by the block, not the axis) clears when that block's
  `Execute` falls. The axis is fine; fix the inputs and trigger again.

## 2. Is `MC_Power` asking for everything?

- `MC_Power` is called **every cycle**, unconditionally, with `Enable` held TRUE. Calling it
  only inside a state of a sequence drops the enable when the sequence moves on, and a
  stalled PLC task drops it too (0x4260).
- **`Enable_Positive` and `Enable_Negative` are both TRUE** for normal operation. With only
  `Enable`, the first move is refused: 0x4357 (minus feed
  enable missing) or 0x4358 (plus), or 0x4223 / 0x422A at the start of a move. The two are
  easy to swap; check with the tool.
- **`Override` is 100.** It is a percentage applied to every move and defaults to 100.0;
  linked to a variable that sits at 0, every move starts and nothing moves.

## 3. `Status` stays FALSE with all enables set

`MC_Power.Status` reports the axis ready. On a digital drive it includes the drive's own
readiness; on an analog drive it can only report the control side.

- **The drive is not ready.** It is in fault, still booting, missing motor or feedback
  configuration, or has no DC-link voltage. For a CoE drive, the place to look is its
  state machine (statusword): hand to **cia402-motion**. For a Beckhoff drive, its
  diagnosis history in XAE or Drive Manager 2.
- **A hardware enable is missing.** `MC_Power` does not drive it. Two different cases:
  - a **plain enable output** that the PLC must set (an enable line on an analog drive or a
    terminal's enable bit). Setting it in the PLC program is the correct fix.
  - an **STO input or a safety circuit** that is open. That is safety hardware: diagnose and
    name it, **never propose bridging, forcing or simulating it in software**
    (`boundaries.md`). If you can't tell which case it is, ask before advising.
- **The axis error is back** (step 1).

## 4. `Status` is TRUE, but the axis does not move

| Check | How to see it |
|---|---|
| **`MC_Stop` still holds the axis.** It keeps the axis locked until its `Execute` goes FALSE after `Done`, and needs a few more cycles to release. | `ST_AxisStatus.MotionCommandsLocked`; error 0x42EF on the next command. Use `MC_Halt` for ordinary stops. |
| **The axis is a coupled slave** (gear or cam), so it is in protected mode. What a move does depends on the axis parameter *Allow motion commands to slave axes*: FALSE refuses it with 0x4B08; TRUE, which axes created in 4024.55 have, decouples the slave without an error and runs the move. | `ST_AxisStatus.ProtectedMode` or `Coupled`. Decouple first. If a slave drops out of sync instead, look for a motion block on it: `coupling.md`. |
| **The move never triggered.** `Execute` needs a rising edge; held TRUE it fires once. Re-triggering while the block is busy is ignored without an error. | twincat-st reviewer rule X11 catches level-driven `Execute`. |
| **The block is not called every cycle while busy.** | 0x4B66, or the block hangs with `Busy` TRUE. |
| **An input is invalid.** A velocity of 0 is not "use the default" (0x4231); acceleration 0 *is* (it takes the axis parameter). | The block's `ErrorID`. |
| **Outside a software limit**, or a target beyond one. | `SoftLimitMinExceeded` / `SoftLimitMaxExceeded`; 0x4460–0x4463. |
| **Another command owns the axis.** A newer command with the default `Aborting` mode replaces the running one, which then reports `CommandAborted`. | `CommandAborted` on the first block. Expected behaviour, not a fault: `axis-lifecycle.md`. |
| **Your application waits for `Homed`** and the axis came up not referenced (absolute encoder without retain data, or a fresh start). | `ST_AxisStatus.Homed`; 0x4002 at start-up. `homing.md`. |
| **A mapped output is unlinked and sent as 0**: a torque or current limit, so the motor has no torque. | Step 0, last item. Status TRUE, no motion, the lag grows. |
| **`MC_Jog` in a standard mode** uses the manual velocity from the axis parameters and ignores its `Velocity` input. If that parameter is tiny, the jog looks dead. | `MC_Jog.Mode`; the manual velocity parameters. |

## 5. It moves, then faults

| Code | Usual cause | Where |
|---|---|---|
| 0x4550 position lag | Window or filter time too tight for the dynamics; an untuned or wrongly scaled axis; a torque or current limit at 0 or too low (unlinked process data, step 0); a mechanical fault (blocked, brake still applied). | `axis-parameters.md`, "Position lag" |
| 0x4551 velocity lag | Same family, on the velocity. | as above |
| 0x435C not in target window in time | Target window or settling time too tight, or the axis hunts around the target. | `axis-parameters.md`, "Target window" |
| 0x435D motion not seen at the encoder | Encoder not linked, wrong encoder, scaling sign or factor wrong, or the motor does not turn (brake, STO). | `axis-parameters.md`, "Scaling" |
| 0x4650 drive dropped out of ready | Drive fault or lost enable during motion. | cia402-motion for CoE drives |

**Never fix a lag error by switching lag monitoring off or widening the window until it
goes away.** The monitoring is what stops an axis that cannot follow. Find out why the lag
is large; widen the window only to a value you can justify from the dynamics, and say so.

If a recording would settle it, say which channels to record (set and actual position,
position lag, set and actual velocity, torque or current) and hand the recording to
**twincat-scope**.

## 6. It moves, but wrong

- **Wrong distance or speed**: encoder scaling, or the reference velocity on a
  velocity-interface drive. Work it out from the mechanics: `axis-parameters.md`.
- **Wrong direction**: the direction is inverted in two places (encoder and drive) or in
  neither, or in the drive's own parameters as well as the NC.
- **Runs away or oscillates on enable**: a direction mismatch between drive and encoder
  gives positive feedback. Disable at once; check both inversions before re-enabling with
  reduced limits.
- **Jumps on enable or after homing**: on a CSP drive the target must equal the actual
  position when the drive enables; that is the drive side, **cia402-motion**.

## Don't rule out hardware

This page leans on configuration and code, because that is what can be checked from the
engineering PC. But a good share of "won't enable" and "faults when it moves" is hardware,
especially when the symptom started without a software change, or after work on the
machine. Keep it in the picture from the start, and keep it general: name the likely
area and how it shows up in TwinCAT, and leave the physical checks to the people on site.

| Area | How it can show up |
|---|---|
| Supply: mains or DC link, the 24 V control supply, a separate brake supply | drive not ready (`Status` FALSE), undervoltage 0x4631, drops out of ready under load 0x4650 |
| Holding brake not releasing | enables, then lag error or a stall at the first move; torque high, no motion |
| Motor or feedback cable, connectors, shielding | encoder errors 0x4464–0x4467, wire break or overcurrent 0x4632–0x4635, faults that come and go with movement or vibration |
| Mechanics: binding, a blocked axis, a slipping coupling or belt, a different gearbox after a repair | lag errors, overload 0x4636, the distance is wrong (scaling no longer matches the mechanics) |
| Limit switches and reference switches: wiring, normally open vs closed, a damaged sensor | homing errors 0x429C–0x429E, an axis that stops in one direction only |
| Temperature: drive, terminal or motor | overtemperature 0x4630, faults after running for a while |
| Bus wiring | `IoDataInvalid`, 0x4651 / 0x4655: **ethercat-diagnostics** |

- Look each code up with the tool, and read the drive's own diagnosis (its error history in
  XAE or its own tool) before assuming either a software or a hardware cause.
- Physical checks are for qualified people following the site's own procedures: the machine
  made safe and isolated, no work on live parts, no reaching into the machine's range of
  motion. Say that; don't give step-by-step electrical instructions.
- Never suggest bypassing, bridging or forcing a safety device, limit switch or enable
  circuit to narrow down a fault (`boundaries.md`).
