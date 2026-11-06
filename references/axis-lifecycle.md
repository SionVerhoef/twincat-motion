# Axis lifecycle and how Tc2_MC2 behaves

This page covers the axis level: states, the order of commands, and where Tc2_MC2 adds to or
differs from the generic PLCopen picture. The coding rules for any `MC_` block (edge-driven
`Execute`, unconditional call, handling `Done`/`Error`/`CommandAborted`) belong to the
**twincat-st** skill; apply them, don't restate them.

## The order of commands

1. **`MC_ReadStatus` / `Axis.ReadStatus()`** first in every cycle that uses the axis.
2. **`MC_Reset`** if an axis error is pending (rising edge on `Execute`).
3. **`MC_Power`** with `Enable`, `Enable_Positive`, `Enable_Negative` held TRUE, called
   every cycle. Wait for `Status` TRUE; it is the gate for everything below.
4. **Homing**, if the application needs a referenced position and the axis is not already
   homed (`ST_AxisStatus.Homed`): `homing.md`.
5. **Moves**: `MC_MoveAbsolute`, `MC_MoveRelative`, `MC_MoveVelocity`, `MC_MoveModulo`,
   `MC_Jog`, couplings.
6. **Stop** with `MC_Halt` for ordinary stops. `MC_Stop` only where the axis must stay locked
   against other commands (see below).
7. **Disable** by dropping `MC_Power.Enable`. Its `BufferMode` decides when: `Aborting`
   (default) drops the enable at once, `Buffered` waits until the running command is done.

## The states

Tc2_MC2 tracks each axis in the PLCopen states. `ST_AxisStatus` has one flag per state, and
`MotionState` holds the state as an enum.

| State | The axis is | Gets there by | Leaves by |
|---|---|---|---|
| Disabled | not enabled; no command moves it | start-up; `MC_Power.Enable` FALSE without an error | `MC_Power.Enable` TRUE → Standstill (or ErrorStop on an error) |
| Standstill | enabled, not moving | `Status` TRUE; any move or stop finished | any motion command |
| Homing | running a homing command | `MC_Home` | homing done → Standstill |
| DiscreteMotion | moving to a target | `MC_MoveAbsolute`, `MC_MoveRelative`, ... | target reached → Standstill; another command |
| ContinuousMotion | moving with no target | `MC_MoveVelocity`, endless jog | `MC_Halt`, `MC_Stop`, another command |
| SynchronizedMotion | a coupled slave | `MC_GearIn`, `MC_CamIn` | `MC_GearOut`, `MC_CamOut`; a move only if the axis parameters allow motion commands on a slave |
| Stopping | in the ramp of `MC_Stop` | `MC_Stop` | standstill reached **and** `MC_Stop.Execute` FALSE → Standstill |
| ErrorStop | stopped by an axis error, commands blocked | any axis error, from any state | `MC_Reset` → Standstill (if still enabled) or Disabled |

A master stays in its own state while slaves couple to it. Read-only blocks (`MC_ReadStatus`,
`MC_ReadParameter`, `MC_ReadActualPosition` and similar) never change the state.

## Where Tc2_MC2 behaves in ways people don't expect

### `MC_Stop` locks the axis

`MC_Stop` sets `Done` when the axis stands still, but `Busy` and `Active` stay TRUE and the
axis refuses every other motion command (error 0x42EF) until `Execute` goes FALSE. Release is
not instant: `Busy` stays TRUE for some cycles after the falling edge, and the block must
keep being called until it drops. `MC_Reset` also releases it. `ST_AxisStatus.MotionCommandsLocked` shows the lock.

Using `MC_Stop` for a normal stop and holding its `Execute` is the classic "the axis won't
move again" bug. Use `MC_Halt`, which stops without locking.

Neither is a safety stop. A stop commanded by the PLC is functional control, whatever ramp
it uses: `boundaries.md`.

### The status is not refreshed by itself

`ST_AxisStatus` (and `Axis.Status`) is only updated when `MC_ReadStatus` (with `Enable`
TRUE) or `Axis.ReadStatus()` runs. Call it once at the start of every PLC cycle that reads
the axis; otherwise code decides on last cycle's or last hour's state. `NcCycleCounter`
inside it shows whether the NC is updating at all.

### Inputs latch on the rising edge

A block reads its inputs when `Execute` rises. Changing `Position` or `Velocity` while it is
busy does nothing, and a second rising edge while busy is ignored without an error. To change
the target of a running move, trigger **a second instance** with the new values; with the
default `Aborting` mode it takes over and the first reports `CommandAborted`.

A falling `Execute` resets the outputs but does **not** cancel the command. If `Execute`
falls before the command ends, the block still shows `Done`, `Error` or `CommandAborted`
for one cycle at the end.

### Zero means different things

- On a move or `MC_Jog`, a dynamics input (`Acceleration`, `Deceleration`, `Jerk`) of 0
  means "use the default from the axis parameters".
- On `MC_Halt` and `MC_Stop`, a deceleration or jerk of 0 (or less) takes the values of the
  last move instead, and a stop never ramps more gently than the move it ends.
- A `Velocity` of 0 on a move is an error (0x4231), not a default.

### Buffer modes

`BufferMode` decides what a new command does to a running one.

| Mode | The new command |
|---|---|
| `MC_Aborting` (default) | takes over at once; the running command reports `CommandAborted` |
| `MC_Buffered` | waits until the running command is done; starts from standstill |
| `MC_BlendingLow` / `High` / `Previous` / `Next` | waits, but passes through the previous target without stopping, at the lower, higher, first or second command's velocity |

- Because `Aborting` is the default, **`CommandAborted` on the first of two moves is
  expected**, not a fault. Code that treats it as an error stops a working sequence.
- Only one command can wait. A second buffered command while one is already waiting is
  rejected with 0x4292; an aborting command always gets through and discards both.
- A buffered command cannot wait behind an endless move (`MC_MoveVelocity`): it takes over
  at once, as if aborting.
- A buffered sequence needs at least two block instances, alternating: a busy instance
  cannot be triggered again.
- `MC_Home` has a `BufferMode` input that is not implemented, and its `Active` output is not
  implemented either.

Coordinated multi-axis paths are NCI, not PTP blocks: `out-of-scope.md`.

### Four kinds of error

| Kind | Example | How it clears |
|---|---|---|
| Function block | invalid input | by itself when `Execute` falls; fix the input and trigger again |
| Communication | the block cannot reach the axis | no reset; it is configuration. Fix, activate, trigger again |
| Axis | position lag, software limit | `MC_Reset` |
| Drive | drive fault | often with `MC_Reset`; some drives need their own reset (cia402-motion) |

The code number tells you which kind it is: look it up with `scripts/nc_error.py`.

### `MC_Jog` modes

`MC_JOGMODE_STANDARD_SLOW` and `MC_JOGMODE_STANDARD_FAST` take velocity and dynamics from the
axis's manual-motion parameters and ignore the block's `Velocity` input.
`MC_JOGMODE_CONTINOUS` (spelled that way in the library) uses the inputs. `MC_JOGMODE_INCHING`
and `MC_JOGMODE_INCHING_MODULO` move a set distance per button press.

### `MC_Power` details

- `Override` is a percentage (0–100, default 100) applied to every move on the axis.
- `Status` is the readiness of the axis, including the drive's on digital drives. On an
  analog drive it can only report the control side.
- The hardware enable of a drive is not driven by `MC_Power`: `triage.md`, step 3.

## Timing

- The NC's SAF task runs the commands, set-point generation and position control; the SVB
  task prepares commands. A command issued by the PLC takes effect in a later SAF cycle, so
  a few cycles between "triggered" and "moving" is normal.
- Code that does arithmetic on axis data each cycle (set points, compensation) belongs in a
  PLC task at the NC's cycle time; at a slower PLC cycle it samples and drifts.
- TwinCAT 4026 handles ADS requests at the start of the SAF cycle; 4024 does it at the end.
  Code that relies on the exact cycle in which an ADS write takes effect can behave
  differently after an upgrade.
