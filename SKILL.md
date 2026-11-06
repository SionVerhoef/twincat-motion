---
name: twincat-motion
description: "Use for Beckhoff TwinCAT 3 motion control: NC axis configuration and parameters, Tc2_MC2 / PLCopen MC_ function blocks (MC_Power, MC_Home, MC_MoveAbsolute, MC_Reset), homing, gearing and cam coupling, NC error codes, the NC axis .xti files, and why an axis will not enable or move. Not for the CiA 402 drive state machine on its own (use cia402-motion), EtherCAT network faults (use ethercat-diagnostics), or general Structured Text (use twincat-st). DRAFT: under development."
---

# twincat-motion

> **Draft.** This skill is under development and not ready to install.
>
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
```

An `.xti` stores only non-default values and the tool has no defaults table: an absent
parameter is at its TwinCAT default, lint checks explicit values only, and a clean lint is
not a full audit. Say so when you report a result. The tool never writes an `.xti`;
propose changes as a parameter-change table or an Automation Interface script
(`references/config-changes.md`).

## Where to read next

Load a reference when the task reaches it, not all of them up front.

| Task | Read |
|---|---|
| Axis won't enable, `MC_Power.Status` stays FALSE, won't move, faults, moves wrong | `references/triage.md` first |
| Order of commands, axis states, `MC_Stop` vs `MC_Halt`, `ST_AxisStatus`, buffer modes, `CommandAborted`, error kinds, `MC_Jog` modes | `references/axis-lifecycle.md` |
| Scaling, reference velocity, CSP vs velocity mode, lag / target / soft-limit monitoring, Kv | `references/axis-parameters.md` |
| Homing: PLC-based, `MC_Home`, step homing, touch probe, drive-based, absolute encoders and retain data | `references/homing.md` |
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
in our own words. `nc_error.py` and `axis_xti.py` are tested on public sample axes. Nothing here
has been run against a real axis: report at that precision.
