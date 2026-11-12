# Boundaries: safety, and which skill owns what

## Safety: this skill does not author safety functions

Read this whenever a task touches STO, SS1, SS2, SLS, SBC, safe homing, safe speed, an
emergency stop, a guard door, TwinSAFE or FSoE, or a SIL, PL or Category claim.

**An NC stop is not a safety stop.** `MC_Stop`, `MC_Halt`, dropping `MC_Power.Enable`, a
software limit and a lag error are functional control: standard software on a standard
controller over a standard bus. Any software fault, wrong link or wrong parameter defeats
them. They are not safety-rated, whatever ramp they use.

A safety function needs safety-rated hardware (the drive's STO inputs, a safety relay or
controller, FSoE devices), a risk assessment, a design to the required performance level or
SIL (ISO 13849-1 or IEC 62061), and validation signed off by a competent person. An agent
provides none of these.

**Never:**
- write, sketch or "start" logic that implements a safety function, in PLC code or anywhere
  else. This holds when there is no safety PLC, when one is "too expensive" and when it is
  "only for testing".
- call an NC stop, a software limit or homing "safe".
- advise bridging, forcing, simulating or muting an STO input, a safety-rated enable, a
  limit switch or any safety device, including to get an axis to enable during
  commissioning. (A plain enable output that the PLC is simply meant to set is not a safety
  device; `triage.md`, step 3.)
- configure or change TwinSAFE, FSoE or a drive's safety parameters.
- state that anything achieves a SIL, PL or Category.

**You may:**
- explain how a missing hardware enable or open STO shows up in TwinCAT (`MC_Power.Status`
  FALSE, drive not ready; 0x4225 when a move starts on a drive that is not ready, 0x4650
  when it drops out during motion) and diagnose an axis that will not enable because of it.
- read an existing safety configuration so the user understands it.
- write the functional part (stop the axis with a ramp, report the state to the HMI),
  labelled as not safety, next to a pointer to the safety controller that must do the real
  job.

When declining, say what the hardware route is and offer the functional part. Don't lecture.

## This skill never moves an axis

Propose jog, move, homing and enable sequences as code or as steps; a person at the machine
runs them, with reduced limits first, within reach of the stop. Never send a motion command,
activate a configuration or write a parameter to a running system over ADS or any other
route. Never claim code compiled or ran unless it did, and say how it was checked: reviewed,
or run against a simulated axis, is not run on the machine.

## Which skill owns what

This skill owns the TwinCAT NC side: the NC axis and its parameters, `Tc2_MC2` blocks at the
axis level, NC error codes, homing in the NC, coupling, the `.xti` axis files.

| When the question is about | Hand to | The seam |
|---|---|---|
| The drive's own state machine (statusword, controlword), why it never reaches Operation enabled, modes of operation, CiA 402 homing methods, touch-probe objects, the drive's user units | **cia402-motion** | `MC_Power.Status` triage starts here and hands over at "the drive is not in Operation enabled". This skill keeps the NC drive type and which NC parameters matter in CSP vs CSV |
| Slaves not in OP, working counter, lost frames, DC sync, AL status codes, SDO aborts, a mapping the slave rejects | **ethercat-diagnostics** | NC errors 0x4466, 0x4651, 0x4655 and `IoDataInvalid` mean the I/O data is bad: that is the bus, go there |
| What this device supports: objects, data types, PDO structure, startup lists, the ESI file | **ethercat-esi** | Use its facts for drive process data and startup parameters instead of guessing |
| Writing or reviewing PLC code: `Execute` edges, call sites, `CommandAborted` handling, OOP shape | **twincat-st** (and its reviewer) | This skill says *what* the axis code must do; twincat-st says how to write it. Its rule X11 catches level-driven `Execute` |
| Diagnosing from a TwinCAT Scope recording, or building one | **twincat-scope** | This skill names the channels (set and actual position, lag, set and actual velocity, torque) and interprets the conclusion |

**One master per drive.** A drive linked to an NC axis is commanded by the NC through the
controlword (0x6040). Never also drive it from PLC code that writes the controlword itself,
such as cia402-motion's `FB_Cia402Axis`: the two overwrite each other. Choose one per drive:
NC axis with `Tc2_MC2`, or PLC-direct CiA 402 with the axis unlinked from the NC.

**If a sibling skill is not installed**, say which one would own the question, answer only the
TwinCAT NC part, and say that the rest is generic. For device facts without ethercat-esi,
point at the drive's CoE tab in XAE or its ESI file rather than guessing an object or a type.

## Out of scope

MC3 (`Tc3_Mc3*`), kinematics (TF511x), the Advanced Motion Pack (TF5400, TF5410, TF5420),
NCI/CNC, XTS, XPlanar, hydraulics and `Tc3_DriveMotionControl`: `out-of-scope.md`.
