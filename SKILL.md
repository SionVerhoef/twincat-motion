---
name: twincat-motion
description: "Use for Beckhoff TwinCAT 3 motion control: NC axis configuration and parameters, Tc2_MC2 / PLCopen MC_ function blocks (MC_Power, MC_Home, MC_MoveAbsolute, MC_Reset), homing, gearing and cam coupling, axis errors and why an axis will not enable or move. Not for the CiA 402 drive state machine on its own (use cia402-motion), EtherCAT network faults (use ethercat-diagnostics), or general Structured Text (use twincat-st). DRAFT: under development."
---

# twincat-motion

> **Draft.** This skill is under development and not ready to install.
>
> **Reference material only. Not for safety functions.** Motion configuration must be
> reviewed and validated by a qualified engineer before it runs on a machine.

## Goal

Get a TwinCAT NC axis configured, enabled, homed and moving correctly, and diagnose why it
is not.

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
propose changes as an Automation Interface script or a parameter-change table.
