---
name: twincat-motion
description: "Load before answering, or opening any file, about a Beckhoff TwinCAT 3 NC axis or Tc2_MC2 motion code: NC behaviour hides in axis parameters and look-alike error codes that models get wrong; this skill holds checked facts, an NC error table and an .xti lint and diff tool. Covers an axis that won't enable or move, MC_ blocks (MC_Power, MC_Home, MC_MoveAbsolute, MC_Halt, MC_Stop, MC_Reset) and axis wrappers, NC error codes, homing, scaling and controller parameters, gearing and cam coupling (MC_GearIn, MC_CamIn: a slave that jumps, lags or drops out), touch probe and registration (MC_TouchProbe, MC_PhasingRelative), and reading, linting or diffing any _Config/NC/Axes .xti file, also two versions of one. Not for Structured Text that only mentions an axis (twincat-st), a CiA 402 statusword or 0x6098 on its own (cia402-motion), AL status codes or working counters (ethercat-diagnostics), ESI files (ethercat-esi), TwinCAT CNC, or TwinSAFE design; never writes safety functions such as STO."
---

# twincat-motion

> **Reference material only. Not for safety functions.** Motion configuration must be
> reviewed and validated by a qualified engineer before it runs on a machine.

## Goal

Get a TwinCAT NC axis configured, enabled, homed and moving correctly, and diagnose why it
is not.

**Scope and safety.** Output is a draft for a qualified engineer. Never generate or modify
logic that implements a safety function; refer to the safety controller instead. When
proposing motion code, always state the assumed units, limits and enable sequence, and tell
the user to test with reduced limits. Never claim code is verified unless it was run on
hardware.

## Rules that override everything else

1. **Never author a safety function, and never work around one.** An NC stop, a software
   limit or homing is not safety. A missing hardware enable or open STO is diagnosed and
   named, never bridged, forced or simulated: `references/boundaries.md`.
2. **Never move an axis or change a running system.** Propose motion as code or steps that a
   person runs, at reduced limits first. No motion commands, no ADS parameter writes, no
   activating a configuration.
3. **Never edit an `.xti` file without an explicit go-ahead.** Configuration changes go out
   as a parameter-change table or an Automation Interface script that a person applies. A
   direct edit only when the user agrees to that change, with XAE closed, the file committed
   and a diff afterwards: `references/config-changes.md`.
4. **Look up every NC error code with the tool.** Neighbouring codes mean different things.
5. **Check which stack before answering.** This skill covers classic NC with `Tc2_MC2`.
   `Tc3_Mc3*` or `McToPlc` is MC3, and 0x81xx codes are MC3 or the Advanced Motion Pack; NCI, XTS, XPlanar, kinematics and the Advanced
   Motion Pack are out too. Say so, don't answer from NC2 knowledge:
   `references/out-of-scope.md`.
6. **Ask who closes the position loop before tuning.** With a position set point (CSP) the
   drive closes it and the NC Kv has no effect: `references/axis-parameters.md`.
7. **Triage before advice.** For "won't enable / won't move / faults", work through
   `references/triage.md` in order; a later step's fix is wrong while an earlier one is open.
8. **Never switch off or widen position-lag monitoring to clear an error.** Find the cause;
   size the window from the measured dynamics and say so.

## Tools

Both scripts need only Python 3.8+ (`py -3` on Windows).

```bash
python3 scripts/nc_error.py 0x4550          # hex as InfoSys prints it; also 16#4550
python3 scripts/nc_error.py 17744 4357      # decimal ErrorID from a watch; bare 4 digits = hex
python3 scripts/nc_error.py --list          # the curated codes
```

Run it for every NC error code instead of answering from memory: neighbouring codes
(0x4357 / 0x4358, 0x4223 / 0x4225) mean different things. A code outside the curated table
gets its family, what part of the family it falls in, and the InfoSys page. Say that the
meaning was not looked up; never borrow a nearby code's meaning. 0x81xx is MC3, which this
skill does not cover. `--json` gives machine-readable output.

`scripts/axis_xti.py` reads NC2 axis files (`_Config/NC/Axes/*.xti`) without XAE:

```bash
python3 scripts/axis_xti.py show "_Config/NC/Axes/Axis 1.xti"   # explicit parameters
python3 scripts/axis_xti.py lint _Config/NC/Axes                 # every axis in a folder
python3 scripts/axis_xti.py diff old.xti new.xti                 # e.g. old from git show
python3 scripts/axis_xti.py diff old.xti new.xti --table         # as a parameter-change table
python3 scripts/axis_xti.py diff old.xti new.xti --ai-csv produced.xml changes.csv
```

An `.xti` stores only non-default values and the tool has no defaults table: an absent
parameter is at its TwinCAT default (one exception: XAE 4024.55 writes
`AllowMotionCmdToSlave="true"` into every new axis, although the default, and an absent
attribute, is FALSE), lint checks explicit values only, and a clean lint is
not a full audit. Say so when you report a result. The tool never writes an `.xti`;
propose changes as a parameter-change table or an Automation Interface script
(`references/config-changes.md`). `diff --table` and `diff --ai-csv` produce either from two
versions of an axis; `--ai-csv` needs the target axis's produced XML.

## Where to read next

Load a reference when the task reaches it, not all of them up front.

| Task | Read |
|---|---|
| Axis won't enable, `MC_Power.Status` stays FALSE, won't move, faults, moves wrong | `references/triage.md` first |
| Order of commands, axis states, `MC_Stop` vs `MC_Halt`, `ST_AxisStatus`, buffer modes, `CommandAborted`, error kinds, `MC_Jog` modes | `references/axis-lifecycle.md` |
| Scaling, reference velocity, CSP vs velocity mode, lag / target / soft-limit monitoring, Kv | `references/axis-parameters.md` |
| Homing: PLC-based, `MC_Home`, step homing, touch probe, drive-based, absolute encoders and retain data | `references/homing.md` |
| Gearing, cam plates, flying saw, phasing, `MC_MoveSuperImposed`, touch-probe registration, external set points; a slave in protected mode | `references/coupling.md` |
| Writing PLC code for an axis: a wrapper FB, PLC-based or `MC_Home` homing | `templates/README.md`, then the template |
| Proposing a configuration change; Automation Interface | `references/config-changes.md` |
| STO, safe stop, E-stop, SIL/PL; which sibling skill owns what | `references/boundaries.md` |
| MC3, NCI/CNC, XTS, XPlanar, kinematics, TF54xx, hydraulics, `Tc3_DriveMotionControl` | `references/out-of-scope.md` |

## Hand-offs

| When | Hand to |
|---|---|
| The drive never reaches Operation enabled, statusword/controlword, modes of operation, CiA 402 homing methods | **cia402-motion** |
| Slaves not in OP, working counter, frame loss, DC sync; NC 0x4466/0x4651/0x4655 or `IoDataInvalid` | **ethercat-diagnostics** |
| What a device supports: objects, data types, PDOs, startup lists, its ESI file | **ethercat-esi** |
| Writing or reviewing the PLC code (`Execute` edges, call sites, OOP shape) | **twincat-st** (and its reviewer) |
| Diagnosing from a Scope recording, or setting one up | **twincat-scope** |

If a sibling skill is not installed, say which one would own the question and answer only the
TwinCAT NC part. Without ethercat-esi, say a device answer is generic and point at the drive's
CoE tab in XAE or its ESI file.

## Status

Written for TwinCAT 3.1.4024 with `Tc2_MC2`; differences in 4026 are named only where known.
The references are built from the Tc2_MC2 documentation and public sample projects, restated
in our own words. `nc_error.py` and `axis_xti.py` are tested on public sample axes. A field
test on 4024.55 / `Tc2_MC2` 3.3.59 with simulated axes checked the templates and the main
claims on the axis lifecycle, homing, coupling and configuration; the references mark what it
observed. Nothing here has been run against a real drive, an absolute encoder or real retain
storage: report at that precision.
