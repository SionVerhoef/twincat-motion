# Homing an NC axis

There is no single right way to home a TwinCAT NC axis. Shops use all six options below,
often several on one machine. Ask what the machine has (switch, hard stop, encoder zero
pulse, absolute encoder, a drive that homes itself) and what accuracy it needs, then pick.
Don't promote one option to the only correct answer.

| The axis has | Usual options |
|---|---|
| a reference switch or cam | 1 PLC-based, 2 `MC_Home` default, 3 step homing |
| a switch plus an encoder zero pulse, and needs repeatability | 2 `MC_Home` default (cam + sync pulse), 3 step homing, 4 touch probe |
| only a hard stop | 1 PLC-based, 3 `MC_StepBlock` |
| a latch input on the drive or terminal | 4 touch probe |
| a drive with its own homing (CiA 402 mode 6) | 5 drive-based |
| an absolute encoder | 6: no homing run, an offset set once |

Every option ends the same way: the axis has a known position **and** something records
that it is homed. Code that later moves to absolute positions must check that record before
it trusts the position.

Homing moves an axis into switches and hard stops. Propose the sequence; a person runs it,
first at reduced speed and torque. A reference switch is not a safety device, and homing
logic is not safe homing: `boundaries.md`.

## 1. PLC-based: move, stop, set position

The most transparent option, and the usual one in many shops: the PLC does the search with
ordinary move blocks and sets the position itself.

1. Enable the axis (`MC_Power.Status` TRUE). If the switch is already active, move off it
   first.
2. Move towards the switch at a low speed: `MC_MoveVelocity`, or `MC_Jog` in continuous mode.
3. On the switch edge, stop with `MC_Halt` (not `MC_Stop`: `axis-lifecycle.md`).
4. Wait for standstill.
5. Set the position with `MC_SetPosition` (`Mode` FALSE = absolute) to the reference value,
   with `Options.ClearPositionLag` TRUE so set and actual position agree.
6. Mark the axis homed.

**Accuracy.** Setting the position at standstill puts the zero where the axis stopped, which
is the switch edge plus the braking distance. That varies with speed and load. Better:
- read the actual position in the cycle the edge is seen, and after standstill call
  `MC_SetPosition` in relative mode (`Mode` TRUE) with `reference − position at edge`. The
  zero is then the switch edge, to within one PLC cycle × the search speed.
- or search fast, back off, and approach again slowly.
- for real repeatability, latch the edge in hardware (option 4).

**Marking homed.** Two ways, both in use:
- **your own flag**, set in step 6 and kept in your PLC code (the homing block or an axis wrapper). Simple and explicit; but
  `ST_AxisStatus.Homed` stays FALSE, so an HMI or code that reads the NC's flag sees "not
  homed".
- **`MC_Home` with `HomingMode := MC_ForceCalibration`**: no movement, no position change;
  it sets the NC's own homed state. Then `ST_AxisStatus.Homed` is the single record.

`MC_SetPosition` alone does not set the NC's homed state.

Template: `templates/FB_HomePlc.TcPOU` does steps 1–6 with the edge-accurate relative shift,
and marks homed either way (a parameter picks which).

**Hard stop instead of a switch.** Run into the stop with a reduced torque limit and detect
the stop (lag rising, velocity zero, torque at the limit). Plan what the position-lag
monitoring will do: it trips when the axis is held against the stop, so either the detection
must come first or the monitoring is handled deliberately for the duration of the search,
and restored afterwards. Option 3 (`MC_StepBlock`) does this for you.

## 2. NC homing with `MC_Home`

`MC_Home.HomingMode` in Tc2_MC2 has four values:

| Mode | Does |
|---|---|
| `MC_DefaultHoming` | runs the NC's homing sequence, configured in the **encoder** parameters |
| `MC_Direct` | sets the position to `Position` at once, no movement, and marks the axis homed |
| `MC_ForceCalibration` | marks the axis homed; no movement, position unchanged |
| `MC_ResetCalibration` | clears the homed state; no movement, position unchanged |

Older TcMC2 documentation listed modes such as absolute switch, reference pulse and block as
"not implemented". They do not exist in Tc2_MC2; step homing (option 3) covers them.
`Tc3_DriveMotionControl` has a different `MC_HomingMode` enum with the same name: check the
library before trusting an enum value (`out-of-scope.md`).

**The default sequence** (encoder parameter *Reference Mode*, default setting):

1. Move towards the reference cam at the homing velocity towards the cam (direction set by an
   encoder parameter). If the cam is already active at the start, skip to step 3.
2. On the cam's rising edge, stop.
3. Move off the cam in the sync-pulse direction at the homing velocity off the cam.
4. Wait for the cam's falling edge.
5. Arm the latch for the encoder's sync (zero) pulse; when it fires, stop.
6. At standstill, set the position to the reference position plus the braking distance, so
   the reference is exact even though the axis stopped a little further on.

`Axis.NcToPlc.HomingState` shows the phase (0 = done, 1–6 = the steps above).

Points that trip people up:

- **`bCalibrationCam` must carry the cam's digital input every cycle.** The NC sees the cam
  only through this input of `MC_Home`.
- **No cam, sync pulse only**: the PLC can fake the cam. Drive `bCalibrationCam` high when
  homing starts and low again when `HomingState` gets to 4 or above.
- **`Position`** is the reference position applied at the end. `DEFAULT_HOME_POSITION`
  takes the reference position from the axis parameters.
- **Errors**: 0x429C cam not found, 0x429D cam not released, 0x429E sync pulse not found.
  Look them up with the tool; the usual causes are a wrong search direction, a cam input not
  passed to the block, or an encoder whose zero pulse is not wired or not latched.
- The encoder's *Reference Mode* offers other sequences besides the default (for example a
  latch from the drive or terminal); which ones appear depends on the encoder type.
- Decouple a slave axis before homing it.

Template: `templates/FB_HomeNc.TcPOU` wraps `MC_Home` with the cam input, the faked cam for a
sync-pulse-only axis, and a run timeout.

## 3. PLCopen Part 5 step homing (`Tc3_MC2_AdvancedHoming`)

The `Tc3_MC2_AdvancedHoming` library splits homing into steps that can be chained:

| Block | Finds the reference at |
|---|---|
| `MC_StepAbsoluteSwitch` | an edge of a reference switch |
| `MC_StepLimitSwitch` | a limit switch used as the reference |
| `MC_StepBlock` | a hard stop (block detection) |
| `MC_StepReferencePulse` | the encoder's zero pulse, usually after a switch step |

The library also has blocks to finish or abort a homing sequence; check its block list on
your build.

- **A step can change position-lag monitoring while it runs**: block detection
  (`MC_StepBlock`) depends on it. Make sure monitoring is active again when the sequence
  ends, also when it is aborted some other way than through the library.
- **`DisableDriveAccess`**: FALSE for Beckhoff drives, where the library may change drive
  settings during the step; usually TRUE for third-party drives, where it cannot.
- Hard-stop homing needs a reduced torque limit so the stop is not damaged.

## 4. Touch-probe homing

The position is latched in hardware at the edge of a probe input or encoder zero pulse,
independent of the PLC cycle. Most accurate, and needs latch-capable hardware: a CoE drive
with its touch-probe objects (0x60B8 / 0x60B9) in the process data, an SoE drive with the
probe parameters in its telegram, or an encoder terminal with a latch.

1. Arm the latch: `MC_TouchProbe`, with a `TRIGGER_REF` describing the probe input and edge.
2. Move slowly over the sensor.
3. On `Done`, `RecordedPosition` holds the position at the edge. Stop with `MC_Halt`.
4. Shift the position so the edge becomes the reference: `MC_SetPosition` in relative mode
   with `reference − RecordedPosition`.
5. Mark homed, as in option 1.

To cancel an armed latch, call `MC_AbortTrigger` with the same `TRIGGER_REF`; otherwise no
new latch can be armed. The drive side of touch probe (objects, modes) is **cia402-motion**.

## 5. Drive-based homing (CiA 402 mode 6)

The drive runs its own homing method (object 0x6098) in homing mode (0x6060 = 6). The methods,
their numbers and the statusword bits are **cia402-motion**'s; vendors also add their own
method numbers, so take the method from that drive's documentation.

The NC side, which this skill owns:

- **The NC owns the drive's controlword and set point** through the process data. Homing in
  the drive needs a way for the PLC to take the drive for the run (mode, method and start
  bit, by mapped PDO or SDO) and hand it back to cyclic position mode afterwards. Plan that
  hand-over explicitly; two writers on one controlword is a classic fault.
- **The actual position jumps** when the drive sets its new zero. Before the NC moves the axis
  again, set position and actual position must agree: re-enable with the lag cleared
  (`MC_SetPosition` or `MC_Home` with `MC_Direct` and `Options.ClearPositionLag`), or the
  axis jumps or trips on position lag.
- **Mark homed** in the NC or in your own flag, as in option 1; the drive's "homing attained"
  bit does not reach `ST_AxisStatus.Homed` by itself.
- On a CSP drive the target position must equal the actual position when position mode
  resumes (cia402-motion).

## 6. Absolute encoders

No homing run. The encoder knows its position at power-up; the offset between encoder zero
and machine zero is set once during commissioning:

- in the **encoder offset parameter** (a configuration change, `config-changes.md`; survives
  restarts), or
- at runtime with `MC_SetPosition`. Whether a runtime offset survives a restart depends on the
  retain setup: verify it on the target, don't assume it.

**NC retain data.** When the travel spans more than the encoder's own range (a single-turn
encoder, or a multiturn whose turns overflow), the NC has to remember the overflow across a
power cycle. That needs NC retain data, set on the SAF task, and retain storage on the
controller.

- Without valid retain data (always the case on the very first start), the outcome depends
  on the retain setting: the strictest one (*Load/Store* in our sources) refuses to start;
  otherwise the NC starts, reports 0x4002, and absolute axes come up **not homed**. 0x4002
  once on the first start is expected; it should not repeat. Check the setting names on
  your build.
- When retain data is missing and the NC starts, absolute axes are not homed. The application must
  check `ST_AxisStatus.Homed` at start-up and refuse absolute moves until the axis is
  referenced again.

Encoder reference system (incremental or absolute, and its overflow handling) is an encoder
parameter; read it with `axis_xti.py show`.
