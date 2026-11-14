# Axis parameters that decide the outcome

An NC axis has an axis part, an encoder, a drive and a controller, each with its own
parameter page in XAE. This page covers the parameters that most often decide whether an axis
works. Parameter names below are as XAE shows them on 3.1.4024; the wording varies slightly
between builds. Where it helps, the `.xti` path that `scripts/axis_xti.py` prints is given
too.

**Read the explicit values with the tool, not by eye**: `axis_xti.py show` lists what an axis
sets, `lint` checks it, `diff` shows what changed. An `.xti` stores only non-default values,
so anything not listed is at its TwinCAT default. (One value XAE 4024.55 writes into every new
axis although it is not the default: `AxisPara/OtherSettings@AllowMotionCmdToSlave="true"`;
see `coupling.md`.) XAE also writes `<ParameterChanged>` elements into `AxisPara` and
`EncPara` whenever a parameter is edited in its UI, and drops some or all of them on later
saves; they are bookkeeping, not settings, and `axis_xti.py` keeps them apart. Changes go out as a parameter-change table
or an Automation Interface script; a direct `.xti` edit only after the user explicitly agrees:
`config-changes.md`.

## First question: who closes the position loop?

| Drive runs | Who closes the position loop | The NC position controller (Kv, Tn, ...) |
|---|---|---|
| a **position** set point: CoE CSP (the AX8000 too), AX5000 in position mode, EL72x1 in position mode | the drive | **has no effect.** Tune in the drive (Drive Manager 2, TE5960 autotuning, the drive's own tool) |
| a **velocity** set point: CoE CSV, analog ±10 V, a terminal in velocity mode | the NC | is the loop. Kv, and the reference velocity, matter |

Tuning NC Kv on a CSP axis is a common and long detour. Find out the mode first: for a CoE
drive, the mapped set point (target position 0x607A means CSP, target velocity 0x60FF means
CSV) and the mode of operation. Mode details are **cia402-motion** territory.

On a CSP axis the NC still computes the position lag (set position minus actual position),
and still monitors it. The actual position arrives a few bus cycles after the set point
was sent, so without dead-time compensation the NC sees a lag that grows with speed even
when the drive follows perfectly. The compensation is an **encoder** setting: in XAE, open
the axis, expand it, select its encoder (*Enc*) and use the *Time Compensation* tab. Set it
from the drive's documentation; Beckhoff's own example for an EL72x1 uses a few cycles.
There are three time-compensation places, all checked on 4024.55 with a simulated axis:

| XAE | `.xti` path |
|---|---|
| Axis > *Enc* > *Time Compensation* tab: mode, *IO Time is absolute*, *Encoder Delay in Cycles*, *Additional Encoder Delay* | `Encoder/EncPara/TimeComp@TimeCompMode`, `@IoTimeAbsolute`, `@EncDelayCycles`, `@AdditionalTimeShift` |
| Axis > *Drive* > *Time Compensation* tab (position mode only): mode, *IO Time is absolute*, *Task Delay in Cycles*, *Drive Delay in Cycles*, *Additional Drive Delay* | `Drive/DrvPara/TimeComp@TimeCompMode`, `@IoTimeAbsolute`, `@TaskDelayCycles`, `@DriveDelayCycles`, `@AdditionalTimeShift` |
| Axis > *Parameter* > *Other Settings* > *Dead Time Compensation (Delay Velo and Position)*, in seconds | `AxisPara/Dynamic@DelayTime` |

The encoder one is the setting meant above. XAE added `Drive/DrvPara/TimeComp@TaskDelayCycles="1"`
to an axis file on its first save after (probably) the first activation, although nobody had
touched a drive setting, and shows *Task Delay in Cycles* = 1. Whether 1 is the built-in
default is not settled; don't read that attribute in a diff as a user's change.

**A simpler alternative: take the following error from the drive.** The drive closes the
loop, so it knows the real following error with no bus delay in it. Map it into the process
data (on a CoE drive, the following-error actual value, 0x60F4) and link it to the PLC for
display, logging and your own checks, and let the drive's own following-error monitoring do
the tight supervision (its window and time, 0x6065 / 0x6066 on a CoE drive). Then the NC's
lag no longer needs to be exact, and you can skip tuning the dead-time compensation. If you
go this way:

- keep NC position-lag monitoring **on**, with a window sized to cover the transport delay
  at maximum speed, so the NC still stops an axis that does not follow at all;
- make sure the drive's monitoring is really set up, not left at a default that never trips;
- check that the drive's value is in units you can read (drive units, not NC units), and
  that the entry is linked: an unlinked input simply stays 0 (`triage.md`, step 0).

What the drive objects mean is **cia402-motion**'s; whether this drive can map them,
**ethercat-esi**'s.

## Beckhoff AX8000 on the NC

The AX8000 axis modules are CoE drives with the standard CiA 402 objects (0x6040, 0x6041,
0x6060 …), not SoE drives like the AX5000. Beckhoff's object dictionary lists no second
profile. Three of its settings matter to the NC axis:

- **Position scaling, 0x3005:01.** The drive sends position in units it sets itself: by
  default 2^20 counts per 360° of the motor. The NC encoder scaling must use the same
  resolution (Example 1 below). If someone changes 0x3005:01 in the drive, re-check the NC
  factor.
- **Fault reaction, 0x605E.** Besides the profile's values, it offers −1, "NC handling".
  The default is 2, a ramp closed in the drive. Find out which one is set before you explain
  how the axis stopped after a fault.
- **No drive homing.** Only cyclic modes exist (8–11 and 15, plus vendor modes), with no
  homing mode, so the NC or the PLC homes the axis (`homing.md`, options 1–4 and 6). Mode 6,
  drive-based homing (option 5), does not apply.

Sources: Beckhoff InfoSys, AX8xxx object dictionary v1.7.0 (`ax8xxx_objects`), pages
18797721227, 18797826827, 18797962251, 18797964299, read 2026-11-08. Drive-side details
(modes, quick stop, statusword bits, PDO modules) are in **cia402-motion**'s Beckhoff notes.

## Beckhoff EL70x7 stepper terminals on the NC

An EL70x7 drives a stepper motor straight from the terminal. Four things decide how it behaves
under an NC axis:

- **The mode follows the process data.** Operation mode 0x8012:01 defaults to *Automatic*:
  the terminal picks *velocity direct* or *position controller* from the predefined PDO
  assignment, and picks again whenever that assignment changes. So editing the terminal's
  process data can silently switch the mode, and with it who closes the position loop (first
  question above). After any process-data change, check which mode is now active. Set
  0x8012:01 explicitly if you want the mode pinned.
- **Velocity scaling.** In velocity mode, the output value ±32767 means ±100 % of the speed
  range in 0x8012:05 (default 2000 full steps per second). The NC reference velocity must be
  that speed range converted to axis units, or the feed-forward is off and the lag grows with
  speed (*Reference velocity* below). For example, with a 200-step motor on a 5 mm lead
  screw, 2000 full steps/s is 10 rev/s, so the reference velocity is 50 mm/s. If someone
  changes 0x8012:05, re-check the NC value.
- **Positioning interface: an alternative to the NC, not a way to use it.** The terminal can
  also run moves itself through its positioning interface (objects 0x7020 / 0x6020), with
  its own homing (a "calibration" against a cam it polls). That is a separate way to run the
  motor with its own PLC code, not something under an NC axis. Find out which way the
  machine uses before debugging an axis that "won't move".
- **Lost steps are not an NC error.** The terminal reports a stall in a status bit. It
  becomes a terminal error only when 0x8012:0A enables that. Unless an encoder is fitted and
  used as the NC encoder, the NC counts the steps it commanded, so lost steps do not show
  up as position lag either.

When the NC axis is linked to the terminal, XAE offers the drive type *CANopen DS402 or
EtherCAT CoE* for it.

Sources: Beckhoff InfoSys, EL70x7 documentation v2.3.0 (2026-07-09), pages 1305123211,
11698650507, 11686582923, 1305115659, read 2026-11-08. Not tested on hardware. The example
numbers are illustrative.

## Scaling

The **encoder scaling factor** turns encoder increments into axis units: units per increment.
TwinCAT splits it into a **numerator** and a **denominator** (default 1). Use both to keep
the ratio exact; a rounded single factor drifts over long travel and breaks modulo axes.

Formula: `numerator / denominator = (units per load revolution) / (gear ratio × increments
per motor revolution)`, where the gear ratio is motor turns per load turn.

**Example 1: linear axis.** Ball screw with 10 mm lead, gearbox 3:1, motor feedback with
2^20 = 1,048,576 increments per motor revolution.

- numerator = 10 (mm per screw revolution)
- denominator = 3 × 1,048,576 = 3,145,728
- factor = 10 / 3,145,728 ≈ 3.1789e-6 mm per increment. Typed as one rounded number it
  would be off by a few parts per million, which is a visible error over a long stroke.

**Example 2: rotary table, modulo.** 360° per table revolution, gearbox 50:1, motor encoder
2^17 = 131,072 increments per revolution.

- numerator = 360, denominator = 50 × 131,072 = 6,553,600
- set the modulo factor to 360 and use `MC_MoveModulo` for positions within a turn.

**Example 3: a third-party CoE drive that scales itself.** Some drives can be set to report
position in their own user units (gear and feed objects in the drive). Then the NC factor is
units per *drive* unit, for example 0.001 mm. Scale in one place only: scaling in both the
drive and the NC multiplies, and a drive reporting raw counts while the NC assumes user units
is off by orders of magnitude. The drive side is **cia402-motion**; the drive's actual
resolution comes from its ESI or manual (ask **ethercat-esi**).

Check a scaling by commanding a short, slow move at reduced limits and measuring it, not by
reading the position display: a wrong factor makes the display agree with itself. On a
velocity-interface axis it also shows in the lag: the feed-forward is off by the same factor,
so the lag grows in proportion to velocity. A factor too small (each increment counted as
less travel than it is) makes the axis lag; too large makes it run ahead of the set point
(negative lag).

**Direction.** Encoder direction and motor polarity can each be inverted. They must agree:
invert both or neither, and not again in the drive's own parameters. A mismatch gives
positive feedback on a velocity-interface drive, and the axis runs away on enable.

## Reference velocity (velocity-interface drives only)

The **reference velocity** is the axis velocity, in units per second, that the drive reaches
at full-scale command (at the configured output ratio, normally 1.0). The NC uses it to turn
a velocity set point into a drive command.

**Example 4.** Analog drive, ±10 V = 3000 rpm. Mechanics of example 1 (10/3 mm per motor
revolution):

- reference velocity = 3000 / 60 × 10 / 3 = 166.67 mm/s
- maximum velocity below it, for example 150 mm/s, so the position controller has headroom.
  `axis_xti.py lint` flags a maximum above the reference velocity (rule D2).

A wrong reference velocity makes the feed-forward wrong. The position controller covers the
difference, so the axis still arrives, but the lag grows with speed. A lag roughly
proportional to velocity is the signature. On a CSP axis the reference velocity has no part
in the set point.

## Velocities and dynamics

- **Maximum velocity**: moves above it are rejected or limited.
- **Manual velocity fast and slow**: what `MC_Jog` uses in its standard modes.
- **Homing velocities** towards the cam and off the cam: what `MC_DefaultHoming` uses.
- **Default acceleration, deceleration and jerk**: used when a move's dynamics input is 0.

`axis_xti.py lint` checks that the other velocities do not exceed the maximum (rule V2).

## Monitoring

| Monitoring | What it does | Error |
|---|---|---|
| **Position lag** (enable, maximum value, filter time; `.xti` `Controller/CtrPara/PosDiffControl`, absent = enabled) | raises an error if the lag stays above the maximum for longer than the filter time | 0x4550 |
| **Velocity lag** | the same on velocity | 0x4551 |
| **Position range** (window) | sets `InPositionArea` when the axis is near its target | — |
| **Target position** (window, monitoring time) | sets `InTargetPosition` once the axis has stayed inside the window for the monitoring time | — |
| **In-target alarm** (timeout) | raises an error when the axis has not settled in the target window in time | 0x435C |
| **Motion monitoring** | raises an error when a commanded motion does not show at the encoder | 0x435D |
| **Software limits** min and max (enable, position) | rejects targets outside, stops an axis that reaches them | 0x4460–0x4463; invalid settings 0x4420 / 0x4421 |

### Position lag

The lag window protects the machine: it stops an axis that is blocked, stalled, wrongly
scaled or not following. So:

- **Don't switch it off** to make an error go away, not even "temporarily for
  commissioning" without saying what replaces it. `axis_xti.py lint` warns when it is off
  (rule C1).
- **Don't widen the window** until the error stops. A lag caused by friction, a dragging
  brake, a wrong gear ratio, or a current limit is a mechanical or sizing fault, not a
  tuning problem.
- **Do size it from the dynamics.** Record the lag during the worst move (fastest, hardest
  acceleration) with Scope (hand the recording to **twincat-scope**), then set the window
  with a margin you can justify and a short filter time.
- On a CSP axis check the dead-time compensation first, or read the drive's own following
  error (both above).

### Target window

A window too tight for the mechanics (backlash, encoder resolution, load) means
`InTargetPosition` never comes and the in-target alarm fires. A window too wide makes code
that waits for `InTargetPosition` move on while the axis is still settling. Size it from the
process tolerance.

### Software limits

Software limits in the NC are functional limits, not safety. Hardware limit switches and any
safety function stay as they are (`boundaries.md`). With limits enabled, the minimum must be
below the maximum (rule E2). An axis that is not homed has no trustworthy position, so its
limits mean little until it is.

## Controller (velocity-interface drives)

- **Kv** (position loop gain) is the main setting. Too low: large lag and soft response.
  Too high: overshoot and oscillation.
- Tn, Tv, Td, dead band and backlash compensation exist for special cases. Change them one
  at a time, with a recording before and after.
- None of this applies on a CSP axis (first section).

Tuning values come from the machine, not from this skill. Never present a number as "the
right Kv"; give the method and let the commissioning engineer choose the value.
